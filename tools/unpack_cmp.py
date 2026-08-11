# -*- coding: utf-8 -*-
"""
Batch .CMP unpacker for Sakura Taisen 1&2 (PSP).

  python unpack_cmp.py <file-or-dir> [...]        writes <name>.dec next to each input

Handles the three M9xVDP2.CMP archive containers too
(u32 count, then count x {u32 offset, u32 size}, each member a CMP stream).
"""
import os, sys, struct
from cmp import decompress, parse_header

def is_archive(d):
    if len(d) < 12: return False
    n = struct.unpack_from('<I', d, 0)[0]
    if not (1 <= n <= 64) or 4 + n*8 > len(d): return False
    off, sz = struct.unpack_from('<II', d, 4)
    return off == 4 + n*8 and off + sz <= len(d)

def handle(path):
    d = open(path, 'rb').read()
    if is_archive(d):
        n = struct.unpack_from('<I', d, 0)[0]
        for k in range(n):
            off, sz = struct.unpack_from('<II', d, 4 + k*8)
            out, m, p, s = decompress(d[off:off+sz])
            dst = f"{path}.{k}.dec"
            open(dst, 'wb').write(out)
            print(f"  [{k}] {sz:8d} -> {len(out):8d}  m{m}/p{p}  {os.path.basename(dst)}")
        return
    out, m, p, s = decompress(d)
    open(path + '.dec', 'wb').write(out)
    status = "OK" if len(out) == s else f"SIZE MISMATCH (hdr {s})"
    print(f"{os.path.basename(path):20s} {len(d):9d} -> {len(out):9d}  m{m}/p{p}  {status}")

targets = []
for a in sys.argv[1:]:
    if os.path.isdir(a):
        for root, _, files in os.walk(a):
            targets += [os.path.join(root, f) for f in files if f.upper().endswith('.CMP')]
    else:
        targets.append(a)

if not targets:
    print(__doc__); sys.exit(1)
for t in targets:
    try:
        handle(t)
    except Exception as ex:
        print(f"{os.path.basename(t):20s} FAILED: {ex}")
