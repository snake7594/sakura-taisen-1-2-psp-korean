# -*- coding: utf-8 -*-
"""사용: python dump2.py <elf> <lo> <hi> [f]"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from mdis import load, disasm_all

path = sys.argv[1]
lo = int(sys.argv[2], 16); hi = int(sys.argv[3], 16)
_, CODE, BASE = load(path)
I = disasm_all(CODE, BASE)

if len(sys.argv) > 4 and sys.argv[4] == 'f':
    x = lo
    while x > BASE:
        mn, op = I.get(x, ('', ''))
        if mn == 'addiu' and op.startswith('$sp, $sp, -'):
            lo = x; break
        x -= 4

for a in range(lo, hi, 4):
    if a in I:
        mn, op = I[a]
        print(f"  {a:08X}  {mn:<9} {op}")
