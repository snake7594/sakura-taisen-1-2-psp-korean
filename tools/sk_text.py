# -*- coding: utf-8 -*-
"""
사쿠라대전 2 본편(ADV) 대사 — `SAKURA2/SAKURA1/SK####.CMP`

.CMP 로 압축돼 있고, 풀면:

    u32LE 헤더 여러 개
        [2] 메시지 인덱스 테이블의 오프셋
        [3] 텍스트 블록의 오프셋
        [4] 전체 크기
    인덱스 테이블 : u32LE, 텍스트 블록 기준 **16비트 단위** 오프셋
    텍스트        : 16비트 리틀엔디안 Shift-JIS (.MES 와 같은 규칙)
                    0xFFFE = 줄바꿈, 0xFFFF = 메시지 끝

`.MES` 는 이벤트·전투·시스템 메시지였고, 평상시 어드벤처 파트 대사는 여기에 있다.
"""
import struct, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmp import decompress

def parse(dec):
    """압축 해제된 SK 데이터 -> (tbl_off, txt_off, [(index, 바이트오프셋, 원시바이트)])"""
    hdr = struct.unpack_from('<8I', dec, 0)
    tbl, txt = hdr[2], hdr[3]
    if not (0 < tbl < txt <= len(dec)): return None
    n = (txt - tbl)//4
    offs = struct.unpack_from(f'<{n}I', dec, tbl)
    out = []
    for i, o in enumerate(offs):
        p = txt + o*2                      # 16비트 단위
        if p >= len(dec): continue
        e = p
        while e + 1 < len(dec):
            if dec[e] == 0xFF and dec[e+1] == 0xFF: break
            e += 2
        out.append((i, p, dec[p:e]))
    return tbl, txt, out

def render(raw):
    s = []
    for i in range(0, len(raw)-1, 2):
        w = raw[i] | (raw[i+1] << 8)
        if w == 0xFFFF: break
        if w == 0xFFFE: s.append('\n'); continue
        if w == 0: continue
        b0, b1 = w >> 8, w & 0xFF
        if 0x81 <= b0 <= 0x9F or 0xE0 <= b0 <= 0xEF:
            try: s.append(bytes([b0, b1]).decode('cp932')); continue
            except Exception: pass
        s.append(f'<{w:04X}>')
    return ''.join(s)

def load(path):
    dec, *_ = decompress(open(path, 'rb').read())
    return dec, parse(dec)

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    for p in sys.argv[1:]:
        dec, r = load(p)
        if r is None:
            print(f"{os.path.basename(p)}: 텍스트 구조 아님"); continue
        tbl, txt, ent = r
        real = [(i, o, raw) for i, o, raw in ent if raw]
        print(f"===== {os.path.basename(p)}  압축해제 {len(dec)}  "
              f"테이블 {tbl:#x}  텍스트 {txt:#x}  메시지 {len(ent)}개(비어있지 않은 것 {len(real)}) =====")
        for i, o, raw in real[:15]:
            print(f"  [{i:4d}] @{o:#07x} {render(raw)!r}")
        print()
