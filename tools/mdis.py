import re, struct
from collections import Counter
from capstone import *
from elf import ELF

def load(path):
    e = ELF(path)
    text = [s for s in e.shdrs if s['sname'] == '.text'][0]
    code = e.d[text['off']: text['off']+text['size']]
    return e, code, text['addr']

def disasm_all(code, base):
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 + CS_MODE_LITTLE_ENDIAN)
    md.skipdata = True
    md.skipdata_setup = ("dw", None, None)
    out = {}
    for i in md.disasm(code, base):
        out[i.address] = (i.mnemonic, i.op_str)
    # fill gaps (capstone may still stop); brute force any missing word
    md2 = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 + CS_MODE_LITTLE_ENDIAN)
    for off in range(0, len(code) - 3, 4):
        a = base + off
        if a not in out:
            got = False
            for j in md2.disasm(code[off:off+4], a):
                out[a] = (j.mnemonic, j.op_str); got = True
            if not got:
                w = struct.unpack_from('<I', code, off)[0]
                out[a] = ('.word', f'0x{w:08x}')
    return out

def find_lui_addiu(insns, target):
    """find code building the 32-bit constant `target` via lui+addiu/ori"""
    hits = []
    hi16 = (target >> 16) & 0xFFFF
    lo16 = target & 0xFFFF
    hi_adj = (hi16 + 1) & 0xFFFF          # when lo16 is sign-negative
    for a in sorted(insns):
        mn, op = insns[a]
        if mn != 'lui': continue
        m = re.match(r'\$(\w+), (0x[0-9a-f]+|\d+)', op)
        if not m: continue
        v = int(m.group(2), 16 if m.group(2).startswith('0x') else 10)
        reg = m.group(1)
        if v not in (hi16, hi_adj): continue
        for k in range(1, 12):
            b = a + 4*k
            if b not in insns: break
            mn2, op2 = insns[b]
            if mn2 in ('addiu','ori','addi'):
                m2 = re.match(rf'\$\w+, \${reg}, (-?\w+)', op2)
                if m2:
                    s = m2.group(1)
                    val = int(s, 16) if s.startswith(('0x','-0x')) else int(s)
                    lo = val & 0xFFFF
                    if (v << 16) + (val if mn2 != 'ori' else lo) & 0xFFFFFFFF == target or \
                       ((v << 16) | lo) == target or \
                       ((v << 16) + (val if val < 0x8000 else val - 0x10000)) & 0xFFFFFFFF == target:
                        hits.append((a, b))
                        break
    return hits
