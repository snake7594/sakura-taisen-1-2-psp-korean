# -*- coding: utf-8 -*-
"""
사쿠라대전 2 본편(ADV) 대사 SK####.CMP 에 자(ruler)를 넣는다. + 분량 집계.

  python make_ruler_test3.py --count    분량만 집계
  python make_ruler_test3.py            자 삽입 후 build/sk/ 에 재압축 저장

메시지는 텍스트 블록 안에 이어 붙어 있고 인덱스가 16비트 단위 오프셋으로 가리킨다.
원래 자리에 같은 바이트 수 이하로만 덮어쓰면 인덱스를 건드릴 필요가 없다.
"""
import os, sys, struct, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmp import decompress
from cmp_compress import compress
from sk_text import parse, render

ROOT  = r"D:\psp\사쿠라대전1_2"
SRC   = os.path.join(ROOT, "extract", "PSP_GAME", "USRDIR", "SAKURA2", "SAKURA1")
BUILD = os.path.join(ROOT, "build", "sk")
DIGITS = "１２３４５６７８９０"
MINCH  = 26
END = b'\xff\xff'

def enc_le(t):
    o = bytearray()
    for ch in t:
        b = ch.encode('cp932'); o += bytes((b[1], b[0]))
    return bytes(o)

def inject(dec):
    r = parse(dec)
    if r is None: return dec, 0
    tbl, txt, ent = r
    starts = sorted({o for _, o, _ in ent})
    nxt = {p: (starts[i+1] if i+1 < len(starts) else len(dec))
           for i, p in enumerate(starts)}
    out = bytearray(dec)
    made = 0
    for p in starts:
        avail = nxt[p] - p                       # 0xFFFF 자리 포함
        nch = (avail - 2)//2
        if nch < MINCH: continue
        ruler = enc_le((DIGITS * ((nch//10)+2))[:nch]) + END
        if len(ruler) > avail: continue
        out[p:p+len(ruler)] = ruler
        out[p+len(ruler): nxt[p]] = b'\x00' * (nxt[p] - p - len(ruler))
        made += 1
    return bytes(out), made

def files():
    return sorted(glob.glob(os.path.join(SRC, "SK[0-9]*.CMP")))

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    fs = files()
    if not fs: sys.exit(f"{SRC} 에 SK*.CMP 가 없습니다")

    if '--count' in sys.argv:
        nmsg = nch = 0
        for p in fs:
            dec, *_ = decompress(open(p, 'rb').read())
            r = parse(dec)
            if r is None: continue
            for i, o, raw in r[2]:
                t = render(raw)
                if t.strip(): nmsg += 1; nch += len(t)
        print(f"SK*.CMP {len(fs)}개 : 메시지 {nmsg}개, {nch}자")
        sys.exit()

    os.makedirs(BUILD, exist_ok=True)
    tot = big = 0
    for p in fs:
        raw = open(p, 'rb').read()
        dec, *_ = decompress(raw)
        new, made = inject(dec)
        if not made: continue
        enc = compress(new)
        chk, *_ = decompress(enc)
        assert chk == new, f"{p} 재압축 왕복 실패"
        if len(enc) > len(raw):
            big += 1
            print(f"  주의 {os.path.basename(p)}: {len(raw)} -> {len(enc)} (커짐)")
        open(os.path.join(BUILD, os.path.basename(p)), 'wb').write(enc)
        tot += made
    print(f"{len(os.listdir(BUILD))}개 파일, 메시지 {tot}개를 자로 교체"
          f"{f'  (원본보다 커진 파일 {big}개)' if big else ''}")
    print(f"-> {BUILD}")
