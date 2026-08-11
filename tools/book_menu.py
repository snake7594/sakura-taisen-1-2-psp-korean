# -*- coding: utf-8 -*-
"""사쿠라대전 2 책자형 시작/설정 메뉴의 그림 글자를 한글로 교체한다.

PBOOK_FL71/72/73 은 책장 가장자리에서 글자가 이어지는 208px짜리
순환 스트립이고, FL711/712/713 은 메모리 카드 선택 페이지, FL81/82/83 은
클리어 기록 페이지다. 모두 CMP 안의 8bpp 인덱스 그림이며, 이 스크립트는
팔레트와 압축 헤더는 그대로 두고 픽셀 인덱스만 다시 그린다.

  python tools/book_menu.py --check   # 압축/좌표/크기 점검만
  python tools/book_menu.py --png     # test_render/book_menu 에 미리보기 저장
  python tools/book_menu.py            # build/patched 에 패치 파일 생성
"""
import os
import sys
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import pbook
from build_iso import SRC_ISO, SECTOR, walk_iso
from cmp import decompress, parse_header, _params
from cmp_compress import compress
from pvr import load_palette

FONT = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched")
PREVIEW = os.path.join(ROOT, "test_render", "book_menu")

S2 = "/PSP_GAME/USRDIR/SAKURA2/SAKURA1/"

RING_TEXT = {
    "PBOOK_FL71.CMP": [
        "시스템 파일 선택",
        "시스템 파일 불러오기",
        "시스템 파일 새로 만들기",
        "시스템 파일 복사 대상 선택",
        "시스템 파일 삭제",
    ],
    "PBOOK_FL72.CMP": [
        "시스템 파일 선택",
        "시스템 파일 불러오기",
        "시스템 파일 새로 만들기",
        "시스템 파일 복사 대상 선택",
        "시스템 파일 삭제",
    ],
    "PBOOK_FL73.CMP": [
        "시스템 파일 선택",
        "시스템 파일 불러오기",
        "시스템 파일 새로 만들기",
        "시스템 파일 복사 대상 선택",
        "시스템 파일 삭제",
    ],
}

PAGE_TEXT = {
    "PBOOK_FL711.CMP": {"title_bg": 254, "title_ink": 4},
    "PBOOK_FL712.CMP": {"title_bg": 107, "title_ink": 16},
    "PBOOK_FL713.CMP": {"title_bg": 167, "title_ink": 4},
}

CLEAR_TEXT = {
    "PBOOK_FL81.CMP": {"title_bg": 254, "title_ink": 132},
    "PBOOK_FL82.CMP": {"title_bg": 168, "title_ink": 190},
    "PBOOK_FL83.CMP": {"title_bg": 171, "title_ink": 202},
}


with open(SRC_ISO, "rb") as _ISO:
    _TABLE = walk_iso(_ISO)


def read_path(path):
    """ISO 안의 정확한 경로에서 파일을 읽는다 (동명이인 방지)."""
    rec_off, lba, size = _TABLE[path]
    with open(SRC_ISO, "rb") as f:
        f.seek(lba * SECTOR)
        return f.read(size)


def font(size):
    return ImageFont.truetype(FONT, size)


def fit_font(text, size, width, height):
    """상자 안에 들어가는 최대 크기의 폰트와 bbox를 반환한다."""
    size = int(size)
    while size > 10:
        f = font(size)
        b = f.getbbox(text)
        if b[2] - b[0] <= width and b[3] - b[1] <= height:
            return f, b
        size -= 1
    f = font(10)
    return f, f.getbbox(text)


def palette_luma(pal):
    rgb = pal[:, :3].astype(np.int32)
    return (299 * rgb[:, 0] + 587 * rgb[:, 1] + 114 * rgb[:, 2]) // 1000


def choose_index(reg, pal, want_light, exclude=()):
    """구역에서 밝거나 어두운 쪽의 최빈 팔레트 인덱스를 고른다."""
    vals, counts = np.unique(reg, return_counts=True)
    banned = set(int(x) for x in exclude)
    luma = palette_luma(pal)
    pairs = [(int(v), int(c)) for v, c in zip(vals, counts)
             if int(v) not in banned and int(v) != 0]
    if not pairs:
        return 0
    if want_light:
        cand = [(v, c) for v, c in pairs if luma[v] >= 150]
    else:
        cand = [(v, c) for v, c in pairs if luma[v] < 150]
    if not cand:
        cand = pairs
    return max(cand, key=lambda p: p[1])[0]


