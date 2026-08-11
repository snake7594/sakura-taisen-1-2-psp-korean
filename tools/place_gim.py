# -*- coding: utf-8 -*-
"""사쿠라대전 2 지도(이동) 화면의 장소 패널을 한글로 바꾼다.

PLACE##_#.GIM 20장. 132x230, INDEX8, 스위즐. **압축이 아니라서** 제자리에
그대로 고쳐 쓰면 된다 — 크기가 변할 일이 없다.

패널 구조 (모두 같다)
    x  0~41   테두리 장식
    x 42~90   세로 띠. 여기에 글자가 세로로 놓인다
    x 91~131  테두리 장식
    글자는 x48~85, y40~185 쯤에 한 글자씩 쌓여 있다.

배경을 지울 때는 띠 안쪽이면서 글자가 안 닿는 열(x=44, x=87)에서 그 행의
색을 가져와 채운다. 띠에 세로 그라데이션이 있어서 한 색으로 밀면 티가 난다.

사쿠라1 의 같은 역할 자산은 ADV_SIDE.SPR 이고 map_signs.py 가 처리한다.
사쿠라2 는 PFS·SPR 을 안 쓰기 때문에 이 파일이 따로 필요하다.
"""
import os, sys, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from build_iso import walk_iso, SRC_ISO, SECTOR

FONT  = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched")

BOX = (44, 30, 88, 200)          # 글자를 그릴 자리 (x0, y0, x1, y1)
BGX = (44, 87)                   # 배경색을 뜨는 열

KO = {
    "PLACE01_0": "제극 앞",     "PLACE02_0": "우구이스다니",
    "PLACE02_1": "시부야",      "PLACE03_0": "칸자키 저택",
    "PLACE04_0": "후카가와",    "PLACE05_0": "아타미",
    "PLACE06_0": "이케부쿠로",  "PLACE07_0": "아사쿠사",
    "PLACE08_0": "제극 앞",     "PLACE08_1": "신주쿠",
    "PLACE08_2": "아카사카",    "PLACE08_3": "아카사카 동굴",
    "PLACE08_4": "아카사카 동굴","PLACE10_0": "오지",
    "PLACE11_0": "미카사 기관부","PLACE11_1": "미카사 갑판",
    "PLACE11_2": "무사시 내부", "PLACE12_0": "이드의 방",
    "PLACE12_1": "미하시라의 방","PLACE12_2": "신황의 방",
}

def gim_image(d):
    """(픽셀데이터 오프셋, w, h, 스위즐, 팔레트오프셋) — 첫 이미지 청크"""
    off, img, pal = 16, None, None
    while off + 16 <= len(d):
        typ, _ = struct.unpack_from('<HH', d, off)
        size, nxt = struct.unpack_from('<II', d, off+4)
        if size <= 0: break
        if typ == 4 and img is None:
            hs, = struct.unpack_from('<H', d, off+16)
            fmt, order, w, h = struct.unpack_from('<HHHH', d, off+16+4)
            if fmt != 5: raise RuntimeError(f"INDEX8 이 아니다 (fmt={fmt})")
            img = (off+16+hs, w, h, order)
        if typ == 5 and pal is None:
            hs, = struct.unpack_from('<H', d, off+16); pal = off+16+hs
        if typ in (2, 3): off += 16
        elif nxt and nxt < size: off += nxt
        else: off += size
    return img, pal

def unswz(b, pitch, hh):
    return b.reshape(hh//8, pitch//16, 8, 16).transpose(0, 2, 1, 3).reshape(hh, pitch)

def swz(a):
    hh, pitch = a.shape
    return a.reshape(hh//8, 8, pitch//16, 16).transpose(0, 2, 1, 3).reshape(-1)

def vtext(text, w, h):
    """세로쓰기 마스크. 한 글자씩 아래로 쌓는다."""
    chars = [c for c in text if c != ' ']
    n = len(chars)
    size = min(w, (h - 4) // n)
    f = ImageFont.truetype(FONT, size)
    m = Image.new('L', (w, h), 0); dr = ImageDraw.Draw(m)
    step = h / n
    for i, c in enumerate(chars):
        b = dr.textbbox((0, 0), c, font=f)
        dr.text(((w - (b[2]-b[0]))//2 - b[0],
                 int(i*step + (step - (b[3]-b[1]))//2) - b[1]), c, font=f, fill=255)
    return np.asarray(m)

def patch(d, ko):
    d = bytearray(d)
    (po, w, h, order), palo = gim_image(bytes(d))
    pitch = (w + 15)//16*16; hh = (h + 7)//8*8
    buf = np.frombuffer(bytes(d[po:po+pitch*hh]), np.uint8)
    img = unswz(buf, pitch, hh).copy() if order else buf.reshape(hh, pitch).copy()

    pal = np.frombuffer(bytes(d[palo:palo+256*4]), np.uint8).reshape(256, 4)
    lum = pal[:, :3].astype(int).sum(1)

    x0, y0, x1, y1 = BOX
    reg = img[y0:y1, x0:x1]
    ink = int(max(np.unique(reg), key=lambda v: lum[v]))     # 가장 밝은 색이 글자

    # 배경: 띠 안쪽이면서 글자가 안 닿는 열에서 그 행의 값을 가져온다
    bg = img[y0:y1, BGX[0]][:, None].repeat(x1-x0, 1)
    m = vtext(ko, x1-x0, y1-y0)
    out = np.where(m >= 128, ink, bg).astype(np.uint8)
    img[y0:y1, x0:x1] = out

    d[po:po+pitch*hh] = (swz(img) if order else img.reshape(-1)).tobytes()
    return bytes(d), ink

def run(check_only=False, make_png=False):
    f = open(SRC_ISO, 'rb'); t = walk_iso(f)
    ps = [p for p in sorted(t) if 'PLACE' in p.upper() and p.upper().endswith('.GIM')]
    os.makedirs(BUILD, exist_ok=True)
    prev = []
    for p in ps:
        nm = os.path.basename(p); stem = nm[:-4]
        if stem not in KO: print(f"  {nm}: 번역 없음 — 건너뜀"); continue
        _, lba, sz = t[p]; f.seek(lba*SECTOR); d = f.read(sz)
        nd, ink = patch(d, KO[stem])
        assert len(nd) == len(d), "크기가 변하면 안 된다"
        print(f"  {nm:<16} -> {KO[stem]}  (잉크 {ink})")
        if make_png:
            import gim
            w, h, _, a = gim.decode(nd)[0]
            prev.append(Image.fromarray(a.astype('uint8'), 'RGBA').convert('RGB'))
        if not check_only:
            open(os.path.join(BUILD, nm), 'wb').write(nd)
    f.close()
    if make_png and prev:
        sh = Image.new('RGB', (len(prev)*136, 230), (30, 30, 30))
        for k, i in enumerate(prev): sh.paste(i, (k*136, 0))
        q = os.path.join(ROOT, "test_render", "_place_ko.png"); sh.save(q)
        print(f"      -> {q}")

if __name__ == '__main__':
    run('--check' in sys.argv, '--png' in sys.argv)
