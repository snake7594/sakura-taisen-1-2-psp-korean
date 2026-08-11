# -*- coding: utf-8 -*-
"""
삽입 결과 전수 검증 + PSP 실해상도(480x272) 목업.

검증: 완성형 2350자를 하나씩
        encode() -> SJIS -> 게임의 글리프 조회 -> 패치된 폰트에서 비트맵 읽기
      원본 렌더 비트맵과 픽셀 단위로 완전히 같은지 확인한다.
      (사쿠라 1 은 FIDX 테이블, 사쿠라 2 는 ELF 루틴 에뮬레이션을 그대로 씀)
"""
import struct, os, sys
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_hangul_font import (HANGUL, SJIS_OF, encode, render_all,
                              fnt4b_index_lut, BUILD, ROOT, SRC, CELL)
from render_test import Sakura1, Sakura2

def verify():
    ink = render_all()
    lut = fnt4b_index_lut(os.path.join(SRC, r"SAKURA2\FNT4B.TPL"))
    f1 = Sakura1(os.path.join(BUILD, "FONTALL.FNT"))
    f2 = Sakura2(os.path.join(BUILD, "FNT4B.CMP"))

    bad1 = bad2 = miss1 = miss2 = 0
    for i, ch in enumerate(HANGUL):
        sjis = SJIS_OF[ch]
        g1, g2 = f1.glyph_index(sjis), f2.glyph_index(sjis)
        if g1 is None: miss1 += 1
        else:
            got = np.rint(f1.bitmap(g1)*15).astype(np.uint8)
            if not np.array_equal(got, ink[i]): bad1 += 1
        if g2 is None: miss2 += 1
        else:
            gy, gx = (g2//32)*CELL, (g2 % 32)*CELL
            got = f2.img[gy:gy+CELL, gx:gx+CELL]
            if not np.array_equal(got, lut[ink[i]]): bad2 += 1
    n = len(HANGUL)
    print(f"완성형 {n}자 전수 검증")
    print(f"  사쿠라 1 (FIDX 조회)          : 일치 {n-bad1-miss1}/{n}"
          f"   불일치 {bad1}   미매핑 {miss1}")
    print(f"  사쿠라 2 (ELF 루틴 에뮬레이션) : 일치 {n-bad2-miss2}/{n}"
          f"   불일치 {bad2}   미매핑 {miss2}")
    return bad1 + bad2 + miss1 + miss2 == 0

# ------------------------------------------------------------ PSP 목업
LINES = ["제국화격단, 등장‼",
         "무사한가, 오리히메!",
         "지금 뭐라고 했어요⁉"]

def mockup(out_png):
    f1 = Sakura1(os.path.join(BUILD, "FONTALL.FNT"))
    scales = [32, 24, 20]
    panels = []
    for px in scales:
        SW, SH = 480, 272
        canvas = np.zeros((SH, SW), np.float32)
        box_h = px*3 + 16
        y0 = SH - box_h - 8
        for r, text in enumerate(LINES):
            b = encode(text); x = 12; i = 0
            while i < len(b):
                sjis = (b[i] << 8) | b[i+1]; i += 2
                g = f1.glyph_index(sjis)
                if g is None or x + px > SW:
                    x += px; continue
                gl = Image.fromarray((f1.bitmap(g)*255).astype(np.uint8), 'L')
                gl = gl.resize((px, px), Image.LANCZOS)
                a = np.asarray(gl, np.float32)/255
                yy = y0 + 8 + r*px
                canvas[yy:yy+px, x:x+px] = np.maximum(canvas[yy:yy+px, x:x+px], a)
                x += px
        rgb = np.zeros((SH, SW, 3), np.uint8)
        rgb[:] = (26, 22, 40)
        rgb[y0:y0+box_h] = (245, 243, 235)
        ink = canvas[..., None]
        base = rgb.astype(np.float32)
        rgb = (base*(1-ink) + np.array([20, 20, 30])*ink).astype(np.uint8)
        im = Image.fromarray(rgb, 'RGB')
        dr = ImageDraw.Draw(im)
        dr.rectangle([0, y0, SW-1, y0+box_h-1], outline=(120, 110, 90))
        dr.text((8, 8), f"PSP 480x272 / 글자 {px}px / 한 줄 최대 {SW//px}자",
                fill=(230, 230, 240))
        panels.append(im)
    S = 2
    sheet = Image.new('RGB', (480*S, 272*S*len(panels) + 8*(len(panels)-1)), (255,255,255))
    for i, im in enumerate(panels):
        sheet.paste(im.resize((480*S, 272*S), Image.NEAREST), (0, i*(272*S+8)))
    sheet.save(out_png)
    print(f"  -> {os.path.basename(out_png)}")

if __name__ == '__main__':
    ok = verify()
    print()
    os.makedirs(os.path.join(ROOT, "test_render"), exist_ok=True)
    mockup(os.path.join(ROOT, "test_render", "psp_mockup.png"))
    sys.exit(0 if ok else 1)
