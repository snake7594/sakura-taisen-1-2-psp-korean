# -*- coding: utf-8 -*-
"""사쿠라1 전투 옆창·미니게임 UI 의 그림 글자를 한글로 바꾼다.

  python tools/spr_ui.py --list   대상만 보기
  python tools/spr_ui.py --png    미리보기 PNG 도 저장
  python tools/spr_ui.py          build/patched 에 .SPR 저장

menu_images.py 와 같은 방식이다 (팔레트 인덱스로 지우고 다시 그린다).
그쪽 JOBS 에 없던 파일만 여기서 다룬다 — 전수조사(548장 컨택트시트 스캔)로
찾아낸 것들이다.

  SLGSIDE.SPR   사쿠라1 전투 옆창의 대원 이름표 7장. **전투 내내 떠 있다.**
  MM_FONTA.SPR  미니게임 공통 UI (조작 설명, 재도전, 순위표, 분/초/점 …)
  MM_YAKU.SPR   화투 족보 이름 16장 (카스/단/열끗/오광 …)
  MC_NAME.SPR   화투 대전 상대 이름 8장
  MC.SPR        미니게임 상대 이름 8장 (MC_NAME 과 그림이 다르다)
  KOIKOI.SPR    화투 시작 대사·메뉴
  CONTINUE.SPR  つづける? / おしまい
  SHINRIAD.SPR  壱~六 (신뢰도 단계 표시)
  COOK/HANA/MAIGO/SHOT/SLOT/SWIM/SOUJI.SPR   미니게임 설명 띠

한자 이름표(大神·紅蘭)는 **가운데 빈 칸이 들어간 조판**이라 원문 그대로
「大 神」처럼 보인다. 한글은 빈 칸 없이 붙여 쓴다.
"""
import os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import spr, spr_write
import menu_images as MI

BUILD = os.path.join(ROOT, "build", "patched")
PREV  = os.path.join(ROOT, "test_render", "sprui")

