# -*- coding: utf-8 -*-
"""사쿠라대전 2 전투 도입 패널 45장과 키네마트론 조작 설명을 한글로 바꾼다.

  python tools/event_gim.py --check --png
  python tools/event_gim.py

EVENT##_#.GIM 은 PLACE 와 같은 132x230 INDEX8 스위즐 GIM 이다. 아래쪽
문구 상자에 **장소명(윗줄) + 적 이름(아랫줄)** 이 들어 있다.

  윗줄 y172~196, 아랫줄 y197~222, 가로 x18~114

파일마다 조합이 달라서 45장을 하나씩 눈으로 읽어 표로 적었다. 자동으로
뽑을 방법이 없고, 잘못 짝지으면 엉뚱한 적 이름이 박힌다.

**아직 완성이 아니다 — 빌드에 넣지 말 것.**

배경 채우기가 안 끝났다. 두 가지를 해 봤다.

  1) 상자 위·아래 행을 세로로 보간 -> 그 행이 상자 테두리라 안쪽과 색이
     달라 붉은 띠가 생겼다.
  2) 상자 좌우 열을 가로로 보간 -> 색은 맞는데, 원문이 상자 끝까지 뻗은
     패널(「闇神威・叉丹」「大日剣・金剛」)에서는 표본 열 자체에 원문
     픽셀이 들어가 잔재가 남고 가로 줄무늬가 생긴다.

고정된 상자로는 안 된다. ep_title.py 처럼 **상자 안에서 글자를 찾아 그
픽셀만 확산으로 메우는** 방식으로 바꿔야 한다. 상자 배경이 매끈한
그라데이션이라 확산이 잘 들어맞을 것이다.

번역표(EV/PLACE/FOE)는 45장을 눈으로 읽어 확정한 것이라 그대로 쓰면 된다.
"""
import os, sys, struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from build_iso import walk_iso, SRC_ISO, SECTOR
import place_gim as PG

FONT  = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched")

L1 = (14, 171, 118, 197)      # 장소명
L2 = (14, 197, 118, 223)      # 적 이름

PLACE = {
    "帝劇前": "제극 앞", "鶯谷": "우구이스다니", "渋谷": "시부야",
    "神崎邸": "칸자키 저택", "深川": "후카가와", "熱海": "아타미",
    "池袋": "이케부쿠로", "浅草": "아사쿠사", "新宿": "신주쿠",
    "赤坂": "아카사카", "王子": "오지", "ミカサ機関部": "미카사 기관부",
    "ミカサ甲板": "미카사 갑판", "武蔵内部": "무사시 내부",
    "イドの間": "이드의 방", "御柱の間": "미하시라의 방", "最終決戦": "최종 결전",
}
FOE = {
    "脇侍・玫": "협시·매", "闇神威・叉丹": "암신위·사탄",
    "大日剣・金剛 智拳・木喰": "대일검·금강 지권·목갈",
    "金剛": "금강", "大日剣・金剛": "대일검·금강",
    "木喰": "목갈", "智拳・木喰": "지권·목갈",
    "土蜘蛛": "토지주", "八葉・土蜘蛛": "팔엽·토지주",
    "火車": "화차", "五鈷・火車": "오고·화차",
    "水狐": "수호", "宝形・水狐": "보형·수호",
    "闇神威・鬼王": "암신위·귀왕", "鬼王": "귀왕", "降魔": "강마",
    "京極慶吾": "쿄고쿠 케이고", "新皇・京極慶吾": "신황·쿄고쿠 케이고",
}
# 45장을 눈으로 읽어 적은 표 (장소, 적)
EV = {
 'EVENT01_0':("帝劇前","脇侍・玫"),      'EVENT01_1':("帝劇前","闇神威・叉丹"),
 'EVENT02_0':("鶯谷","大日剣・金剛 智拳・木喰"),
 'EVENT02_1':("鶯谷","金剛"),            'EVENT02_2':("鶯谷","大日剣・金剛"),
 'EVENT02_3':("鶯谷","木喰"),            'EVENT02_4':("渋谷","木喰"),
 'EVENT02_5':("渋谷","智拳・木喰"),      'EVENT03_0':("神崎邸","土蜘蛛"),
 'EVENT03_1':("神崎邸","八葉・土蜘蛛"),  'EVENT04_0':("深川","火車"),
 'EVENT04_1':("深川","五鈷・火車"),      'EVENT05_1':("熱海","水狐"),
 'EVENT05_2':("熱海","宝形・水狐"),      'EVENT05_3':("熱海","大日剣・金剛"),
 'EVENT05_4':("熱海","大日剣・金剛"),    'EVENT06_0':("池袋","水狐"),
 'EVENT06_1':("池袋","宝形・水狐"),      'EVENT06_2':("池袋","宝形・水狐"),
 'EVENT07_0':("浅草","火車"),            'EVENT07_1':("浅草","五鈷・火車"),
 'EVENT07_2':("浅草","五鈷・火車"),      'EVENT07_3':("浅草","五鈷・火車"),
 'EVENT08_0':("帝劇前","智拳・木喰"),    'EVENT08_1':("新宿","闇神威・鬼王"),
 'EVENT08_2':("赤坂","脇侍・玫"),        'EVENT08_3':("赤坂","八葉・土蜘蛛"),
 'EVENT08_4':("赤坂","大日剣・金剛"),    'EVENT08_5':("赤坂","八葉・土蜘蛛"),
 'EVENT08_6':("赤坂","大日剣・金剛"),    'EVENT08_7':("帝劇前","智拳・木喰"),
 'EVENT08_8':("赤坂","闇神威・鬼王"),    'EVENT10_0':("王子","鬼王"),
 'EVENT10_1':("王子","土蜘蛛"),          'EVENT10_2':("王子","金剛"),
 'EVENT11_0':("ミカサ機関部","八葉・土蜘蛛"),
 'EVENT11_1':("ミカサ甲板","降魔"),      'EVENT11_2':("ミカサ甲板","八葉・土蜘蛛"),
 'EVENT11_3':("武蔵内部","降魔"),        'EVENT11_4':("武蔵内部","大日剣・金剛"),
 'EVENT11_5':("ミカサ甲板","八葉・土蜘蛛"),
 'EVENT11_6':("武蔵内部","大日剣・金剛"),'EVENT12_0':("イドの間","闇神威・鬼王"),
 'EVENT12_1':("御柱の間","京極慶吾"),    'EVENT12_2':("最終決戦","新皇・京極慶吾"),
}

