# -*- coding: utf-8 -*-
"""사쿠라대전 1 의 화 제목 카드 10 장을 한글로 바꾼다.

  python tools/ep_title.py --png    미리보기만
  python tools/ep_title.py          build/patched 에 ADVMISC.PFS 저장

ADVMISC.PFS 안의 title1.spr ~ title10.spr, 480x256 **8bpp 인덱스 + 256색
팔레트**다 (청크 idx=1 이 팔레트, idx=2 가 압축된 그림).
동영상이 아니라 그림이라 고칠 수 있다. (사쿠라2 의 화 제목은 PMF 동영상이다.)

어려운 점은 글자가 **배경 그림 위에 직접 얹혀** 있다는 것이다. PLACE 패널처럼
좌우에서 배경을 떠 올 수가 없다. 대신 배경이 원래 **초점이 나간 흐린 그림**
이라는 점을 이용한다.

  1) 글자 찾기 — 배경은 흐리고 글자는 윤곽이 날카롭다. 중앙값 필터를 씌운
     것과의 차이가 큰 자리가 글자다.
  2) 배경 복원 — 글자 자리를 지우고 둘레 값을 스며들게 한다(확산). 원래
     배경이 흐리므로 이렇게 메워도 티가 안 난다.
  3) 한글 그리기 — 원본 글자에서 속색과 테두리색을 그대로 뽑아 쓴다.
     카드마다 분홍/흰색으로 다르다.
  ※ 아직 완성이 아니다. 배경 복원은 잘 되지만 원본 글자의 **어두운 테두리가
     얼룩으로 남는다**. 문턱을 12 로 낮추고 9 로 부풀려도 봤는데, 그러면
     배경까지 뭉개지고 속색·테두리색 표본이 테두리 쪽으로 쏠려 글자가
     배경에 묻힌다. 밝기·채도로 글자 속을 먼저 찾고 거기서 조금만 부풀리는
     방식으로 다시 짜야 한다.

  4) 되돌리기 — 팔레트를 늘릴 수 없으므로 원래 256색 중 가장 가까운 색으로
     찍는다. 배경이 흐린 그림이라 색이 촘촘해서 티가 크게 안 난다.
"""
import os, sys, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import spr, spr_write, pfs
from build_iso import walk_iso, SRC_ISO, SECTOR

FONT  = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched")
NAME  = "ADVMISC.PFS"

# 원문과 번역. 두 줄이며 첫 줄은 화 번호다.
KO = {
    'title1':  ["제1화",  "제도・꽃의 화격단"],
    'title2':  ["제2화",  "적의 이름은 흑지소회"],
    'title3':  ["제3화",  "나는 대장 실격!?"],
    'title4':  ["제4화",  "폭주! 폭주! 대폭주!"],
    'title5':  ["제5화",  "꽃으로 피워라!", "소녀의 오기로!"],
    'title6':  ["제6화",  "제도 대붕괴!?"],
    'title7':  ["제7화",  "결전  목숨이 다하도록!"],
    'title8':  ["제8화",  "평화로운 나날은", "데이트야!"],
    'title9':  ["제9화",  "나타난 최종 병기"],
    'title10': ["제10화", "최후의 심판"],
}

def quantize(rgb, pal):
    """RGB -> 원래 팔레트에서 가장 가까운 인덱스. 팔레트는 늘릴 수 없다."""
    P = pal[:, :3].astype(np.int32)
    flat = rgb.reshape(-1, 3).astype(np.int32)
    out = np.empty(len(flat), np.uint8)
    for i in range(0, len(flat), 20000):          # 메모리를 아끼려고 나눠 센다
        c = flat[i:i+20000]
        d = ((c[:, None, :] - P[None, :, :])**2).sum(-1)
        out[i:i+20000] = d.argmin(1)
    return out.reshape(rgb.shape[:2])

def text_mask(rgb):
    """흐린 배경 위의 날카로운 글자를 찾는다."""
    g = Image.fromarray(rgb).convert('L')
    med = g.filter(ImageFilter.MedianFilter(9))
    d = np.abs(np.asarray(g).astype(int) - np.asarray(med).astype(int))
    m = Image.fromarray((d > 26).astype(np.uint8)*255)
    m = m.filter(ImageFilter.MaxFilter(5))          # 테두리까지 넉넉히
    return np.asarray(m) > 0

