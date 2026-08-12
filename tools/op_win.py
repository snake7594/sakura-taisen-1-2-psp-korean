# -*- coding: utf-8 -*-
"""사쿠라대전 1 타이틀 화면의 그림 글자를 한글로 바꾼다.

  python tools/op_win.py --png   미리보기만
  python tools/op_win.py         build/patched 에 SPR 저장

두 파일이다. 둘 다 /PSP_GAME/USRDIR/SAKURA1/SAKURA0/OP/ 에 있다.

  OP_WIN.SPR   416x416 **16bpp**. 메뉴 간판.
                 위   演目        (오른쪽->왼쪽으로 「目演」으로 보인다)
                 아래 帝国華撃団  (마찬가지로 「団撃華国帝」)
                 가운데 메뉴 글자는 ELF 문자열이라 이미 한글이다.
  TL_NEW.SPR   타이틀 메뉴 라벨. 사쿠라2 의 SK2TITLE.GIM 과 같은 역할인데
                 1편 것은 여태 빠져 있었다.

16bpp 라 팔레트 제약이 없다. 색은 원본에서 뽑아 그대로 쓴다.

**바이트 순서를 조심해야 한다.** spr_write.unpack16 은 빅엔디안으로 읽는데
이 그림은 리틀엔디안 ARGB1555 다. spr.decode_pixels 를 쓰면 알아서 맞는다.
빅엔디안으로 읽으면 노란 바탕에 형광색이 되어 한눈에 틀린 것을 알 수 있다.
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import spr, spr_write
from build_iso import walk_iso, SRC_ISO, SECTOR

FONT  = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched")

# 파일 -> [(이미지번호, 상자, 번역, 정렬)] — 상자는 (x0,y0,x1,y1)
JOBS = {
    'OP_WIN.SPR': [
        (0, (128, 12, 272, 54),  "공연",      'center'),
        (0, (100, 346, 310, 377), "제국화격단", 'center'),
    ],
    'TL_NEW.SPR': [
        (3, None, "게임 시작",            'center'),
        (4, None, "START 버튼을 누르세요", 'center'),
        (5, None, "사쿠라대전 2로",        'center'),
        (6, None, "사쿠라대전 2로",        'center'),
        (7, None, "일러스트 감상",         'center'),
    ],
}

def images(d):
    """[(청크, 엔트리, db, 번호)] — 디코드되는 이미지만"""
    out, k = [], 0
    for o, s, ix, c in spr.chunks(d):
        cnt, ents, db = spr.entries(c)
        for e in ents:
            out.append((c, e, db, k)); k += 1
    return out

def rgb_of(c, e, db):
    w, h, fmt = e[0], e[1], e[2]
    bpp = spr.BPP[fmt & 0x0F]
    a = np.asarray(spr.decode_pixels(spr_write.raw_px(c, e, db), w, h, bpp, None))
    return a[:, :, :3].astype(np.uint8)

def to_u16(rgb):
    """리틀엔디안 ARGB1555 로 되돌린다 (최상위 비트 0)."""
    r = (rgb[..., 0].astype(np.uint32)*31//255) << 10
    g = (rgb[..., 1].astype(np.uint32)*31//255) << 5
    b = (rgb[..., 2].astype(np.uint32)*31//255)
    return (r | g | b).astype('<u2')

def sample(rgb, box):
    """(속색, 테두리색, 배경) — 상자 안 글자에서 뽑는다."""
    x0, y0, x1, y1 = box
    reg = rgb[y0:y1, x0:x1]
    g = reg.astype(int).sum(2)
    lo, hi = np.percentile(g, 5), np.percentile(g, 95)
    core = reg[g >= hi - 1].mean(0) if (g >= hi-1).any() else np.array([255, 255, 255])
    bg = reg[g <= lo + 1].mean(0) if (g <= lo+1).any() else np.array([0, 0, 0])
    mid = reg[(g > lo+1) & (g < hi-1)]
    edge = mid.mean(0) if len(mid) else bg
    return core.astype(np.uint8), edge.astype(np.uint8), bg

def bg_rows(rgb, box):
    """상자 각 행의 배경색 — 상자 바깥 왼쪽 열에서 뜬다."""
    x0, y0, x1, y1 = box
    left = max(0, x0-6)
    return rgb[y0:y1, left][:, None, :].repeat(x1-x0, 1)

def redraw(rgb, box, text):
    x0, y0, x1, y1 = box
    core, edge, _ = sample(rgb, box)
    out = rgb.copy()
    out[y0:y1, x0:x1] = bg_rows(rgb, box)
    im = Image.fromarray(out); dr = ImageDraw.Draw(im)
    w, h = x1-x0, y1-y0
    size = max(9, h - 4)
    f = ImageFont.truetype(FONT, size)
    while size > 8:
        f = ImageFont.truetype(FONT, size)
        b = dr.textbbox((0, 0), text, font=f)
        if b[2]-b[0] <= w-6 and b[3]-b[1] <= h-4: break
        size -= 1
    b = dr.textbbox((0, 0), text, font=f)
    tx = x0 + (w - (b[2]-b[0]))//2 - b[0]
    ty = y0 + (h - (b[3]-b[1]))//2 - b[1]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                dr.text((tx+dx, ty+dy), text, font=f, fill=tuple(int(v) for v in edge))
    dr.text((tx, ty), text, font=f, fill=tuple(int(v) for v in core))
    return np.asarray(im)

def run(make_png=False):
    f = open(SRC_ISO, 'rb'); t = walk_iso(f)
    prev = []
    for nm, jobs in JOBS.items():
        p = [x for x in t if os.path.basename(x).upper() == nm and '/SAKURA1/' in x][0]
        _, lba, sz = t[p]; f.seek(lba*SECTOR); d = f.read(sz)
        imgs = images(d)
        # 같은 이미지에 상자가 여럿일 수 있다 (OP_WIN 은 위·아래 두 곳).
        # 원본에서 매번 새로 읽으면 앞 것이 지워지므로 이어서 그린다.
        changes, orig = {}, {}
        for k, box, ko, _al in jobs:
            c, e, db, _ = imgs[k]
            if k not in changes:
                orig[k] = rgb_of(c, e, db); changes[k] = orig[k].copy()
            rgb = changes[k]
            bx = box or (0, 0, rgb.shape[1], rgb.shape[0])
            changes[k] = redraw(rgb, bx, ko)
            print(f"  {nm} #{k} {rgb.shape[1]}x{rgb.shape[0]} {bx} -> {ko}")
        if make_png:
            for k in changes:
                prev.append((f"{nm}#{k}", Image.fromarray(orig[k]), Image.fromarray(changes[k])))
        changes = {k: to_u16(v) for k, v in changes.items()}
        if not make_png:
            nd = spr_write.rebuild(d, changes)
            os.makedirs(BUILD, exist_ok=True)
            q = os.path.join(BUILD, nm); open(q, 'wb').write(nd)
            print(f"      {len(d):,} -> {len(nd):,}B  -> {q}")
    f.close()
    if make_png and prev:
        W = max(max(a.width, b.width) for _, a, b in prev)
        H = max(max(a.height, b.height) for _, a, b in prev)
        sh = Image.new('RGB', (2*(W+6), len(prev)*(H+6)), (40, 40, 40))
        for k, (n, a, b) in enumerate(prev):
            sh.paste(a, (0, k*(H+6))); sh.paste(b, (W+6, k*(H+6)))
        q = os.path.join(ROOT, "test_render", "_opwin_ko.png"); sh.save(q)
        print(f"      -> {q}")

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    run('--png' in sys.argv)