def fill_v(img, pal, box):
    """상자 좌우 바깥 열을 **가로로** 보간해 배경을 만든다.

    처음에는 위·아래 행을 세로로 섞었는데, 그 행들이 상자의 테두리라
    안쪽과 색이 달라 붉은 띠가 생겼다. 상자 배경은 행마다 색이 변하는
    가로 그라데이션이라, 같은 행의 좌우 여백에서 떠 와야 맞는다.
    RGB 로 섞고 가장 가까운 팔레트 색으로 되돌린다."""
    x0, y0, x1, y1 = box
    prgb = pal[:, :3].astype(np.float64)
    L = prgb[img[y0:y1, max(0, x0-4)]]
    R = prgb[img[y0:y1, min(img.shape[1]-1, x1+3)]]
    tt = np.linspace(0, 1, x1-x0)[None, :, None]
    mix = L[:, None, :]*(1-tt) + R[:, None, :]*tt
    d = ((mix[:, :, None, :] - prgb[None, None, :, :])**2).sum(-1)
    return d.argmin(-1).astype(np.uint8)

def draw_line(img, pal, box, text, lum):
    x0, y0, x1, y1 = box
    reg = img[y0:y1, x0:x1]
    bg = fill_v(img, pal, box)
    bglum = float(lum[bg].mean())
    ink = int(max(np.unique(reg), key=lambda v: abs(lum[v]-bglum)))
    w, h = x1-x0, y1-y0
    size = h - 2
    f = ImageFont.truetype(FONT, size)
    m = Image.new('L', (w, h), 0); dr = ImageDraw.Draw(m)
    while size > 7:
        f = ImageFont.truetype(FONT, size)
        b = dr.textbbox((0, 0), text, font=f)
        if b[2]-b[0] <= w-2 and b[3]-b[1] <= h-2: break
        size -= 1
    b = dr.textbbox((0, 0), text, font=f)
    dr.text(((w-(b[2]-b[0]))//2 - b[0], (h-(b[3]-b[1]))//2 - b[1]), text, font=f, fill=255)
    a = np.asarray(m)
    img[y0:y1, x0:x1] = np.where(a >= 128, ink, bg).astype(np.uint8)
    return ink, size

def run(check_only=False, make_png=False):
    f = open(SRC_ISO, 'rb'); t = walk_iso(f)
    ps = [p for p in sorted(t) if os.path.basename(p)[:-4] in EV and p.upper().endswith('.GIM')]
    os.makedirs(BUILD, exist_ok=True)
    prev = []
    for p in ps:
        nm = os.path.basename(p); stem = nm[:-4]
        ja_p, ja_f = EV[stem]
        if ja_p not in PLACE: raise KeyError(f"{stem}: 장소 '{ja_p}' 번역 없음")
        if ja_f not in FOE:   raise KeyError(f"{stem}: 적 '{ja_f}' 번역 없음")
        _, lba, sz = t[p]; f.seek(lba*SECTOR); d = bytearray(f.read(sz))
        (po, w, h, order), palo = PG.gim_image(bytes(d))
        pitch = (w+15)//16*16; hh = (h+7)//8*8
        buf = np.frombuffer(bytes(d[po:po+pitch*hh]), np.uint8)
        img = (PG.unswz(buf, pitch, hh) if order else buf.reshape(hh, pitch)).copy()
        pal = np.frombuffer(bytes(d[palo:palo+1024]), np.uint8).reshape(256, 4)
        lum = pal[:, :3].astype(int).sum(1)
        if make_png: before = pal[img[:h, :w]][:, :, :3].astype('uint8').copy()
        i1, s1 = draw_line(img, pal, L1, PLACE[ja_p], lum)
        i2, s2 = draw_line(img, pal, L2, FOE[ja_f], lum)
        d[po:po+pitch*hh] = (PG.swz(img) if order else img.reshape(-1)).tobytes()
        print(f"  {nm:<16} {PLACE[ja_p]} / {FOE[ja_f]}  (잉크 {i1}/{i2})")
        if make_png:
            prev.append((Image.fromarray(before),
                         Image.fromarray(pal[img[:h, :w]][:, :, :3].astype('uint8'))))
        if not check_only:
            open(os.path.join(BUILD, nm), 'wb').write(bytes(d))
    f.close()
    if make_png and prev:
        W, H = prev[0][0].width, prev[0][0].height
        sh = Image.new('RGB', (2*(W+4), len(prev)*(H+4)), (30, 30, 30))
        for k, (a, b) in enumerate(prev):
            sh.paste(a, (0, k*(H+4))); sh.paste(b, (W+4, k*(H+4)))
        q = os.path.join(ROOT, "test_render", "_event_ko.png"); sh.save(q)
        print(f"      -> {q}")

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    run('--check' in sys.argv, '--png' in sys.argv)
