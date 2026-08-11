# -*- coding: utf-8 -*-
"""
.CMP / .SPR 안의 PVR 텍스처를 PNG 로 뽑는다.

  python extract_pvr.py            image_png/pvr/ 에 추출 + 컨택트시트

.CMP 는 풀면 PVR 이 하나 이상 들어 있고, .SPR("SEGA SPRED 02.0M")은
빅엔디안 청크 테이블 뒤에 조각들이 붙어 있어 각 조각을 다시 훑는다.
팔레트는 같은 이름의 .CL / .PAL 을 쓴다.
"""
import os, sys, io, struct
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_iso import walk_iso, SRC_ISO, SECTOR
from cmp import decompress
import pvr

OUT = r"D:\psp\사쿠라대전1_2\image_png\pvr"

def spr_chunks(d):
    """SEGA SPR 컨테이너 -> [바이트열, ...]
    16바이트 매직 뒤에 빅엔디안 [오프셋, 크기, 번호, 예약] 이 이어진다."""
    if d[:8] != b'SEGA SPR': return []
    out, o = [], 0x10
    while o + 16 <= len(d):
        off, size, idx, rsv = struct.unpack_from('>4I', d, o)
        if off == 0 or off > len(d) or size == 0: break
        if off + size > len(d): break
        out.append(d[off:off+size])
        o += 16
        if o >= off: break            # 테이블이 데이터에 닿으면 끝
    return out

def flatten(a):
    im = Image.fromarray(a, 'RGBA')
    bg = Image.new('RGB', im.size, (255, 255, 255))
    bg.paste(im, mask=im.split()[3])
    return bg

def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(SRC_ISO, 'rb')
    table = walk_iso(f)
    def rd(p):
        _, lba, sz = table[p]; f.seek(lba*SECTOR); return f.read(sz)

    # 팔레트: 같은 폴더 우선, 없으면 이름만 같으면 인정
    pal_by_dir, pal_by_name = {}, {}
    for p in table:
        if p.upper().endswith(('.CL', '.PAL')):
            stem = os.path.splitext(os.path.basename(p))[0].upper()
            pal_by_dir[(os.path.dirname(p), stem)] = p
            pal_by_name.setdefault(stem, p)

    made, nofmt, failed = [], [], []
    for p in sorted(table):
        up = p.upper()
        if not up.endswith(('.CMP', '.SPR')): continue
        stem = os.path.splitext(os.path.basename(p))[0]
        try:
            raw = rd(p)
            d = decompress(raw)[0] if up.endswith('.CMP') else raw
        except Exception as e:
            failed.append((p, str(e)[:60])); continue

        palp = (pal_by_dir.get((os.path.dirname(p), stem.upper()))
                or pal_by_name.get(stem.upper()))
        palb = rd(palp) if palp else None

        blobs = spr_chunks(d) if up.endswith('.SPR') else [d]
        imgs = []
        for b in blobs:
            imgs += pvr.decode(b, palb)
        if not imgs:
            nofmt.append((p, len(d))); continue

        rel = os.path.dirname(p.strip('/')).replace('/', os.sep)
        base = os.path.join(OUT, rel)
        os.makedirs(base, exist_ok=True)
        for i, (w, h, info, a) in enumerate(imgs):
            dst = os.path.join(base, stem + (f"_{i:03d}" if len(imgs) > 1 else "") + ".png")
            Image.fromarray(a, 'RGBA').save(dst)
            made.append((dst, p, w, h, info))

    print(f"PVR 텍스처 {len(made)}장 추출")
    print(f"PVR 아닌 파일 {len(nofmt)}개, 읽기 실패 {len(failed)}개")

    # ---- 컨택트시트 (면적 큰 것부터) ----
    sheets = os.path.join(OUT, "_sheets"); os.makedirs(sheets, exist_ok=True)
    items = sorted(made, key=lambda r: -(r[2]*r[3]))
    PER, CW, CH, cols = 24, 240, 150, 4
    n = 0
    for s in range(0, len(items), PER):
        grp = items[s:s+PER]
        rows = (len(grp)+cols-1)//cols
        sheet = Image.new('RGB', (cols*(CW+8), rows*(CH+22)), (235, 236, 242))
        dr = ImageDraw.Draw(sheet)
        for k, (dst, isop, w, h, info) in enumerate(grp):
            try: im = flatten(np.asarray(Image.open(dst).convert('RGBA')))
            except Exception: continue
            im.thumbnail((CW, CH), Image.LANCZOS)
            c, r = k % cols, k//cols
            x, y = c*(CW+8)+4, r*(CH+22)+18
            sheet.paste(im, (x + (CW-im.width)//2, y + (CH-im.height)//2))
            dr.text((x, r*(CH+22)+4), f"{os.path.basename(dst)} {w}x{h}"[:44],
                    fill=(30, 30, 70))
        sheet.save(os.path.join(sheets, f"pvr_{n:03d}.png")); n += 1
    print(f"컨택트시트 {n}장 -> {sheets}")

    with open(os.path.join(OUT, "index.tsv"), 'w', encoding='utf-8') as fh:
        fh.write("png\tiso_path\twidth\theight\tformat\n")
        for dst, isop, w, h, info in made:
            fh.write(f"{os.path.relpath(dst, OUT)}\t{isop}\t{w}\t{h}\t{info}\n")
    with open(os.path.join(OUT, "_not_pvr.txt"), 'w', encoding='utf-8') as fh:
        for p, ln in nofmt: fh.write(f"{p}\t{ln}\n")
    print(f"목록 -> {os.path.join(OUT, 'index.tsv')}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
