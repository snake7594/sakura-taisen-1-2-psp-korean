# -*- coding: utf-8 -*-
"""
한글 글리프를 만들어 두 게임의 폰트에 삽입한다.

배치 전략
    두 게임 모두 JIS 1수준 한자 영역이 글리프 번호로 연속이다.
        사쿠라 1 (FONTALL.FNT) : SJIS 0x889F(ku16 ten1) -> 글리프 498
        사쿠라 2 (FNT4B)       : 같은 코드            -> 글리프 492
    KS X 1001 완성형 2350자 = 정확히 25행(ku16~ku40) x 94칸 이므로
    ku16~ku40 의 한자를 한글로 덮어쓴다. ku41~47 한자와 가나/기호는 그대로 둔다.
    두 게임이 같은 SJIS 코드 = 같은 한글이 되므로 텍스트 인코더 하나로 양쪽을 쓴다.

주의점 (게임마다 다름)
    FONTALL : Morton(Z-order) 배치, 하위 니블 먼저, 값 0=잉크 / 15=배경
    FNT4B   : 1024px 폭 선형 아틀라스, 상위 니블 먼저, 값 15=잉크 / 0=배경
"""
import struct, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmp import decompress
from cmp_compress import compress

ROOT   = r"D:\psp\사쿠라대전1_2"
SRC    = os.path.join(ROOT, "extract", "PSP_GAME", "USRDIR")
BUILD  = os.path.join(ROOT, "build")
# 나눔스퀘어네오 Bold (cBd). 획이 가늘어 32px 로 키워 잡는다 —
# 2350자를 다 그려 재 본 값 (셀 가장자리에 닿는 글자 / 잉크 비율):
#     맑은고딕Bold 31px  1058자  35.0%   ← 처음에 쓰던 것, 실기에서 문제 없었다
#     네오 Bold    31px    35자  29.9%   조금 흐리다
#     네오 Bold    32px   192자  31.8%   ← 이것
#     네오 Bold    33px  1950자  34.4%   너무 많이 닿는다
# 32px 는 잉크가 검증된 기준(35%)에 가까우면서, 가장자리에 닿는 비율은 8%로
# 이미 잘 돌던 맑은고딕(45%)보다 훨씬 낮다.
FONT   = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                      r"Microsoft\Windows\Fonts\NanumSquareNeo-cBd.ttf")
SIZE   = 32
CELL   = 32
S1_BASE, S2_BASE = 498, 492                    # ku16 ten1 의 글리프 번호
# 전각공백(0x8140) 의 자간. 32=전각.
# 16(반각)으로 낮춰 봤지만 실기에서 효과가 없었다. 원인은 SAKURA1.ELF 0x08954358 이
# 로드할 때 아래 9자의 메트릭을 기본값으로 되쓰기 때문 (테이블 @0x08AAFE4C, u16 LE):
#     0x8140 　 0x8141 、 0x8142 。 0x8169 （ 0x816A ） 0x8175 「 0x8176 」 0x8177 『 0x8178 』
# 하필 첫 항목이 전각 공백이라 파일 수정이 무시된다. 되쓰기 대상이 아닌 문자라면
# width 가 먹히는지는 make_ruler_test.py 로 확인 중.
SPACE_WIDTH = 32

# FIDX 엔트리는 { u16 glyph, u8 xOffset, u8 width } 이다 (u16 폭이 아님).
# SAKURA1.ELF 0x08953DA4 가 +2/+3 바이트를 각각 읽어 돌려주고,
# 0x0895400C 가 min(offset) / max(offset+width) 로 문자열 폭을 잰다.
# 실제 폰트에도 width=16(반각) 121개, width=26 12개가 들어 있다.

# ---------------------------------------------------------------- 코드 변환
def jis2sjis(ku, ten):
    if ku % 2: s2 = ten + 0x3F + (1 if ten > 63 else 0)
    else:      s2 = ten + 0x9E
    s1 = (ku + 0x101)//2 if ku <= 62 else (ku + 0x181)//2
    return (s1 << 8) | s2

