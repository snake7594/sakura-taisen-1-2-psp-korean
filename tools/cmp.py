# -*- coding: utf-8 -*-
"""
Sakura Taisen 1&2 (PSP)  ".CMP" decompressor.

Reverse engineered from SAKURA2.ELF (.text @ 0x08900000):
    dispatcher      0x0893EADC
    method 0        0x0893EC3C   byte stream, 16-bit match token
    method 1        0x0893ED44   byte stream,  8-bit match token
    method 2        0x0893EE3C   nibble stream, 8-bit match token
    method 3        0x0893EFF4   nibble stream, 16-bit match token
    nibble helpers  0x0893F1CC readNibble / 0x0893F20C readByte / 0x0893F2BC writeNibble
    param tables    0x089AFFC4 (m0) 0x089AFFCC (m1) 0x089AFFD0 (m2) 0x089AFFD4 (m3)

HEADER
    byte0  bit7    1 = short header (4 bytes), 0 = long header (8 bytes)
           bit6-4  method 0..3
           bit3-0  param -> (offsetBits, lengthBias) from that method's table
    short  uncompressed size = BE32(hdr) & 0x00FFFFFF , payload at +4
    long   uncompressed size = BE32(hdr+4)            , payload at +8

ALGORITHM (all methods, classic LZSS)
    16-bit flag reservoir seeded with 0xFF00; each step it is shifted left and
    masked to 16 bits, and when it equals 0xFF00 again a fresh flag byte is
    pulled in as (flag << 8) | 0xFF.  Bit 15 is then the current flag:
        1 -> emit one literal unit
        0 -> read a match token:
                offset = token & ((1 << offsetBits) - 1)
                count  = (token >> offsetBits) + lengthBias
             copy `count` units from (outPos - offset), one unit at a time so
             overlapping runs work; units before the start of the buffer read 0.
    Loop ends once outPos reaches the uncompressed size (in units).

    Methods 0/1 work on bytes; methods 2/3 work on 4-bit nibbles (the unit count
    is size*2) with the high nibble of a byte coming first.
"""
import struct

# (offsetBits, lengthBias) tables, read straight out of SAKURA2.ELF.
# The tables are laid out back to back, and the game does not range-check
# `param`, so an out-of-range param simply reads into the next table -- these
# 8-entry slices reproduce that behaviour exactly.
_TBL = bytes([0x0C,0x03, 0x0B,0x03, 0x0A,0x03, 0x09,0x03,
              0x06,0x03, 0x05,0x03, 0x06,0x02, 0x05,0x02,
              0x08,0x04, 0x07,0x04, 0x04,0x00, 0x00,0x00])
_BASE = {0: 0, 1: 8, 2: 12, 3: 16}      # byte offset of each method's table

def _params(method, param):
    o = _BASE[method] + param*2
    return _TBL[o], _TBL[o+1]

def parse_header(src):
    b0 = src[0]
    method, param = (b0 >> 4) & 7, b0 & 0x0F
    if b0 & 0x80:
        return method, param, struct.unpack_from('>I', src, 0)[0] & 0xFFFFFF, 4
    return method, param, struct.unpack_from('>I', src, 4)[0], 8


def _lzss_bytes(src, i, size, obits, bias, wide):
    omask = (1 << obits) - 1
    dst = bytearray(size + 4096)          # slack: a match may overrun the tail
    n, res = 0, 0xFF00
    while True:
        res &= 0xFFFF
        if res == 0xFF00:
            res = (src[i] << 8) | 0xFF; i += 1
        if res & 0x8000:
            dst[n] = src[i]; i += 1; n += 1
        else:
            if wide:
                tok = (src[i] << 8) | src[i+1]; i += 2
            else:
                tok = src[i]; i += 1
            off, cnt = tok & omask, (tok >> obits) + bias
            for _ in range(cnt):
                dst[n] = dst[n-off] if n >= off else 0
                n += 1
        if n >= size:
            break
        res <<= 1
    return bytes(dst[:size])


class _NibIn:
    """nibble reader; even index = high nibble (0x0893F1CC / 0x0893F20C)"""
    __slots__ = ('b', 'p')
    def __init__(self, b, start): self.b, self.p = b, start*2
    def nib(self):
        p = self.p; self.p = p + 1
        return (self.b[p >> 1] >> 4) if not (p & 1) else (self.b[p >> 1] & 0xF)
    def byte(self):
        p = self.p
        if not (p & 1):
            self.p = p + 2
            return self.b[p >> 1]
        return (self.nib() << 4) | self.nib()


def _lzss_nibbles(src, i, size, obits, bias, wide):
    omask = (1 << obits) - 1
    limit = size * 2                       # unit count is nibbles
    out = bytearray(size + 4096)          # slack: a match may overrun the tail
    rd = _NibIn(src, i)

    def rd_out(p):
        return (out[p >> 1] >> 4) if not (p & 1) else (out[p >> 1] & 0xF)
    def wr_out(p, v):
        k = p >> 1
        if p & 1: out[k] = (out[k] & 0xF0) | (v & 0xF)
        else:     out[k] = ((v & 0xF) << 4) | (out[k] & 0xF)

    n, res = 0, 0xFF00
    while True:
        res &= 0xFFFF
        if res == 0xFF00:
            res = (rd.byte() << 8) | 0xFF
        if res & 0x8000:
            wr_out(n, rd.nib()); n += 1
        else:
            tok = ((rd.byte() << 8) | rd.byte()) if wide else rd.byte()
            off, cnt = tok & omask, (tok >> obits) + bias
            for _ in range(cnt):
                wr_out(n, rd_out(n-off) if n >= off else 0)
                n += 1
        if n >= limit:
            break
        res <<= 1
    return bytes(out[:size])


def decompress(src):
    """returns (data, method, param, declared_size)"""
    method, param, size, i = parse_header(src)
    obits, bias = _params(method, param)
    if method == 0:   out = _lzss_bytes(src, i, size, obits, bias, True)
    elif method == 1: out = _lzss_bytes(src, i, size, obits, bias, False)
    elif method == 2: out = _lzss_nibbles(src, i, size, obits, bias, False)
    elif method == 3: out = _lzss_nibbles(src, i, size, obits, bias, True)
    else: raise ValueError(f"unknown CMP method {method}")
    return out, method, param, size


if __name__ == '__main__':
    import sys, os
    for p in sys.argv[1:]:
        raw = open(p, 'rb').read()
        try:
            out, m, pa, sz = decompress(raw)
            print(f"{os.path.basename(p):16s} {len(raw):8d} -> {len(out):9d} "
                  f"(hdr {sz})  method={m} param={pa}")
            open(p + '.dec', 'wb').write(out)
        except Exception as ex:
            print(f"{os.path.basename(p):16s} FAILED: {ex}")
