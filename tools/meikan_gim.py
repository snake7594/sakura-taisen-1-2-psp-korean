# -*- coding: utf-8 -*-
"""필살기 이름 세로 배너(SLGSIDE/MEIKAN/*.GIM) 30장을 한글로 바꾼다.

  python tools/meikan_gim.py --png [이름...]   미리보기만
  python tools/meikan_gim.py                   build/patched/MEIKAN 에 저장

132x230 INDEX8 스위즐 GIM. 인물 그림 위에 세로쓰기 붓글씨.
파일 이름 = 인물_기술 (K1/K2=필살기, HG=합체기, NG=장거리, TE=?, BS=적).

프랑스어(IRI)·러시아어(MAR)·이탈리아어(ORI)·독일어(REN) 배너 20장은
일본어가 아니므로 손대지 않는다.

번역은 게임 안 퀴즈(SK1303)에서 쓴 표기를 따른다 — 앵화방신, 앵화무상,
백화제방, 귀신굉천살, 방마성진, 설화파문십궤, 로패오단, 연작·비룡의 춤.
퀴즈에 없는 것은 같은 방식(한자 음차)으로 옮겼다.

원문을 지우는 자동 검출은 세 번 실패했다 — 배너마다 색조·잉크·질감이
다르고 주사선 디더까지 깔려 있어 초상화와 글자를 기계로 못 가른다.
그래서 **원문 열 위에 배너 색조의 세로 리본을 깔고 그 위에 쓴다.**
리본이 원문을 완전히 덮으므로 잔재가 없고, 30장이 균일하게 나온다.
열 위치는 원본 배치(오른쪽 열이 위, 왼쪽 열이 아래)를 따른다.
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
BUILD = os.path.join(ROOT, "build", "patched", "MEIKAN")

# 오른쪽 열부터. (원문, [열 문자열...])
KO = {
 'KAN_HG': ("純情一路",             ["순정일로"],                   'dark'),
 'KAN_K1': ("三進転掌",             ["삼진전장"],                   'dark'),
 'KAN_K2': ("三十六掌",             ["삼십육장"],                   'dark'),
 'KAN_NG': ("征遠鎮",               ["정원진"],                     'dark'),
 'KAN_TE': ("鷺牌五段",             ["로패오단"],                   'dark'),
 'KAS_BS': ("紅蓮火輪双",           ["홍련화륜쌍"],                 'dark'),
 'KON_BS': ("鬼神轟天殺",           ["귀신굉천살"],                 'dark'),
 'KOR_HG': ("我愛你",               ["워아이니"],                   'dark'),
 'KOR_K1': ("雀牌ロボ",             ["작패로봇"],                   'dark'),
 'KOR_K2': ("聖獣ロボ・改",         ["성수로봇·개"],                'dark'),
 'KOR_NG': ("超絶 猛火赤龍咬翔",    ["초절", "맹화적룡교상"],       'dark'),
 'KOR_TE': ("球電ロボ",             ["구전로봇"],                   'dark'),
 'MOK_BS': ("皓矢念臨演舞",         ["호시염림연무"],               'dark'),
 'OGA_K1': ("狼虎滅却 天地一矢",    ["낭호멸각", "천지일시"],       'dark'),
 'OGA_K2': ("狼虎滅却 天狼転化",    ["낭호멸각", "천랑전화"],       'dark'),
 'OGA_TE': ("狼虎滅却 三刃成虎",    ["낭호멸각", "삼인성호"],       'dark'),
 'ONI_K2': ("破邪剣征 桜花放神",    ["파사검정", "앵화방신"],       'light'),
 'ONI_TE': ("諸力諸来 放魔星辰",    ["제력제래", "방마성진"],       'light'),
 'SAK_HG': ("二人はさくら色",       ["두 사람은", "벚꽃빛"],        'light'),
 'SAK_K1': ("破邪剣征 桜花霧翔",    ["파사검정", "앵화무상"],       'light'),
 'SAK_K2': ("破邪剣征 桜花爛漫",    ["파사검정", "앵화란만"],       'light'),
 'SAK_NG': ("破邪剣征 桜花天舞",    ["파사검정", "앵화천무"],       'light'),
 'SAK_TE': ("破邪剣征 百花斉放",    ["파사검정", "백화제방"],       'light'),
 'SUI_BS': ("雪花波紋十軌",         ["설화파문십궤"],               'light'),
 'SUM_HG': ("二人の愛は永遠に",     ["두 사람의", "사랑은 영원히"], 'light'),
 'SUM_K1': ("神崎風塵流 連雀の舞",  ["칸자키 풍진류", "연작의 춤"], 'light'),
 'SUM_K2': ("神崎風塵流 不死鳥の舞",["칸자키 풍진류", "불사조의 춤"],'light'),
 'SUM_NG': ("神崎風塵流 紫仙燕子花",["칸자키 풍진류", "자선연자화"],'light'),
 'SUM_TE': ("神崎風塵流 飛竜の舞",  ["칸자키 풍진류", "비룡의 춤"], 'light'),
 'TSU_BS': ("九印曼荼羅",           ["구인만다라"],                 'dark'),
}


def load(nm):
    f = open(SRC_ISO, 'rb'); t = walk_iso(f)
    p = [x for x in t if os.path.basename(x) == nm + '.GIM' and '/MEIKAN/' in x][0]
    _, lba, sz = t[p]; f.seek(lba*SECTOR); d = bytearray(f.read(sz)); f.close()
    return d, sz

def dominant(rgb):
    """배너 색조 — 중간톤 픽셀의 중앙값"""
    half = rgb[::4, ::4].reshape(-1, 3).astype(np.float32)
    lum = half.sum(1)
    mid = half[(lum > np.percentile(lum, 25)) & (lum < np.percentile(lum, 75))]
    return np.median(mid, axis=0) if len(mid) else np.array([128., 80., 80.])

def draw_ribbon_col(rgb, cx, ytop, ybot, text, style, tint, hw_min=0):
    """세로 리본 + 세로쓰기. (ytop, ybot) 중 None 인 쪽은 글자 수에 맞춘다."""
    h, w = rgb.shape[:2]
    chars = [c for c in text if c != ' ']
    n = len(chars)
    had_top, had_bot = ytop is not None, ybot is not None
    avail = (ybot if had_bot else h-14) - (ytop if had_top else 14)
    ch = min(52, max(18, avail//n))
    total = ch*n
    # 양쪽을 다 준 경우(한 열짜리)는 **줄이지 않는다** — 줄이면 원문 아래
    # 글자가 리본 밖으로 삐져나온다 (征遠鎮 의 鎮 이 그랬다).
    if not had_top: ytop = ybot - total - 6
    if not had_bot: ybot = ytop + total + 12
    hw = max(ch//2 + 4, hw_min)          # 원문 열을 다 덮어야 잔재가 안 남는다
    x0, x1 = max(3, cx-hw), min(w-3, cx+hw)
    y0, y1 = max(4, ytop-6), min(h-4, ybot+2)
    if style == 'dark':
        fill = tint*0.35 + np.array([255.,255.,255.])*0.65
        core_c, edge_c = np.array([15.,10.,10.]), tint*0.55
    else:
        fill = tint*0.42
        core_c, edge_c = np.array([245.,242.,238.]), tint*0.3
    # 리본 (둥근 모서리)
    S = 4
    rb = Image.new('L', ((x1-x0)*S, (y1-y0)*S), 0)
    ImageDraw.Draw(rb).rounded_rectangle([0, 0, (x1-x0)*S-1, (y1-y0)*S-1], radius=8*S, fill=255)
    ra = np.asarray(rb.resize((x1-x0, y1-y0), Image.LANCZOS)).astype(np.float32)/255
    reg = rgb[y0:y1, x0:x1].astype(np.float32)
    reg = reg*(1-ra[...,None]) + fill[None,None,:]*ra[...,None]
    rgb[y0:y1, x0:x1] = np.clip(reg, 0, 255).astype(np.uint8)
    # 글자
    f4 = ImageFont.truetype(FONT, ch*S)
    m = Image.new('L', ((x1-x0)*S, (y1-y0)*S), 0); dr = ImageDraw.Draw(m)
    ys = ytop - y0 + ( (ybot-ytop) - total )//2
    for i, c in enumerate(chars):
        b = dr.textbbox((0, 0), c, font=f4)
        dr.text(((x1-x0)*S//2 - (b[2]+b[0])//2,
                 (ys + i*ch)*S + ch*S//2 - (b[3]+b[1])//2), c, font=f4, fill=255)
    a = np.asarray(m.resize((x1-x0, y1-y0), Image.LANCZOS)).astype(np.float32)/255
    ring = np.asarray(Image.fromarray((a*255).astype('uint8'))
                      .filter(ImageFilter.MaxFilter(3))).astype(np.float32)/255
    reg = rgb[y0:y1, x0:x1].astype(np.float32)
    reg = reg*(1-ring[...,None]) + edge_c[None,None,:]*ring[...,None]
    reg = reg*(1-a[...,None]) + core_c[None,None,:]*a[...,None]
    rgb[y0:y1, x0:x1] = np.clip(reg, 0, 255).astype(np.uint8)
    return ch

# 원문 열 자리는 50장이 거의 같다 — 한 열이면 가운데, 두 열이면 오른쪽 98 /
# 왼쪽 42. 획 에너지로 재 봤지만 배너마다 몇 px 씩 흔들려 원문이 삐져나왔다.
# 고정값 + 넉넉한 반폭이 훨씬 안정적이다.
CX1, CX2R, CX2L = 66, 98, 42
HW1, HW2 = 48, 36

def run(make_png=False, only=None):
    os.makedirs(BUILD, exist_ok=True)
    prev = []
    for nm, (ja, cols_ko, style) in KO.items():
        if only and nm not in only: continue
        d, sz = load(nm)
        (po, w, h, order), palo = PG.gim_image(bytes(d))
        pitch = (w+15)//16*16; hh = (h+7)//8*8
        buf = np.frombuffer(bytes(d[po:po+pitch*hh]), np.uint8)
        img = (PG.unswz(buf, pitch, hh) if order else buf.reshape(hh, pitch)).copy()
        pal = np.frombuffer(bytes(d[palo:palo+1024]), np.uint8).reshape(256, 4)
        rgb = pal[img[:h, :w]][:, :, :3].astype(np.uint8).copy()
        before = rgb.copy()
        tint = dominant(rgb)
        sizes = []
        if len(cols_ko) == 1:
            sizes.append(draw_ribbon_col(rgb, CX1, 10, h-8, cols_ko[0], style, tint, HW1))
        else:
            sizes.append(draw_ribbon_col(rgb, CX2R, 12, None, cols_ko[0], style, tint, HW2))
            sizes.append(draw_ribbon_col(rgb, CX2L, None, h-10, cols_ko[1], style, tint, HW2))
        print(f"  {nm}: {ja} -> {' / '.join(cols_ko)}  ({sizes}px)")
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
        cols_n = min(6, len(prev))
        rows_n = (len(prev)+cols_n-1)//cols_n
        sh = Image.new('RGB', (cols_n*2*136, rows_n*236), (25,25,25))
        for k,(nm,a,b) in enumerate(prev):
            x=(k%cols_n)*2*136; y=(k//cols_n)*236
            sh.paste(a,(x,y)); sh.paste(b,(x+134,y))
        q = os.path.join(ROOT, 'test_render', '_meikan_ko.png')
        sh.resize((int(sh.width*1.5), int(sh.height*1.5)), Image.LANCZOS).save(q); print('  ->', q)

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    only = [a for a in sys.argv[1:] if not a.startswith('--')] or None
    run('--png' in sys.argv, only)
