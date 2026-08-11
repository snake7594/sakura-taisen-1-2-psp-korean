# -*- coding: utf-8 -*-
"""
Sakura Taisen 1&2 (PSP) -- dialogue text extractor.

SAKURA 1   /PSP_GAME/USRDIR/SAKURA1/**/*.PFS  ("PAKFILE" archives, see pfs.py)
           members come in pairs  NNNN.bin (script bytecode) + NNNNtbl.bin (text)
           NNNNtbl.bin:
               u16BE  tableWords     -> entryCount = tableWords / 2
               u16BE  (unknown)
               entryCount x { u16BE id, u16BE offset }   offset is in 16-bit WORDS
               text block at 4 + entryCount*4, strings are plain big-endian
               Shift-JIS, NUL terminated, "$$" = line break

SAKURA 2   /PSP_GAME/USRDIR/SAKURA2/SAKURA2/*.MES
               u32BE  count
               count x u32BE  absolute byte offset
               entry = 4 byte header (speaker / voice id) then text stored as
               16-bit LITTLE-endian units holding Shift-JIS pairs
               0xFFFE = line break, 0xFFFF = end of message

Note for Sakura 2: SJIS 0x81AC and 0x81B8-0x81E6 are gaiji -- the font draws
custom glyphs there, not the nominal maths symbols (see fnt4b_map.py).
"""
import struct, sys, io, os

# ---------------- Sakura 1 ----------------
def parse_tbl(d):
    words = struct.unpack_from('>H', d, 0)[0]
    n = words // 2
    base = 4 + n*4
    out = []
    for k in range(n):
        idv, off = struct.unpack_from('>HH', d, 4 + k*4)
        p = base + off*2                      # offsets count 16-bit words
        if p >= len(d): continue
        e = d.find(b'\x00', p)
        if e < 0: e = len(d)
        out.append((k, idv, d[p:e]))
    return out

def s1_text(raw):
    return raw.decode('cp932', 'replace').replace('$$', '\n')

# ---------------- Sakura 2 ----------------
def parse_mes(d):
    n = struct.unpack_from('>I', d, 0)[0]
    offs = struct.unpack_from(f'>{n}I', d, 4)
    ends = list(offs[1:]) + [len(d)]
    out = []
    for i, (o, e) in enumerate(zip(offs, ends)):
        out.append((i, d[o:o+4], d[o+4:e]))
    return out

def s2_text(body):
    s = []
    for i in range(0, len(body) - 1, 2):
        w = body[i] | (body[i+1] << 8)
        if w == 0xFFFE: s.append('\n'); continue
        if w == 0xFFFF: break
        if w == 0: continue
        b0, b1 = w >> 8, w & 0xFF
        if 0x81 <= b0 <= 0x9F or 0xE0 <= b0 <= 0xEF:
            try: s.append(bytes([b0, b1]).decode('cp932')); continue
            except Exception: pass
        s.append(f'<{w:04X}>')
    return ''.join(s)

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    what = sys.argv[1] if len(sys.argv) > 1 else ''
    if what.lower().endswith('tbl.bin'):
        for k, idv, raw in parse_tbl(open(what, 'rb').read()):
            if raw: print(f"[{k:4d}] id=0x{idv:04X}\n{s1_text(raw)}\n")
    elif what.lower().endswith('.mes'):
        for i, hdr, body in parse_mes(open(what, 'rb').read()):
            print(f"[{i:4d}] {hdr.hex()}\n{s2_text(body)}\n")
    else:
        print(__doc__)
