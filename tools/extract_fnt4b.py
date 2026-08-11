# -*- coding: utf-8 -*-
"""Sakura Taisen 2 (PSP) FNT4B font: .CMP decompress -> PNG atlas."""
import numpy as np, struct, os
from PIL import Image, ImageDraw
from cmp import decompress

SRC = r"D:\psp\사쿠라대전1_2\extract\PSP_GAME\USRDIR\SAKURA2"
OUT = r"D:\psp\사쿠라대전1_2\font_png"
os.makedirs(OUT, exist_ok=True)

raw = open(os.path.join(SRC, "FNT4B.CMP"), 'rb').read()
dec, method, param, size = decompress(raw)
open(os.path.join(OUT, "FNT4B.dec"), 'wb').write(dec)
W, H = struct.unpack('>HH', dec[:4])
print(f"FNT4B.CMP {len(raw)} -> {len(dec)} (method {method}, param {param}); image {W}x{H} 4bpp")

a = np.frombuffer(dec[4:4+W*H//2], np.uint8).reshape(H, W//2)
img = np.empty((H, W), np.uint8)
# High nibble is the LEFT pixel -- same convention as the engine's own nibble
# accessors (readNibble @0x0893F1CC treats an even index as the high nibble).
# Note this is the opposite of the .FNT glyph bitmaps, which are low-first.
img[:, 0::2], img[:, 1::2] = a >> 4, a & 0xF

# ---- palette from FNT4B.TPL : u32 count, then count x u16 BE (ARGB1555) ----
tpl = open(os.path.join(SRC, "FNT4B.TPL"), 'rb').read()
ncol = struct.unpack('>I', tpl[:4])[0]
pal = np.frombuffer(tpl[4:4+ncol*2], dtype='>u2')
lum = np.array([round(((c >> 10) & 0x1F) * 255 / 31) for c in pal], np.uint8)
print("palette luminance by index:", lum.tolist())

Image.fromarray(lum[img], 'L').save(os.path.join(OUT, "FNT4B_atlas.png"))
rgba = np.zeros((H, W, 4), np.uint8)
rgba[..., 3] = 255 - lum[img]                      # black ink, alpha from coverage
Image.fromarray(rgba, 'RGBA').save(os.path.join(OUT, "FNT4B_atlas_alpha.png"))

# raw 4bpp index image (exact round-trip: gray = value*17)
Image.fromarray(img*17, 'L').save(os.path.join(OUT, "FNT4B_atlas_raw4bpp.png"))

cols, cell = W//32, 32
n = (H//cell) * cols
print(f"{n} glyph cells ({cols} per row x {H//cell} rows)")

S, PC = 2, 16
pv = Image.new('RGB', (PC*(cell*S+4), 16*(cell*S+14)), (235,235,240))
dr = ImageDraw.Draw(pv)
for i in range(256):
    r, c = divmod(i, cols)
    g = img[r*cell:(r+1)*cell, c*cell:(c+1)*cell]
    pr, pc = divmod(i, PC)
    tile = Image.fromarray(lum[g], 'L').convert('RGB').resize((cell*S, cell*S), Image.NEAREST)
    pv.paste(tile, (pc*(cell*S+4)+2, pr*(cell*S+14)+12))
    dr.text((pc*(cell*S+4)+2, pr*(cell*S+14)+1), str(i), fill=(70,70,120))
pv.save(os.path.join(OUT, "FNT4B_preview.png"))

# tail comparison strip: last 32 glyphs of FNT4B
strip = np.hstack([img[(H//cell-1)*cell:H, c*cell:(c+1)*cell] for c in range(cols)])
Image.fromarray(lum[strip], 'L').resize((strip.shape[1]*2, strip.shape[0]*2), Image.NEAREST) \
     .save(os.path.join(OUT, "FNT4B_tail.png"))
print("done ->", OUT)
