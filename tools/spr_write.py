# -*- coding: utf-8 -*-
"""
.SPR 다시 쓰기 — 이미지 한 장을 갈아 끼운다.

바꾼 이미지는 spr_compress 로 **다시 압축**해 넣는다. fmt 상위 니블을 0 으로
두면 날것으로도 읽히지만(spr.py 머리말), 그러면 파일이 4~5배로 불어
ISO 의 배정 공간을 넘는다. 다시 압축하면 원본 대비 101% 쯤에서 그친다.

컨테이너는 청크표에 각 청크의 절대 오프셋과 크기가 들어 있으므로,
바뀐 이미지 청크만 새로 만들고 표를 다시 계산하면 된다.
다른 청크(애니메이션·히트박스)는 바이트 그대로 옮긴다.
"""
import os, sys, struct
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spr, spr_compress

ALIGN = 16

def raw_px(body, ent, db):
    """엔트리 -> 압축을 푼 픽셀 바이트열 (bpp 상관없이)"""
    w, h, fmt, q, eo, es = ent
    need = w*h*spr.BPP[fmt & 0x0F]//8
    raw = body[db+eo: db+eo+es]
    return spr.lzss(raw, need)[0] if (fmt >> 4) else raw[:need]

def unpack_px(body, ent, db):
    """엔트리 -> (h, w) 팔레트 인덱스 배열 (4/8bpp 만)"""
    w, h, fmt, q, eo, es = ent
    bpp = spr.BPP[fmt & 0x0F]
    a = np.frombuffer(raw_px(body, ent, db), np.uint8)
    if bpp == 8:
        return a[:w*h].reshape(h, w).copy()
    if bpp == 4:                     # 하위 니블이 왼쪽 픽셀
        o = np.empty(w*h, np.uint8)
        o[0::2], o[1::2] = a & 0xF, a >> 4
        return o[:w*h].reshape(h, w).copy()
    raise ValueError(f"{bpp}bpp 는 인덱스 이미지가 아니다")

def unpack16(body, ent, db):
    """16bpp 이미지 -> (h, w) u16 배열 (빅엔디안 ABGR1555 값 그대로)"""
    w, h, fmt, q, eo, es = ent
    a = np.frombuffer(raw_px(body, ent, db), dtype='>u2')
    return a[:w*h].reshape(h, w).copy()

def rgb1555(v):
    """ABGR1555 -> (r, g, b) 0~31"""
    return (v & 0x1F, (v >> 5) & 0x1F, (v >> 10) & 0x1F)

def mk1555(r, g, b, a=1):
    return (a << 15) | (int(b) << 10) | (int(g) << 5) | int(r)

def pack_px(img, bpp):
    if bpp == 8: return img.astype(np.uint8).tobytes()
    if bpp == 16: return img.astype('>u2').tobytes()
    if bpp == 4:
        f = img.astype(np.uint8).reshape(-1)
        return ((f[1::2] << 4) | (f[0::2] & 0xF)).astype(np.uint8).tobytes()
    raise ValueError(bpp)

def rebuild(d, changes):
    """changes = {이미지번호: (h,w) 인덱스배열}. 새 .SPR 바이트열을 돌려준다."""
    ch = spr.chunks(d)
    if not ch: raise ValueError("SPR 이 아니다")

    # 이미지 청크 찾기 — 장수·엔트리가 모두 말이 되는 청크
    img_i = None
    for k, (off, size, idx, body) in enumerate(ch):
        cnt, ents, db = spr.entries(body)
        if cnt and any(e[5] for e in ents):      # size 가 실제로 있는 것
            img_i = k; break
    if img_i is None: raise ValueError("이미지 청크를 못 찾음")

    off, size, idx, body = ch[img_i]
    cnt, ents, db = spr.entries(body)
    for i in changes:
        if not (0 <= i < cnt): raise ValueError(f"이미지 번호 {i} 없음 (장수 {cnt})")

    # 새 이미지 청크: 머리 + 엔트리표 + 데이터
    head = bytearray(body[:0x10])
    tbl, blob = bytearray(), bytearray()
    for i, (w, h, fmt, q, eo, es) in enumerate(ents):
        if i in changes:
            bpp = spr.BPP[fmt & 0x0F]
            raw = pack_px(changes[i], bpp)
            # 원래 압축돼 있던 것은 다시 압축한다. 날것으로 두면 파일이 4~5배로
            # 불어 ISO 의 배정 공간(섹터 단위)을 넘는다.
            data = spr_compress.compress(raw) if (fmt >> 4) else raw
            nfmt = fmt
        else:
            data = body[db+eo: db+eo+es]
            nfmt = fmt
        while len(blob) % 4: blob += b'\x00'
        tbl += struct.pack('>4H2I', w, h, nfmt, q, len(blob), len(data))
        blob += data
    newbody = bytes(head + tbl + blob)

    # 컨테이너 다시 쌓기 (청크 차례는 그대로)
    bodies = [newbody if k == img_i else c[3] for k, c in enumerate(ch)]
    tbl_len = 0x10 + len(ch)*16
    cur = (tbl_len + ALIGN - 1)//ALIGN*ALIGN
    out = bytearray(d[:0x10])
    places = []
    for b in bodies:
        places.append(cur); cur += (len(b) + ALIGN - 1)//ALIGN*ALIGN
    for (o, s, ix, _), at, b in zip(ch, places, bodies):
        out += struct.pack('>4I', at, len(b), ix, 0)
    out = bytearray(out.ljust(places[0], b'\x00'))
    for at, b in zip(places, bodies):
        out = bytearray(out.ljust(at, b'\x00')) + bytearray(b)
    return bytes(out.ljust(cur, b'\x00'))

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    from build_iso import walk_iso, SRC_ISO, SECTOR

    def pics(x):
        """이미지 청크의 압축 푼 픽셀들"""
        for o, s2, i2, b in spr.chunks(x):
            c, e, db = spr.entries(b)
            if c and any(t[5] for t in e):
                return [raw_px(b, t, db) for t in e if t[5]]
        return []

    f = open(SRC_ISO, 'rb'); table = walk_iso(f)
    n = ok = skip = 0
    for p2 in sorted(table):
        if not p2.upper().endswith('.SPR'): continue
        _, lba, sz = table[p2]; f.seek(lba*SECTOR); d = f.read(sz)
        if not spr.chunks(d): continue
        try:
            nd = rebuild(d, {})
        except Exception as e:
            skip += 1; continue
        n += 1
        a, b2 = pics(d), pics(nd)
        if len(a) == len(b2) and all(x == y for x, y in zip(a, b2)): ok += 1
        else: print(f"  다름: {p2}")
    print(f"무압축 재기록 왕복 검증: {ok}/{n} 일치 (건너뜀 {skip})")
