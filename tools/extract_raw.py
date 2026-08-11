# -*- coding: utf-8 -*-
"""
PVR 헤더가 없는 .CMP — 폭을 추정해 PNG 로 뽑는다.

  python extract_raw.py            image_png/raw/ 에 추출 + 컨택트시트

.CMP 는 대부분 드림캐스트 PVR 텍스처지만(extract_pvr.py 가 처리),
일부는 헤더 없는 날 인덱스 비트맵이다. 크기가 어디에도 안 적혀 있어
데이터에서 행 간격을 추정한다.

추정 방법 — **바이트 자기일치도**
  정답 폭 W 에서는 세로로 이웃한 픽셀 d[i], d[i+W] 가 같을 확률이 튄다.
  평탄한 배경에 휘둘리지 않도록 배경값(최빈값)이 아닌 위치만 센다.
  주변 폭들의 중앙값 대비 얼마나 튀는지(peak)로 고르고,
  직사각형이어야 하므로 **픽셀 수를 나누는 폭**을 우선한다.

  정답을 아는 TITLP_D1(384x354, 「サクラ大戦」 로고) 로 검증했다.
  앞서 실패한 세 방법(행 차이 최소화 / FFT 자기상관 / 2의 거듭제곱)과 달리
  이 방법은 그 파일에서 384 를 1순위로 집어낸다.

대상 — **팔레트 짝(.CL/.PAL)이 있는 파일만**
  .CMP 확장자는 압축 컨테이너일 뿐이라 안에 이미지가 아닌 것도 많다.
  SK*(사쿠라2 대사), M*VDP1/M*LOW(맵 데이터), FNT4B(폰트) 등을 비트맵으로
  그리면 노이즈만 나온다. 인덱스 이미지는 반드시 같은 이름의 팔레트가
  있으므로 그것을 기준으로 걸러낸다.

주의 — 맞지 않는 경우
  TITLP_D2 처럼 **폭이 다른 이미지 여러 장이 헤더 없이 이어 붙은** 파일이 있다.
  이런 파일은 어떤 단일 폭으로도 전체가 맞지 않는다(일부 구간만 읽힌다).
  확정된 폭은 WIDTHS 에 적어 두고 그 값을 우선 쓴다.
"""
import os, sys, io
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_iso import walk_iso, SRC_ISO, SECTOR
from cmp import decompress
from pvr import load_palette, walk as pvr_walk

OUT = r"D:\psp\사쿠라대전1_2\image_png\raw"

# 눈으로 확인해 확정한 폭 (픽셀 단위)
WIDTHS = {
    'TITLP_D1':   384,     # 「サクラ大戦」 로고 — 아래쪽은 다른 이미지
    'OB_D1':      544,     # 주제가 가사 자막
    'OB_D2':      544,
    'OB_D3':      544,
    'PBOOK_FL80': 128,     # 캐릭터 얼굴 세로 나열
    'PBOOK_FL81': 496,     # 「サクラ大戦 クリア記録」
    'PBOOK_FL82': 496,
    'PBOOK_FL83': 496,
    'PBOOK_FL701': 160,    # 세이브 아이콘
    'PBOOK_FL702': 160,
    'PBOOK_FL703': 160,
}

