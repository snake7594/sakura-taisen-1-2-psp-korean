# -*- coding: utf-8 -*-
"""
드림캐스트 PowerVR (PVR) 텍스처 — 이 게임 이미지의 실제 형식.

사쿠라대전 1·2 는 드림캐스트판 이식이라 이미지가 DC 의 PVR 그대로 들어 있다.
그래서 파일 어디에도 폭이 없어 보였던 것이고, 폭을 바꿔가며 그려도 글자가
어긋나 보였던 것이다 — 픽셀이 **트위들(Morton/Z 순서)** 로 섞여 있기 때문.

  .CMP 를 풀면 아래가 이어 붙어 있다 (한 파일에 여러 장이 들어가기도 한다)

  [GBIX]  선택, 8+n바이트   'GBIX' u32 size u64 globalIndex
  [PVRT]  16바이트 헤더
          +0x00  'PVRT'
          +0x04  u32  이후 바이트 수 (헤더 나머지 8 + 픽셀)
          +0x08  u8   pixelFormat   색 형식
          +0x09  u8   dataFormat    배치 방식
          +0x0A  u16  (미사용)
          +0x0C  u16  width
          +0x0E  u16  height
  [픽셀]  nextSize - 8 바이트

팔레트(PAL4/PAL8)는 같은 이름의 .CL / .PAL 파일에 들어 있다.
"""
import struct
import numpy as np

PIXEL_FMT = {0x00: 'ARGB1555', 0x01: 'RGB565', 0x02: 'ARGB4444', 0x03: 'YUV422',
             0x04: 'BUMP', 0x05: 'PAL4', 0x06: 'PAL8'}
DATA_FMT = {0x01: 'SQUARE_TWIDDLED', 0x02: 'SQUARE_TWIDDLED_MIP',
            0x03: 'VQ', 0x04: 'VQ_MIP', 0x05: 'PAL4_TWIDDLED',
            0x06: 'PAL8_TWIDDLED', 0x07: 'RECTANGLE', 0x08: 'RECT_STRIDE',
            0x09: 'RECT_TWIDDLED', 0x0A: 'SMALL_VQ_x', 0x0B: 'RECTANGLE_ST',
            0x0D: 'RECT_TWIDDLED2', 0x10: 'SMALL_VQ', 0x11: 'SMALL_VQ_MIP',
            0x12: 'SQUARE_TWIDDLED_MIP2'}

PAL4_FMTS = {0x05}
PAL8_FMTS = {0x06}
VQ_FMTS   = {0x03, 0x04, 0x10, 0x11}
MIP_FMTS  = {0x02, 0x04, 0x11, 0x12}
NONTWIDDLE = {0x07, 0x08, 0x0B}          # 사각형 = 선형 배치

class PvrError(ValueError): pass


# ---------------------------------------------------------------- 헤더 훑기
def _pow2(v):
    return v >= 8 and (v & (v-1)) == 0

def walk(d):
    """바이트열 안의 PVRT 텍스처를 순서대로 찾는다.

    'PVRT' 는 픽셀 데이터 안에서도 우연히 나올 수 있어(1037x512 같은 헛짚음이
    실제로 나왔다) 폭·높이가 2의 거듭제곱인지, 크기 필드가 파일 안에 들어맞는지
    확인한다. 하나 찾으면 그 길이만큼 건너뛰어 다음 것을 찾는다.

    반환: [(오프셋, pixelFormat, dataFormat, width, height, 픽셀바이트), ...]"""
    out, o, n = [], 0, len(d)
    while True:
        o = d.find(b'PVRT', o)
        if o < 0 or o + 16 > n: break
        nxt = struct.unpack_from('<I', d, o+4)[0]
        pf, df = d[o+8], d[o+9]
        w, h = struct.unpack_from('<HH', d, o+12)
        px_len = nxt - 8
        ok = (_pow2(w) and _pow2(h) and w <= 2048 and h <= 2048
              and 8 <= nxt and o + 8 + nxt <= n
              and df in DATA_FMT and pf in PIXEL_FMT)
        if not ok:
            o += 4
            continue
        out.append((o, pf, df, w, h, d[o+16: o+16+px_len]))
        o = o + 8 + nxt
    return out


# ---------------------------------------------------------------- 트위들
_MORTON = {}

def _morton(side):
    """정사각 블록 안의 Z 곡선 좌표 (x, y)"""
    if side in _MORTON: return _MORTON[side]
    i = np.arange(side*side, dtype=np.uint32)
    x = np.zeros(i.shape, np.uint32); y = np.zeros(i.shape, np.uint32)
    for b in range(16):
        x |= ((i >> (2*b)) & 1) << b
        y |= ((i >> (2*b+1)) & 1) << b
    _MORTON[side] = (x, y)
    return x, y

def untwiddle(flat, w, h):
    """트위들된 1차원 픽셀 -> (h, w).

    PVR 은 짧은 변을 한 변으로 하는 정사각 블록들을 긴 변을 따라 늘어놓고,
    각 블록 안을 Z 곡선으로 채운다."""
    side = min(w, h)
    x, y = _morton(side)
    out = np.zeros((h, w), flat.dtype)
    nblk = (w*h)//(side*side)
    for b in range(nblk):
        blk = flat[b*side*side:(b+1)*side*side]
        if blk.size == 0: break
        tile = np.zeros((side, side), flat.dtype)
        tile[y[:blk.size], x[:blk.size]] = blk
        if w >= h: out[:, b*side:(b+1)*side] = tile
        else:      out[b*side:(b+1)*side, :] = tile
    return out


