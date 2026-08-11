# `.CMP` compression — Sakura Taisen 1&2 (PSP)

Reverse engineered from `PSP_GAME/USRDIR/SAKURA2/SAKURA2.ELF`.
`PSP_GAME/SYSDIR/EBOOT.BIN` is `~PSP`-encrypted, but `SYSDIR/BOOT.BIN` is a plain
ELF — and it turned out to be only a loader that chain-loads `SAKURA1.ELF` /
`SAKURA2.ELF`, which are plain `ET_EXEC` MIPS ELFs. `.text` sits at `0x08900000`.

## Addresses

| what | address |
|---|---|
| dispatcher | `0x0893EADC` |
| method 0 — byte stream, 16-bit token | `0x0893EC3C` |
| method 1 — byte stream, 8-bit token | `0x0893ED44` |
| method 2 — nibble stream, 8-bit token | `0x0893EE3C` |
| method 3 — nibble stream, 16-bit token | `0x0893EFF4` |
| `readNibble(buf, &pos)` | `0x0893F1CC` |
| `readByte(buf, &pos)` | `0x0893F20C` |
| `writeNibble(v, buf, &pos)` | `0x0893F2BC` |
| param tables | `0x089AFFC4` m0 · `0x089AFFCC` m1 · `0x089AFFD0` m2 · `0x089AFFD4` m3 |

Called as `decompress(dst, src)`; the dispatcher splits the first byte and tail-calls
the method with `(dst, src+hdr, uncompressedSize, param)`.

## Header

```
byte0   bit7    1 = short header (4 bytes), 0 = long header (8 bytes)
        bit6-4  method (0..3)
        bit3-0  param  -> (offsetBits, lengthBias)
short   size = BE32(hdr) & 0x00FFFFFF ,  payload at +4
long    size = BE32(hdr+4)            ,  payload at +8
```

`FNT4B.CMP` starts `80 1B 40 04` → short header, method 0, param 0, size `0x1B4004` = 1 785 860.

## Parameter tables

The four tables are laid out back to back and `param` is **not** range-checked, so an
out-of-range param simply reads into the next table. One shipped file (`method 0, param 6`)
relies on this.

| param | m0 `0x089AFFC4` | m1 `0x089AFFCC` | m2 `0x089AFFD0` | m3 `0x089AFFD4` |
|---|---|---|---|---|
| 0 | 12, 3 | 6, 3 | 6, 2 | 8, 4 |
| 1 | 11, 3 | 5, 3 | 5, 2 | 7, 4 |
| 2 | 10, 3 | 6, 2 | 8, 4 | 4, 0 |
| 3 |  9, 3 | 5, 2 | 7, 4 | 0, 0 |

(as `offsetBits, lengthBias`)

## Algorithm — LZSS, identical for all four methods

A 16-bit flag reservoir is seeded with `0xFF00`. Each step it is shifted left and masked
to 16 bits; whenever it equals `0xFF00` again, all 8 flag bits have been consumed and a
fresh byte is pulled in as `(flag << 8) | 0xFF`. Bit 15 is the current flag:

* **1 → literal**: emit one unit straight from the input.
* **0 → match**: read a token, then
  ```
  offset = token & ((1 << offsetBits) - 1)
  count  = (token >> offsetBits) + lengthBias
  ```
  and copy `count` units from `outPos - offset`, **one unit at a time** so overlapping
  runs (`offset` smaller than `count`) expand correctly. Units read from before the
  start of the buffer yield 0.

The loop ends once `outPos` reaches the size from the header. The inner copy has no
bound check, so a final match can run slightly past the declared size — allocate slack
and truncate.

Methods 0/1 work on **bytes**. Methods 2/3 work on **4-bit nibbles** (unit count is
`size * 2`), and the **high nibble of a byte comes first**.

## Nibble order in 4bpp pixel data — watch out

The engine's own accessors (`readNibble` @ `0x0893F1CC`) treat an **even index as the
high nibble**, and the decompressed `FNT4B` atlas follows the same rule: the high
nibble of a byte is the **left** pixel. Decoding it low-first still produces
recognisable glyphs, but every horizontally adjacent pixel pair is swapped, which
shows up as a comb/torn edge on diagonals — very visible on `△▲▽▼`.

The `.FNT` glyph bitmaps (`FONTALL.FNT`, `ENDING.FNT`) are the **opposite**:
Morton/Z-order with **low nibble first**. `MG_FONT.CG` is drawn at 2x horizontal
scale so both nibbles of each byte are equal and the order does not matter there.

## Archive containers

`SAKURA2/SAKURA2/M9{1,2,3}VDP2.CMP` are not CMP streams but small archives:

```
u32 count
count x { u32 offset, u32 size }     // little-endian
```

each member being an ordinary CMP stream.

## Verification

All 400 `.CMP` files on the disc: 397 direct streams (392 × m0, 2 × m1, 1 × m2, 5 × m3)
plus 3 archives holding 12 members. Every one decompresses to exactly the size declared
in its header.
