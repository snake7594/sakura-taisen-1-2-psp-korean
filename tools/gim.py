# -*- coding: utf-8 -*-
"""
PSP GIM 이미지 디코더.

  파일     "MIG.00.1PSP\\0" 16바이트 + 청크 트리
  청크     u32 type, u32 size, u32 nextOffset, u32 childOffset   (모두 청크 시작 기준)
           type 2=ROOT 3=PICTURE 4=IMAGE 5=PALETTE 0xFF=FILEINFO
  IMAGE/PALETTE 의 헤더(청크+0x10)
           0x00 u16 headerSize   0x04 u16 format   0x06 u16 pixelOrder(1=스위즐)
           0x08 u16 width        0x0A u16 height   0x0C u16 bpp
           0x0E u16 pitchAlign   0x10 u16 heightAlign
           0x1C u32 pixelsOffset (헤더 기준)      0x20 u32 pixelsEnd

  format   0=RGBA5650 1=RGBA5551 2=RGBA4444 3=RGBA8888 4=INDEX4 5=INDEX8 6=INDEX16 7=INDEX32
"""
import struct
import numpy as np

MAGIC = b"MIG.00.1PSP\x00"
FMT_NAME = {0: 'RGBA5650', 1: 'RGBA5551', 2: 'RGBA4444', 3: 'RGBA8888',
            4: 'INDEX4', 5: 'INDEX8', 6: 'INDEX16', 7: 'INDEX32'}
BPP = {0: 16, 1: 16, 2: 16, 3: 32, 4: 4, 5: 8, 6: 16, 7: 32}

class GimError(ValueError): pass

def _chunks(d, start, end):
    """형제 청크들을 (type, 시작오프셋) 으로 훑는다"""
    o = start
    while o + 16 <= end:
        t, size, nxt, child = struct.unpack_from('<4I', d, o)
        if size == 0 or nxt == 0: break
        yield t, o, child
        o += nxt

def _find(d, start, end, want, depth=0, seen=None):
    """형제 순회와 자식 재귀가 같은 청크를 두 번 잡으므로 오프셋으로 중복을 없앤다"""
    if seen is None: seen = set()
    out = []
    for t, o, child in _chunks(d, start, end):
        if o in seen: continue
        seen.add(o)
        size = struct.unpack_from('<I', d, o+4)[0]
        if t == want: out.append(o)
        if child and depth < 6:
            out += _find(d, o+child, min(o+size, end), want, depth+1, seen)
    return sorted(set(out))

def _unswizzle(a, pitch, height):
    rb, br = pitch//16, height//8
    n = rb*br*128
    if a.size < n: a = np.concatenate([a, np.zeros(n-a.size, np.uint8)])
    return a[:n].reshape(br, rb, 8, 16).transpose(0, 2, 1, 3).reshape(br*8, pitch)

def _read_block(d, off):
    """IMAGE / PALETTE 청크 -> (width, height, format, 픽셀 바이트 2차원)"""
    h = off + 0x10
    hs, fmt, order = (struct.unpack_from('<H', d, h)[0],
                      struct.unpack_from('<H', d, h+4)[0],
                      struct.unpack_from('<H', d, h+6)[0])
    w, ht = struct.unpack_from('<HH', d, h+8)
    pitch_a, height_a = struct.unpack_from('<HH', d, h+0x0E)
    po, pe = struct.unpack_from('<II', d, h+0x1C)
    if fmt not in BPP: raise GimError(f"모르는 포맷 {fmt}")
    bpp = BPP[fmt]
    pitch = (w * bpp + 7)//8
    if pitch_a: pitch = ((pitch + pitch_a - 1)//pitch_a)*pitch_a
    rows = ht
    if height_a: rows = ((ht + height_a - 1)//height_a)*height_a
    data = d[h+po: h+pe if pe > po else len(d)]
    need = pitch*rows
    a = np.frombuffer(data[:need], np.uint8)
    if a.size < need: a = np.concatenate([a, np.zeros(need-a.size, np.uint8)])
    if order == 1 and pitch % 16 == 0 and rows % 8 == 0:
        img = _unswizzle(a, pitch, rows)
    else:
        img = a.reshape(rows, pitch)
    return w, ht, fmt, img

def _to_rgba(w, h, fmt, raw, pal=None):
    if fmt in (4, 5, 6, 7):
        if fmt == 4:
            idx = np.empty((raw.shape[0], raw.shape[1]*2), np.uint16)
            idx[:, 0::2] = raw & 0xF; idx[:, 1::2] = raw >> 4
        elif fmt == 5:
            idx = raw.astype(np.uint16)
        else:
            idx = raw.view(np.uint16 if fmt == 6 else np.uint32).astype(np.uint32)
        idx = idx[:h, :w]
        if pal is None:
            g = (idx.astype(np.float32) / max(1, idx.max()) * 255).astype(np.uint8)
            return np.dstack([g, g, g, np.full_like(g, 255)])
        p = pal
        idx = np.clip(idx, 0, len(p)-1)
        return p[idx]
    b = raw
    if fmt == 3:
        px = b.view(np.uint32)[:, :w][:h]
        r = (px & 0xFF).astype(np.uint8); g = ((px >> 8) & 0xFF).astype(np.uint8)
        bl = ((px >> 16) & 0xFF).astype(np.uint8); a = ((px >> 24) & 0xFF).astype(np.uint8)
        return np.dstack([r, g, bl, a])
    px = b.view(np.uint16)[:, :w][:h].astype(np.uint32)
    if fmt == 0:
        r = ((px & 0x1F)*255//31).astype(np.uint8)
        g = (((px >> 5) & 0x3F)*255//63).astype(np.uint8)
        bl = (((px >> 11) & 0x1F)*255//31).astype(np.uint8)
        a = np.full_like(r, 255)
    elif fmt == 1:
        r = ((px & 0x1F)*255//31).astype(np.uint8)
        g = (((px >> 5) & 0x1F)*255//31).astype(np.uint8)
        bl = (((px >> 10) & 0x1F)*255//31).astype(np.uint8)
        a = (((px >> 15) & 1)*255).astype(np.uint8)
    else:
        r = ((px & 0xF)*17).astype(np.uint8)
        g = (((px >> 4) & 0xF)*17).astype(np.uint8)
        bl = (((px >> 8) & 0xF)*17).astype(np.uint8)
        a = (((px >> 12) & 0xF)*17).astype(np.uint8)
    return np.dstack([r, g, bl, a])

def decode(d):
    """GIM 바이트열 -> [(width, height, 포맷이름, RGBA ndarray), ...]"""
    if d[:12] != MAGIC: raise GimError("GIM 이 아님")
    imgs = _find(d, 0x10, len(d), 4)
    pals = _find(d, 0x10, len(d), 5)
    pal = None
    if pals:
        pw, ph, pf, praw = _read_block(d, pals[0])
        pal = _to_rgba(pw, ph, pf, praw).reshape(-1, 4)
    out = []
    for o in imgs:
        w, h, fmt, raw = _read_block(d, o)
        out.append((w, h, FMT_NAME.get(fmt, str(fmt)), _to_rgba(w, h, fmt, raw, pal)))
    return out

if __name__ == '__main__':
    import sys, os
    from PIL import Image
    for p in sys.argv[1:]:
        d = open(p, 'rb').read()
        for i, (w, h, f, a) in enumerate(decode(d)):
            out = os.path.splitext(p)[0] + (f"_{i}" if i else "") + ".png"
            Image.fromarray(a, 'RGBA').save(out)
            print(f"  {os.path.basename(p)} [{i}] {w}x{h} {f} -> {os.path.basename(out)}")
