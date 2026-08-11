# -*- coding: utf-8 -*-
"""사쿠라대전 2 책 UI (PBOOKTTL.CMP) 한글판을 만든다.

PBOOKTTL.CMP 는 **CMP 스트림이 두 개 이어 붙은** 파일이다. 이걸 몰라서
한동안 헤맸다 — 앞 스트림만 풀면 종이 질감만 나오고 글자가 안 보인다.

    스트림1  0x000000 ~ 0x035E7C  (압축 220,797B -> 754,176B)  책 표지·종이
    스트림2  0x035E7D ~ 파일 끝    (method0 param0 -> 643,584B)  문자 레이어

문자 레이어는 **열 우선 + 상하 반전 + 4bpp high-nibble-first** 로 저장된다.

    nibble_offset = x*48 + (47 - y)
    stored        = flipud(title).T

그래서 보통의 row-major 이미지로 읽으면 잡음으로만 보인다. 이 변환을 거치면
「오늘의 일정」「옵션」 같은 글자가 그대로 읽힌다.

한글 문자 레이어는 별도 작업(문서 'Stage054B')에서 만들어진 것을 받아 쓴다.
받은 파일은 스트림2 는 정확한데 **스트림1 이 통째로 0 으로 지워져 있었다**
(풀면 754,176 바이트가 전부 0). 책 표지 그림이 사라지므로 그대로 쓰면 안 된다.
그래서 여기서는

    원본의 스트림1 (압축 바이트 그대로)  +  받은 파일의 스트림2

로 이어 붙인다. 재압축하지 않으므로 두 스트림 모두 원래 바이트가 유지되고,
크기도 396,523B 로 원본 슬롯(예산 403,456B) 안에 들어간다.
"""
import os, sys, math
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from cmp import decompress
from build_iso import walk_iso, SRC_ISO, SECTOR

NAME   = "PBOOKTTL.CMP"
ISOP   = "/PSP_GAME/USRDIR/SAKURA2/SAKURA1/" + NAME
DONOR  = os.path.join(ROOT, "책 ui 수정", "성공본", NAME)
BUILD  = os.path.join(ROOT, "build", "patched")
SPLIT  = 220797                      # 스트림1 이 쓰는 압축 바이트 수

def read_iso():
    f = open(SRC_ISO, 'rb'); t = walk_iso(f)
    _, lba, sz = t[ISOP]; f.seek(lba*SECTOR); d = f.read(sz); f.close()
    return d

def char_layer(stream2):
    """문자 레이어를 사람이 보는 방향의 2차원 배열로 (48행)"""
    d = np.frombuffer(stream2, np.uint8)
    nib = np.stack([d >> 4, d & 15], 1).reshape(-1)      # high-nibble-first
    cols = len(nib) // 48
    return np.flipud(nib[:cols*48].reshape(cols, 48).T)

def run(check_only=False):
    orig = read_iso()
    if not os.path.exists(DONOR):
        print(f"  한글 문자 레이어 원본이 없다: {DONOR}"); return
    donor = open(DONOR, 'rb').read()

    merged = orig[:SPLIT] + donor[SPLIT:]
    budget = math.ceil(len(orig)/2048)*2048
    print(f"  원본 {len(orig):,}B  받은것 {len(donor):,}B  합본 {len(merged):,}B  예산 {budget:,}B")
    if len(merged) > budget:
        raise RuntimeError("원본 슬롯을 넘는다")

    # 스트림1 은 원본과 같아야 하고, 스트림2 는 받은 것과 같아야 한다
    s1m = bytes(decompress(merged)[0]);        s1o = bytes(decompress(orig)[0])
    s2m = bytes(decompress(merged[SPLIT:])[0]); s2d = bytes(decompress(donor[SPLIT:])[0])
    assert s1m == s1o,  "스트림1 이 원본과 다르다 — 책 표지가 깨진다"
    assert s2m == s2d,  "스트림2 가 받은 것과 다르다"
    print(f"  스트림1 원본 유지 OK ({len(s1o):,}B)   스트림2 한글판 OK ({len(s2d):,}B)")

    # 받은 파일을 그대로 쓰면 안 되는 이유를 눈으로 남긴다
    z = np.frombuffer(bytes(decompress(donor)[0]), np.uint8)
    print(f"  참고: 받은 파일의 스트림1 은 {100*(z==0).mean():.0f}% 가 0 이다 (그대로 쓰면 표지가 사라진다)")

    if not check_only:
        os.makedirs(BUILD, exist_ok=True)
        q = os.path.join(BUILD, NAME)
        open(q, 'wb').write(merged)
        print(f"      -> {q}")

if __name__ == '__main__':
    run('--check' in sys.argv)
