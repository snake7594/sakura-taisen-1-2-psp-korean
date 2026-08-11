# -*- coding: utf-8 -*-
"""
.SPR 이미지용 LZSS 압축기 (spr.lzss 의 역함수).

무압축으로 저장하면 파일이 4~5배로 불어 ISO 의 배정 공간을 넘는다.
그래서 원래 방식대로 다시 압축해야 한다.

풀이 쪽(0x08961A68)은 4096바이트 링버퍼의 **절대 위치**로 매치를 가리키지만,
링버퍼는 결국 '최근 4096바이트의 출력'이므로 보통의 LZ77 과 같다.
    거리 d = (r - pos) & 0xFFF,  길이 3~18
겹치는 복사(d < 길이)도 풀이 쪽이 한 바이트씩 옮기므로 그대로 성립한다.

시작 시 링버퍼는 0 으로 차 있지만, 자료 앞을 가리키는 매치는 쓰지 않는다.
맨 앞 몇 바이트를 조금 손해 볼 뿐이고 정확성이 확실하다.
"""
import sys, os
from collections import defaultdict

MINM, MAXM, WIN = 3, 18, 4096
R0 = 0xFEE

def compress(src):
    n = len(src)
    out = bytearray()
    flags, nbits, part = 0, 0, bytearray()
    heads = defaultdict(list)          # 3바이트 -> 최근 위치들
    i, r = 0, R0

    def flush():
        nonlocal flags, nbits, part
        if nbits:
            out.append(flags); out.extend(part)
            flags, nbits, part = 0, 0, bytearray()

    def emit(bit, data):
        nonlocal flags, nbits, part
        if bit: flags |= (1 << nbits)
        nbits += 1; part += data
        if nbits == 8: flush()

    while i < n:
        best_len, best_d = 0, 0
        if i + MINM <= n:
            key = src[i:i+MINM]
            cand = heads.get(bytes(key))
            if cand:
                for p in reversed(cand[-64:]):        # 가까운 것부터 64개만
                    d = i - p
                    if d <= 0 or d > WIN: continue
                    L = 0
                    while L < MAXM and i + L < n and src[p + L] == src[i + L]:
                        L += 1
                    if L > best_len:
                        best_len, best_d = L, d
                        if L == MAXM: break
        if best_len >= MINM:
            pos = (r - best_d) & 0xFFF
            b0 = pos & 0xFF
            b1 = ((pos >> 8) << 4) | (best_len - MINM)
            emit(0, bytes((b0, b1)))
            for k in range(best_len):
                if i + MINM <= n: heads[bytes(src[i:i+MINM])].append(i)
                i += 1; r = (r + 1) & 0xFFF
        else:
            emit(1, bytes((src[i],)))
            if i + MINM <= n: heads[bytes(src[i:i+MINM])].append(i)
            i += 1; r = (r + 1) & 0xFFF
    flush()
    return bytes(out)

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import spr
    from build_iso import walk_iso, SRC_ISO, SECTOR
    f = open(SRC_ISO, 'rb'); table = walk_iso(f)
    tot = ok = 0
    ratio = []
    for p in sorted(table):
        if not p.upper().endswith('.SPR'): continue
        _, lba, sz = table[p]; f.seek(lba*SECTOR); d = f.read(sz)
        for off, size, ix, b in spr.chunks(d):
            c, e, db = spr.entries(b)
            if not (c and any(t[5] for t in e)): continue
            for w, h, fmt, q, eo, es in e[:3]:
                if not es: continue
                need = w*h*spr.BPP[fmt & 0x0F]//8
                raw = b[db+eo: db+eo+es]
                px = spr.lzss(raw, need)[0] if (fmt >> 4) else raw[:need]
                enc = compress(px)
                back = spr.lzss(enc, need)[0]
                tot += 1
                if back == px: ok += 1
                else: print(f"  왕복 실패 {p} {w}x{h}")
                if fmt >> 4: ratio.append(len(enc)/max(1, es))
            break
        if tot > 240: break
    import statistics
    print(f"압축 왕복 검증 {ok}/{tot} 일치")
    if ratio:
        print(f"원본 압축본 대비 크기: 평균 {statistics.mean(ratio)*100:.0f}% "
              f"(최대 {max(ratio)*100:.0f}%)")
