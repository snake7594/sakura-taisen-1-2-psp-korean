# -*- coding: utf-8 -*-
"""
.SPR — 세가 SPRED 스프라이트 컨테이너.

  python spr.py            image_png/spr/ 에 추출 + 컨택트시트
  python spr.py --info     구조와 포맷 분포만 출력

SAKURA1.ELF 에서 역추적했다.
    파서        0x08954800   memcmp(파일, "SEGA SPRED", 10) 후 청크표 순회
    이미지청크  0x089579CC   (슬롯 2)
    bpp 표      0x08AAFEE4   [4,4,8,8,8,16,24,32]  ← fmt & 0x0F 로 색인
    압축 해제   0x08961A68   lzss(src, srcSize, dst, dstSize)

컨테이너 (전부 **빅엔디안**)
  +0x00  'SEGA SPRED 02.0M'
  +0x10  청크표 [u32 offset][u32 size][u32 index][u32 rsv] 반복 (index < 14)

  팔레트 청크  크기 0x1010 = 16B 머리 + 4096B = u16 2048색 (ABGR1555, 0=투명)
  이미지 청크  +0x00 u16 장수, +0x10 부터 16바이트 엔트리
               [u16 w][u16 h][u16 fmt][u16 ?][u32 offset][u32 size]
               offset 은 엔트리표 끝(0x10 + 장수*0x10) 기준

  fmt 는 두 니블로 나뉜다
      하위 니블 = 색 형식 (bpp 표 색인)   1 -> 4bpp, 4 -> 8bpp, 5 -> 16bpp
      상위 니블 = 압축 여부               0 -> 날것, 그 외 -> LZSS
    실제로 쓰이는 값: 0x01 0x04 (날것), 0x11 0x14 0x15 (압축)

압축 = 고전 오쿠무라식 LZSS (0x08961A68 그대로)
    링버퍼 4096바이트, 0 으로 초기화, 쓰기 위치 r = 0xFEE 에서 시작
    플래그 바이트에서 **LSB 부터** 비트를 꺼낸다
      1 -> 리터럴 1바이트 (출력과 링버퍼 양쪽에 쓴다)
      0 -> 매치 2바이트 b0, b1
           pos = b0 | ((b1 >> 4) << 8)      링버퍼 **절대 위치** 12비트
           len = (b1 & 0x0F) + 3
           링버퍼에서 한 바이트씩 읽어 출력과 링버퍼에 함께 쓴다
    출력이 dstSize 에 닿으면 끝. dstSize = w * h * bpp / 8.

    ※ 상대 오프셋을 쓰는 .CMP 의 LZSS(cmp.py)와는 다른 방식이다.
"""
import os, sys, io, struct, collections
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_iso import walk_iso, SRC_ISO, SECTOR

OUT = r"D:\psp\사쿠라대전1_2\image_png\spr"
MAGIC = b'SEGA SPR'
BPP = [4, 4, 8, 8, 8, 16, 24, 32]        # 0x08AAFEE4


# ----------------------------------------------------------------- 컨테이너
def chunks(d):
    """[(offset, size, index, 바이트열), ...]"""
    if d[:8] != MAGIC: return []
    out, o = [], 0x10
    while o + 16 <= len(d):
        off, size, idx, rsv = struct.unpack_from('>4I', d, o)
        if off == 0 or size == 0 or off > len(d) or off+size > len(d): break
        if idx >= 14: break
        out.append((off, size, idx, d[off:off+size]))
        o += 16
        if o >= off: break
    return out

def entries(c):
    """이미지 청크 -> (장수, [(w, h, fmt, q, offset, size), ...], 데이터시작)

    애니메이션·히트박스 청크도 앞 u16 이 우연히 그럴듯한 장수로 읽히므로
    모든 줄이 말이 되는지 확인한다."""
    if len(c) < 0x20: return 0, [], 0
    cnt = struct.unpack_from('>H', c, 0)[0]
    if not (1 <= cnt <= 4096): return 0, [], 0
    db = 0x10 + cnt*0x10
    if db > len(c): return 0, [], 0
    ents = []
    for i in range(cnt):
        o = 0x10 + i*0x10
        w, h, fmt, q = struct.unpack_from('>4H', c, o)
        off, size = struct.unpack_from('>2I', c, o+8)
        if fmt > 0xFF or (fmt & 0x0F) >= len(BPP): return 0, [], 0
        if w > 2048 or h > 2048: return 0, [], 0
        if size and db + off + size > len(c): return 0, [], 0
        ents.append((w, h, fmt, q, off, size))
    return cnt, ents, db


