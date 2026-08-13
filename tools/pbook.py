# -*- coding: utf-8 -*-
"""사쿠라대전 2 메뉴책(PBOOK*) 이미지 읽기/쓰기.

포맷을 알아내는 데 오래 걸렸으므로 근거를 남겨 둔다.

  PBOOK_BG.GIM 이 열쇠였다. GIM 은 소니 표준 포맷이라 헤더에 형식이 적혀 있다.
      INDEX8 / order=1(스위즐) / 192x269 / pitchAlign 16 / heightAlign 8
      팔레트 RGBA8888 256색
  이걸 그대로 풀었더니 나선제본 노트 그림이 정확히 나왔다. 즉 이 게임 이미지는
  **8bpp 인덱스**이고 스위즐은 **16바이트 x 8행** 블록이다.

  .PCG 는 .CMP 의 압축 안 한 판이다. PBOOK_FL83 은 둘 다 있어서
  decompress(PBOOK_FL83.CMP) == PBOOK_FL83.PCG 로 압축 해제기를 검증했다.
  바이트 단위로 완전히 일치한다 — 압축 쪽은 문제가 없었다.

  남은 건 **행 폭(pitch)** 뿐이었는데 파일마다 다르고 어디에도 안 적혀 있다.
  자기상관으로 잰다: b[i+P] 와 b[i] 의 평균 절대차가 가장 작은 P 가 실제 폭.
  같은 그림에서 위아래로 붙은 픽셀은 비슷하기 때문이다.
  GIM 으로 검증했다 — 스위즐 상태에서는 16(블록 폭)에서 최소가 나오고,
  언스위즐한 뒤에는 192 에서 최소가 나온다. 정답과 같다.
  그래서 최적 P 가 32 미만이면 '아직 스위즐 상태'로 보고 풀어서 다시 잰다.

  주의 — PBOOK_FL4 는 **문구마다 폭이 다른 낱장을 이어 붙인 파일**이다.
  낱장 폭 = 글자수 x 32픽셀. 4bpp 라 바이트폭은 그 절반이다.
      上書きしますか？   8자 -> 256px (128B)   <- 이 폭에서 깨끗이 나온다
      読み込みますか？   8자 -> 256px (128B)
      保存しますか？     7자 -> 224px (112B)   <- 256 으로 읽으면 사선으로 밀린다
      複写しますか？     7자 -> 224px
      消去しますか？     7자 -> 224px
  그래서 PITCH 의 128 은 '가장 흔한 폭'일 뿐이고, 고칠 때는 낱장마다
  시작 바이트와 폭을 따로 찾아야 한다. 8자짜리 두 개는 지금 값 그대로 읽힌다.

  PBOOK_FLB0 도 같다. 앞은 64픽셀, 뒤는 96픽셀이다.
      0x0000~0x1FFF  64px x 256행  메모리 카드 라벨 A-1 A-2 B-1 B-2 C-1 C-2 D-1 D-2
      0x2000~0x2BFF  96px x  64행  L 前ページ / 後ページ R   <- book_page_nav.py
  이쪽은 앞부분이 측정한 폭(32바이트=64픽셀)에서 깨끗하게 읽혀서 폭을
  맞췄다고 판단하기 쉬웠다. **앞이 읽힌다고 파일 전체가 그 폭인 것은 아니다.**

  즉 PITCH 는 '그 파일에서 가장 흔한 폭'이고, 자산을 고칠 때는 해당 띠의
  폭을 따로 확인해야 한다.

  PBOOKBG2 는 아직 못 풀었다. 8bpp/4bpp x 폭 5종 x 스위즐 유무를 다 해 봤지만
  전부 잡음이다. 다만 PVN 배경 아틀라스라 글자가 없어서 번역에는 필요 없다.

  .PVN 은 타일 배치표다. 32x32 타일, 격자 20x14 -> 640x448.
  0x28 부터 u32 바이트 오프셋 280개. 전부 0x20 의 배수이고 세로 이동은
  0x2000 단위다 — 8bpp 선형 아틀라스의 (y*pitch + x) 오프셋이다.
"""
import os, sys, struct
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_iso import walk_iso, SRC_ISO, SECTOR
from cmp import decompress

# 자기상관으로 잰 실제 행 폭. swz### 는 '### 로 언스위즐한 뒤 그 폭'이라는 뜻.
PITCH = {
    "PBOOKBG2.CMP":    ("swz", 256), "PBOOKTTL.CMP":    ("lin", 384),
    "PBOOK_AD.CMP":    ("swz", 256), "PBOOK_BS2.CMP":   ("lin",  72),
    "PBOOK_BT1.CMP":   ("lin", 352), "PBOOK_BT2.CMP":   ("swz", 320),
    "PBOOK_EC.CMP":    ("lin", 352), "PBOOK_EC2.CMP":   ("swz", 320),
    "PBOOK_FL4.CMP":   ("4bpp", 128),   # 바이트폭 128 = 256픽셀
    "PBOOK_FL71.CMP":  ("lin", 208),
    "PBOOK_FL72.CMP":  ("lin", 208), "PBOOK_FL73.CMP":  ("lin", 208),
    "PBOOK_FL701.CMP": ("lin",  80), "PBOOK_FL702.CMP": ("lin",  80),
    "PBOOK_FL703.CMP": ("lin",  80), "PBOOK_FL711.CMP": ("lin", 496),
    "PBOOK_FL712.CMP": ("lin", 496), "PBOOK_FL713.CMP": ("lin", 496),
    "PBOOK_FL8.CMP":   ("lin",  80), "PBOOK_FL80.CMP":  ("lin", 128),
    "PBOOK_FL81.CMP":  ("lin", 496), "PBOOK_FL82.CMP":  ("lin", 496),
    "PBOOK_FL83.CMP":  ("lin", 496), "PBOOK_FL83.PCG":  ("lin", 496),
    "PBOOK_FL91A.CMP": ("swz", 512), "PBOOK_RC.CMP":    ("lin",  32),
    "PBOOK_FLB.CMP":   ("lin",  32), "PBOOK_FLB0.CMP":  ("lin",  32),
}

