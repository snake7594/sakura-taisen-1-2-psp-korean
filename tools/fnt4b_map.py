# -*- coding: utf-8 -*-
"""
Sakura Taisen 2 (PSP) -- FNT4B font: Shift-JIS -> glyph index.

The mapping is not a table in the data files; it is code in SAKURA2.ELF.
Rather than transcribe it, this script emulates the game's own routines:

    0x08947210  drawChar(sjis, ...)   entry point; valid range 0x8140..0xEAA4
    0x089464EC  sjisToJis(sjis)       -> (jisHi << 8) | jisLo, ISO-2022 bytes
                                         (row/cell biased by 0x20)
    then, on ku' = jis >> 8:
      ku' <  0x30   0x08946FF0  jump table @0x089B0150, one handler per JIS row
      ku' <  0x50   inline      glyph = 492 + (ku'-0x30)*94 + (ten'-0x21)
                                (JIS level 1 kanji, fully contiguous)
      ku' >= 0x50   0x08946F50  if-chain of 12 JIS level 2 kanji

Atlas layout, straight from the blitter at 0x08947310:
    32 glyphs per row, 32x32 cells, row stride 512 bytes (1024 px @ 4bpp)
    glyph g -> (row = g // 32, col = g % 32)

Layout of the 3488 cells:
    0    .. 491   JIS ku 1-15 subset  (includes the custom gaiji below)
    492  .. 3456  JIS level 1 kanji, all 2965 of them
    3457 .. 3468  12 JIS level 2 kanji (also aliased at SJIS 0x9873-0x987E)
    3469 .. 3487  blank padding

Gaiji: glyphs 107-135 are reached by SJIS 0x81AC and 0x81B8-0x81E6 -- nominally
〓 and the maths symbols ∈∋⊆⊇⊂⊃∪∩∧∨¬⇒⇔∀∃∠⊥⌒∂∇≡≒≪≫√∽∝∵ -- but the font
draws custom characters there instead: ‼? ‼ マ ザ ー グ ー ス and the rare kanji
剎甦戮鬪慟哭擲爛邂逅冑檄渕澤條濱廣繚瞞璧炸.  Codes 0x81E7 onward are normal again.
"""
import sys, io, os
from collections import Counter
from elf import ELF
from mips import CPU

ELF_PATH = r"D:\psp\사쿠라대전1_2\extract\PSP_GAME\USRDIR\SAKURA2\SAKURA2.ELF"
OUT      = r"D:\psp\사쿠라대전1_2\font_png"
NGLYPH   = 3488
GAIJI    = range(107, 136)          # image differs from the nominal SJIS char
BLANK    = range(3469, NGLYPH)

cpu = CPU(ELF(ELF_PATH))

def glyph_of(sjis):
    """exactly what the game computes for a Shift-JIS code"""
    if not (0x8140 <= sjis <= 0xEAA4):
        return 0
    code = cpu.call(0x089464EC, sjis) & 0xFFFF
    ku = (code >> 8) & 0xFF
    if ku < 0x30:
        return cpu.call(0x08946FF0, ku, code & 0xFF) & 0xFFFF
    if ku < 0x50:
        a1 = 0 if code < 0x307F else ((code - 0x307F) >> 8) + 1
        return (code - 0x2E35) - a1 * 162
    return cpu.call(0x08946F50, code, code & 0xFF) & 0xFFFF

def ch(s):
    try: return bytes([s >> 8, s & 0xFF]).decode('cp932')
    except Exception: return None

def build():
    fwd = {}
    for hi in list(range(0x81, 0xA0)) + list(range(0xE0, 0xF0)):
        for lo in range(0x40, 0xFD):
            if lo == 0x7F: continue
            s = (hi << 8) | lo
            if s > 0xEAA4: continue
            g = glyph_of(s)
            if (g == 0 and s != 0x8140) or g >= NGLYPH: continue
            fwd[s] = g
    return fwd

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    fwd = build()
    print(f"mapped SJIS codes : {len(fwd)}")
    print(f"distinct glyphs   : {len(set(fwd.values()))} / {NGLYPH}")

    by_ku = Counter()
    for s, g in fwd.items():
        code = cpu.call(0x089464EC, s) & 0xFFFF
        by_ku[(code >> 8) - 0x20] += 1
    print("\nglyphs per JIS row (ku):")
    for ku in sorted(by_ku):
        print(f"   ku {ku:2d}: {by_ku[ku]:4d}")

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "FNT4B_map.tsv"), 'w', encoding='utf-8') as f:
        f.write("# Sakura Taisen 2 (PSP) FNT4B: Shift-JIS -> glyph index\n")
        f.write("# atlas 1024x3488, 32 cols, 32x32 cells; glyph -> row=g//32, col=g%32\n")
        f.write("# note: gaiji = the drawn glyph is NOT the nominal SJIS character\n")
        f.write("# glyph\trow\tcol\tSJIS\tchar\tnote\n")
        for s in sorted(fwd, key=lambda k: (fwd[k], k)):
            g = fwd[s]
            note = 'gaiji' if g in GAIJI else ('blank' if g in BLANK else '')
            f.write(f"{g}\t{g//32}\t{g%32}\t{s:04X}\t{ch(s) or ''}\t{note}\n")
    print(f"\nwrote {os.path.join(OUT, 'FNT4B_map.tsv')}")