# ----------------------------------------------------------------- LZSS
def lzss(src, need):
    """0x08961A68 을 그대로 옮긴 것. 링버퍼 절대 위치 방식."""
    ring = bytearray(4096)
    r = 0xFEE
    out = bytearray(need)
    n = 0
    i, N = 0, len(src)
    flags, nbits = 0, 0
    while n < need:
        if nbits == 0:
            if i >= N: break
            flags = src[i]; i += 1; nbits = 8
        bit = flags & 1
        flags >>= 1; nbits -= 1
        if bit:                                  # 리터럴
            if i >= N: break
            c = src[i]; i += 1
            out[n] = c; n += 1
            ring[r] = c; r = (r + 1) & 0xFFF
        else:                                    # 매치
            if i + 1 >= N: break
            b0, b1 = src[i], src[i+1]; i += 2
            pos = b0 | ((b1 >> 4) << 8)
            ln = (b1 & 0x0F) + 3
            for _ in range(ln):
                c = ring[pos]
                out[n] = c; n += 1
                ring[r] = c
                pos = (pos + 1) & 0xFFF
                r = (r + 1) & 0xFFF
                if n >= need: break
    return bytes(out), n


# ----------------------------------------------------------------- 팔레트
def palette(d):
    """팔레트 청크(idx=1) -> (N, 4) RGBA. 없으면 None

    머리 16바이트 (빅엔디안 u16)
        +0  데이터 바이트 수
        +2  색 하나의 크기 : 4 면 4바이트, 그 밖(0)이면 2바이트
        +4  팔레트 한 벌의 색 수 (16 / 256)
        +6  형식 코드 — 크기를 정하지 않는다. COOKBG 는 code=1 이지만 2바이트다.

    4바이트 색은 [A][R][G][B] 순서. 채널을 뒤집으면 피부가 파래지고
    사쿠라의 검은 머리·빨간 리본이 갈색 머리·파란 리본이 되어 틀린다.
    2바이트 색은 빅엔디안 ABGR1555 (R 이 하위) 이고 인덱스 0 을 투명으로 쓴다."""
    for off, size, idx, c in chunks(d):
        if idx != 1 or size <= 0x10: continue
        raw = c[0x10:]
        wide = struct.unpack_from('>H', c, 2)[0] == 4
        if wide:
            a = np.frombuffer(raw[:len(raw)//4*4], np.uint8).reshape(-1, 4)
            pl = np.empty((len(a), 4), np.uint8)
            pl[:, 0], pl[:, 1], pl[:, 2], pl[:, 3] = a[:, 1], a[:, 2], a[:, 3], a[:, 0]
        else:
            p = np.frombuffer(raw[:len(raw)//2*2], dtype='>u2').astype(np.uint32)
            r = ((p & 0x1F)*255//31).astype(np.uint8)
            g = (((p >> 5) & 0x1F)*255//31).astype(np.uint8)
            b = (((p >> 10) & 0x1F)*255//31).astype(np.uint8)
            al = np.full(p.shape, 255, np.uint8)
            pl = np.dstack([r, g, b, al])[0].copy()
            pl[0, 3] = 0                               # 인덱스 0 투명
        return pl
    return None


# ----------------------------------------------------------------- 디코드
def decode_pixels(raw, w, h, bpp, pal):
    if bpp == 4:
        a = np.frombuffer(raw, np.uint8)
        o = np.empty(a.size*2, np.uint8)
        o[0::2], o[1::2] = a >> 4, a & 0xF          # 상위 니블이 왼쪽
        idx = o[:w*h]
    elif bpp == 8:
        idx = np.frombuffer(raw, np.uint8)[:w*h]
    elif bpp == 16:
        # **리틀엔디안 ARGB1555** (R 이 상위) — 팔레트(빅엔디안, R 이 하위)와 다르다.
        # 빅엔디안으로 읽으면 계단현상이 생기고, R/B 를 바꾸면 제국화격단 문장이
        # 남색, 「サクラ大戦」 로고가 보라가 되어 틀린다. 드림캐스트 PVR 의
        # 네이티브 ARGB1555 와 같은 배치다.
        # 최상위 비트는 96.6% 가 0 이라 불투명 플래그가 아니다 -> 알파 고정.
        p = np.frombuffer(raw[:w*h*2], dtype='<u2').astype(np.uint32)
        r = (((p >> 10) & 0x1F)*255//31).astype(np.uint8)
        g = (((p >> 5) & 0x1F)*255//31).astype(np.uint8)
        b = ((p & 0x1F)*255//31).astype(np.uint8)
        a = np.full(p.shape, 255, np.uint8)
        px = np.dstack([r, g, b, a])[0]
        if px.shape[0] < w*h:
            px = np.vstack([px, np.zeros((w*h-px.shape[0], 4), np.uint8)])
        return px.reshape(h, w, 4)
    else:
        return None
    if idx.size < w*h:
        idx = np.concatenate([idx, np.zeros(w*h-idx.size, np.uint8)])
    idx = idx.reshape(h, w)
    if pal is None:
        g = (idx.astype(np.uint16)*255//max(1, int(idx.max()))).astype(np.uint8)
        return np.dstack([g, g, g, np.full_like(g, 255)])
    ncol = 16 if bpp == 4 else 256
    p = pal[:ncol]
    if len(p) < ncol:
        p = np.vstack([p, np.zeros((ncol-len(p), 4), np.uint8)])
    return p[np.clip(idx, 0, ncol-1)]

def images(d):
    """[(w, h, fmt, bpp, 압축여부, RGBA), ...]"""
    pal = palette(d)
    out = []
    for off, size, idx, c in chunks(d):
        cnt, ents, db = entries(c)
        if not ents: continue
        for w, h, fmt, q, eo, es in ents:
            if not (w and h and es): continue
            if db + eo + es > len(c): continue
            bpp = BPP[fmt & 0x0F]
            need = w*h*bpp//8
            if need <= 0: continue
            blob = c[db+eo: db+eo+es]
            if fmt >> 4:
                raw, got = lzss(blob, need)
                if got < need*0.9: continue          # 제대로 안 풀림
            else:
                if es < need: continue
                raw = blob[:need]
            a = decode_pixels(raw, w, h, bpp, pal)
            if a is None: continue
            out.append((w, h, fmt, bpp, bool(fmt >> 4), a))
    return out


# ----------------------------------------------------------------- 실행
def survey(table, rd):
    fmts = collections.Counter(); kinds = collections.Counter(); nfile = 0
    ok = collections.Counter(); bad = collections.Counter()
    for p in sorted(table):
        if not p.upper().endswith('.SPR'): continue
        d = rd(p); ch = chunks(d)
        if not ch: continue
        nfile += 1
        for off, size, idx, c in ch:
            cnt, ents, db = entries(c)
            kinds['팔레트' if size == 0x1010 else ('이미지' if ents else '기타')] += 1
            for w, h, fmt, q, eo, es in ents:
                if not (w and h and es): continue
                fmts[fmt] += 1
                bpp = BPP[fmt & 0x0F]; need = w*h*bpp//8
                blob = c[db+eo: db+eo+es]
                if fmt >> 4:
                    _, got = lzss(blob, need)
                    (ok if got >= need else bad)[fmt] += 1
                else:
                    (ok if es >= need else bad)[fmt] += 1
    print(f"SPR 파일 {nfile}개")
    print("청크 종류:", dict(kinds))
    print("서브이미지 fmt 분포 (bpp = 표[fmt & 0xF], 압축 = 상위 니블)")
    for k, v in fmts.most_common():
        print(f"   fmt=0x{k:02X}  {BPP[k & 0x0F]:>2}bpp "
              f"{'압축' if k >> 4 else '날것'}  {v:>6}장   "
              f"성공 {ok[k]:>6} / 실패 {bad[k]}")

def main():
    f = open(SRC_ISO, 'rb'); table = walk_iso(f)
    def rd(p):
        _, lba, sz = table[p]; f.seek(lba*SECTOR); return f.read(sz)
    if '--info' in sys.argv:
        survey(table, rd); return

    os.makedirs(OUT, exist_ok=True)
    made = []
    for p in sorted(table):
        if not p.upper().endswith('.SPR'): continue
        imgs = images(rd(p))
        if not imgs: continue
        stem = os.path.splitext(os.path.basename(p))[0]
        base = os.path.join(OUT, os.path.dirname(p.strip('/')).replace('/', os.sep))
        os.makedirs(base, exist_ok=True)
        for i, (w, h, fmt, bpp, comp, a) in enumerate(imgs):
            dst = os.path.join(base, f"{stem}_{i:04d}.png")
            Image.fromarray(a, 'RGBA').save(dst)
            made.append((dst, p, w, h, fmt, bpp, comp))
    print(f"SPR 이미지 {len(made)}장 -> {OUT}")

    sheets = os.path.join(OUT, "_sheets"); os.makedirs(sheets, exist_ok=True)
    items = sorted(made, key=lambda r: -(r[2]*r[3]))
    PER, CW, CH, cols = 24, 200, 170, 6
    n = 0
    for s in range(0, len(items), PER):
        grp = items[s:s+PER]
        rows = (len(grp)+cols-1)//cols
        sh = Image.new('RGB', (cols*CW, rows*CH), (235, 236, 242))
        dr = ImageDraw.Draw(sh)
        for k, (dst, isop, w, h, fmt, bpp, comp) in enumerate(grp):
            try:
                im = Image.open(dst).convert('RGBA')
                bg = Image.new('RGB', im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[3]); im = bg
            except Exception: continue
            im.thumbnail((CW-8, CH-22), Image.LANCZOS)
            c2, r2 = k % cols, k//cols
            sh.paste(im, (c2*CW+4, r2*CH+16))
            dr.text((c2*CW+2, r2*CH+3),
                    f"{os.path.basename(dst)} {w}x{h}"[:30], fill=(30, 30, 70))
        sh.save(os.path.join(sheets, f"spr_{n:03d}.png")); n += 1
    print(f"컨택트시트 {n}장 -> {sheets}")
    with open(os.path.join(OUT, "index.tsv"), 'w', encoding='utf-8') as fh:
        fh.write("png\tiso_path\twidth\theight\tfmt\tbpp\t압축\n")
        for dst, isop, w, h, fmt, bpp, comp in made:
            fh.write(f"{os.path.relpath(dst, OUT)}\t{isop}\t{w}\t{h}\t"
                     f"0x{fmt:02X}\t{bpp}\t{'예' if comp else '아니오'}\n")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
