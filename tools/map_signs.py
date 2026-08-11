# -*- coding: utf-8 -*-
"""
지도 화면의 방 이름 표지판을 한글로 다시 그린다.

  python map_signs.py --png   미리보기만 (test_render/signs/)
  python map_signs.py         build/patched/ADVMISC.PFS 저장

표지판은 ADVMISC.PFS 안의 두 .spr 에 들어 있다.
    tmap_kan.spr  대제국극장 지도 — 표지판 43장 (4~46번)
    fuka_kan.spr  후카가와 저택 지도 — 표지판 20장

그림 구조 (112~176 x 48, 16bpp 직접색)
    y 0~3   위 테두리 언저리      y 4     가로 테두리 선
    y 6~38  **글자 자리**         y 40~47 판 아래 그림자
    x 0~7 / w-8~w-1              좌우 테두리
글자 자리만 덮어써서 테두리와 그림자를 지키고, 알파 비트도 건드리지 않는다.
"""
import os, sys, io, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spr, spr_write
from make_hangul_font import FONT as KFONT
from menu_images import read_iso, text_mask
from pfs import entries as pfs_entries

ROOT  = r"D:\psp\사쿠라대전1_2"
BUILD = os.path.join(ROOT, "build", "patched")
PREV  = os.path.join(ROOT, "test_render", "signs")
SECT  = 2048

TMAP = {
 4: "사쿠라의 방", 5: "칸나의 방", 6: "마리아의 방", 7: "코란의 방",
 8: "아이리스의 방", 9: "스미레의 방", 10: "서고", 11: "아야메의 방",
 12: "대장실", 13: "살롱", 14: "홀", 15: "２층 객석", 16: "테라스",
 17: "↓１층", 18: "숙직실", 19: "지배인실", 20: "사무국", 21: "주방",
 22: "의상실", 23: "식당", 24: "분장실", 25: "도구실", 26: "무대 옆",
 27: "대도구실", 28: "무대", 29: "１층 객석", 30: "로비", 31: "현관",
 32: "매점", 33: "↑２층", 34: "↓지하", 35: "창고", 36: "단련실",
 37: "의무실", 38: "탈의실", 39: "수영장", 40: "샤워실", 41: "작전실",
 42: "지령실", 43: "증기연산기실", 44: "지하격납고", 45: "↑１층", 46: "빈방",
}
FUKA = {
 0: "사용인실 三", 1: "사용인실 四", 2: "２층 식당", 3: "거실", 4: "로비",
 5: "침실 三", 6: "침실 四", 7: "↓１층", 8: "２층 개인실", 9: "사용인실 一",
 10: "사용인실 二", 11: "１층 식당", 12: "응접실", 13: "주방", 14: "대기실",
 15: "현관 홀", 16: "침실 一", 17: "침실 二", 18: "↑２층", 19: "１층 개인실",
}
JOBS = {"tmap_kan.spr": TMAP, "fuka_kan.spr": FUKA}

def sign_box(w, h):
    """표지판의 글자 자리. 테두리(좌우 8px, 위 6px)와 아래 그림자를 뺀다."""
    return (9, 6, w - 9, 39)

