# -*- coding: utf-8 -*-
"""사쿠라대전 1 타이틀 화면의 그림 글자를 한글로 바꾼다.

  python tools/op_win.py --png   미리보기만
  python tools/op_win.py         build/patched 에 SPR 저장

두 파일이다. 둘 다 /PSP_GAME/USRDIR/SAKURA1/SAKURA0/OP/ 에 있다.

  OP_WIN.SPR   416x416 **16bpp**. 메뉴 간판.
                 위   演目        (오른쪽->왼쪽으로 「目演」으로 보인다)
                 아래 帝国華撃団  (마찬가지로 「団撃華国帝」)
  TL_NEW.SPR   타이틀 메뉴 라벨 5장. **8bpp 팔레트**이고 장마다 팔레트
                 뱅크가 다르다 (엔트리의 q 값이 2048색 팔레트 안 시작 위치).

────────────────────────────────────────────────────────────────────────
전에 이 파일이 낸 사고 — 같은 실수를 되풀이하지 않도록 적어 둔다.

1) **TL_NEW 를 16bpp 로 착각했다.** 실제는 fmt=0x14 = 8bpp 팔레트다.
   RGB 로 읽어 u16 으로 되쓰니 한 픽셀에 2바이트가 들어가, 게임은 그걸
   인덱스로 읽어 무지개 잡음이 됐다. **fmt 하위 니블을 반드시 확인할 것.**

2) **바이트 순서를 두 번 뒤집었다.** spr.decode_pixels 의 16bpp 갈래는
   리틀엔디안으로 읽는데 spr_write.pack_px 는 빅엔디안으로 쓴다. 둘을
   짝지으면 값이 뒤집힌다. 왕복이 맞는 짝은 **unpack16 + pack_px**
   (둘 다 빅엔디안)이다. 실제로 확인했다 —
       pack_px(unpack16(원본), 16) == 원본  ->  참

3) **16bpp 채널 차례는 팔레트와 같은 ABGR1555 (R 이 하위)** 다.
   R 을 상위로 읽으면 분홍 간판이 보라가 된다. 화면 사진과 대조해 확인했다.

4) 손대지 않은 픽셀까지 RGB 로 갔다 오면 5비트 반올림으로 값이 바뀐다.
   **고칠 상자 안만 건드리고 나머지는 원본 값 그대로 둔다.**
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import spr, spr_write
from build_iso import walk_iso, SRC_ISO, SECTOR

FONT  = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched")

# OP_WIN: (이미지번호, 상자, 번역)
OPWIN = [
    (0, (128, 12, 272, 54),   "공연"),
    (0, (100, 346, 310, 377), "제국화격단"),
]
# TL_NEW: 이미지번호 -> (원문, 번역). 장 전체가 라벨 하나다.
TLNEW = {
    3: ("ゲームをはじめる",   "게임 시작"),
    4: ("Press START button", "START 버튼을 누르세요"),
    5: ("サクラ大戦2 へ",     "사쿠라대전 2로"),
    6: ("サクラ大戦2 へ",     "사쿠라대전 2로"),
    # 후지시마 코스케 캐릭터 원안 표기다. 사람 이름이라 그대로 옮긴다.
    # 86x11 밖에 안 돼서 「일러스트：후지시마 코스케」(13칸)는 6px 이 되어
    # 안 읽힌다. 원문도 9자 9.5px 이니 10칸에 맞춘다.
    7: ("イラスト：藤島康介", "원화 후지시마 코스케"),
}

def read(nm):
    f = open(SRC_ISO, 'rb'); t = walk_iso(f)
    p = [x for x in t if os.path.basename(x) == nm and '/SAKURA1/' in x][0]
    _, lba, sz = t[p]; f.seek(lba*SECTOR); d = f.read(sz); f.close()
    return d

def img_chunk(d):
    for off, size, idx, body in spr.chunks(d):
        cnt, ents, db = spr.entries(body)
        if cnt and any(e[5] for e in ents):
            return body, ents, db
    raise RuntimeError("이미지 청크 없음")

def mask_of(text, w, h, pad=4):
    """4배로 그려 줄인 글자 알파 (0~1). 상자에 맞게 크기를 줄인다."""
    S = 4
    size = h
    while size > 6:
        f = ImageFont.truetype(FONT, size)
        b = f.getbbox(text)
        if b[2]-b[0] <= w-pad and b[3]-b[1] <= h-pad: break
        size -= 1
    f4 = ImageFont.truetype(FONT, size*S)
    m = Image.new('L', (w*S, h*S), 0); dr = ImageDraw.Draw(m)
    b = dr.textbbox((0, 0), text, font=f4)
    dr.text((w*S//2 - (b[2]+b[0])//2, h*S//2 - (b[3]+b[1])//2), text, font=f4, fill=255)
    return np.asarray(m.resize((w, h), Image.LANCZOS)).astype(np.float32)/255, size

# ───────────────────────────────────────────────────── OP_WIN (16bpp ABGR1555)
def u16_to_rgb(u):
    u = u.astype(np.uint32)
    return np.dstack([((u & 31)*255//31), (((u >> 5) & 31)*255//31),
                      (((u >> 10) & 31)*255//31)]).astype(np.uint8)

def rgb_to_u16(rgb, hi=1):
    r = (rgb[..., 0].astype(np.uint32)*31 + 127)//255
    g = (rgb[..., 1].astype(np.uint32)*31 + 127)//255
    b = (rgb[..., 2].astype(np.uint32)*31 + 127)//255
    return ((hi << 15) | (b << 10) | (g << 5) | r).astype(np.uint16)

def do_opwin(make_png):
    d = read('OP_WIN.SPR')
    body, ents, db = img_chunk(d)
    e = ents[0]; w, h = e[0], e[1]
    u = spr_write.unpack16(body, e, db)
    assert spr_write.pack_px(u, 16) == spr_write.raw_px(body, e, db)[:u.size*2], "왕복 실패"
    before = u16_to_rgb(u)
    for _k, (x0, y0, x1, y1), ko in OPWIN:
        reg = u[y0:y1, x0:x1]
        rgb = u16_to_rgb(reg).astype(np.float32)
        # 배경은 상자 바깥 왼쪽 열에서 뜬다. **속색을 「가장 밝은 색」으로
        # 잡으면 안 된다** — 아래 간판은 초록 바탕에 검은 글자라 배경이
        # 잡혀 글자가 안 보인다. 배경 밝기에서 가장 먼 색이 글자다.
        bgcol = u16_to_rgb(u[y0:y1, max(0, x0-6):max(1, x0-5)]).astype(np.float32)
        lum = rgb.sum(2).reshape(-1); px = rgb.reshape(-1, 3)
        # 원문 글자는 **밝은 속 + 어두운 테두리**다. 속은 가장 밝은 3%,
        # 테두리는 가장 어두운 3%. 위 검은 판에서는 어두운 쪽이 배경과 같아
        # 테두리가 저절로 사라지고, 아래 초록 간판에서는 남색 테두리가 잡힌다.
        core = px[lum >= np.percentile(lum, 97)].mean(0)
        edge = px[lum <= np.percentile(lum, 3)].mean(0)
        a, size = mask_of(ko, x1-x0, y1-y0)
        ring = np.asarray(Image.fromarray((a*255).astype('uint8'))
                          .filter(ImageFilter.MaxFilter(3))).astype(np.float32)/255
        out = np.repeat(bgcol, x1-x0, axis=1).astype(np.float32)
        out = out*(1-ring[..., None]) + edge*ring[..., None]
        out = out*(1-a[..., None]) + core*a[..., None]
        u[y0:y1, x0:x1] = rgb_to_u16(np.clip(out, 0, 255).astype(np.uint8),
                                     hi=int(reg[0, 0]) >> 15)
        print(f"  OP_WIN.SPR #0 ({x0},{y0})-({x1},{y1}) -> {ko}  ({size}px)")
    if make_png:
        return ('OP_WIN.SPR', Image.fromarray(before), Image.fromarray(u16_to_rgb(u)))
    nd = spr_write.rebuild(d, {0: u})
    os.makedirs(BUILD, exist_ok=True)
    q = os.path.join(BUILD, 'OP_WIN.SPR'); open(q, 'wb').write(nd)
    print(f"      {len(d):,} -> {len(nd):,}B  -> {q}")
    return None

# ─────────────────────────────────────────────────── TL_NEW (8bpp 팔레트 뱅크)
def do_tlnew(make_png):
    d = read('TL_NEW.SPR')
    pal = spr.palette(d)
    body, ents, db = img_chunk(d)
    changes, prev = {}, []
    for k, e in enumerate(ents):
        if k not in TLNEW: continue
        w, h, fmt, q, eo, es = e
        assert spr.BPP[fmt & 0x0F] == 8, "8bpp 가 아니다"
        idx = spr_write.unpack_px(body, e, db)
        bank = pal[q:q+256, :3].astype(np.float32)
        # 배경 = 가장 흔한 인덱스, 글자 = 나머지
        bg = int(np.bincount(idx.reshape(-1), minlength=256).argmax())
        gl = (idx != bg)
        er = np.asarray(Image.fromarray((gl*255).astype('uint8'))
                        .filter(ImageFilter.MinFilter(5))) > 0
        core = int(np.bincount(idx[er].reshape(-1), minlength=256).argmax()) if er.any() \
               else int(np.bincount(idx[gl].reshape(-1), minlength=256).argmax())
        ringpx = gl & ~er
        edge = int(np.bincount(idx[ringpx].reshape(-1), minlength=256).argmax()) if ringpx.any() else core
        ja, ko = TLNEW[k]
        a, size = mask_of(ko, w, h, pad=6)
        ring = np.asarray(Image.fromarray((a*255).astype('uint8'))
                          .filter(ImageFilter.MaxFilter(3))).astype(np.float32)/255
        out = np.tile(bank[bg], (h, w, 1))
        out = out*(1-ring[..., None]) + bank[edge]*ring[..., None]
        out = out*(1-a[..., None]) + bank[core]*a[..., None]
        # 뱅크 안에서 가장 가까운 색으로 되돌린다. 안 쓰는 인덱스도 이 장의
        # 것이므로 써도 된다. 글자가 없는 자리는 원래 배경 인덱스로 못박는다.
        dif = ((out.reshape(-1, 1, 3) - bank[None, :, :])**2).sum(2)
        ni = dif.argmin(1).astype(np.uint8).reshape(h, w)
        ni[(a <= 0.002) & (ring <= 0.002)] = bg
        changes[k] = ni
        print(f"  TL_NEW.SPR #{k} {w}x{h} 뱅크{q}  {ja} -> {ko}  "
              f"({size}px, 배경{bg} 속{core} 테{edge})")
        if make_png:
            prev.append((f"TL_NEW#{k}", Image.fromarray(pal[q:q+256][idx][:, :, :3].astype('uint8')),
                         Image.fromarray(pal[q:q+256][ni][:, :, :3].astype('uint8'))))
    if make_png:
        return prev
    nd = spr_write.rebuild(d, changes)
    os.makedirs(BUILD, exist_ok=True)
    p = os.path.join(BUILD, 'TL_NEW.SPR'); open(p, 'wb').write(nd)
    print(f"      {len(d):,} -> {len(nd):,}B  -> {p}")
    # 되읽어 검증 — 인덱스가 그대로 들어갔는지
    b2, e2, db2 = img_chunk(nd)
    for k, ni in changes.items():
        got = spr_write.unpack_px(b2, e2[k], db2)
        assert np.array_equal(got, ni), f"#{k} 되읽기 불일치"
    print("      되읽기 검증: 통과")
    return None

def run(make_png=False):
    a = do_opwin(make_png)
    b = do_tlnew(make_png)
    if not make_png: return
    prev = ([a] if a else []) + (b or [])
    W = max(max(x.width for x in (p[1], p[2])) for p in prev)
    H = sum(max(p[1].height, p[2].height) + 6 for p in prev)
    sh = Image.new('RGB', (2*(W+6), H), (40, 40, 40)); y = 0
    for n, o, c in prev:
        sh.paste(o.convert('RGB'), (0, y)); sh.paste(c.convert('RGB'), (W+6, y))
        y += max(o.height, c.height) + 6
    q = os.path.join(ROOT, "test_render", "_opwin_ko.png")
    s = min(1.0, 1400/sh.width)
    sh.resize((int(sh.width*s), int(sh.height*s)), Image.LANCZOS).save(q)
    print(f"      -> {q}")

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    run('--png' in sys.argv)
