# -*- coding: utf-8 -*-
"""
메뉴 이미지에 박힌 일본어를 한글로 다시 그린다.

  python menu_images.py --list    대상과 원문을 보여주기만
  python menu_images.py --png     결과를 미리보기 PNG 로도 저장
  python menu_images.py           build/patched/ 에 패치된 .SPR 저장

메뉴 글자는 텍스트가 아니라 그림에 구워져 있다. 그래서
  1) 팔레트 이미지를 인덱스 배열로 풀고
  2) 글자가 있던 자리를 배경색으로 지우고
  3) 같은 자리에 한글을 그린 뒤
  4) 안티에일리어싱 픽셀은 팔레트에서 가장 가까운 색으로 옮긴다
새 색을 만들지 않으니 팔레트를 건드릴 필요가 없다.

저장은 spr_write 가 **무압축**으로 한다 (압축기가 없어도 되는 이유는 거기 설명).
"""
import os, sys, io, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spr, spr_write
from make_hangul_font import FONT as KFONT
from build_iso import walk_iso, SRC_ISO, SECTOR

ROOT  = r"D:\psp\사쿠라대전1_2"
BUILD = os.path.join(ROOT, "build", "patched")
PREV  = os.path.join(ROOT, "test_render", "menu")

_iso = open(SRC_ISO, 'rb'); _table = walk_iso(_iso)
_byname = {}
for _p in _table: _byname.setdefault(os.path.basename(_p).upper(), []).append(_p)

def read_iso(name):
    """ISO 에서 파일 하나를 읽는다 (extract/ 는 일부만 풀려 있어 못 쓴다)"""
    c = _byname.get(name.upper(), [])
    if len(c) != 1: return None
    _, lba, sz = _table[c[0]]
    _iso.seek(lba*SECTOR); return _iso.read(sz)

# (SPR 파일 이름, 이미지번호, 넣을 한글, 글자 상자 or None=전체)
JOBS = [
 # ── 코이코이(화투) 명령 ──
 ("CMDHANA.SPR", 0, "패 선택", None),
 ("CMDHANA.SPR", 1, "결정",    None),
 ("CMDHANA.SPR", 2, "취소",    None),
 ("CMDHANA.SPR", 3, "족보",    None),
 # ── 미아 찾기 ──
 ("CMDMAIGO.SPR", 0, "아이 선택", None),
 ("CMDMAIGO.SPR", 1, "결정",      None),
 ("CMDMAIGO.SPR", 2, "결정",      None),
 # ── 요리 ──
 ("CMDRYORI.SPR", 0, "선택", None),
 ("CMDRYORI.SPR", 1, "결정", None),
 ("CMDRYORI.SPR", 2, "결정", None),
 # ── 족보 설명 ──
 ("CMDSETSU.SPR", 0, "다음 족보", None),
 ("CMDSETSU.SPR", 1, "설명 끝",   None),
 # ── 사격 ──
 ("CMDSHOT.SPR", 0, "조준 이동", None),
 ("CMDSHOT.SPR", 1, "쏜다！",    None),
 ("CMDSHOT.SPR", 2, "쏜다！",    None),
 # ── 슬롯 ──
 ("CMDSLOT.SPR", 0, "드럼 회전", None),
 ("CMDSLOT.SPR", 1, "멈춘다",    None),
 ("CMDSLOT.SPR", 2, "멈춘다",    None),
 ("CMDSLOT.SPR", 3, "멈춘다",    None),
 # ── 청소 / 수영 ──
 ("CMDSOUJI.SPR", 0, "좌우로", None),
 ("CMDSWIM.SPR",  0, "좌우로", None),
 ("CMDSWIM.SPR",  1, "헤엄",   None),
 ("CMDSWIM.SPR",  2, "헤엄",   None),
 # ── 화투 규칙 설정 ──
 ("MCCONFIG.SPR", 0, "국화잔을 껍데기로", None),
 ("MCCONFIG.SPR", 1, "비를 껍데기로",     None),
 ("MCCONFIG.SPR", 2, "달맞이술과 꽃놀이술", None),
 ("MCCONFIG.SPR", 3, "도라 족보（점수２배 찬스！）", None),
 ("MCCONFIG.SPR", 4, "규칙 설정 끝",      None),
 ("MCCONFIG.SPR", 5, "유",                None),
 ("MCCONFIG.SPR", 6, "무",                None),
 # ── 화투 첫 화면 (테두리 안쪽에만 그린다) ──
 ("MC_MENU.SPR", 0, "고이고이\n대전",     (16, 16, 144, 80)),
 ("MC_MENU.SPR", 1, "초보자\n에게",       (16, 16, 144, 80)),
 ("MC_MENU.SPR", 2, "원하는\n규칙으로",   (16, 16, 144, 80)),
 ("MC_MENU.SPR", 3, "화투를\n그만두기",   (16, 16, 144, 80)),
 ("MC_MENU.SPR", 4, "족보 소개\n와 해설", (16, 16, 144, 80)),
 ("MC_MENU.SPR", 6, "그 아이와\n승부",    (16, 16, 144, 80)),
 ("MC_MENU.SPR", 7, "항목을 골라 결정합니다", None),
 # ── 창 제목 라벨 (16bpp 직접색) ──
 ("SYSTEM.SPR", 0, "시스템", (16, 147, 94, 174)),
 ("OPTION.SPR", 0, "옵션",   (14, 294, 102, 319)),
]

