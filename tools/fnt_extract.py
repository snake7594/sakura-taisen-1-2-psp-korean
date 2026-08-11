# -*- coding: utf-8 -*-
"""
Sakura Taisen 1&2 (PSP)  ---  .FNT font extractor

Container layout (all big-endian):
  0x00  'FONT' + 4 pad
  0x08  'FIDX' u16 ver u16 hdrlen | u32 nEntries(0x4000) | u16 defW u16 pad
        then nEntries x { u16 glyphIndex (0xFFFF = none), u16 width }
        entry index == ShiftJIS code - 0x8000
  ..    'FPAL' u32 secLen | u32 nColors | ... | 8 x u16 alpha ramp (ARGB4444, black)
  ..    'FIMG' u32 secLen | u32 nGlyphs | u32 pad
        then nGlyphs x 512 bytes  =  32x32 pixels, 4bpp

Pixel order inside a glyph: **Morton / Z-order curve**, low nibble first.
  nibble m -> x = odd bits of m, y = even bits of m
Value 0 = solid ink (black), 15 = background (transparent).
"""
import numpy as np, struct, os, sys
from PIL import Image, ImageDraw

SRC = r"D:\psp\사쿠라대전1_2\extract\PSP_GAME\USRDIR"
OUT = r"D:\psp\사쿠라대전1_2\font_png"
os.makedirs(OUT, exist_ok=True)
W = H = 32

# ---- Morton order table: order[k] = raster index of the k-th nibble ----
def morton_order():
    o = np.empty(W*H, np.int64)
    for m in range(W*H):
        x = y = 0
        for b in range(5):
            y |= ((m >> (2*b))   & 1) << b     # even bits -> y
            x |= ((m >> (2*b+1)) & 1) << b     # odd  bits -> x
        o[m] = y*W + x
    return o
ORDER = morton_order()

def decode_glyphs(raw):
    """raw: (n,512) uint8 -> (n,32,32) uint8 of 4bpp values"""
    n = raw.shape[0]
    nb = np.empty((n, W*H), np.uint8)
    nb[:, 0::2] = raw & 0x0F          # low nibble first
    nb[:, 1::2] = raw >> 4
    img = np.empty_like(nb)
    img[:, ORDER] = nb
    return img.reshape(n, H, W)

def parse(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'FONT', "not a FONT container"
    fidx, fpal, fimg = d.find(b'FIDX'), d.find(b'FPAL'), d.find(b'FIMG')
    nEntries = struct.unpack_from('>I', d, fidx+8)[0]
    nGlyphs  = struct.unpack_from('>I', d, fimg+8)[0]
    ent = np.frombuffer(d[fidx+16: fidx+16+nEntries*4], dtype='>u2').reshape(-1, 2)
    raw = np.frombuffer(d[fimg+16: fimg+16+nGlyphs*512], np.uint8).reshape(nGlyphs, 512)
    pal = np.frombuffer(d[fpal+32: fpal+48], dtype='>u2')
    return ent, raw, pal, nGlyphs

def sjis_char(code):
    try:
        return bytes([(code >> 8) + 0x80, code & 0xFF]).decode('cp932')
    except Exception:
        return ''

def build(path, name, cols=64):
    ent, raw, pal, n = parse(path)
    imgs = decode_glyphs(raw)
    rows = (n + cols - 1)//cols
    # grayscale atlas: value*17 -> 0(ink) .. 255(background). exact 4bpp round-trip
    atlas = np.full((rows*H, cols*W), 255, np.uint8)
    for i in range(n):
        r, c = divmod(i, cols)
        atlas[r*H:(r+1)*H, c*W:(c+1)*W] = imgs[i] * 17
    Image.fromarray(atlas, 'L').save(os.path.join(OUT, f"{name}_atlas.png"))

    # RGBA version: black ink, alpha from the 4bpp level
    rgba = np.zeros((rows*H, cols*W, 4), np.uint8)
    rgba[..., 3] = 255 - atlas
    Image.fromarray(rgba, 'RGBA').save(os.path.join(OUT, f"{name}_atlas_alpha.png"))

    # mapping table
    lines = [f"# {name}: {n} glyphs, cell {W}x{H}, atlas {cols} cols x {rows} rows",
             "# glyph\trow\tcol\tSJIS\tchar\twidth"]
    used = 0
    for code in range(ent.shape[0]):
        g, wid = int(ent[code, 0]), int(ent[code, 1])
        if g == 0xFFFF: continue
        used += 1
        r, c = divmod(g, cols)
        lines.append(f"{g}\t{r}\t{c}\t{code+0x8000:04X}\t{sjis_char(code)}\t{wid}")
    open(os.path.join(OUT, f"{name}_map.tsv"), 'w', encoding='utf-8').write('\n'.join(lines))

    # labelled preview of the first 256 glyphs
    S, PC = 2, 16
    pv = Image.new('RGB', (PC*(W*S+4), 16*(H*S+14)), (235,235,240))
    dr = ImageDraw.Draw(pv)
    for i in range(min(256, n)):
        r, c = divmod(i, PC)
        gi = Image.fromarray(imgs[i]*17, 'L').convert('RGB').resize((W*S, H*S), Image.NEAREST)
        pv.paste(gi, (c*(W*S+4)+2, r*(H*S+14)+12))
        dr.text((c*(W*S+4)+2, r*(H*S+14)+1), str(i), fill=(70,70,120))
    pv.save(os.path.join(OUT, f"{name}_preview.png"))
    print(f"{name}: {n} glyphs, {used} mapped codes -> atlas {cols*W}x{rows*H}, palette {[hex(p) for p in pal]}")
    return n

build(os.path.join(SRC, r"SAKURA1\SAKURA0\FONT\FONTALL.FNT"), "FONTALL")
build(os.path.join(SRC, r"SAKURA1\SAKURA0\FONT\ENDING.FNT"),  "ENDING", cols=32)

# ---- MG_FONT.CG : 16 glyphs of 32x32, 4bpp, plain linear rows (32x512 strip).
#      Note: opposite polarity to the .FNT files -- 0 = background, 15 = ink.
a = np.frombuffer(open(os.path.join(SRC, r"SAKURA2\SAKURA3\MG_FONT.CG"),'rb').read(), np.uint8)
b = a.reshape(-1, 16)
o = np.empty((b.shape[0], 32), np.uint8)
o[:, 0::2], o[:, 1::2] = b & 0xF, b >> 4
Image.fromarray(o*17, 'L').save(os.path.join(OUT, "MG_FONT.png"))
print(f"MG_FONT: 32x{o.shape[0]} strip, {o.shape[0]//32} glyphs of 32x32")
print("\nwritten to", OUT)
