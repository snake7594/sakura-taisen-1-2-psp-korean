# -*- coding: utf-8 -*-
"""
.CMP 압축기 (method 0 / param 0) — cmp.py 의 역연산.

포맷은 CMP_FORMAT.md 참고. 게임의 압축 해제 루틴이 그대로 읽을 수 있는
스트림을 만든다.

    헤더 4바이트 : 0x80 | (24비트 원본 크기, 빅엔디안)
    본문         : 플래그 바이트(MSB부터) 1=리터럴 / 0=매치
                   매치 토큰 = BE16,  길이=(w>>obits)+bias,  거리=w&((1<<obits)-1)

**param 을 맞춰야 한다.** obits/bias 는 param 이 정한다 (CMP_FORMAT.md 표).
    param 0 : 12비트 거리 / 길이 3~18     — 창이 넓고 매치가 짧다
    param 3 :  9비트 거리 / 길이 3~130    — 창이 좁고 매치가 길다
M##LOW.CMP 처럼 param 3 으로 압축된 파일을 param 0 으로 다시 압축하면
긴 매치를 못 써서 33% 나 커진다. 원본과 같은 param 으로 압축할 것.

압축 후 반드시 cmp.decompress() 로 왕복 검증할 것.
"""
import struct

CHAIN = 512         # 후보 탐색 깊이 (크면 압축률↑ 속도↓)

def compress(src: bytes, obits: int = 12, bias: int = 3, header: bytes = None) -> bytes:
    """obits/bias 는 원본 param 과 같게 줄 것.
    header 를 주면 그 헤더를 그대로 쓰고 크기 칸만 고친다 (긴 헤더 보존용)."""
    MINLEN = bias
    MAXLEN = bias + (1 << (16 - obits)) - 1
    MAXOFF = (1 << obits) - 1
    n = len(src)
    if header is None:
        out = bytearray(struct.pack('>I', 0x80000000 | (n & 0xFFFFFF)))
    else:
        out = bytearray(header)
        # 첫 바이트에 method/param 이 들어 있으므로 **그대로 두고** 크기만 고친다.
        # 0x80|크기 로 덮어쓰면 param 니블이 지워져 (0x83 -> 0x80) 게임이
        # 엉뚱한 param 으로 읽는다.
        if header[0] & 0x80: out[1:4] = struct.pack('>I', n & 0xFFFFFF)[1:]
        else:                out[4:8] = struct.pack('>I', n)
    heads = {}                      # 3바이트 키 -> 최근 위치 목록
    items, flags, nbits = [], 0, 0

    def flush():
        nonlocal items, flags, nbits
        if not nbits: return
        out.append((flags << (8 - nbits)) & 0xFF)
        for it in items: out.extend(it)
        items, flags, nbits = [], 0, 0

    def emit(tok, is_lit):
        nonlocal flags, nbits
        flags = (flags << 1) | (1 if is_lit else 0)
        nbits += 1
        items.append(tok)
        if nbits == 8: flush()

    i = 0
    while i < n:
        best_len, best_off = 0, 0
        if i + MINLEN <= n:
            key = src[i:i+MINLEN]
            lst = heads.get(key)
            if lst:
                lo = i - MAXOFF
                limit = min(MAXLEN, n - i)
                for p in reversed(lst):
                    if p < lo: break
                    if src[p:p+best_len+1] != src[i:i+best_len+1]:
                        continue            # 현재 최고보다 길어질 수 없음
                    L = best_len + 1
                    while L < limit and src[p+L] == src[i+L]:
                        L += 1
                    if L > best_len:
                        best_len, best_off = L, i - p
                        if L == limit: break
        if best_len >= MINLEN:
            tok = ((best_len - MINLEN) << obits) | best_off
            emit(bytes((tok >> 8, tok & 0xFF)), False)
            step = best_len
        else:
            emit(bytes((src[i],)), True)
            step = 1
        # 해시 갱신
        for k in range(i, min(i + step, n - MINLEN + 1)):
            heads.setdefault(src[k:k+MINLEN], []).append(k)
            l = heads[src[k:k+MINLEN]]
            if len(l) > CHAIN: del l[0]
        i += step
    flush()
    return bytes(out)

if __name__ == '__main__':
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cmp import decompress
    for p in sys.argv[1:]:
        raw = open(p, 'rb').read()
        enc = compress(raw)
        dec, m, pa, sz = decompress(enc)
        ok = dec == raw
        print(f"{os.path.basename(p)}: {len(raw)} -> {len(enc)} "
              f"({100*len(enc)/len(raw):.1f}%)  왕복검증 {'OK' if ok else '실패'}")
        if ok: open(p + '.cmp', 'wb').write(enc)
