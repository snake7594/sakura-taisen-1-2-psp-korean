# -*- coding: utf-8 -*-
"""
사쿠라 2 명령창 CMD_WIN.CMP 의 라벨을 한글로 다시 그린다.

  python cmdwin.py --png   미리보기만
  python cmdwin.py         build/patched/CMD_WIN.CMP 저장

이 파일은 .SPR 이 아니라 날 .CMP 라 팔레트 청크가 없다. 풀면 128픽셀 폭
4bpp 이미지(128x560)이고, 글자 띠 두 곳만 또렷하게 글자다.
    y 180~212  アイテム
    y 492~524  環境設定
다른 구역은 창 무늬라 **건드리지 않는다**. 글자 띠만 덮어써서 위험을 줄였다.
색은 0(검정)~15(흰색) 회색 띠라 알파값을 그대로 인덱스로 쓸 수 있다.
"""
import os, sys, io
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cmp import decompress, parse_header, _params as cmp_params
from cmp_compress import compress
from make_hangul_font import FONT as KFONT
from menu_images import read_iso

ROOT  = r"D:\psp\사쿠라대전1_2"
BUILD = os.path.join(ROOT, "build", "patched")
NAME  = "CMD_WIN.CMP"
W = 128
BANDS = [(180, 212, "아이템"), (492, 524, "환경설정")]

def unpack4(d):
    a = np.frombuffer(d, np.uint8)
    o = np.empty(len(a)*2, np.uint8)
    o[0::2], o[1::2] = a & 0xF, a >> 4      # 하위 니블이 왼쪽 픽셀
    h = len(o)//W
    return o[:W*h].reshape(h, W).copy()

def pack4(img):
    f = img.reshape(-1).astype(np.uint8)
    return ((f[1::2] << 4) | (f[0::2] & 0xF)).astype(np.uint8).tobytes()

def draw(img, y0, y1, text):
    bh = y1 - y0
    for s in range(bh, 7, -1):
        f = ImageFont.truetype(KFONT, s)
        l, t, r, b = f.getbbox(text)
        if (r-l) <= W-8 and (b-t) <= bh-4: break
    m = Image.new('L', (W, bh), 0)
    ImageDraw.Draw(m).text(((W-(r-l))//2 - l, (bh-(b-t))//2 - t), text, font=f, fill=255)
    al = np.asarray(m, np.float32)/255.0
    img[y0:y1] = np.clip((al*15).round(), 0, 15).astype(np.uint8)

def main():
    raw = read_iso(NAME)
    dec = decompress(raw)[0]
    img = unpack4(dec)
    print(f"  {NAME}: {len(raw)} -> {len(dec)}B, {W}x{img.shape[0]}")
    for y0, y1, ko in BANDS:
        draw(img, y0, y1, ko)
        print(f"    y {y0}~{y1}  '{ko}'")
    nd = pack4(img)
    assert len(nd) == len(dec), f"{len(nd)} != {len(dec)}"
    if '--png' in sys.argv:
        q = os.path.join(ROOT, "test_render", "_cmdwin_ko.png")
        Image.fromarray((img*17).astype(np.uint8), 'L').resize(
            (W*3, img.shape[0]*3), Image.NEAREST).save(q)
        print(f"    -> {q}")
        return
    m, p, _, hl = parse_header(raw)
    ob, bi = cmp_params(m, p)
    enc = compress(nd, ob, bi, header=raw[:hl])
    assert decompress(enc)[0] == nd, "재압축 왕복 실패"
    os.makedirs(BUILD, exist_ok=True)
    q = os.path.join(BUILD, NAME)
    open(q, 'wb').write(enc)
    print(f"  {len(raw)} -> {len(enc)}B  -> {q}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