def nearest_palette(pal, allowed, rgb):
    allowed = np.asarray(sorted(set(int(x) for x in allowed)), dtype=np.int32)
    if allowed.size == 0:
        return 0
    d = ((pal[allowed, :3].astype(np.int32) - np.asarray(rgb, np.int32)) ** 2).sum(1)
    return int(allowed[int(d.argmin())])


def draw_box(img, pal, text, box, size, bg=None, ink=None, align="center",
             preserve=False):
    """팔레트 인덱스 이미지의 한 상자에 글자를 다시 그린다."""
    x0, y0, x1, y1 = box
    reg = img[y0:y1, x0:x1]
    used = np.unique(reg)
    if bg is None:
        bg = choose_index(reg, pal, True)
    if ink is None:
        ink = choose_index(reg, pal, False, exclude=(bg,))
    bg, ink = int(bg), int(ink)
    if bg not in used:
        used = np.unique(np.append(used, bg))
    if ink not in used:
        used = np.unique(np.append(used, ink))

    bw, bh = x1 - x0, y1 - y0
    f, b = fit_font(text, size, max(1, bw - 2), max(1, bh - 2))
    tw, th = b[2] - b[0], b[3] - b[1]
    mask = Image.new("L", (bw, bh), 0)
    dr = ImageDraw.Draw(mask)
    if align == "right":
        tx = bw - tw - 3 - b[0]
    elif align == "left":
        tx = 2 - b[0]
    else:
        tx = (bw - tw) // 2 - b[0]
    ty = (bh - th) // 2 - b[1]
    dr.text((tx, ty), text, font=f, fill=255)

    bg_rgb = pal[bg, :3].astype(np.int32)
    ink_rgb = pal[ink, :3].astype(np.int32)
    lut = {0: bg}
    for q in range(1, 17):
        t = q / 16.0
        rgb = np.rint(bg_rgb * (1.0 - t) + ink_rgb * t).astype(np.int32)
        lut[q] = nearest_palette(pal, used, rgb)
    alpha = np.asarray(mask, dtype=np.int32)
    qa = np.clip((alpha * 16 + 127) // 255, 0, 16)
    if preserve:
        # 책자 페이지의 상단 띠는 상태별 질감이 있으므로, 원문 잉크를
        # 중심으로 4px 확장해 지우고 나머지 배경 픽셀은 보존한다.
        base = reg.copy()
        clear = (reg == ink)
        for _ in range(4):
            clear = (clear |
                     np.roll(clear, 1, 0) | np.roll(clear, -1, 0) |
                     np.roll(clear, 1, 1) | np.roll(clear, -1, 1))
        base[clear] = bg
        out = base
    else:
        out = np.full(reg.shape, bg, dtype=np.uint8)
    for q in range(1, 17):
        out[qa == q] = lut[q]
    reg[:] = out
    return bg, ink, (f.size, tw, th)


def draw_ring(img, texts, size=23, start=160):
    """208px 스트립의 오른쪽 시작점에서 문장을 한 바퀴 이어 붙인다."""
    width = img.shape[1]
    rows = [(80, 109), (112, 141), (144, 173), (176, 206), (208, 238)]
    for text, (y0, y1) in zip(texts, rows):
        img[y0:y1, :] = 0
        f = font(size)
        b = f.getbbox(text)
        tw, th = b[2] - b[0], b[3] - b[1]
        while tw > width and size > 12:
            size -= 1
            f = font(size)
            b = f.getbbox(text)
            tw, th = b[2] - b[0], b[3] - b[1]
        line = Image.new("L", (max(1, tw), y1 - y0), 0)
        dr = ImageDraw.Draw(line)
        ty = ((y1 - y0) - th) // 2 - b[1]
        dr.text((-b[0], ty), text, font=f, fill=255)
        # 여기서 나온 값은 **팔레트 인덱스로 그대로 쓰인다.** 안티에일리어싱
        # 중간값(1~254)을 그냥 두면 엉뚱한 팔레트 색이 찍혀 글자 둘레에
        # 색 얼룩이 생긴다. FL71~73 은 짝이 되는 .PAL 이 없어서 중간값을
        # 팔레트에 맞춰 고를 방법도 없다. 그래서 0/255 로만 자른다.
        # 원본도 대부분 0 과 255 두 값으로 그려져 있다.
        src = np.where(np.asarray(line) >= 128, 255, 0).astype(np.uint8)
        out = np.zeros((y1 - y0, width), dtype=np.uint8)
        first = min(width - start, tw)
        if first > 0:
            out[:, start:start + first] = src[:, :first]
        rest = min(start, max(0, tw - first))
        if rest > 0:
            out[:, :rest] = src[:, first:first + rest]
        img[y0:y1, :] = out


def page_patch(name, img, pal):
    """메모리 카드 선택 페이지 1장을 패치한다."""
    # 테두리 안쪽의 흰 라벨 칸. A/B 원형 버튼은 건드리지 않는다.
    # 칸 간격은 92px, 폭 74px 이다 (흰 배경 인덱스 255 의 열 구간을 재서 확인).
    # 95px 로 잡으면 C·D 가 오른쪽으로 밀려 원문 조각이 남는다.
    port_boxes = [(19, 21, 93, 48), (111, 21, 185, 48),
                  (203, 21, 277, 48), (295, 21, 369, 48)]
    for box, label in zip(port_boxes, ("포트 A", "포트 B", "포트 C", "포트 D")):
        draw_box(img, pal, label, box, 25, bg=255)

    # 오른쪽의 일본어 決定/取消. 원형 A/B 표시는 원본을 살린다.
    # 원문 글자는 x 416~464 에 있다. 440 부터 잡으면 「決」「取」이 안 지워져
    # 한글과 겹친다.
    a_box = (414, 21, 465, 47)
    b_box = (414, 52, 465, 78)
    a_bg = choose_index(img[a_box[1]:a_box[3], a_box[0]:a_box[2]], pal, False)
    b_bg = choose_index(img[b_box[1]:b_box[3], b_box[0]:b_box[2]], pal, False)
    draw_box(img, pal, "결정", a_box, 26, bg=a_bg, ink=255)
    draw_box(img, pal, "취소", b_box, 26, bg=b_bg, ink=255)

    bg = PAGE_TEXT[name]["title_bg"]
    ink = PAGE_TEXT[name]["title_ink"]
    draw_box(img, pal, "메모리 카드 선택", (17, 249, 232, 274), 28,
             bg=bg, ink=ink, preserve=True)


def clear_patch(name, img, pal):
    """클리어 기록 페이지의 상단 제목을 교체한다."""
    job = CLEAR_TEXT[name]
    draw_box(img, pal, "사쿠라대전 클리어 기록", (202, 14, 476, 42), 30,
             bg=job["title_bg"], ink=job["title_ink"], align="right",
             preserve=True)


def preview(name, img, pal=None):
    os.makedirs(PREVIEW, exist_ok=True)
    out = os.path.join(PREVIEW, name.replace(".CMP", ".png"))
    if pal is None:
        Image.fromarray(img, "L").save(out)
    else:
        Image.fromarray(pal[img], "RGBA").save(out)


def repack(name, mutate, pal=None, check_only=False, make_png=False):
    path = S2 + name
    raw = read_path(path)
    dec = decompress(raw)[0]
    original, info = pbook.decode(name, dec)
    img = original.copy()
    mutate(img, pal)
    new_dec = pbook.encode(img, info)
    method, param, _, hlen = parse_header(raw)
    obits, bias = _params(method, param)
    packed = compress(new_dec, obits, bias, header=raw[:hlen])
    assert decompress(packed)[0] == new_dec, f"{name}: 재압축 왕복 불일치"
    if len(packed) > len(raw):
        raise RuntimeError(f"{name}: 원본 자리 초과 {len(packed)} > {len(raw)}")
    if make_png:
        preview(name, img, pal)
    print(f"  {name}: {img.shape[1]}x{img.shape[0]}  {len(raw):,} -> {len(packed):,}B")
    if not check_only:
        os.makedirs(BUILD, exist_ok=True)
        out = os.path.join(BUILD, name)
        with open(out, "wb") as f:
            f.write(packed)
        print(f"      -> {out}")


def page_palette(name):
    return load_palette(read_path(S2 + name[:-4] + ".PAL"))


def run(check_only=False, make_png=False):
    for name, texts in RING_TEXT.items():
        repack(name, lambda img, _pal, texts=texts: draw_ring(img, texts),
               check_only=check_only, make_png=make_png)

    for name in PAGE_TEXT:
        pal = page_palette(name)
        repack(name, lambda img, pal, name=name: page_patch(name, img, pal),
               pal=pal, check_only=check_only,
               make_png=make_png)

    for name in CLEAR_TEXT:
        pal = page_palette(name)
        repack(name, lambda img, pal, name=name: clear_patch(name, img, pal),
               pal=pal, check_only=check_only,
               make_png=make_png)


if __name__ == "__main__":
    run(check_only="--check" in sys.argv, make_png="--png" in sys.argv)