def hangul_list():
    """KS X 1001 완성형 2350자 (EUC-KR 코드 순)"""
    out = []
    for cp in range(0xAC00, 0xD7A4):
        ch = chr(cp)
        try:
            b = ch.encode('euc_kr')
        except Exception:
            continue
        if len(b) == 2: out.append((b, ch))
    out.sort()
    return [ch for _, ch in out]

HANGUL = hangul_list()
SJIS_OF = {ch: jis2sjis(16 + i//94, 1 + i % 94) for i, ch in enumerate(HANGUL)}

# 폰트가 표준 문자 대신 전용 글리프를 그리는 자리 (양쪽 게임 공통)
GAIJI = {'⁉': 0x81AC, '‼': 0x81B8}

def encode(text):
    """한글/기존 문자 문자열 -> 게임이 쓰는 Shift-JIS 바이트열.

    한글은 재배치한 ku16~ku40 코드로, 외자는 전용 코드로, ASCII 는 전각으로
    바꾼다. 게임 렌더러는 2바이트 코드를 다루므로 반각은 쓰지 않는다."""
    out = bytearray()
    for ch in text:
        if ch in SJIS_OF:
            out += struct.pack('>H', SJIS_OF[ch]); continue
        if ch in GAIJI:
            out += struct.pack('>H', GAIJI[ch]); continue
        if ch == ' ':
            out += b'\x81\x40'; continue                  # 전각 공백
        if '!' <= ch <= '~':
            ch = chr(ord(ch) - 0x21 + 0xFF01)             # ASCII -> 전각
        try:
            out += ch.encode('cp932')
        except Exception:
            raise ValueError(f"폰트에 넣을 수 없는 문자: {ch!r} (U+{ord(ch):04X})")
    return bytes(out)

# ---------------------------------------------------------------- 글리프 렌더
def render_all():
    f = ImageFont.truetype(FONT, SIZE)
    asc, desc = f.getmetrics()
    y0 = (CELL - (asc + desc)) / 2          # 모든 글자에 같은 베이스라인
    adv = f.getlength(HANGUL[0])
    x0 = (CELL - adv) / 2
    out = np.empty((len(HANGUL), CELL, CELL), np.uint8)
    for i, ch in enumerate(HANGUL):
        im = Image.new('L', (CELL, CELL), 0)
        ImageDraw.Draw(im).text((x0, y0), ch, font=f, fill=255)
        a = np.asarray(im, np.uint16)
        out[i] = ((a * 15 + 127) // 255).astype(np.uint8)   # 0~15 잉크 강도
    return out

# ---------------------------------------------------------------- 사쿠라 1
def morton_order():
    o = np.empty(CELL*CELL, np.int64)
    for m in range(CELL*CELL):
        x = y = 0
        for b in range(5):
            y |= ((m >> (2*b)) & 1) << b
            x |= ((m >> (2*b+1)) & 1) << b
        o[m] = y*CELL + x
    return o
ORDER = morton_order()

def patch_fontall(ink, path_in, path_out, space_width=SPACE_WIDTH):
    d = bytearray(open(path_in, 'rb').read())
    fidx = d.find(b'FIDX')
    fimg = d.find(b'FIMG')
    base = fimg + 16
    n = struct.unpack_from('>I', d, fimg+8)[0]
    for i in range(len(ink)):
        g = S1_BASE + i
        assert g < n, f"글리프 {g} 가 폰트 범위({n})를 넘음"
        val = (15 - ink[i]).astype(np.uint8)          # 0=잉크, 15=배경
        nb = val.reshape(-1)[ORDER]                   # 래스터 -> Morton
        packed = (nb[0::2] & 0xF) | (nb[1::2] << 4)   # 하위 니블 먼저
        d[base + g*512: base + (g+1)*512] = packed.tobytes()
    # 띄어쓰기 자간을 줄인다 (한국어는 일본어와 달리 어절마다 공백이 들어간다)
    ent = fidx + 16 + (0x8140 - 0x8000)*4
    old_w = d[ent+3]
    d[ent+3] = space_width
    open(path_out, 'wb').write(bytes(d))
    return len(d), old_w, space_width

# ---------------------------------------------------------------- 사쿠라 2
def fnt4b_index_lut(tpl_path):
    """FNT4B 팔레트는 인덱스가 잉크 농도에 대해 단조롭지 않다
    (idx0=0%, idx1=93.5% … idx14=6.5%, idx15=100%).
    원하는 잉크 강도 0~15 를 실제로 그 농도를 내는 팔레트 인덱스로 바꾼다."""
    tpl = open(tpl_path, 'rb').read()
    pal = np.frombuffer(tpl[4:36], dtype='>u2')
    lum = np.array([((c >> 10) & 0x1F)*255/31 for c in pal])
    pal_ink = (255 - lum)/255
    return np.array([int(np.argmin(np.abs(pal_ink - d/15))) for d in range(16)],
                    np.uint8)

def patch_fnt4b(ink, cmp_in, cmp_out):
    lut = fnt4b_index_lut(os.path.join(SRC, r"SAKURA2\FNT4B.TPL"))
    raw, method, param, size = decompress(open(cmp_in, 'rb').read())
    W, H = struct.unpack('>HH', raw[:4])
    body = bytearray(raw[4:4+W*H//2])
    pitch = W//2
    for i in range(len(ink)):
        g = S2_BASE + i
        gx, gy = (g % 32)*CELL, (g // 32)*CELL
        assert gy + CELL <= H, f"글리프 {g} 가 아틀라스를 넘음"
        val = lut[ink[i]]                              # 팔레트 인덱스로 변환
        for row in range(CELL):
            line = val[row]
            packed = (line[0::2] << 4) | (line[1::2] & 0xF)   # 상위 니블 먼저
            off = (gy+row)*pitch + gx//2
            body[off:off+CELL//2] = packed.tobytes()
    newraw = raw[:4] + bytes(body) + raw[4+W*H//2:]
    assert len(newraw) == len(raw)
    enc = compress(newraw)
    chk, *_ = decompress(enc)
    assert chk == newraw, "재압축 왕복 검증 실패"
    open(cmp_out, 'wb').write(enc)
    return len(enc), len(open(cmp_in, 'rb').read())

# ---------------------------------------------------------------- main
if __name__ == '__main__':
    os.makedirs(BUILD, exist_ok=True)
    print(f"완성형 {len(HANGUL)}자, 폰트 {os.path.basename(FONT)} {SIZE}px")
    print(f"  '가' -> SJIS 0x{SJIS_OF['가']:04X},  '힝' -> SJIS 0x{SJIS_OF[HANGUL[-1]]:04X}")
    ink = render_all()
    print(f"  렌더 완료: 평균 잉크 커버리지 {ink.mean()/15*100:.1f}%")

    s1_in  = os.path.join(SRC, r"SAKURA1\SAKURA0\FONT\FONTALL.FNT")
    s1_out = os.path.join(BUILD, "FONTALL.FNT")
    sz, ow, nw = patch_fontall(ink, s1_in, s1_out)
    print(f"  사쿠라1: {os.path.basename(s1_out)} {sz} bytes "
          f"(글리프 {S1_BASE}~{S1_BASE+len(ink)-1} 교체, 공백 자간 {ow}->{nw})")

    s2_in  = os.path.join(SRC, r"SAKURA2\FNT4B.CMP")
    s2_out = os.path.join(BUILD, "FNT4B.CMP")
    new, old = patch_fnt4b(ink, s2_in, s2_out)
    print(f"  사쿠라2: {os.path.basename(s2_out)} {new} bytes (원본 {old}, "
          f"{100*new/old:.1f}%)  글리프 {S2_BASE}~{S2_BASE+len(ink)-1} 교체")
    print(f"\n-> {BUILD}")