# (파일, 이미지번호, 한글, 상자 or None)
JOBS = [
 # ── 사쿠라1 전투 옆창 대원 이름 ──
 ("SLGSIDE.SPR", 17, "오오가미",  None, 'H'),
 ("SLGSIDE.SPR", 18, "사쿠라",    None, 'H'),
 ("SLGSIDE.SPR", 19, "스미레",    None, 'H'),
 ("SLGSIDE.SPR", 20, "마리아",    None, 'H'),
 ("SLGSIDE.SPR", 21, "아이리스",  None, 'H'),
 ("SLGSIDE.SPR", 22, "코란",      None, 'H'),
 ("SLGSIDE.SPR", 23, "칸나",      None, 'H'),

 # ── 미니게임 공통 UI ──
 ("MM_FONTA.SPR",  0, "마우스 불가", None, 'H'),
 ("MM_FONTA.SPR",  1, "끝난 뒤에는?", None, 'H'),
 ("MM_FONTA.SPR",  2, "조작 설명",  None, 'H'),
 ("MM_FONTA.SPR",  3, "조작 연습",  None, 'H'),
 ("MM_FONTA.SPR",  4, "다시 도전",  None, 'H'),
 ("MM_FONTA.SPR",  5, "단자 전환",  None, 'H'),
 ("MM_FONTA.SPR",  6, "게임 종료",  None, 'H'),
 ("MM_FONTA.SPR",  7, "기록 삭제",  None, 'H'),
 ("MM_FONTA.SPR",  8, "재개",      None, 'H'),
 ("MM_FONTA.SPR",  9, "시작",      None, 'H'),
 ("MM_FONTA.SPR", 10, "1P 단자",   None, 'H'),
 ("MM_FONTA.SPR", 11, "2P 단자",   None, 'H'),
 ("MM_FONTA.SPR", 12, "족보 설명", None, 'H'),
 ("MM_FONTA.SPR", 13, "1위",       None, 'H'),
 ("MM_FONTA.SPR", 14, "2위",       None, 'H'),
 ("MM_FONTA.SPR", 15, "3위",       None, 'H'),
 ("MM_FONTA.SPR", 16, "분",        None, 'H'),
 ("MM_FONTA.SPR", 17, "초",        None, 'H'),
 ("MM_FONTA.SPR", 18, "점",        None, 'H'),
 ("MM_FONTA.SPR", 20, "불가",      None, 'H'),
 ("MM_FONTA.SPR", 21, "순위표",    None, 'H'),

 # ── 화투 족보 이름 ──
 ("MM_YAKU.SPR",  0, "껍데기",   None, 'H'),
 ("MM_YAKU.SPR",  1, "단",       None, 'H'),
 ("MM_YAKU.SPR",  2, "열끗",     None, 'H'),
 ("MM_YAKU.SPR",  3, "달맞이술", None, 'H'),
 ("MM_YAKU.SPR",  4, "꽃놀이술", None, 'H'),
 ("MM_YAKU.SPR",  5, "고도리",   None, 'H'),
 ("MM_YAKU.SPR",  6, "홍단",     None, 'H'),
 ("MM_YAKU.SPR",  7, "청단",     None, 'H'),
 ("MM_YAKU.SPR",  8, "오광",     None, 'H'),
 ("MM_YAKU.SPR",  9, "삼광",     None, 'H'),
 ("MM_YAKU.SPR", 10, "사광",     None, 'H'),
 ("MM_YAKU.SPR", 11, "비사광",   None, 'H'),
 ("MM_YAKU.SPR", 12, "그만!",    None, 'H'),
 ("MM_YAKU.SPR", 13, "고!",      None, 'H'),
 ("MM_YAKU.SPR", 14, "선권",     None, 'H'),
 ("MM_YAKU.SPR", 15, "합계",     None, 'H'),
 ("MM_YAKU.SPR", 17, "문",       None, 'H'),

 # ── 화투 대전 상대 이름 (세로쓰기 붓글씨 이름패) ──
 ("MC_NAME.SPR", 0, "신구지사쿠라", None, 'V'),
 ("MC_NAME.SPR", 1, "키리시마칸나", None, 'V'),
 ("MC_NAME.SPR", 2, "칸자키스미레", None, 'V'),
 ("MC_NAME.SPR", 3, "리코란",       None, 'V'),
 ("MC_NAME.SPR", 4, "마리아타치바나", None, 'V'),
 ("MC_NAME.SPR", 5, "아이리스",     None, 'V'),
 ("MC_NAME.SPR", 6, "후지에다아야메", None, 'V'),
 ("MC_NAME.SPR", 7, "살녀",         None, 'V'),

 # MC.SPR 은 앞 6장이 캐릭터 그림이고 #6 부터가 이름패다
 ("MC.SPR",  6, "아이리스",     None, 'V'),
 ("MC.SPR",  7, "키리시마칸나", None, 'V'),
 ("MC.SPR",  8, "리코란",       None, 'V'),
 ("MC.SPR",  9, "마리아타치바나", None, 'V'),
 ("MC.SPR", 10, "칸자키스미레", None, 'V'),
 ("MC.SPR", 11, "신구지사쿠라", None, 'V'),
 ("MC.SPR", 12, "후지에다아야메", None, 'V'),
 ("MC.SPR", 13, "살녀",         None, 'V'),

 # ── 화투 시작 화면 ──
 ("KOIKOI.SPR",  2, "선택\n결정\n쓰지 않음\n쓰지 않음", None, 'H'),
 ("KOIKOI.SPR",  3, "패 선택\n결정\n취소\n족보표",      None, 'H'),
 ("KOIKOI.SPR",  4, "오빠\n승부!",       None, 'H'),
 ("KOIKOI.SPR",  5, "대장,\n승부!",      None, 'H'),
 ("KOIKOI.SPR",  6, "오오가미 씨,\n승부!", None, 'H'),
 ("KOIKOI.SPR",  7, "대장,\n승부!",      None, 'H'),
 ("KOIKOI.SPR",  8, "소위,\n승부!",      None, 'H'),
 ("KOIKOI.SPR",  9, "오오가미 씨\n승부!", None, 'H'),
 ("KOIKOI.SPR", 10, "오오가미 군,\n승부야!", None, 'H'),
 ("KOIKOI.SPR", 11, "오오가미 군이\n날 이길 수\n있을까!", None, 'H'),
 ("KOIKOI.SPR", 12, "남은\n도전\n횟수",  None, 'H'),

 ("CONTINUE.SPR", 0, "계속할까?", None, 'H'),
 ("CONTINUE.SPR", 1, "끝",        None, 'H'),

 ("SHINRIAD.SPR", 0, "1", None, 'H'),
 ("SHINRIAD.SPR", 1, "2", None, 'H'),
 ("SHINRIAD.SPR", 2, "3", None, 'H'),
 ("SHINRIAD.SPR", 3, "4", None, 'H'),
 ("SHINRIAD.SPR", 4, "5", None, 'H'),
 ("SHINRIAD.SPR", 5, "6", None, 'H'),
]