def draw_sign(a, text):
    """a = (h,w) u16 (ABGR1555). 글자 자리를 판 색으로 지우고 한글을 그린다."""
    h, w = a.shape
    x0, y0, x1, y1 = sign_box(w, h)
    reg = a[y0:y1, x0:x1]
    vals, cnt = np.unique(reg, return_counts=True)
    bg = int(vals[cnt.argmax()])                      # 판 바탕
    ink = None; best = -1
    for v, c in zip(vals.tolist(), cnt.tolist()):
        if v == bg: continue
        if c > best: best, ink = c, v
    if ink is None: return None, None
    br, bgc, bb = spr_write.rgb1555(bg)
    ir, ig, ib = spr_write.rgb1555(ink)
    aflag = (bg >> 15) & 1

    reg[:] = bg
    bw, bh = x1 - x0, y1 - y0
    m = Image.new('L', (bw, bh), 0)
    inner = text_mask(text, int(bw * 0.94), int(bh * 0.82))
    m.paste(inner, ((bw - inner.width) // 2, (bh - inner.height) // 2))
    qa = np.clip((np.asarray(m, np.float32) / 255.0 * 16).round().astype(np.int32), 0, 16)
    lut = np.array([spr_write.mk1555(round(br + (ir - br) * q / 16),
                                     round(bgc + (ig - bgc) * q / 16),
                                     round(bb + (ib - bb) * q / 16), aflag)
                    for q in range(17)], np.uint16)
    reg[:] = np.where(qa > 0, lut[qa], reg)
    return bg, ink

def patch_spr(body, table, prev_dir=None, tag=''):
    """.spr 바이트열 -> 표지판을 한글로 바꾼 새 바이트열"""
    ch = spr.chunks(body)
    ents = db = None
    for off, size, ix, b in ch:
        c, e, dbb = spr.entries(b)
        if c and any(t[5] for t in e): ents, db, blob = e, dbb, b; break
    changes = {}
    for i, ko in sorted(table.items()):
        w, h, fmt, q, eo, es = ents[i]
        if not es: print(f"    [{i}] 빈 이미지 — 건너뜀"); continue
        a = spr_write.unpack16(blob, ents[i], db)
        bg, ink = draw_sign(a, ko)
        changes[i] = a
        if prev_dir:
            r, g, bl = spr_write.rgb1555(a.astype(np.uint32))
            al = np.where((a >> 15) & 1, 255, 0).astype(np.uint8)
            Image.fromarray(np.dstack([r*255//31, g*255//31, bl*255//31, al]).astype(np.uint8),
                            'RGBA').save(os.path.join(prev_dir, f"{tag}_{i:02d}.png"))
    print(f"    {len(changes)}장 교체")
    return spr_write.rebuild(body, changes)

def rebuild_pfs(d, new_members):
    """PFS 재조립 (reinsert.build_pfs 와 같은 방식)"""
    mem = pfs_entries(d)
    out = bytearray(b'PAKFILE\x00' + struct.pack('>II', len(mem), 0))
    head = 0x10 + len(mem)*24
    cur = ((head + SECT - 1)//SECT)*SECT
    blobs = []
    for name, off, sz in mem:
        body = new_members.get(name, d[off:off+sz])
        out += name.encode('ascii').ljust(16, b'\x00') + struct.pack('>II', cur//SECT, len(body))
        blobs.append((cur, body))
        cur += ((len(body) + SECT - 1)//SECT)*SECT
    out = bytearray(out.ljust(blobs[0][0], b'\x00'))
    for at, body in blobs:
        out = bytearray(out.ljust(at, b'\x00')) + bytearray(body)
    return bytes(out.ljust(cur, b'\x00'))

def main():
    png = '--png' in sys.argv
    if png: os.makedirs(PREV, exist_ok=True)
    d = read_iso("ADVMISC.PFS")
    mem = {n: (o, s) for n, o, s in pfs_entries(d)}
    new = {}
    for name, table in JOBS.items():
        o, s = mem[name]
        print(f"  {name}  {s} B")
        nb = patch_spr(d[o:o+s], table, PREV if png else None, name[:-4])
        print(f"    {s} -> {len(nb)} B")
        new[name] = nb
    # ADV_SIDE.SPR (낱개 파일, 8bpp 세로쓰기)
    sd = read_iso("ADV_SIDE.SPR")
    pal = spr.palette(sd)
    for off, size, ix, b in spr.chunks(sd):
        c, e, dbb = spr.entries(b)
        if not (c and any(t[5] for t in e)): continue
        ch2 = {}
        for i, ko in sorted(SIDE.items()):
            if not e[i][5]: continue
            a = spr_write.unpack_px(b, e[i], dbb)
            draw_side(a, pal, ko)
            ch2[i] = a
            if png:
                Image.fromarray(pal[a].astype(np.uint8), 'RGBA').save(
                    os.path.join(PREV, f"side_{i:02d}.png"))
        print(f"  ADV_SIDE.SPR : {len(ch2)}장 교체")
        if not png:
            nsd = spr_write.rebuild(sd, ch2)
            os.makedirs(BUILD, exist_ok=True)
            open(os.path.join(BUILD, "ADV_SIDE.SPR"), 'wb').write(nsd)
            print(f"    {len(sd)} -> {len(nsd)} B")
        break
    if png: print(f"  -> {PREV}"); return
    nd = rebuild_pfs(d, new)
    os.makedirs(BUILD, exist_ok=True)
    q = os.path.join(BUILD, "ADVMISC.PFS")
    open(q, 'wb').write(nd)
    print(f"  ADVMISC.PFS {len(d)} -> {len(nd)} B  -> {q}")



# ── 오른쪽 세로 패널 ADV_SIDE.SPR ────────────────────────────────
# 8bpp 팔레트 그림이고 글자가 **세로쓰기**다. 나무판 무늬 위에 글자가 있어
# 글자가 있던 자리만 판 색으로 지우고 그 자리에 세로로 다시 쓴다.
SIDE = {
 1: "대제국극장", 2: "후카가와폐가",
 3: "남은", 4: "회", 5: "１", 6: "２", 7: "３", 8: "４", 9: "５",
 10: "６", 11: "７", 12: "８", 13: "９", 14: "１０",
 15: "태정１２년", 16: "태정１３년",
 17: "정월", 18: "１월", 19: "３월", 20: "４월", 21: "５월",
 22: "６월", 23: "７월", 24: "８월", 25: "９월",
 26: "제극의긴하루",
}

def vtext_mask(text, bw, bh):
    """세로쓰기 알파 마스크. 글자를 위에서 아래로 쌓는다."""
    n = len(text)
    for s in range(min(bw, bh // max(n, 1)), 5, -1):
        f = ImageFont.truetype(KFONT, s)
        if all((f.getbbox(c)[2] - f.getbbox(c)[0]) <= bw for c in text): break
    step = bh // n
    m = Image.new('L', (bw, bh), 0)
    dr = ImageDraw.Draw(m)
    for k, ch in enumerate(text):
        l, t, r, b = f.getbbox(ch)
        dr.text(((bw - (r - l)) // 2 - l, k*step + (step - (b - t)) // 2 - t),
                ch, font=f, fill=255)
    return m

def draw_side(img, pal, text):
    """8bpp 팔레트 그림. 글자 자리만 지우고 세로로 한글을 쓴다."""
    h, w = img.shape
    bg = int(img[0, 0])                       # 판 바탕 (모서리)
    nb = (img != bg)
    ys, xs = np.where(nb)
    if not len(ys): return None, None
    y0, y1, x0, x1 = ys.min(), ys.max()+1, xs.min(), xs.max()+1
    reg = img[y0:y1, x0:x1]
    vals, cnt = np.unique(reg, return_counts=True)
    # 잉크는 **가장 어두운 색**으로 잡는다. 나무 무늬가 깔려 있어
    # '가장 흔한 색'을 쓰면 무늬 색이 뽑혀 글자가 배경에 묻힌다.
    cand = [(int(pal[v][:3].astype(int).sum()), int(v)) for v in vals.tolist()
            if v != bg and pal[v][3] >= 128 and cnt[list(vals).index(v)] >= 8]
    if not cand: return None, None
    ink = min(cand)[1]
    reg[:] = bg
    bh2, bw2 = y1-y0, x1-x0
    m = vtext_mask(text, int(bw2*0.96), int(bh2*0.98))
    full = Image.new('L', (bw2, bh2), 0)
    full.paste(m, ((bw2-m.width)//2, (bh2-m.height)//2))
    qa = np.clip((np.asarray(full, np.float32)/255.0*16).round().astype(np.int32), 0, 16)
    ok = np.zeros(len(pal), bool); ok[vals] = True
    from menu_images import nearest
    bg_rgb, ink_rgb = pal[bg][:3].astype(np.int32), pal[ink][:3].astype(np.int32)
    lut = {q: (bg if q == 0 else (ink if q == 16 else
           nearest(pal, ok, (bg_rgb*(16-q) + ink_rgb*q)//16))) for q in range(17)}
    out = np.vectorize(lut.get)(qa).astype(np.uint8)
    reg[:] = np.where(qa > 0, out, reg)
    return bg, ink


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