def unswizzle(b, pitch):
    h = len(b) // pitch // 8 * 8
    return b[:pitch*h].reshape(h//8, pitch//16, 8, 16).transpose(0, 2, 1, 3).reshape(h, pitch)

def swizzle(a):
    h, pitch = a.shape
    return a.reshape(h//8, 8, pitch//16, 16).transpose(0, 2, 1, 3).reshape(-1)

def measure_pitch(b, hi=1400):
    """행 폭을 자기상관으로 잰다. 32 미만이 나오면 스위즐된 자료다.

    이건 **첫 추정**일 뿐이다. 진짜 폭의 근처값이 이길 때가 있어서
    (PBOOK_FL4 는 실제 128 인데 112 가 더 낮게 나온다) 눈으로 확인한
    값은 PITCH 표에 적어 둔다. 표가 먼저고 이 함수는 표에 없는 파일용이다.
    약수로 후보를 좁히는 방법도 해 봤지만 16 같은 작은 약수가 이겨서
    오히려 여러 파일이 틀어졌다."""
    b = b.astype(np.int16); n = min(80000, len(b) - hi)
    return min((float(np.abs(b[P:P+n] - b[:n]).mean()), P) for P in range(8, hi))[1]

def to4(b):
    """4bpp 바이트열 -> 픽셀 인덱스 (저니블이 왼쪽 픽셀)"""
    return np.stack([b & 15, b >> 4], 1).reshape(-1)

def from4(px):
    """to4 의 역. 픽셀 수가 홀수면 안 된다."""
    p = px.reshape(-1, 2).astype(np.uint8)
    return (p[:, 0] & 15) | (p[:, 1] << 4)

def decode(name, data):
    """(2차원 인덱스 배열, 되돌리기 정보) 반환"""
    kind, p = PITCH.get(name.upper(), (None, None))
    if kind == "4bpp":
        b = np.frombuffer(data, np.uint8)
        h = len(b) // p
        img = to4(b[:p*h]).reshape(h, p*2)
        return img, ("4bpp", p, bytes(b[p*h:]))
    b = np.frombuffer(data, np.uint8)
    if kind is None:
        p = measure_pitch(b)
        kind = "swz" if p < 32 else "lin"
        if kind == "swz":
            p = min((measure_pitch(unswizzle(b, q).reshape(-1)), q)
                    for q in (256, 320, 384, 448, 496, 512, 640) if len(b) >= q*8)[1]
    # 폭의 배수로 안 떨어지는 파일이 있다. 남는 꼬리는 그대로 들고 있다가
    # 되돌릴 때 붙인다 — 0 으로 채우면 원본과 달라진다.
    h = (len(b) // p // 8 * 8) if kind == "swz" else (len(b) // p)
    used = p * h
    tail = bytes(b[used:])
    img = unswizzle(b[:used], p) if kind == "swz" else b[:used].reshape(h, p)
    return img, (kind, p, tail)

def encode(a, info):
    """decode 의 역."""
    kind, p, tail = info
    if kind == "4bpp": out = from4(a.reshape(-1))
    elif kind == "swz": out = swizzle(a)
    else: out = a.reshape(-1)
    return bytes(out) + tail

def read_iso(name):
    f = open(SRC_ISO, 'rb'); t = walk_iso(f)
    p = [x for x in t if os.path.basename(x).upper() == name.upper()][0]
    _, lba, sz = t[p]; f.seek(lba*SECTOR); d = f.read(sz); f.close()
    return d

def load(name):
    """ISO 에서 읽어 인덱스 이미지로. .CMP 면 압축을 푼다."""
    raw = read_iso(name)
    return decode(name, decompress(raw)[0] if name.upper().endswith('.CMP') else raw)

def pvn_layout(name):
    """.PVN 타일 배치표 -> (타일폭, 타일높이, 격자W, 격자H, 오프셋배열)"""
    d = read_iso(name)
    tw, th = struct.unpack_from('<HH', d, 4)
    gw, gh = struct.unpack_from('<HH', d, 0x1C)
    return tw, th, gw, gh, np.frombuffer(d, '<u4', gw*gh, 0x28)

if __name__ == '__main__':
    from PIL import Image
    out = os.path.join(os.path.dirname(HERE), "test_render", "book")
    os.makedirs(out, exist_ok=True)
    for nm in sorted(PITCH):
        try:
            a, info = load(nm)
            Image.fromarray(a).save(os.path.join(out, f"{nm}.png"))
            print(f"  {nm:<18} {info[0]} 피치{info[1]}  {a.shape[1]}x{a.shape[0]}")
        except Exception as e:
            print(f"  {nm:<18} 실패 {e}")
