# -*- coding: utf-8 -*-
"""책 UI 문자 레이어(PBOOKTTL 스트림2)에 남은 일본어를 한글로 바꾼다.

book_ttl.py 가 만든 합본을 입력으로 받아 스트림2 만 다시 그린다.
레이어는 4bpp, **열 우선 + 상하 반전 + high-nibble-first** 다.

    nibble_offset = x*H + (H-1 - y)
    stored        = flipud(img).T

**높이 H 가 구역마다 다르다.** 이걸 몰라서 뒤쪽이 잡음으로 보였다.

    H=48  메뉴 문자 (오늘의 일정, 옵션, 환경 설정, 기록 일람, 본체 RAM …)
          이 파일에서 다루는 범위. x 0~10000 쯤.
    H=96  화 제목과 일부 설정 라벨. H48 좌표 x10742 는 H96 좌표 x5371 이다
          (x * 48 / 96). 「第四話 芸者が大暴れ！」 처럼 읽힌다.

H=96 구역은 **32행짜리 같은 문구가 3벌** 쌓인 것이다 (보통/선택/강조).
세 밴드 모두 잉크 15 를 쓰지만 배경 장식이 달라서, 고칠 때는 밴드마다
따로 그려야 한다.

아직 일본어로 남은 것 (H=96 좌표):
    x7418~7547   追加シナリオ / ＶＭサウンド
    x7806~7973   記録9～16へ→ / 記録1～8へ→
    x7985~8144   戦闘 / 中断記録
같은 줄에 「신뢰도 아이콘」「문장 빨리 넘기기」「중단한 곳부터」 같은 한글이
이미 섞여 있으므로, 경계를 잘못 잡으면 멀쩡한 한글이 지워진다.
글자가 서로 붙어 있어 잉크 구간만으로는 낱말 경계가 안 나뉜다 —
확대해서 눈으로 나눠야 한다.

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

# H=96 구역. 32행짜리 같은 문구가 3벌 쌓여 있어 밴드마다 따로 그린다.
JOBS96 = [
    (7418, 7494, "追加シナリオ",   "추가 시나리오"),
    (7496, 7548, "ＶＭサウンド",   "VM 사운드"),
    # 왼쪽에 작은 한글 「사용 안 함」이 7815 까지 붙어 있다. 잉크가 이어져
    # 있어 구간 검출로는 안 나뉘므로 확대해서 잰 값이다. 7806 부터 잡으면
    # 「함」이 지워진다.
    (7817, 7890, "記録9～16へ→",  "기록 9~16→"),
    (7892, 7959, "記録1～8へ→",   "기록 1~8→"),
    # 원문이 6자 60px 라 한글도 6자로 맞춘다. 띄어쓰기를 넣으면 글자가
    # 작아져서 읽기 어렵다.
    (7960, 8026, "戦闘中断記録",   "전투중단기록"),
]

def load(H=48):
    raw = open(SRC, 'rb').read()
    s2  = bytes(decompress(raw[SPLIT:])[0])
    return raw, unpack(s2, H), len(s2)

def unpack(s2, H):
    d   = np.frombuffer(s2, np.uint8)
    nib = np.stack([d >> 4, d & 15], 1).reshape(-1)
    cols = len(nib) // H
    return np.flipud(nib[:cols*H].reshape(cols, H).T)     # 사람이 보는 방향

def store(img, nbytes):
    """unpack 의 역: flipud(img).T -> high-nibble-first 4bpp.
    높이를 무엇으로 잡든 정확한 역변환이라, H=48 로 고친 뒤 H=96 으로
    다시 읽어 고치는 식으로 이어 붙일 수 있다."""
    flat = np.flipud(img).T.reshape(-1).astype(np.uint8)
    hi, lo = flat[0::2], flat[1::2]
    out = ((hi << 4) | lo).astype(np.uint8)
    return bytes(out) + b'\x00' * (nbytes - len(out))

def draw(img, x0, x1, text, y0=0, y1=None):
    y1 = img.shape[0] if y1 is None else y1
    box = img[y0:y1, x0:x1]
    vals = np.unique(box)
    ink = int(vals.max())                     # 글자는 가장 밝은 값
    w, h = x1 - x0, y1 - y0
    size = h - 8
    while size > 8:
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
    raw, img, n2 = load(48)
    print(f"  H48 레이어 {img.shape[1]:,} x {img.shape[0]}")
    for x0, x1, ja, ko in JOBS:
        for p0, p1 in PROTECT:
            if x0 < p1 and p0 < x1:
                raise RuntimeError(f"보존 구간 {p0}~{p1} 과 겹친다: {x0}~{x1}")
        ink, size = draw(img, x0, x1, ko)
        print(f"  x{x0}~{x1}  {ja} -> {ko}  (잉크 {ink}, {size}px)")
    s2 = store(img, n2)

    # H=96 구역. 같은 바이트열을 다른 높이로 다시 읽어 이어서 고친다.
    img96 = unpack(s2, 96)
    print(f"  H96 레이어 {img96.shape[1]:,} x {img96.shape[0]}")
    for x0, x1, ja, ko in JOBS96:
        for b in range(3):                     # 보통/선택/강조 3벌
            ink, size = draw(img96, x0, x1, ko, b*32, (b+1)*32)
        print(f"  x{x0}~{x1}  {ja} -> {ko}  (3벌, 잉크 {ink}, {size}px)")
    s2 = store(img96, n2)
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