# ---------------------------------------------------------------- 색 변환
def _unpack16(px, pf):
    """u16 배열 -> RGBA"""
    p = px.astype(np.uint32)
    if pf == 0x00:            # ARGB1555
        r = ((p >> 10) & 0x1F)*255//31; g = ((p >> 5) & 0x1F)*255//31
        b = (p & 0x1F)*255//31;         a = ((p >> 15) & 1)*255
    elif pf == 0x01:          # RGB565
        r = ((p >> 11) & 0x1F)*255//31; g = ((p >> 5) & 0x3F)*255//63
        b = (p & 0x1F)*255//31;         a = np.full(p.shape, 255)
    elif pf == 0x02:          # ARGB4444
        r = ((p >> 8) & 0xF)*17; g = ((p >> 4) & 0xF)*17
        b = (p & 0xF)*17;        a = ((p >> 12) & 0xF)*17
    else:
        g0 = (p & 0xFF).astype(np.uint8)
        return np.dstack([g0, g0, g0, np.full(p.shape, 255, np.uint8)])
    return np.dstack([r.astype(np.uint8), g.astype(np.uint8),
                      b.astype(np.uint8), a.astype(np.uint8)])

def load_palette(raw):
    """u16 팔레트 -> RGBA(N,4). 빅엔디안 ABGR1555, 인덱스 0 은 투명."""
    if raw is None or len(raw) < 32: return None
    n = len(raw)//2
    p = np.frombuffer(raw[:n*2], dtype='>u2').astype(np.uint32)
    r = ((p & 0x1F)*255//31).astype(np.uint8)
    g = (((p >> 5) & 0x1F)*255//31).astype(np.uint8)
    b = (((p >> 10) & 0x1F)*255//31).astype(np.uint8)
    a = np.full(p.shape, 255, np.uint8); a[0] = 0
    return np.dstack([r, g, b, a])[0]


# ---------------------------------------------------------------- 디코드
def decode_one(pf, df, w, h, px, pal=None):
    """텍스처 하나 -> (RGBA ndarray, 설명)"""
    tw = df not in NONTWIDDLE

    if df in VQ_FMTS:
        # 코드북 256개 x 2x2 픽셀 x u16 = 2048바이트, 그 뒤에 인덱스 (w/2)*(h/2)
        cb_n = 256 if df in (0x03, 0x04) else 64
        cb = np.frombuffer(px[:cb_n*8], np.uint16).reshape(-1, 4)
        idx = np.frombuffer(px[cb_n*8:], np.uint8)
        iw, ih = w//2, h//2
        need = iw*ih
        if idx.size < need: idx = np.concatenate([idx, np.zeros(need-idx.size, np.uint8)])
        idx = untwiddle(idx[-need:] if idx.size > need else idx[:need], iw, ih)
        blk = cb[np.clip(idx, 0, len(cb)-1)]        # (ih, iw, 4)
        out16 = np.zeros((h, w), np.uint16)
        out16[0::2, 0::2] = blk[:, :, 0]; out16[1::2, 0::2] = blk[:, :, 1]
        out16[0::2, 1::2] = blk[:, :, 2]; out16[1::2, 1::2] = blk[:, :, 3]
        return _unpack16(out16, pf), f"VQ cb{cb_n}"

    if df in PAL4_FMTS or pf == 0x05:
        need = w*h//2
        raw = px[-need:] if (df in MIP_FMTS and len(px) > need) else px[:need]
        a = np.frombuffer(raw.ljust(need, b'\0'), np.uint8)
        flat = np.empty(a.size*2, np.uint8)
        flat[0::2], flat[1::2] = a & 0xF, a >> 4      # 하위 니블 먼저
        idx = untwiddle(flat, w, h) if tw else flat[:w*h].reshape(h, w)
        bits = 4
    elif df in PAL8_FMTS or pf == 0x06:
        need = w*h
        raw = px[-need:] if (df in MIP_FMTS and len(px) > need) else px[:need]
        idx = np.frombuffer(raw.ljust(need, b'\0'), np.uint8)
        idx = untwiddle(idx, w, h) if tw else idx[:w*h].reshape(h, w)
        bits = 8
    else:
        need = w*h*2
        raw = px[-need:] if (df in MIP_FMTS and len(px) > need) else px[:need]
        a = np.frombuffer(raw.ljust(need, b'\0'), np.uint16)
        a = untwiddle(a, w, h) if tw else a[:w*h].reshape(h, w)
        return _unpack16(a, pf), "direct"

    if pal is None:
        g = (idx.astype(np.float32)/max(1, int(idx.max()))*255).astype(np.uint8)
        return np.dstack([g, g, g, np.full_like(g, 255)]), f"pal{bits} (팔레트없음)"
    return pal[np.clip(idx, 0, len(pal)-1)], f"pal{bits}"

def decode(d, pal_bytes=None):
    """바이트열 -> [(width, height, 설명, RGBA ndarray), ...]"""
    pal = load_palette(pal_bytes)
    out = []
    for o, pf, df, w, h, px in walk(d):
        try:
            rgba, note = decode_one(pf, df, w, h, px, pal)
        except Exception as e:
            continue
        info = (f"{w}x{h} {PIXEL_FMT.get(pf, hex(pf))}/"
                f"{DATA_FMT.get(df, hex(df))} {note}")
        out.append((w, h, info, rgba))
    return out