def inpaint(rgb, mask, rounds=90):
    """글자 자리를 둘레 색으로 메운다. 배경이 흐려서 확산으로 충분하다."""
    img = rgb.astype(np.float32).copy()
    img[mask] = np.nan
    for _ in range(rounds):
        p = np.stack([np.roll(img, 1, 0), np.roll(img, -1, 0),
                      np.roll(img, 1, 1), np.roll(img, -1, 1)])
        with np.errstate(invalid='ignore'):
            mean = np.nanmean(p, axis=0)
        fill = np.isnan(img) & ~np.isnan(mean)
        img[fill] = mean[fill]
        if not np.isnan(img).any(): break
    img[np.isnan(img)] = 0
    return np.clip(img, 0, 255).astype(np.uint8)

def colors(rgb, mask):
    """(속색, 테두리색) — 글자 한가운데와 가장자리에서 뽑는다."""
    m = Image.fromarray(mask.astype(np.uint8)*255)
    core = np.asarray(m.filter(ImageFilter.MinFilter(5))) > 0
    edge = mask & ~core
    def mode(sel):
        v = rgb[sel]
        if not len(v): return np.array([255, 255, 255], np.uint8)
        q = (v // 16).astype(np.int32)
        key = q[:, 0]*256 + q[:, 1]*16 + q[:, 2]
        k = np.bincount(key).argmax()
        return v[key == k].mean(0).astype(np.uint8)
    return mode(core), mode(edge)

def draw(rgb, lines, core, edge):
    im = Image.fromarray(rgb).convert('RGB')
    dr = ImageDraw.Draw(im)
    H = rgb.shape[0]
    n = len(lines)
    size = 34 if n == 2 else 30
    for i, s in enumerate(lines):
        f = ImageFont.truetype(FONT, size if i else size - 4)
        b = dr.textbbox((0, 0), s, font=f)
        w = b[2]-b[0]
        x = 40 + i*26
        y = int(H*0.30) + i*(size + 8) - b[1]
        if x + w > rgb.shape[1] - 12:                  # 넘치면 줄여서 맞춘다
            f = ImageFont.truetype(FONT, max(16, int(size*(rgb.shape[1]-52-x)/w)))
            b = dr.textbbox((0, 0), s, font=f); y = int(H*0.30)+i*(size+8)-b[1]
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                if dx or dy: dr.text((x+dx-b[0], y+dy), s, font=f, fill=tuple(int(v) for v in edge))
        dr.text((x-b[0], y), s, font=f, fill=tuple(int(v) for v in core))
    return np.asarray(im)

def run(make_png=False):
    f = open(SRC_ISO, 'rb'); t = walk_iso(f)
    p = [x for x in t if os.path.basename(x).upper() == NAME][0]
    _, lba, sz = t[p]; f.seek(lba*SECTOR); d = f.read(sz); f.close()

    new = {}
    prev = []
    for name, off, size in pfs.entries(d):
        stem = name[:-4].lower()
        if stem not in KO: continue
        body = d[off:off+size]
        # 첫 청크에 이미지가 없는 파일이 있다 (애니메이션·히트박스 청크가 먼저 온다).
        # 16bpp 항목만 고른다. 같은 파일에 8bpp 부속 이미지가 섞여 있다.
        got = None
        for o2, s2, ix, b in spr.chunks(body):
            cnt, ents, db = spr.entries(b)
            if ents: got = (b, ents[0], db); break
        if got is None: print(f"  {name}: 이미지 없음 — 건너뜀"); continue
        b, e, db = got
        w, h = e[0], e[1]
        pal = spr.palette(body)
        idx = spr_write.unpack_px(b, e, db)
        rgb = pal[idx][:, :, :3]
        m = text_mask(rgb)
        core, edge = colors(rgb, m)
        clean = inpaint(rgb, m)
        out = draw(clean, KO[stem], core, edge)
        new[name] = quantize(out, pal)
        print(f"  {name:<14} {w}x{h}  글자 {int(m.sum()):>6}px  속{tuple(core)} 테{tuple(edge)}")
        if make_png:
            prev.append((stem, Image.fromarray(rgb), Image.fromarray(out)))
    if make_png:
        W = max(max(a.width, bimg.width) for _, a, bimg in prev)
        H = max(max(a.height, bimg.height) for _, a, bimg in prev)
        sh = Image.new('RGB', (2*(W+4), len(prev)*(H+4)), (40, 40, 40))
        for k, (s, a, bimg) in enumerate(prev):
            sh.paste(a, (0, k*(H+4))); sh.paste(bimg, (W+4, k*(H+4)))
        q = os.path.join(ROOT, "test_render", "_ep_ko.png"); sh.save(q)
        print(f"      -> {q}")
    return new

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    run('--png' in sys.argv)
