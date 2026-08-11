# -*- coding: utf-8 -*-
"""
번역문(TSV 의 ko / ja 열) -> 게임 바이트열. text_dump 의 렌더러와 정확히 역함수여야 한다.

  s1_encode : 사쿠라 1  빅엔디안 SJIS, "$$" = 줄바꿈, NUL 종료
  s2_encode : 사쿠라 2  16비트 리틀엔디안 단위, 0xFFFE = 줄바꿈, 0xFFFF = 끝

공통 처리
  한글          -> make_hangul_font 가 재배치한 ku16~ku40 코드
  ⁉ ‼          -> 외자 코드 0x81AC / 0x81B8
  翔 冑 璧      -> 사쿠라 2 에서는 외자 코드로. 사쿠라 1 에는 그 글리프가 없다.
  <XXXX> {XXXX} -> 그 16비트 값을 그대로 (게임 제어 코드)
  ASCII         -> **그대로 보존**. 원문 일부(선택지 ID 등 스크립트 메타데이터)가
                   반각 숫자를 쓰므로 전각으로 바꾸면 게임 로직이 깨진다.
                   대사에 반각을 쓰면 글리프가 없어 안 보이니, 번역문에는 전각을 쓸 것.
"""
import re, struct, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_hangul_font import SJIS_OF, GAIJI          # 한글 -> SJIS, ⁉ ‼

# 사쿠라 2 전용 외자 (사쿠라 1 폰트에는 이 글리프가 없다)
GAIJI_S2 = dict(GAIJI); GAIJI_S2.update({'翔': 0x81BF, '冑': 0x81DC, '璧': 0x81E5})

TOKEN = re.compile(r'<([0-9A-Fa-f]{2})>|<([0-9A-Fa-f]{4})>|\{([0-9A-Fa-f]{4})\}')

class EncodeError(ValueError): pass

def _units(text, gaiji):
    """문자열 -> 16비트 코드 목록 (제어 토큰 포함). 줄바꿈은 None 으로 표시."""
    out, i = [], 0
    while i < len(text):
        m = TOKEN.match(text, i)
        if m:
            g = m.group(1) or m.group(2) or m.group(3)
            out.append(int(g, 16)); i = m.end(); continue
        ch = text[i]; i += 1
        if ch == '\n': out.append(None); continue
        if ch in gaiji: out.append(gaiji[ch]); continue
        if ch in SJIS_OF: out.append(SJIS_OF[ch]); continue
        if ' ' <= ch <= '~':                 # 반각 ASCII 는 원형 보존
            out.append(('a', ord(ch))); continue
        try:
            b = ch.encode('cp932')
        except Exception:
            raise EncodeError(f"폰트에 없는 문자: {ch!r} (U+{ord(ch):04X})")
        if len(b) != 2:
            raise EncodeError(f"2바이트가 아닌 문자: {ch!r}")
        out.append((b[0] << 8) | b[1])
    return out

def s1_encode(text):
    """빅엔디안 SJIS + "$$" 줄바꿈. NUL 은 붙이지 않는다(호출자가 붙임)."""
    out = bytearray()
    for u in _units(text, GAIJI):
        if u is None:                       out += b'$$'
        elif isinstance(u, tuple):          out += bytes((u[1],))
        else:                               out += struct.pack('>H', u)
    return bytes(out)

def s2_encode(text):
    """16비트 리틀엔디안. 0xFFFE = 줄바꿈, 0xFFFF = 끝(호출자가 붙임)."""
    out = bytearray()
    for u in _units(text, GAIJI_S2):
        v = 0xFFFE if u is None else (u[1] if isinstance(u, tuple) else u)
        out += struct.pack('<H', v)
    return bytes(out)


# ---------------------------------------------------------------- 역함수 (검증용)
_REV_KR   = {v: k for k, v in SJIS_OF.items()}
_REV_G1   = {v: k for k, v in GAIJI.items()}
_REV_G2   = {v: k for k, v in GAIJI_S2.items()}

def _decode_units(units, rev_gaiji):
    out = []
    for u in units:
        if u is None: out.append('\n'); continue
        if isinstance(u, tuple): out.append(chr(u[1])); continue   # 반각 ASCII
        if u in _REV_KR:   out.append(_REV_KR[u]); continue
        if u in rev_gaiji: out.append(rev_gaiji[u]); continue
        b0, b1 = u >> 8, u & 0xFF
        if 0x81 <= b0 <= 0x9F or 0xE0 <= b0 <= 0xEF:
            try:
                out.append(bytes([b0, b1]).decode('cp932')); continue
            except Exception: pass
        out.append(f'<{u:04X}>')
    return ''.join(out)

def s1_decode(b):
    """s1_encode 의 역함수 — Shift-JIS 규칙대로 1/2바이트를 가려 읽는다"""
    units, i = [], 0
    while i < len(b):
        if b[i] == 0x24 and i+1 < len(b) and b[i+1] == 0x24:
            units.append(None); i += 2; continue
        if (0x81 <= b[i] <= 0x9F or 0xE0 <= b[i] <= 0xEF) and i+1 < len(b):
            units.append((b[i] << 8) | b[i+1]); i += 2; continue
        units.append(('a', b[i])); i += 1
    return _decode_units(units, _REV_G1)

def s2_decode(b):
    """s2_encode 의 역함수 (끝의 0xFFFF 는 제외하고 넘길 것)"""
    units = []
    for i in range(0, len(b) - 1, 2):
        u = b[i] | (b[i+1] << 8)
        if u == 0xFFFF: break
        if u == 0xFFFE: units.append(None)
        elif 0x20 <= u <= 0x7E: units.append(('a', u))
        else: units.append(u)
    return _decode_units(units, _REV_G2)