def load_font(size):
    return ImageFont.truetype(KFONT, size)

def text_mask(text, bw, bh):
    """상자 크기에 맞춰 한글을 그린 알파 마스크. '\\n' 으로 줄을 나눈다."""
    lines = text.split('\n')
    for s in range(bh, 7, -1):
        f = load_font(s)
        boxes = [f.getbbox(l) for l in lines]
        wmax = max(b[2]-b[0] for b in boxes)
        lh = int(s*1.18)
        if wmax <= bw and lh*len(lines) <= bh: break
    m = Image.new('L', (bw, bh), 0)
    dr = ImageDraw.Draw(m)
    y = (bh - lh*len(lines))//2
    for l, b in zip(lines, boxes):
        dr.text(((bw-(b[2]-b[0]))//2 - b[0], y - b[1] + (lh-s)//2), l, font=f, fill=255)
        y += lh
    return m

def nearest(pal, pal_ok, rgb):
    """팔레트에서 가장 가까운 색의 인덱스 (RGB 만 견준다)"""
    d = ((pal[pal_ok][:, :3].astype(np.int32) - np.array(rgb, np.int32))**2).sum(1)
    return int(np.flatnonzero(pal_ok)[int(d.argmin())])

def redraw(img, pal, text, box):
    """img=(h,w) 인덱스 배열. box 안의 글자를 지우고 한글을 그린다."""
    h, w = img.shape
    x0, y0, x1, y1 = box if box else (0, 0, w, h)
    reg = img[y0:y1, x0:x1]

    vals, cnt = np.unique(reg, return_counts=True)
    # 배경은 **그림 모서리 색**이다. 이 라벨 그림들은 바탕이 한 색으로 깔려 있고
    # 모서리에는 글자가 닿지 않는다. '구역에서 가장 흔한 색'으로 고르면
    # 굵은 글자가 빽빽한 그림에서 잉크와 배경이 뒤집힌다(MC_MENU 에서 겪었다).
    # 팔레트 알파도 믿을 수 없다 — 여기서는 0번이 투명이 아니라 청록색이다.
    bg = int(img[0, 0])
    # 잉크 = 배경이 아니면서 가장 흔한 인덱스
    ink = None; best = -1
    for v, c in zip(vals.tolist(), cnt.tolist()):
        if v == bg: continue
        if c > best: best, ink = c, v
    if ink is None: return None, None

    bg_rgb  = pal[bg][:3].astype(np.int32)
    ink_rgb = pal[ink][:3].astype(np.int32)
    # 섞은 색을 찾을 후보 — 그 이미지가 이미 쓰는 인덱스로 제한하면
    # 팔레트 다른 구역(다른 그림용 색)으로 튀는 것을 막을 수 있다
    ok = np.zeros(len(pal), bool); ok[vals] = True

    reg[:] = bg                                    # 지우기
    bw, bh = x1-x0, y1-y0
    m = Image.new('L', (bw, bh), 0)
    inner = text_mask(text, int(bw*0.92), int(bh*0.86))
    m.paste(inner, ((bw-inner.width)//2, (bh-inner.height)//2))
    al = np.asarray(m, np.float32)/255.0

    # 알파 단계별로 팔레트 인덱스를 미리 정해 둔다 (픽셀마다 찾지 않도록)
    lut = {}
    for q in range(17):
        t = q/16.0
        c = (bg_rgb*(1-t) + ink_rgb*t).round().astype(np.int32)
        lut[q] = bg if t < 0.03 else (ink if t > 0.97 else nearest(pal, ok, c))
    qa = np.clip((al*16).round().astype(np.int32), 0, 16)
    out = np.vectorize(lut.get)(qa).astype(np.uint8)
    reg[:] = np.where(qa > 0, out, reg)
    return bg, ink

def redraw16(img, text, box):
    """16bpp(ABGR1555) 그림. 팔레트가 없으니 색을 바로 섞는다."""
    h, w = img.shape
    x0, y0, x1, y1 = box if box else (0, 0, w, h)
    reg = img[y0:y1, x0:x1]
    vals, cnt = np.unique(reg, return_counts=True)
    # 창 제목표는 바탕색이 넓게 깔려 있고 글자는 적다 -> 최빈색이 배경이다.
    # (8bpp 라벨은 사정이 달라 redraw() 에서 모서리 색을 쓴다)
    bg = int(vals[cnt.argmax()])
    ink = None; best = -1
    for v, c in zip(vals.tolist(), cnt.tolist()):
        if v == bg: continue
        if c > best: best, ink = c, v
    if ink is None: return None, None
    br, bgc, bb = spr_write.rgb1555(bg)
    ir, ig, ib = spr_write.rgb1555(ink)

    reg[:] = bg
    bw, bh = x1-x0, y1-y0
    m = Image.new('L', (bw, bh), 0)
    inner = text_mask(text, int(bw*0.92), int(bh*0.86))
    m.paste(inner, ((bw-inner.width)//2, (bh-inner.height)//2))
    al = np.asarray(m, np.float32)/255.0
    qa = np.clip((al*16).round().astype(np.int32), 0, 16)
    lut = np.array([spr_write.mk1555(round(br+(ir-br)*q/16),
                                     round(bgc+(ig-bgc)*q/16),
                                     round(bb+(ib-bb)*q/16),
                                     (bg >> 15) | (ink >> 15))
                    for q in range(17)], np.uint16)
    reg[:] = np.where(qa > 0, lut[qa], reg)
    return bg, ink

def main():
    listing = '--list' in sys.argv
    png = '--png' in sys.argv
    if png: os.makedirs(PREV, exist_ok=True)
    if not listing: os.makedirs(BUILD, exist_ok=True)

    byfile = {}
    for rel, idx, ko, box in JOBS: byfile.setdefault(rel, []).append((idx, ko, box))

    for rel, items in byfile.items():
        d = read_iso(rel)
        if d is None: print(f"  없음: {rel}"); continue
        pal = spr.palette(d)
        ch = spr.chunks(d)
        body = db = None
        for off, size, ix, b in ch:
            c, e, dbb = spr.entries(b)
            if c and any(t[5] for t in e): body, ents, db = b, e, dbb; break
        changes = {}
        for idx, ko, box in items:
            bpp = spr.BPP[ents[idx][2] & 0x0F]
            if bpp == 16:
                img = spr_write.unpack16(body, ents[idx], db)
                bg, ink = redraw16(img, ko, box)
            else:
                img = spr_write.unpack_px(body, ents[idx], db)
                bg, ink = redraw(img, pal, ko, box)
            changes[idx] = img
            print(f"    [{idx}] {ents[idx][0]}x{ents[idx][1]}  '{ko.replace(chr(10),'/')}'  배경={bg} 잉크={ink}")
            if png:
                if bpp == 16:
                    r, g, b = spr_write.rgb1555(img.astype(np.uint32))
                    rgba = np.dstack([r*255//31, g*255//31, b*255//31,
                                      np.full(img.shape, 255)]).astype(np.uint8)
                else:
                    rgba = pal[img]
                Image.fromarray(rgba.astype(np.uint8), 'RGBA').save(
                    os.path.join(PREV, f"{rel[:-4]}_{idx}.png"))
        print(f"  {rel}: {len(changes)}장")
        if not listing:
            nd = spr_write.rebuild(d, changes)
            q = os.path.join(BUILD, rel)
            open(q, 'wb').write(nd)
            print(f"      {len(d)} -> {len(nd)}B  {q}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
