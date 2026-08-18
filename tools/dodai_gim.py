# -*- coding: utf-8 -*-
"""전투 연습(戦闘演習) 성적 화면 3장을 한글로 바꾼다.

  python tools/dodai_gim.py --png   미리보기만
  python tools/dodai_gim.py         build/patched/SAKURA2 에 저장

SAKURA2/SAKURA2/ 의 318x256 INDEX8 스위즐 GIM.

  E_DODAI1  帝国華撃団・花組 戦闘演習 / 初級演習 開始 / 壱位 弐位 参位 / 点x3
  E_DODAI2  初級演習・戦闘成績 / 生存数 撃破数 打撃総合 損害総合 味方行動数 / 合計点数
  H_DODAI   項目

금속판에 새긴 글자라 배경이 가로 줄무늬 질감이다. 채움은 **행마다 좌우
이웃을 선형 보간**한다 — 가로 질감에는 이게 확산보다 훨씬 자연스럽다.
글자 마스크는 상자 안에서 행 중앙값과 밝기가 크게 다른 픽셀.
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
BUILD = os.path.join(ROOT, "build", "patched", "SAKURA2")

# (상자, 한글, 잉크)  잉크 'dark'=금속에 새김, 'light'=검은 판에 흰 글자
JOBS = {
 'E_DODAI1': [
   ((46, 25, 284, 48),  "제국화격단·화조 전투 연습", 'dark'),
   ((112, 56, 253, 77), "초급 연습 시작", 'dark'),
   ((106, 87, 149, 107), "1위", 'dark'),
   ((106, 116, 149, 136), "2위", 'dark'),
   ((106, 144, 149, 164), "3위", 'dark'),
   ((196, 90, 216, 104), "점", 'light'),
   ((196, 118, 216, 132), "점", 'light'),
   ((196, 146, 216, 160), "점", 'light'),
 ],
 'E_DODAI2': [
   ((72, 24, 288, 45),  "초급 연습·전투 성적", 'dark'),
   ((18, 54, 66, 69),   "생존 수", 'light'),
   ((18, 70, 66, 85),   "격파 수", 'light'),
   ((15, 87, 74, 101),  "타격 총합", 'light'),
   ((15, 103, 74, 117), "피해 총합", 'light'),
   ((12, 120, 77, 134), "아군 행동 수", 'light'),
   ((12, 144, 78, 160), "합계 점수", 'light'),
 ],
 'H_DODAI': [
   ((36, 24, 132, 53),  "항목", 'dark'),
 ],
}

def glyph_mask(rgb, box):
    x0, y0, x1, y1 = box
    reg = rgb[y0:y1, x0:x1].astype(int)
    lum = reg.sum(2)
    med = np.median(lum, axis=1, keepdims=True)
    m = np.abs(lum - med) > 90
    m = np.asarray(Image.fromarray((m*255).astype('uint8')).filter(ImageFilter.MaxFilter(3))) > 0
    return m

def scanline_fill(rgb, box, m):
    x0, y0, x1, y1 = box
    reg = rgb[y0:y1, x0:x1].astype(np.float32)
    w = x1 - x0
    for r in range(reg.shape[0]):
        row = m[r]
        if not row.any(): continue
        xs = np.nonzero(~row)[0]
        if not len(xs):                          # 온 행이 글자면 위 행을 복사
            reg[r] = reg[r-1] if r else reg[r+1]
            continue
        for c in range(3):
            reg[r, :, c] = np.interp(np.arange(w), xs, reg[r, xs, c])
    rgb[y0:y1, x0:x1] = np.clip(reg, 0, 255).astype(np.uint8)

def ink_colors(rgb, box, m, style):
    reg = rgb[box[1]:box[3], box[0]:box[2]].astype(np.float32)
    px = reg[m]
    if not len(px): px = reg.reshape(-1, 3)
    lum = px.sum(1)
    if style == 'light':
        return px[lum >= np.percentile(lum, 75)].mean(0)
    return px[lum <= np.percentile(lum, 25)].mean(0)

def draw(rgb, box, text, ink):
    x0, y0, x1, y1 = box
    w, h = x1-x0, y1-y0
    S = 4
    size = h - 2
    while size > 6:
        f = ImageFont.truetype(FONT, size)
        b = f.getbbox(text)
        if b[2]-b[0] <= w-4 and b[3]-b[1] <= h-2: break
        size -= 1
    f4 = ImageFont.truetype(FONT, size*S)
    mk = Image.new('L', (w*S, h*S), 0); dr = ImageDraw.Draw(mk)
    b = dr.textbbox((0,0), text, font=f4)
    dr.text((w*S//2-(b[2]+b[0])//2, h*S//2-(b[3]+b[1])//2), text, font=f4, fill=255)
    a = np.asarray(mk.resize((w, h), Image.LANCZOS)).astype(np.float32)/255
    reg = rgb[y0:y1, x0:x1].astype(np.float32)
    reg = reg*(1-a[...,None]) + ink[None,None,:]*a[...,None]
    rgb[y0:y1, x0:x1] = np.clip(reg, 0, 255).astype(np.uint8)
    return size

def run(make_png=False):
    os.makedirs(BUILD, exist_ok=True)
    f = open(SRC_ISO, 'rb'); t = walk_iso(f)
    prev = []
    for nm, jobs in JOBS.items():
        p = [x for x in t if os.path.basename(x) == nm + '.GIM' and '/SAKURA2/SAKURA2/' in x][0]
        _, lba, sz = t[p]; f.seek(lba*SECTOR); d = bytearray(f.read(sz))
        (po, w, h, order), palo = PG.gim_image(bytes(d))
        pitch = (w+15)//16*16; hh = (h+7)//8*8
        buf = np.frombuffer(bytes(d[po:po+pitch*hh]), np.uint8)
        img = (PG.unswz(buf, pitch, hh) if order else buf.reshape(hh, pitch)).copy()
        pal = np.frombuffer(bytes(d[palo:palo+1024]), np.uint8).reshape(256, 4)
        rgb = pal[img[:h, :w]][:, :, :3].astype(np.uint8).copy()
        before = rgb.copy()
        for box, ko, style in jobs:
            m = glyph_mask(rgb, box)
            ink = ink_colors(rgb, box, m, style)
            if style == 'light':
                # 검은 판의 흰 글자 — 글자가 판 폭을 거의 다 차지해서 좌우 보간을
                # 쓰면 판 테두리의 밝은 금속색이 안으로 번진다 (피해 총합 행이
                # 하얗게 떴다). 판 색은 평평하니 어두운 중앙값으로 통째 채운다.
                x0, y0, x1, y1 = box
                reg = rgb[y0:y1, x0:x1]
                lum = reg.astype(int).sum(2)
                good = (~m) & (lum <= np.median(lum))
                plate = np.median(reg[good].reshape(-1, 3), axis=0) if good.any() else np.array([40, 10, 10])
                reg[m] = plate.astype(np.uint8)
                ink = np.array([235., 235., 235.])
            else:
                scanline_fill(rgb, box, m)
            size = draw(rgb, box, ko, ink)
        print(f"  {nm}: {' / '.join(k for _, k, _2 in jobs)}")
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
    f.close()
    if make_png and prev:
        sh = Image.new('RGB', (2*324, len(prev)*262), (30,30,30))
        for k,(nm,a,b) in enumerate(prev):
            sh.paste(a, (0, k*262)); sh.paste(b, (324, k*262))
        q = os.path.join(ROOT, 'test_render', '_dodai_ko.png')
        sh.resize((sh.width*2, sh.height*2), Image.NEAREST).save(q); print('  ->', q)

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    run('--png' in sys.argv)
