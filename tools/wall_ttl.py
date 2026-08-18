# -*- coding: utf-8 -*-
"""사쿠라2 화 제목 카드(WALL/TTL001~013.GIM) 13장을 한글로 바꾼다.

  python tools/wall_ttl.py --png [이름...]   미리보기만
  python tools/wall_ttl.py                   build/patched/WALL 에 저장

480x256 INDEX8 스위즐 GIM. 사진 배경 위에 흰 속 + 어두운 테두리 글자가
계단식으로 놓여 있다. SK2_ADV.BIN 이 TTL001~012 를 이름으로 읽는다
(TTL013 은 이름 문자열이 없지만 같은 형식이라 같이 바꾼다).

**줄 상자는 격자를 씌워 눈으로 잰 값이다.** 자동 검출은 두 번 실패했다 —
이 카드들은 배경에 눈송이·꽃잎·불꽃 같은 날카롭고 밝은 알갱이가 많아
밝기·중앙값 방식 모두 배경을 글자로 잘못 잡는다. 상자 안에서만 마스크를
잡으면 잘못 잡아도 피해가 상자 안이라 티가 안 난다.

오른쪽 아래의 벚꽃 문양 장식은 상자 밖이라 자동으로 보존된다.
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import place_gim as PG
from build_iso import walk_iso, SRC_ISO, SECTOR

FONT  = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched", "WALL")

# 이름 -> [(상자, 한글)]  상자 = (x0,y0,x1,y1) — 원문 줄 자리를 격자로 잰 값
JOBS = {
 'TTL001': [((44, 68, 212, 112), "제1화"),   ((92, 116, 420, 168), "꽃 피는 제도")],
 'TTL002': [((52, 76, 218, 122), "제2화"),   ((92, 126, 445, 182), "아이리스의 편지")],
 'TTL003': [((44, 72, 204, 116), "제3화"),   ((92, 124, 445, 174), "아아, 맞선")],
 'TTL004': [((44, 58, 214, 104), "제4화"),   ((76, 108, 452, 162), "대소동! 불덩이"),
            ((116, 162, 445, 212), "게이샤 걸즈")],
 'TTL005': [((44, 56, 204, 104), "제5화"),   ((92, 108, 390, 159), "설레고 부끄러운"),
            ((196, 156, 424, 209), "여름 방학")],
 'TTL006': [((44, 74, 214, 122), "제6화"),   ((92, 126, 462, 182), "레니여, 총을 들라")],
 'TTL007': [((44, 68, 212, 116), "제7화"),   ((52, 121, 448, 176), "철 지난 칠석")],
 'TTL008': [((52, 68, 218, 116), "제8화"),   ((20, 121, 462, 179), "제도의 가장 긴 하루!?")],
 'TTL009': [((36, 54, 204, 104), "제9화"),   ((80, 106, 274, 159), "극장의"),
            ((46, 156, 454, 214), "메리 크리스마스")],
 'TTL010': [((36, 48, 212, 96), "제10화"),   ((92, 100, 304, 152), "거리에 눈이"),
            ((176, 148, 444, 204), "내리듯이")],
 'TTL011': [((36, 68, 260, 119), "제11화"),  ((60, 118, 445, 174), "지상 최대의 작전")],
 'TTL012': [((36, 71, 209, 122), "최종회"),  ((81, 121, 454, 182), "소녀들의 만가")],
 'TTL013': [((36, 44, 260, 96), "제13화"),   ((92, 96, 354, 152), "그대 위해"),
            ((146, 146, 394, 204), "기적은 울린다")],
}

def load(nm):
    f = open(SRC_ISO, 'rb'); t = walk_iso(f)
    p = [x for x in t if os.path.basename(x) == nm + '.GIM'][0]
    _, lba, sz = t[p]; f.seek(lba*SECTOR); d = bytearray(f.read(sz)); f.close()
    return d, sz

def glyph_mask(rgb, boxes):
    """상자 안의 날카로운 획(글자·테두리·그림자)만 잡는다."""
    g = Image.fromarray(rgb).convert('L')
    med = np.asarray(g.filter(ImageFilter.MedianFilter(9))).astype(int)
    d = np.abs(np.asarray(g).astype(int) - med)
    sharp = np.asarray(Image.fromarray((d > 16).astype(np.uint8)*255)
                       .filter(ImageFilter.MaxFilter(7))) > 0
    m = np.zeros(rgb.shape[:2], bool)
    H, W = m.shape
    glyph_mask.sharp = sharp        # 거울 복사에서 원문 조각을 피할 때 쓴다
    for (x0, y0, x1, y1), _ in boxes:
        # 그림자·테두리가 상자 밖으로 몇 픽셀 삐져나온다 — 8px 여유를 준다
        m[max(0,y0-8):min(H,y1+8), max(0,x0-8):min(W,x1+8)] =             sharp[max(0,y0-8):min(H,y1+8), max(0,x0-8):min(W,x1+8)]
    return m

def inpaint(rgb, mask, rounds=120):
    img = rgb.astype(np.float32).copy(); img[mask] = np.nan
    for _ in range(rounds):
        p4 = np.stack([np.roll(img,1,0), np.roll(img,-1,0), np.roll(img,1,1), np.roll(img,-1,1)])
        with np.errstate(invalid='ignore'):
            mean = np.nanmean(p4, axis=0)
        fill = np.isnan(img) & ~np.isnan(mean)
        if not fill.any(): break
        img[fill] = mean[fill]
    return np.clip(np.nan_to_num(img, nan=128), 0, 255).astype(np.uint8)

def edge_color(rgb, mask):
    px = rgb[mask].astype(np.float32)
    if not len(px): return np.array([30., 30., 80.])
    lum = px.sum(1)
    return px[lum <= np.percentile(lum, 15)].mean(0)

def draw_text(rgb, box, text, edge):
    x0, y0, x1, y1 = box
    w, h = x1-x0, y1-y0
    S = 4
    size = h - 2
    while size > 8:
        f = ImageFont.truetype(FONT, size)
        b = f.getbbox(text)
        if b[2]-b[0] <= w-6 and b[3]-b[1] <= h-4: break
        size -= 1
    f4 = ImageFont.truetype(FONT, size*S)
    m = Image.new('L', (w*S, h*S), 0); dr = ImageDraw.Draw(m)
    b = dr.textbbox((0,0), text, font=f4)
    dr.text((2*S - b[0], h*S//2 - (b[3]+b[1])//2), text, font=f4, fill=255)
    a = np.asarray(m.resize((w, h), Image.LANCZOS)).astype(np.float32)/255
    ring = np.asarray(Image.fromarray((a*255).astype('uint8'))
                      .filter(ImageFilter.MaxFilter(5))).astype(np.float32)/255
    reg = rgb[y0:y1, x0:x1].astype(np.float32)
    reg = reg*(1-ring[...,None]) + edge[None,None,:]*ring[...,None]
    reg = reg*(1-a[...,None]) + np.array([250.,250.,250.])[None,None,:]*a[...,None]
    rgb[y0:y1, x0:x1] = np.clip(reg, 0, 255).astype(np.uint8)
    return size

def run(make_png=False, only=None):
    os.makedirs(BUILD, exist_ok=True)
    prev = []
    for nm, jobs in JOBS.items():
        if only and nm not in only: continue
        d, sz = load(nm)
        (po, w, h, order), palo = PG.gim_image(bytes(d))
        pitch = (w+15)//16*16; hh = (h+7)//8*8
        buf = np.frombuffer(bytes(d[po:po+pitch*hh]), np.uint8)
        img = (PG.unswz(buf, pitch, hh) if order else buf.reshape(hh, pitch)).copy()
        pal = np.frombuffer(bytes(d[palo:palo+1024]), np.uint8).reshape(256, 4)
        rgb = pal[img[:h, :w]][:, :, :3].astype(np.uint8).copy()
        before = rgb.copy()
        mask = glyph_mask(rgb, jobs)
        edge = edge_color(rgb, mask)
        # 확산은 넓은 자리에서 밋밋한 얼룩을 만든다 (사진의 디더·줄무늬 질감이
        # 사라져 회색 헝겊을 댄 것처럼 보였다). 대신 **상자 위쪽을 거울로 복사**해
        # 질감을 그대로 가져오고, 확산은 거울이 못 닿는 자리의 보험으로만 쓴다.
        base = inpaint(rgb, mask)
        rgb2 = base.copy()
        H, W = rgb.shape[:2]
        # 상자 띠를 **아래쪽 띠의 핑퐁 타일**로 통째 덮는다.
        #   - 마스크만 채우면 흐릿한 원문 가장자리가 남는다 (1차 시도)
        #   - 확산은 넓은 자리에 밋밋한 얼룩을 만든다 (2차 시도)
        #   - 거울 복사는 원천에 원문이 겹치면 막히고, 막힌 자리가 얼룩진다 (3차)
        # 아랫줄부터 채우면 원천(바로 아래 띠)이 항상 깨끗하다 — 마지막 줄의
        # 아래는 원본 그대로고, 그 윗줄의 아래는 방금 채운 띠다.
        # 첫 줄(제N화)은 위 하늘에서, 나머지는 아래에서 가져온다. 아래 사슬을
        # 끝까지 쓰면 밑바닥 질감(편지지 따위)이 두 띠를 타고 올라와 엉뚱한
        # 자리에 나타난다 — 첫 줄만이라도 위에서 끊어 주면 눈에 안 띈다.
        srt = sorted(jobs, key=lambda j: j[0][1])
        for (box, ko) in srt[:0:-1] + [srt[0]]:
            first = (box, ko) == srt[0]
            x0, y0, x1, y1 = box
            yt = max(0, y0-12); yb = min(H, y1+8)
            xl = max(0, x0-4); xr = min(W, x1+4)
            if first and yt >= 6:                # 첫 줄: 위 띠에서 핑퐁
                sh = min(24, yt)
                for y in range(yt, yb):
                    k = (y-yt) % (2*sh)
                    ysrc = yt-1 - (k if k < sh else 2*sh-1-k)
                    rgb2[y, xl:xr] = rgb2[ysrc, xl:xr]
            else:                                # 나머지: 아래 띠에서 핑퐁
                sh = min(24, H - yb)
                for y in range(yt, yb):
                    k = (yb-1-y) % (2*sh)
                    ysrc = yb + (k if k < sh else 2*sh-1-k)
                    rgb2[y, xl:xr] = rgb2[ysrc, xl:xr]
        rgb = rgb2
        for box, ko in jobs:
            draw_text(rgb, box, ko, edge)
        print(f"  {nm}: {' / '.join(k for _, k in jobs)}")
        if make_png:
            prev.append((nm, Image.fromarray(before), Image.fromarray(rgb))); continue
        P = pal[:, :3].astype(np.int32)
        changed = (rgb != before).any(2)
        flat = rgb[changed].astype(np.int32)
        if flat.size:
            dif = ((flat[:, None, :] - P[None, :, :])**2).sum(2)
            img[:h, :w][changed] = dif.argmin(1).astype(np.uint8)
        d[po:po+pitch*hh] = (PG.swz(img) if order else img.reshape(-1)).tobytes()
        assert len(d) == sz
        q = os.path.join(BUILD, nm + '.GIM'); open(q, 'wb').write(bytes(d))
    if make_png and prev:
        sh = Image.new('RGB', (2*486, len(prev)*262), (30,30,30))
        for k,(nm,a,b) in enumerate(prev):
            sh.paste(a, (0, k*262)); sh.paste(b, (486, k*262))
        q = os.path.join(ROOT, 'test_render', '_wall_ko.png'); sh.save(q); print('  ->', q)

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    only = [a for a in sys.argv[1:] if not a.startswith('--')] or None
    run('--png' in sys.argv, only)
