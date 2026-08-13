# -*- coding: utf-8 -*-
"""세이브 목록 아이콘(ICON0.PNG) 30장의 일본어를 한글로 바꾼다.

  python tools/save_icons.py --png   미리보기만
  python tools/save_icons.py         build/patched 에 PNG 저장

PSP 세이브 데이터 목록에 뜨는 144x80 그림이다. 게임 안 불러오기/저장 화면과
XMB 세이브 관리 양쪽에 나오므로 눈에 자주 띈다.

  SAKURA1/INFO/SK1_01~10.PNG   第一話 ~ 第十話
  SAKURA1/INFO/SK1_BATTLE.PNG  戦闘中断
  SAKURA1/INFO/SK1_SYS.PNG     システムファイル
  SAKURA1/INFO/SK_NEW.PNG      新規セーブ / ファイル作成
  SAKURA2/INFO/SK2_01~13.PNG   第一話 ~ 第十三話
  SAKURA2/INFO/SK2_BATTLE.PNG  戦闘中断
  SAKURA2/INFO/SK2_SYS.PNG     システムファイル
  SAKURA2/INFO/SK_NEW.PNG      新規セーブ / ファイル作成

SK_NEW 는 두 폴더에 같은 이름으로 들어 있고 내용이 다르다. build_iso 가
이름으로 짝지으므로 폴더별로 따로 넣어야 한다 (BY_PATH).

글자는 **검은 속 + 흰 테두리**다. 배경이 그림이라 상자를 통째로 지우면 안 되고
글자 획만 골라 지운다. 고르는 법:

    흰 테두리 = min(R,G,B) > 200
    검은 속   = max(R,G,B) < 80
    글자      = (검은데 곁에 흰 것이 있다) 또는 (흰데 곁에 검은 것이 있다)

캐릭터 그림의 검은 윤곽선은 곁에 흰 것이 없어서 걸러진다. 밝은 살색·옷은
min 이 200 을 못 넘어서 걸러진다. 그래도 머리카락 몇 점이 걸리므로
**문구가 있는 상자 안으로만** 제한한다.

지운 자리는 확산으로 메운다 (event_gim.py 와 같은 방식).
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from build_iso import walk_iso, SRC_ISO, SECTOR

FONT  = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched")

# 이름 -> (상자, 줄들)   상자 = (x0, y0, x1, y1)
JOBS = {}
for i in range(1, 11):
    JOBS[f"SK1_{i:02d}"] = ((4, 1, 96, 32), [f"제{i}화"])
for i in range(1, 14):
    JOBS[f"SK2_{i:02d}"] = ((64, 1, 144, 32), [f"제{i}화"])
JOBS["SK1_BATTLE"] = ((2, 1, 94, 32), ["전투 중단"])
JOBS["SK2_BATTLE"] = ((50, 1, 144, 32), ["전투 중단"])
JOBS["SK1_SYS"]    = ((3, 6, 144, 32), ["시스템 파일"])
JOBS["SK2_SYS"]    = ((3, 4, 144, 32), ["시스템 파일"])
JOBS["SK_NEW"]     = ((18, 1, 130, 50), ["새 저장 파일", "만들기"])

def text_mask(rgb, box):
    x0, y0, x1, y1 = box
    V = rgb.max(2); mn = rgb.min(2)
    white = (mn > 200); dark = (V < 80)
    dil = lambda m: np.asarray(Image.fromarray((m*255).astype('uint8'))
                               .filter(ImageFilter.MaxFilter(7))) > 0
    m = (dark & dil(white)) | (white & dil(dark))
    keep = np.zeros_like(m); keep[y0:y1, x0:x1] = True
    m &= keep
    return np.asarray(Image.fromarray((m*255).astype('uint8'))
                      .filter(ImageFilter.MaxFilter(5))) > 0

def inpaint(rgb, mask, rounds=140):
    img = rgb.astype(np.float32).copy()
    img[mask] = np.nan
    for _ in range(rounds):
        p4 = np.stack([np.roll(img, 1, 0), np.roll(img, -1, 0),
                       np.roll(img, 1, 1), np.roll(img, -1, 1)])
        with np.errstate(invalid='ignore'):
            mean = np.nanmean(p4, axis=0)
        fill = np.isnan(img) & ~np.isnan(mean)
        if not fill.any(): break
        img[fill] = mean[fill]
    img = np.nan_to_num(img, nan=float(np.nanmean(img)))
    return np.clip(img, 0, 255).astype(np.uint8)

def draw_lines(rgb, box, lines):
    """검은 속 + 흰 테두리로 그린다. 4배로 그려 줄여 계단을 없앤다."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    lh = h / len(lines)
    S = 4
    size = int(lh) + 6
    while size > 6:
        f = ImageFont.truetype(FONT, size)
        if all(f.getbbox(t)[2] - f.getbbox(t)[0] <= w - 4 for t in lines) and \
           max(f.getbbox(t)[3] - f.getbbox(t)[1] for t in lines) <= lh - 3: break
        size -= 1
    f4 = ImageFont.truetype(FONT, size*S)
    m = Image.new('L', (w*S, h*S), 0); dr = ImageDraw.Draw(m)
    for k, t in enumerate(lines):
        b = dr.textbbox((0, 0), t, font=f4)
        dr.text((w*S//2 - (b[2]+b[0])//2,
                 int((k + 0.5)*lh*S - (b[3]+b[1])/2)), t, font=f4, fill=255)
    a = np.asarray(m.resize((w, h), Image.LANCZOS)).astype(np.float32)/255
    core = Image.fromarray((a*255).astype('uint8'))
    ring = np.asarray(core.filter(ImageFilter.MaxFilter(5))).astype(np.float32)/255
    out = rgb.astype(np.float32).copy()
    reg = out[y0:y1, x0:x1]
    reg[:] = reg*(1-ring[..., None]) + np.array([255., 255., 255.])*ring[..., None]
    reg[:] = reg*(1-a[..., None]) + np.array([16., 16., 16.])*a[..., None]
    return np.clip(out, 0, 255).astype(np.uint8), size

