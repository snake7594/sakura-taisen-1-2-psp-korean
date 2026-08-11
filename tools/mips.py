# -*- coding: utf-8 -*-
"""Minimal MIPS32r2 (little-endian) interpreter -- enough to run the pure
   integer helper functions in SAKURA2.ELF."""
import struct
from elf import ELF

M32 = 0xFFFFFFFF
def s32(v): return v - 0x100000000 if v & 0x80000000 else v
def se16(v): return v - 0x10000 if v & 0x8000 else v

class CPU:
    def __init__(self, elf):
        self.e = elf
        self.mem = {}                      # writable overlay (stack etc.)
        self.STACK = 0x0A000000
    def rd32(self, a):
        if a in self.mem: return self.mem[a]
        b = self.e.read_va(a, 4)
        if b is None or len(b) < 4: raise MemoryError(f"read 0x{a:08X}")
        return struct.unpack('<I', b)[0]
    def rd8(self, a):
        w = self.rd32(a & ~3)
        return (w >> (8*(a & 3))) & 0xFF
    def rd16(self, a):
        w = self.rd32(a & ~3)
        return (w >> (8*(a & 2))) & 0xFFFF
    def wr32(self, a, v): self.mem[a] = v & M32
    def wr8(self, a, v):
        base = a & ~3; w = self.rd32(base); sh = 8*(a & 3)
        self.mem[base] = (w & ~(0xFF << sh) | ((v & 0xFF) << sh)) & M32
    def wr16(self, a, v):
        base = a & ~3; w = self.rd32(base); sh = 8*(a & 2)
        self.mem[base] = (w & ~(0xFFFF << sh) | ((v & 0xFFFF) << sh)) & M32

    def call(self, addr, a0=0, a1=0, a2=0, a3=0, maxsteps=200000):
        r = [0]*32
        r[29] = self.STACK; r[31] = 0xDEADBEEF
        r[4], r[5], r[6], r[7] = a0 & M32, a1 & M32, a2 & M32, a3 & M32
        pc, steps = addr, 0
        pending = None                      # (target_pc,) after delay slot
        while steps < maxsteps:
            steps += 1
            w = self.rd32(pc)
            npc = pc + 4
            jump = self.exec(w, r, pc)
            if jump is not None:
                target, likely, taken = jump
                if likely and not taken:
                    pc = npc + 4            # skip delay slot
                    continue
                # execute delay slot
                dw = self.rd32(npc)
                self.exec(dw, r, npc)
                if taken:
                    if target == 0xDEADBEEF: return r[2] & M32
                    pc = target
                else:
                    pc = npc + 4
                continue
            pc = npc
        raise RuntimeError("step limit")

    def exec(self, w, r, pc):
        op = w >> 26
        rs, rt, rd = (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
        sa, fn = (w >> 6) & 31, w & 63
        imm = w & 0xFFFF
        simm = se16(imm)
        def setr(i, v):
            if i: r[i] = v & M32
        if op == 0:
            if fn == 0:   setr(rd, r[rt] << sa)                    # sll
            elif fn == 2: setr(rd, r[rt] >> sa)                    # srl
            elif fn == 3: setr(rd, s32(r[rt]) >> sa)               # sra
            elif fn == 4: setr(rd, r[rt] << (r[rs] & 31))          # sllv
            elif fn == 6: setr(rd, r[rt] >> (r[rs] & 31))          # srlv
            elif fn == 7: setr(rd, s32(r[rt]) >> (r[rs] & 31))     # srav
            elif fn == 8: return (r[rs], False, True)              # jr
            elif fn == 9:
                setr(rd if rd else 31, pc + 8); return (r[rs], False, True)   # jalr
            elif fn == 10:                                          # movz
                if r[rt] == 0: setr(rd, r[rs])
            elif fn == 11:                                          # movn
                if r[rt] != 0: setr(rd, r[rs])
            elif fn == 32 or fn == 33: setr(rd, r[rs] + r[rt])      # add/addu
            elif fn == 34 or fn == 35: setr(rd, r[rs] - r[rt])      # sub/subu
            elif fn == 36: setr(rd, r[rs] & r[rt])
            elif fn == 37: setr(rd, r[rs] | r[rt])
            elif fn == 38: setr(rd, r[rs] ^ r[rt])
            elif fn == 39: setr(rd, ~(r[rs] | r[rt]))
            elif fn == 42: setr(rd, 1 if s32(r[rs]) < s32(r[rt]) else 0)
            elif fn == 43: setr(rd, 1 if r[rs] < r[rt] else 0)
            else: raise NotImplementedError(f"SPECIAL fn={fn} @0x{pc:08X}")
            return None
        if op == 1:                                                 # REGIMM
            t = pc + 4 + (simm << 2)
            if rt == 0:  return (t, False, s32(r[rs]) < 0)          # bltz
            if rt == 1:  return (t, False, s32(r[rs]) >= 0)         # bgez
            if rt == 2:  return (t, True,  s32(r[rs]) < 0)          # bltzl
            if rt == 3:  return (t, True,  s32(r[rs]) >= 0)         # bgezl
            raise NotImplementedError(f"REGIMM rt={rt} @0x{pc:08X}")
        if op in (2, 3):                                            # j / jal
            t = (pc & 0xF0000000) | ((w & 0x3FFFFFF) << 2)
            if op == 3: r[31] = pc + 8
            return (t, False, True)
        if op == 4:  return (pc+4+(simm<<2), False, r[rs] == r[rt])
        if op == 5:  return (pc+4+(simm<<2), False, r[rs] != r[rt])
        if op == 6:  return (pc+4+(simm<<2), False, s32(r[rs]) <= 0)
        if op == 7:  return (pc+4+(simm<<2), False, s32(r[rs]) > 0)
        if op == 20: return (pc+4+(simm<<2), True,  r[rs] == r[rt])
        if op == 21: return (pc+4+(simm<<2), True,  r[rs] != r[rt])
        if op == 22: return (pc+4+(simm<<2), True,  s32(r[rs]) <= 0)
        if op == 23: return (pc+4+(simm<<2), True,  s32(r[rs]) > 0)
        if op == 8 or op == 9: setr(rt, r[rs] + simm)               # addi/addiu
        elif op == 10: setr(rt, 1 if s32(r[rs]) < simm else 0)      # slti
        elif op == 11: setr(rt, 1 if r[rs] < (simm & M32) else 0)   # sltiu
        elif op == 12: setr(rt, r[rs] & imm)
        elif op == 13: setr(rt, r[rs] | imm)
        elif op == 14: setr(rt, r[rs] ^ imm)
        elif op == 15: setr(rt, imm << 16)                          # lui
        elif op == 31:                                              # SPECIAL3
            if fn == 0:                                             # ext
                pos, size = sa, rd + 1
                setr(rt, (r[rs] >> pos) & ((1 << size) - 1))
            elif fn == 4:                                           # ins
                pos, msb = sa, rd
                size = msb - pos + 1
                mask = ((1 << size) - 1) << pos
                setr(rt, (r[rt] & ~mask) | ((r[rs] << pos) & mask))
            elif fn == 32:                                          # BSHFL
                if sa == 16: setr(rd, r[rt] & 0xFF | (0xFFFFFF00 if r[rt] & 0x80 else 0))
                elif sa == 24: setr(rd, r[rt] & 0xFFFF | (0xFFFF0000 if r[rt] & 0x8000 else 0))
                else: raise NotImplementedError(f"BSHFL sa={sa}")
            else: raise NotImplementedError(f"SPECIAL3 fn={fn} @0x{pc:08X}")
        elif op == 32: setr(rt, (lambda v: v-0x100 if v & 0x80 else v)(self.rd8(r[rs]+simm)))
        elif op == 33: setr(rt, (lambda v: v-0x10000 if v & 0x8000 else v)(self.rd16(r[rs]+simm)))
        elif op == 35: setr(rt, self.rd32(r[rs]+simm))
        elif op == 36: setr(rt, self.rd8(r[rs]+simm))
        elif op == 37: setr(rt, self.rd16(r[rs]+simm))
        elif op == 40: self.wr8(r[rs]+simm, r[rt])
        elif op == 41: self.wr16(r[rs]+simm, r[rt])
        elif op == 43: self.wr32(r[rs]+simm, r[rt])
        else: raise NotImplementedError(f"op={op} @0x{pc:08X} w=0x{w:08X}")
        return None