def best_stride(a, lo=32, hi=1300):
    """바이트 자기일치도로 행 간격 추정 -> (간격, 튐 정도)"""
    if a.size < 4000: return None, 0.0
    bg = np.bincount(a).argmax()
    live = a != bg
    if live.sum() < 1000: return None, 0.0
    Ls, sc = [], []
    for L in range(lo, min(hi, a.size//4)+1):
        m = live[:-L]
        if m.sum() < 500: break
        Ls.append(L); sc.append(float((a[:-L][m] == a[L:][m]).mean()))
    if not Ls: return None, 0.0
    arr = np.array(sc); Ls = np.array(Ls)
    base = np.array([np.median(arr[max(0, i-40):i+41]) for i in range(len(arr))])
    peak = arr - base
    n = a.size
    div = [(int(Ls[i]), float(peak[i])) for i in np.argsort(-peak)[:150]
           if n % int(Ls[i]) == 0]
    if div: return div[0]
    i = int(np.argmax(peak))
    return int(Ls[i]), float(peak[i])

def main():
    os.makedirs(OUT, exist_ok=True)
    f = open(SRC_ISO, 'rb'); table = walk_iso(f)
    def rd(p):
        _, lba, sz = table[p]; f.seek(lba*SECTOR); return f.read(sz)
    palp = {}
    for p in table:
        if p.upper().endswith(('.CL', '.PAL')):
            palp.setdefault(os.path.splitext(os.path.basename(p))[0].upper(), p)

    made, skipped = [], []
    for p in sorted(table):
        if not p.upper().endswith('.CMP'): continue
        stem = os.path.splitext(os.path.basename(p))[0]
        pb = palp.get(stem.upper())
        if not pb: continue                     # 팔레트가 없으면 이미지가 아니다
        try: d = decompress(rd(p))[0]
        except Exception: continue
        if pvr_walk(d): continue                # PVR 은 extract_pvr.py 담당

        pal = load_palette(rd(pb))
        bpp = 8 if (pal is not None and len(pal) > 16) else 4
        a = np.frombuffer(d, np.uint8)
        if bpp == 4:
            px = np.empty(a.size*2, np.uint8); px[0::2], px[1::2] = a & 0xF, a >> 4
        else:
            px = a

        if stem in WIDTHS:
            w, conf, how = WIDTHS[stem], 1.0, '확정'
        else:
            s, conf = best_stride(a)
            if not s: skipped.append((p, len(d), '추정실패')); continue
            w, how = (s*2 if bpp == 4 else s), '추정'
        h = px.size//w
        if not (16 <= w <= 2048 and 8 <= h <= 2048):
            skipped.append((p, len(d), f'크기이상 {w}x{h}')); continue

        im2 = px[:w*h].reshape(h, w)
        if pal is not None:
            rgba = pal[np.clip(im2, 0, len(pal)-1)]
        else:
            g = (im2.astype(np.float32)/max(1, int(im2.max()))*255).astype(np.uint8)
            rgba = np.dstack([g, g, g, np.full_like(g, 255)])
        rel = os.path.dirname(p.strip('/')).replace('/', os.sep)
        base = os.path.join(OUT, rel); os.makedirs(base, exist_ok=True)
        dst = os.path.join(base, stem + '.png')
        Image.fromarray(rgba, 'RGBA').save(dst)
        made.append((dst, p, w, h, how, conf))

    print(f"날 비트맵 {len(made)}장 추출 (건너뜀 {len(skipped)}개)")
    conf_n = sum(1 for r in made if r[4] == '확정')
    print(f"  확정 폭 {conf_n}장, 추정 폭 {len(made)-conf_n}장")

    sheets = os.path.join(OUT, "_sheets"); os.makedirs(sheets, exist_ok=True)
    items = sorted(made, key=lambda r: -(r[2]*r[3]))
    PER, CW, CH, cols = 24, 240, 150, 4
    n = 0
    for s in range(0, len(items), PER):
        grp = items[s:s+PER]
        rows = (len(grp)+cols-1)//cols
        sheet = Image.new('RGB', (cols*(CW+8), rows*(CH+22)), (235, 236, 242))
        dr = ImageDraw.Draw(sheet)
        for k, (dst, isop, w, h, how, conf) in enumerate(grp):
            try:
                im = Image.open(dst).convert('RGBA')
                bg = Image.new('RGB', im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[3]); im = bg
            except Exception: continue
            im.thumbnail((CW, CH), Image.LANCZOS)
            c, r = k % cols, k//cols
            x, y = c*(CW+8)+4, r*(CH+22)+18
            sheet.paste(im, (x + (CW-im.width)//2, y + (CH-im.height)//2))
            dr.text((x, r*(CH+22)+4), f"{os.path.basename(dst)} {w}x{h} {how}"[:44],
                    fill=(30, 30, 70))
        sheet.save(os.path.join(sheets, f"raw_{n:03d}.png")); n += 1
    print(f"컨택트시트 {n}장 -> {sheets}")

    with open(os.path.join(OUT, "index.tsv"), 'w', encoding='utf-8') as fh:
        fh.write("png\tiso_path\twidth\theight\t폭출처\t튐정도\n")
        for dst, isop, w, h, how, conf in made:
            fh.write(f"{os.path.relpath(dst, OUT)}\t{isop}\t{w}\t{h}\t{how}\t{conf:.3f}\n")
    print(f"목록 -> {os.path.join(OUT, 'index.tsv')}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
