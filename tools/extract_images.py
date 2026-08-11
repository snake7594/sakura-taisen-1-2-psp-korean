# -*- coding: utf-8 -*-
"""
ISO 안의 이미지를 PNG 로 뽑는다.

  python extract_images.py            image_png/ 에 추출 + 컨택트시트 생성

대상
  .GIM  223개  표준 PSP 이미지 (UI·메뉴·타이틀 — 일본어 텍스트가 가장 많다)
  .PNG   33개  이미 PNG 라 그대로 꺼낸다

컨택트시트(`image_png/_sheets/`)를 보고 일본어가 든 이미지를 골라내면 된다.
"""
import os, sys, io, struct
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_iso import walk_iso, SRC_ISO, SECTOR
import gim

OUT = r"D:\psp\사쿠라대전1_2\image_png"

def flatten(a):
    """RGBA -> 흰 배경에 합성한 RGB (투명 배경 글자를 눈으로 보기 위해)"""
    im = Image.fromarray(a, 'RGBA')
    bg = Image.new('RGB', im.size, (255, 255, 255))
    bg.paste(im, mask=im.split()[3])
    return bg

def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(SRC_ISO, 'rb')
    table = walk_iso(f)
    def get(lba, sz): f.seek(lba*SECTOR); return f.read(sz)

    made = []          # (출력경로, ISO경로, w, h, 포맷)
    nfail = 0
    for p in sorted(table):
        up = p.upper()
        if not (up.endswith('.GIM') or up.endswith('.PNG')): continue
        rec, lba, sz = table[p]
        d = get(lba, sz)
        rel = p.strip('/').replace('/', os.sep)
        base = os.path.join(OUT, os.path.dirname(rel))
        os.makedirs(base, exist_ok=True)
        stem = os.path.splitext(os.path.basename(p))[0]
        if up.endswith('.PNG'):
            dst = os.path.join(base, stem + '.png')
            open(dst, 'wb').write(d)
            try:
                im = Image.open(dst); made.append((dst, p, im.width, im.height, 'PNG'))
            except Exception: nfail += 1
            continue
        try:
            imgs = gim.decode(d)
        except Exception as e:
            nfail += 1
            continue
        for i, (w, h, fmt, a) in enumerate(imgs):
            if w == 0 or h == 0: continue
            dst = os.path.join(base, stem + (f"_{i}" if i else "") + ".png")
            Image.fromarray(a, 'RGBA').save(dst)
            made.append((dst, p, w, h, fmt))
    print(f"이미지 {len(made)}장 추출 (실패 {nfail}개 파일)")

    # ---- 컨택트시트 ----
    sheets = os.path.join(OUT, "_sheets")
    os.makedirs(sheets, exist_ok=True)
    # 큰 것부터 보이도록 면적순
    items = sorted(made, key=lambda r: -(r[2]*r[3]))
    PER, CW, CH = 24, 240, 150
    from PIL import ImageDraw
    n = 0
    for s in range(0, len(items), PER):
        grp = items[s:s+PER]
        cols = 4; rows = (len(grp)+cols-1)//cols
        sheet = Image.new('RGB', (cols*(CW+8), rows*(CH+22)), (235, 236, 242))
        dr = ImageDraw.Draw(sheet)
        for k, (dst, isop, w, h, fmt) in enumerate(grp):
            try: im = Image.open(dst).convert('RGBA')
            except Exception: continue
            im = flatten(np.asarray(im))
            im.thumbnail((CW, CH), Image.LANCZOS)
            c, r = k % cols, k//cols
            x, y = c*(CW+8)+4, r*(CH+22)+18
            sheet.paste(im, (x + (CW-im.width)//2, y + (CH-im.height)//2))
            label = f"{os.path.basename(dst)}  {w}x{h}"
            dr.text((x, r*(CH+22)+4), label[:44], fill=(30, 30, 70))
        p = os.path.join(sheets, f"sheet_{n:03d}.png")
        sheet.save(p); n += 1
    print(f"컨택트시트 {n}장 -> {sheets}")

    with open(os.path.join(OUT, "index.tsv"), 'w', encoding='utf-8') as fh:
        fh.write("png\tiso_path\twidth\theight\tformat\n")
        for dst, isop, w, h, fmt in made:
            fh.write(f"{os.path.relpath(dst, OUT)}\t{isop}\t{w}\t{h}\t{fmt}\n")
    print(f"목록 -> {os.path.join(OUT, 'index.tsv')}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
