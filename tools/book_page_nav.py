# -*- coding: utf-8 -*-
"""책 UI 아래쪽 「前ページ / 後ページ」 를 한글로 바꾼다.

  python tools/book_page_nav.py --png    미리보기만
  python tools/book_page_nav.py          build/patched 에 저장

받은 작업본 문서가 "이전/다음 페이지 문구와 펜 커서는 메인 문자 레이어와
독립된 별도 레이어"라고만 적어 놓고 어느 파일인지는 안 밝혀서 오래 걸렸다.
답은 **PBOOK_FLB0.CMP 의 뒷부분**이다.

찾은 과정 — 쓸모 있는 순서대로

  1) 이름이 코드에 나오는 자산만 후보로 남긴다. TITLE_D.BIN 에서
     PBOOK_FLB.CMP / PBOOK_FLB0.CMP 를 찾았다.
  2) PBOOK_FLB.PAL 이 32바이트(16색)라 **4bpp** 다.
  3) 폭은 자기상관으로 32바이트(=64픽셀)가 나왔는데, 그 폭으로 읽으면
     앞부분만 맞고 뒤가 잡음이었다. **파일 하나에 폭이 두 개다.**

         0x0000~0x1FFF   64픽셀 x 256행 — 메모리 카드 라벨
                         A-1 A-2 B-1 B-2 C-1 C-2 D-1 D-2 (8장 x 32행)
         0x2000~0x2BFF   96픽셀 x 64행  — 페이지 이동 문구  <- 이 파일이 다루는 것

     PBOOK_FL4 도 같은 식이라 (낱장마다 폭이 다름) 한 번 겪은 함정이었는데
     이번엔 앞부분이 읽히니까 폭이 맞다고 지레 판단했다.

레이아웃은 PBOOKTTL 의 문자 레이어와 달리 **그냥 행우선**이다.
열우선·상하반전이 아니다 (그쪽 공식을 그대로 적용하면 글자가 눕는다).

  4bpp high-nibble-first, 한 행 48바이트
  윗줄 y0~31   「L　前ページ」   L 은 x7~17,  일본어는 x29~86
  아랫줄 y32~63 「後ページ　R」  일본어는 x11~68, R 은 x80~90
  글자 높이는 두 줄 다 y6~19 (14px)

L / R 은 버튼 표시이므로 **건드리지 않는다**. 일본어 자리만 지우고 다시 쓴다.

이 파일은 SAKURA1/ 과 SAKURA2/ 두 곳에 같은 내용으로 들어 있다. build_iso
쪽에서 두 경로 모두에 써 준다 (MULTI_PATH).
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from build_iso import walk_iso, SRC_ISO, SECTOR
from cmp import decompress, parse_header, _params
from cmp_compress import compress

FONT  = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched")
NAME  = "PBOOK_FLB0.CMP"

OFF, W, H = 0x2000, 96, 64          # 페이지 이동 구역
ROWB      = W // 2                  # 4bpp 한 행 48바이트
INK_Y     = (6, 20)                 # 원문 글자가 차지한 세로 범위

# (밴드 y0, 지울 x범위, 번역, 원문)
# 「이전 페이지」는 다섯 글자라 원문 네 글자보다 넓다. L/R 을 뺀 자리를
# 남김없이 써야 들어가므로 상자를 텍스처 끝까지 잡았다 (14px 로 앉는다).
JOBS = [
    (0,  (20, 95), "이전 페이지", "前ページ"),
    (32, ( 2, 78), "다음 페이지", "後ページ"),
]
PAD = 1

# 안티에일리어싱 단계 수. **압축 크기 때문에 있는 값이다.**
# 이 파일은 1,922바이트라 한 섹터(2,048)에 들어가야 한다. 16단계 그대로
# 쓰면 2,167바이트가 되어 안 들어간다 — 한글 다섯 글자가 원문 네 글자보다
# 획이 많아 중간 밝기 픽셀이 늘고, 그만큼 LZSS 가 잡을 반복이 줄어든다.
#   16단계 2,167  /  8단계 2,065  /  6단계 2,040  /  4단계 1,979  /  2단계 1,723
# 4단계면 이 크기에서 눈으로 구분이 안 되고 69바이트 여유가 남는다.
LEVELS = 4

def unpack(buf):
    b = np.frombuffer(buf[OFF:OFF + ROWB*H], np.uint8)
    n = np.empty(b.size*2, np.uint8); n[0::2] = (b >> 4) & 15; n[1::2] = b & 15
    return n.reshape(H, W)

def pack(img):
    f = img.reshape(-1).astype(np.uint8)
    return ((f[0::2] << 4) | f[1::2]).astype(np.uint8).tobytes()

def fit(jobs):
    """두 줄을 **같은 크기**로 앉힌다. 줄마다 따로 재면 상자 폭이 1px 달라서
    14px 와 15px 로 갈리는데, 나란히 놓이는 문구라 눈에 띈다."""
    h = INK_Y[1] - INK_Y[0]
    size = h + 3
    while size > 8:
        f = ImageFont.truetype(FONT, size)
        if all(f.getbbox(ko)[2] - f.getbbox(ko)[0] <= x1 - x0 - 2*PAD
               for _, (x0, x1), ko, _ in jobs): break
        size -= 1
    return size

def draw(img, y0, x0, x1, text, size):
    """x0~x1 을 지우고 그 안에 text 를 그린다. 세로는 원문과 같은 자리."""
    band = img[y0:y0+32]
    band[:, x0:x1] = 0
    # 4배로 그려서 줄여야 계단이 안 진다 (원문도 안티에일리어싱이 들어 있다)
    S = 4
    f4 = ImageFont.truetype(FONT, size*S)
    m = Image.new('L', ((x1-x0)*S, 32*S), 0); dr = ImageDraw.Draw(m)
    b = dr.textbbox((0, 0), text, font=f4)
    dr.text(((x1-x0)*S//2 - (b[2]+b[0])//2,
             int((INK_Y[0]+INK_Y[1])/2*S - (b[3]+b[1])/2)), text, font=f4, fill=255)
    a = np.asarray(m.resize((x1-x0, 32), Image.LANCZOS)).astype(np.int32)
    v = np.clip((a*15 + 127)//255, 0, 15)
    step = 15/(LEVELS - 1)
    band[:, x0:x1] = np.clip(np.round(np.round(v/step)*step), 0, 15).astype(np.uint8)
    return size

def run(make_png=False):
    with open(SRC_ISO, 'rb') as f:
        t = walk_iso(f)
        p = [x for x in t if os.path.basename(x) == NAME and '/SAKURA1/' in x][0]
        _, lba, sz = t[p]; f.seek(lba*SECTOR); raw = f.read(sz)
    dec = bytes(decompress(raw)[0])
    method, param, _, hlen = parse_header(raw)
    obits, bias = _params(method, param)

    img = unpack(dec)
    before = img.copy()
    size = fit(JOBS)
    for y0, (x0, x1), ko, ja in JOBS:
        draw(img, y0, x0, x1, ko, size)
        print(f"  y{y0:>3} x{x0}~{x1}  {ja} -> {ko}  ({size}px)")

    d = bytearray(dec)
    d[OFF:OFF + ROWB*H] = pack(img)
    out = bytes(d)
    assert len(out) == len(dec), "길이가 바뀌면 안 된다"

    if make_png:
        sh = Image.new('L', (W, H*2 + 6), 60)
        sh.paste(Image.fromarray((before*17).astype(np.uint8)), (0, 0))
        sh.paste(Image.fromarray((img*17).astype(np.uint8)), (0, H+6))
        q = os.path.join(ROOT, "test_render", "_pagenav_ko.png")
        sh.resize((W*6, sh.height*6), Image.NEAREST).save(q)
        print(f"      -> {q}")
        return

    packed = compress(out, obits, bias, header=raw[:hlen])
    alloc = (len(raw) + SECTOR - 1)//SECTOR*SECTOR
    print(f"  재압축 {len(raw)} -> {len(packed)}바이트 / 배정 {alloc}"
          f"  ({'들어감' if len(packed) <= alloc else '자리 부족!'})")
    back = bytes(decompress(packed)[0])
    print(f"  재압축 검증: {'통과' if back == out else '불일치'}")
    assert back == out and len(packed) <= alloc
    os.makedirs(BUILD, exist_ok=True)
    q = os.path.join(BUILD, NAME); open(q, 'wb').write(packed)
    print(f"      -> {q}")

if __name__ == '__main__':
    sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    run('--png' in sys.argv)
