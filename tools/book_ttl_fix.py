# -*- coding: utf-8 -*-
"""책 UI 문자 레이어(PBOOKTTL 스트림2)에 남은 일본어를 한글로 바꾼다.

book_ttl.py 가 만든 합본을 입력으로 받아 스트림2 만 다시 그린다.
레이어는 26,816 x 48, 4bpp, **열 우선 + 상하 반전 + high-nibble-first** 다.

    nibble_offset = x*48 + (47 - y)
    stored        = flipud(img).T

받은 작업본 문서가 정한 **회귀 금지 구간**을 넘지 않는지 반드시 검사한다.
한 화면의 잔상만 보고 넓게 지우면 다른 화면의 멀쩡한 글자가 같이 사라진다.
"""
import os, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from cmp import decompress, parse_header
from cmp_compress import compress
import book_ttl

FONT  = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched")
SRC   = os.path.join(BUILD, "PBOOKTTL.CMP")     # book_ttl.py 결과물
SPLIT = book_ttl.SPLIT

# 문서가 보존하라고 못박은 구간 (작업 좌표 기준)
# 문서의 "x>=3952 기존 화살표 보존" 은 그 화살표 하나를 가리키는 말이지
# 파일 끝까지를 뜻하지 않는다. 실제 잉크 구간을 보고 4000 까지로 잡는다.
PROTECT = [(1040, 1064), (2144, 2171), (2459, 2465), (3749, 3943), (3952, 4000)]

# (x0, x1, 원문, 번역)  — x1 은 포함하지 않는다
# 경계는 잉크가 끊기는 틈을 재서 잡았다. 5964~5970, 6124~6132, 6324~6336 이
# 빈 구간이라 그 안쪽으로만 쓴다 — 이웃 글자를 건드리지 않는다.
JOBS = [
    (5809, 5966, "記録一覧",          "기록 일람"),
    (5968, 6128, "本体ＲＡＭ",        "본체 RAM"),
    (6130, 6330, "カートリッジＲＡＭ", "카트리지 RAM"),
]

def load():
    raw = open(SRC, 'rb').read()
    s2  = bytes(decompress(raw[SPLIT:])[0])
    d   = np.frombuffer(s2, np.uint8)
    nib = np.stack([d >> 4, d & 15], 1).reshape(-1)
    H = 48; cols = len(nib) // H
    img = np.flipud(nib[:cols*H].reshape(cols, H).T)      # 사람이 보는 방향
    return raw, img, len(s2)

def store(img, nbytes):
    """load 의 역: flipud(img).T -> high-nibble-first 4bpp"""
    flat = np.flipud(img).T.reshape(-1).astype(np.uint8)
    hi, lo = flat[0::2], flat[1::2]
    out = ((hi << 4) | lo).astype(np.uint8)
    return bytes(out) + b'\x00' * (nbytes - len(out))

def draw(img, x0, x1, text):
    box = img[:, x0:x1]
    vals = np.unique(box)
    ink = int(vals.max())                     # 글자는 가장 밝은 값
    w, h = x1 - x0, 48
    size = 40
    while size > 12:
        f = ImageFont.truetype(FONT, size)
        b = f.getbbox(text)
        if b[2]-b[0] <= w-2 and b[3]-b[1] <= h-6: break
        size -= 1
    m = Image.new('L', (w, h), 0)
    dr = ImageDraw.Draw(m)
    b = f.getbbox(text)
    dr.text(((w-(b[2]-b[0]))//2 - b[0], (h-(b[3]-b[1]))//2 - b[1]), text, font=f, fill=255)
    a = np.asarray(m, np.int32)
    box[:] = np.clip((a * ink + 127) // 255, 0, ink).astype(np.uint8)
    return ink, size

def run(check_only=False):
    raw, img, n2 = load()
    print(f"  문자 레이어 {img.shape[1]:,} x {img.shape[0]}")
    for x0, x1, ja, ko in JOBS:
        for p0, p1 in PROTECT:
            if x0 < p1 and p0 < x1:
                raise RuntimeError(f"보존 구간 {p0}~{p1} 과 겹친다: {x0}~{x1}")
        ink, size = draw(img, x0, x1, ko)
        print(f"  x{x0}~{x1}  {ja} -> {ko}  (잉크 {ink}, {size}px)")

    s2 = store(img, n2)
    m, p, _, hl = parse_header(raw[SPLIT:])
    from cmp import _params
    ob, bi = _params(m, p)
    packed = compress(s2, ob, bi, header=raw[SPLIT:SPLIT+hl])
    assert bytes(decompress(packed)[0]) == s2, "재압축 왕복 실패"
    merged = raw[:SPLIT] + packed
    # 스트림1 은 손대지 않았는지 확인
    assert bytes(decompress(merged)[0]) == bytes(decompress(raw)[0]), "스트림1 이 바뀌었다"
    budget = 403456
    print(f"  합본 {len(merged):,}B / 예산 {budget:,}B  들어감={len(merged)<=budget}")
    if len(merged) > budget: raise RuntimeError("슬롯 초과")
    if not check_only:
        open(SRC, 'wb').write(merged)
        print(f"      -> {SRC}")

if __name__ == '__main__':
    run('--check' in sys.argv)