def pick_ink(reg, pal, bg):
    """잉크 = **배경 밝기에서 가장 먼 색**. MI.redraw 는 '가장 흔한 색'을 쓰는데
    이름패처럼 안티에일리어싱이 두꺼운 그림에서는 중간톤이 잡혀 글자가
    흐려진다 (대원 이름표가 배경에 묻혀 안 보였다)."""
    vals, cnt = np.unique(reg, return_counts=True)
    lum = pal[:, :3].astype(np.int32).sum(1)
    bgl = int(lum[bg])
    best, bi = -1, None
    for v, c in zip(vals.tolist(), cnt.tolist()):
        if v == bg or c < reg.size*0.01: continue
        d = abs(int(lum[v]) - bgl)
        if d > best: best, bi = d, v
    return bi

def redraw_h(img, pal, text, box):
    """MI.redraw 와 같되 잉크를 밝기 대비로 고른다."""
    h, w = img.shape
    x0, y0, x1, y1 = box if box else (0, 0, w, h)
    reg = img[y0:y1, x0:x1]
    vals = np.unique(reg)
    bg = int(img[y0, x0])
    ink = pick_ink(reg, pal, bg)
    if ink is None: return None, None
    bg_rgb = pal[bg][:3].astype(np.int32); ink_rgb = pal[ink][:3].astype(np.int32)
    ok = np.zeros(len(pal), bool); ok[vals] = True
    reg[:] = bg
    bw, bh = x1-x0, y1-y0
    m = Image.new('L', (bw, bh), 0)
    inner = MI.text_mask(text, int(bw*0.96), int(bh*0.92))
    m.paste(inner, ((bw-inner.width)//2, (bh-inner.height)//2))
    al = np.asarray(m, np.float32)/255.0
    lut = {}
    for q in range(17):
        t = q/16.0
        c = (bg_rgb*(1-t) + ink_rgb*t).round().astype(np.int32)
        lut[q] = bg if t < 0.03 else (ink if t > 0.97 else MI.nearest(pal, ok, c))
    qa = np.clip((al*16).round().astype(np.int32), 0, 16)
    out = np.vectorize(lut.get)(qa).astype(np.uint8)
    reg[:] = np.where(qa > 0, out, reg)
    return bg, ink

def vmask(text, bw, bh):
    """세로쓰기 마스크 — 한 글자씩 아래로 쌓는다."""
    from PIL import ImageDraw, ImageFont
    ch = [c for c in text if c != ' ']
    n = len(ch)
    size = min(bw, max(8, (bh-4)//n))
    f = ImageFont.truetype(MI.KFONT, size)
    m = Image.new('L', (bw, bh), 0); dr = ImageDraw.Draw(m)
    step = bh/n
    for i, c in enumerate(ch):
        b = dr.textbbox((0, 0), c, font=f)
        dr.text(((bw-(b[2]-b[0]))//2 - b[0],
                 int(i*step + (step-(b[3]-b[1]))//2) - b[1]), c, font=f, fill=255)
    return m

def redraw_v(img, pal, text, box):
    """세로쓰기 이름패. MI.redraw 와 같은데 마스크만 세로다.

    이름패는 **가장자리 테두리를 살려야** 한다 — 상자를 통째로 배경색으로
    칠하면 검은 테두리와 금색 테가 날아간다. 그래서 안쪽 여백만 지운다."""
    h, w = img.shape
    x0, y0, x1, y1 = box if box else (0, 0, w, h)
    pad_x = max(3, (x1-x0)//8); pad_y = max(3, (y1-y0)//14)
    ix0, iy0, ix1, iy1 = x0+pad_x, y0+pad_y, x1-pad_x, y1-pad_y
    reg = img[iy0:iy1, ix0:ix1]
    vals, cnt = np.unique(reg, return_counts=True)
    # **최빈색을 배경으로 쓰면 안 된다** — 「真宮寺さくら」처럼 획이 굵은 이름은
    # 검정이 바탕보다 넓어서 색이 뒤집힌다. 안쪽 모서리가 바탕이다.
    bg = int(reg[0, 0])
    ink = pick_ink(reg, pal, bg)
    if ink is None: return None, None
    bg_rgb = pal[bg][:3].astype(np.int32); ink_rgb = pal[ink][:3].astype(np.int32)
    ok = np.zeros(len(pal), bool); ok[vals] = True
    reg[:] = bg
    bw, bh = ix1-ix0, iy1-iy0
    al = np.asarray(vmask(text, bw, bh), np.float32)/255.0
    lut = {}
    for q in range(17):
        t = q/16.0
        c = (bg_rgb*(1-t) + ink_rgb*t).round().astype(np.int32)
        lut[q] = bg if t < 0.03 else (ink if t > 0.97 else MI.nearest(pal, ok, c))
    qa = np.clip((al*16).round().astype(np.int32), 0, 16)
    out = np.vectorize(lut.get)(qa).astype(np.uint8)
    reg[:] = np.where(qa > 0, out, reg)
    return bg, ink

def main():
    listing = '--list' in sys.argv
    png = '--png' in sys.argv
    if png: os.makedirs(PREV, exist_ok=True)
    if not listing: os.makedirs(BUILD, exist_ok=True)

    byfile = {}
    for rel, i, ko, box, mode in JOBS: byfile.setdefault(rel, []).append((i, ko, box, mode))

    for rel, items in byfile.items():
        d = MI.read_iso(rel)
        if d is None:
            print(f"  ! {rel}: ISO 에서 못 찾음 (이름이 여럿이거나 없음)"); continue
        pal = spr.palette(d)
        body, ents, db = None, None, None
        for off, size, idx, c in spr.chunks(d):
            cnt, e, base = spr.entries(c)
            if cnt and any(x[5] for x in e):
                body, ents, db = c, e, base; break
        if body is None:
            print(f"  ! {rel}: 이미지 청크 없음"); continue
        changes, prev = {}, []
        for i, ko, box, mode in items:
            if i >= len(ents):
                print(f"  ! {rel} #{i}: 장수 {len(ents)} 초과"); continue
            if ents[i][0] == 0 or ents[i][1] == 0 or ents[i][5] == 0:
                print(f"  ! {rel} #{i}: 빈 이미지 (건너뜀)"); continue
            e = ents[i]
            w, h, fmt = e[0], e[1], e[2]
            bpp = spr.BPP[fmt & 0x0F]
            if bpp == 16:
                img = spr_write.unpack16(body, e, db)
                before = img.copy()
                bg, ink = MI.redraw16(img, ko, box)
            else:
                img = spr_write.unpack_px(body, e, db)
                before = img.copy()
                q = e[3]
                bank = pal[q:q+256] if pal is not None and q+256 <= len(pal) else pal
                bg, ink = redraw_v(img, bank, ko, box) if mode == 'V' else redraw_h(img, bank, ko, box)
            if bg is None:
                print(f"  ! {rel} #{i}: 잉크를 못 찾음 (건너뜀)"); continue
            changes[i] = img
            print(f"  {rel} #{i} {w}x{h} {bpp}bpp -> {ko!r}  (배경{bg} 잉크{ink})")
            if png and bpp != 16:
                bank2 = bank[:, :3].astype('uint8')
                prev.append((i, Image.fromarray(bank2[before]), Image.fromarray(bank2[img])))
        if listing or not changes: continue
        nd = spr_write.rebuild(d, changes)
        open(os.path.join(BUILD, rel), 'wb').write(nd)
        print(f"      {len(d):,} -> {len(nd):,}B")
        if png and prev:
            W = max(max(a.width, b.width) for _, a, b in prev)
            H = sum(max(a.height, b.height)+4 for _, a, b in prev)
            sh = Image.new('RGB', (2*(W+4), H), (30, 30, 30)); y = 0
            for i, a, b in prev:
                sh.paste(a.convert('RGB'), (0, y)); sh.paste(b.convert('RGB'), (W+4, y))
                y += max(a.height, b.height)+4
            sh.save(os.path.join(PREV, rel.replace('.SPR', '')+'.png'))

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
