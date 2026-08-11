# -*- coding: utf-8 -*-
"""메뉴책·저장 대화상자 낱장 문구를 한글로 덧그린다.

PBOOK_FL4 는 문구마다 낱장이 따로인 파일이다. 낱장은 높이 32, 폭은
글자수 x 32 픽셀, 4bpp. 시작 바이트와 폭은 아래 JOBS 에 적어 둔다
(pbook.py 주석의 구간 탐색으로 찾았다).

글자는 흰색(인덱스 15) 바탕 검정(0). 안티에일리어싱은 0~15 사이 값이다.
원본 글자보다 짧아지므로 남는 자리는 검정으로 지운다.
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pbook
from cmp import decompress, _params, parse_header
from cmp_compress import compress

FONT = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched")

# (시작바이트, 폭바이트, 원문, 번역)
JOBS = [
    (0x03900, 128, "上書きしますか？",   "덮어쓸까요?"),
    (0x04900, 112, "保存しますか？",     "저장할까요?"),
    (0x05700, 112, "複写しますか？",     "복사할까요?"),
    (0x06500, 112, "消去しますか？",     "지울까요?"),
    (0x07300, 128, "読み込みますか？",   "불러올까요?"),
    # 아래 셋은 시작점을 자동으로 찾았다. 32행 창을 16바이트(=한 글자)씩 밀면서
    # 위아래 2행의 잉크가 **0** 인 정렬을 골랐다 — 글자 띠는 가장자리가 비어 있다.
    # 눈으로만 맞추면 세로 한 행 밀린 것을 구분할 수 없다.
    (0x082E0,  32, "はい",             "예"),
    (0x088D0,  48, "いいえ",           "아니오"),
    (0x0BB00,  64, "アイテム",         "아이템"),
]

def draw(text, w, h=32, size=26):
    """검정 바탕에 흰 글자. 4bpp 인덱스(0~15) 배열로 돌려준다.

    가로가 남으면 왼쪽에 붙인다 — 원본도 왼쪽 정렬이다."""
    img = Image.new('L', (w, h), 0)
    dr = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, size)
    x0, y0, x1, y1 = dr.textbbox((0, 0), text, font=f)
    if x1 - x0 > w:                       # 자리에 안 맞으면 줄여서 맞춘다
        size = max(12, int(size * w / (x1 - x0)))
        f = ImageFont.truetype(FONT, size)
        x0, y0, x1, y1 = dr.textbbox((0, 0), text, font=f)
    dr.text((-x0, (h - (y1 - y0)) // 2 - y0), text, font=f, fill=255)
    return (np.asarray(img).astype(np.uint16) * 15 // 255).astype(np.uint8)

def run(check_only=False):
    name = "PBOOK_FL4.CMP"
    raw = pbook.read_iso(name)
    dec = decompress(raw)[0]
    # 같은 method/param 으로 되압축해야 크기가 안 늘어난다. 헤더 길이도
    # parse_header 가 알려주는 값을 써야 한다 — 짧은 헤더는 4바이트다.
    method, param, _, hlen = parse_header(raw)
    obits, bias = _params(method, param)
    d = bytearray(dec)
    for off, wb, ja, ko in JOBS:
        wpx = wb * 2
        a = draw(ko, wpx)
        d[off:off + wb*32] = pbook.from4(a.reshape(-1)).tobytes()
        print(f"  0x{off:05X} {wpx:>4}px  {ja}  ->  {ko}")
    out = bytes(d)
    assert len(out) == len(dec), "길이가 바뀌면 안 된다"
    packed = compress(out, obits, bias, header=raw[:hlen])
    print(f"  재압축 {len(raw)} -> {len(packed)} 바이트 "
          f"({'들어감' if len(packed) <= len(raw) else '자리 부족!'})")
    # 되풀어서 원하는 그림이 나오는지 확인
    back = decompress(packed)[0]
    print(f"  재압축 검증: {'통과' if bytes(back) == out else '불일치'}")
    if not check_only and len(packed) <= len(raw):
        os.makedirs(BUILD, exist_ok=True)
        p = os.path.join(BUILD, "PBOOK_FL4.CMP")
        open(p, 'wb').write(packed)
        print(f"      -> {p}")

if __name__ == '__main__':
    run('--check' in sys.argv)