def run(make_png=False):
    f = open(SRC_ISO, 'rb'); table = walk_iso(f)
    paths = sorted(p for p in table if '/INFO/' in p.upper() and p.upper().endswith('.PNG'))
    prev = []
    os.makedirs(BUILD, exist_ok=True)
    for p in paths:
        name = os.path.basename(p)[:-4]
        if name not in JOBS: continue
        _, lba, sz = table[p]; f.seek(lba*SECTOR); raw = f.read(sz)
        im = Image.open(__import__('io').BytesIO(raw)).convert('RGB')
        rgb = np.asarray(im).copy()
        box, lines = JOBS[name]
        m = text_mask(rgb, box)
        clean = inpaint(rgb, m)
        out, size = draw_lines(clean, box, lines)
        who = 'SAKURA1' if '/SAKURA1/' in p else 'SAKURA2'
        print(f"  {who}/{name:<11} {box} -> {' / '.join(lines)}  ({size}px, 지운 화소 {int(m.sum())})")
        if make_png:
            prev.append((f"{who[-1]}_{name}", im, Image.fromarray(out)))
            continue
        # 원본과 같은 자리에 들어가야 하므로 크기를 확인한다.
        # **트루컬러로 다시 저장하면 안 들어간다.** 원본은 훨씬 좋은 인코더로
        # 눌러 놓은 트루컬러 PNG 라, PIL 로 다시 저장하면 2배가 되는 것도 있다
        # (SK1_SYS 8,052 -> 16,747 / 배정 8,192). 256색 팔레트로 저장하면
        # 7~9KB 로 떨어져 모두 넉넉히 들어간다. 144x80 셀화라 색이 남는다.
        import io as _io
        b = _io.BytesIO()
        Image.fromarray(out).quantize(colors=256, dither=Image.FLOYDSTEINBERG)              .save(b, 'PNG', optimize=True, compress_level=9)
        best = b.getvalue()
        alloc = (sz + SECTOR - 1)//SECTOR*SECTOR
        if len(best) > alloc:
            raise RuntimeError(f"{name}: {len(best)} > 배정 {alloc}")
        d = os.path.join(BUILD, who); os.makedirs(d, exist_ok=True)
        open(os.path.join(d, name + '.PNG'), 'wb').write(best)
        print(f"      {sz:,} -> {len(best):,}B / 배정 {alloc:,}")
    f.close()
    if make_png and prev:
        W, H, cols = 144, 80, 4
        rows = (len(prev)*2 + cols - 1)//cols
        sh = Image.new('RGB', (cols*(W*2+6), rows*(H*2+6)), (40, 40, 40))
        k = 0
        for n, a, b in prev:
            for im in (a, b):
                sh.paste(im.resize((W*2, H*2), Image.NEAREST),
                         ((k % cols)*(W*2+6), (k//cols)*(H*2+6))); k += 1
        q = os.path.join(ROOT, "test_render", "_saveicons.png"); sh.save(q)
        print(f"      -> {q}")

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    run('--png' in sys.argv)
