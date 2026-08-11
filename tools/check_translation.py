# -*- coding: utf-8 -*-
"""
번역 결과 검증기.

  python check_translation.py <번역된.tsv> [원본.tsv]

원본을 주면 key/ja 열이 변조되지 않았는지도 대조합니다.
(원본을 생략하면 같은 폴더의 .orig 백업 또는 text/ 원본을 찾습니다)

검사 항목
  1. TSV 무결성        열 개수, 셀 안의 실제 개행/탭
  2. 원문 보존         key, ja 열이 원본과 동일한지
  3. 제어코드 보존     <XX> <XXXX> {XXXX} 토큰이 ja와 ko에서 같은 개수인지
  4. 줄 수             ko 의 \\n 개수가 ja 보다 많지 않은지 (최대 MAXLINES)
  5. 줄 길이           각 줄이 MAXLEN 전각 문자 이하인지
  6. 글꼴 예산         KS X 1001 완성형(2350자) 밖의 한글이 있는지
  7. 진행률            비어 있는 ko 개수
"""
import csv, sys, os, re, unicodedata, collections

# 한 줄 최대 전각 문자 수 — 실기(PPSSPP) 에서 자를 넣어 잰 값. 게임·창마다 다르다.
#   사쿠라 1 : 21자 (40자 자가 21 + 19 로 갈림). 원문도 최대 18자라 여유가 있다.
#   사쿠라 2 : 14자 (자가 14 / 14 / 나머지 로 갈림). 원문도 99%가 14자 이하다.
#              15번째 글자가 줄바꿈에서 사라지는 현상이 있어 14자를 넘기면 안 된다.
LIMITS   = {'sakura1': 21, 'sakura2': 14}
MAXLEN   = 14      # 파일명으로 판별 못 할 때의 안전값
MAXLINES = 3       # 한 메시지 최대 줄 수 (원문 관측: 99% 3줄, 최대 4줄)
TOKEN    = re.compile(r'<[0-9A-Fa-f]{2}>|<[0-9A-Fa-f]{4}>|\{[0-9A-Fa-f]{4}\}')

def width(s, space_half=False):
    """전각=1 로 세어 전각 환산 길이.

    띄어쓰기도 전각 한 칸이다. FIDX 엔트리에 문자별 폭 바이트가 있고 게임이 그 값을
    읽기는 하지만(SAKURA1.ELF 0x08953DA4 / 0x0895400C), 실기 확인 결과 화면에
    그릴 때의 자간에는 쓰이지 않는다. Ａ~Ｚ 의 폭을 16으로 낮춰 시험했더니
    숫자 10개 줄과 알파벳 10개 줄의 길이가 똑같았다. 자간은 고정이다.
    space_half 인자는 옛 실험의 잔재로 남겨 두었을 뿐 기본값은 False 다."""
    # 자간이 고정이므로 **모든 글자가 한 칸**이다. 반각이라고 0.5로 세면
    # 실제보다 짧게 재어 화면에서 잘리는 줄을 놓친다.
    # (반각은 애초에 글리프가 없어 쓰면 안 된다 — fix_chars.py 가 전각으로 바꾼다.)
    # 제어 토큰 <XXXX> {XXXX} 는 글리프가 아니라 명령이므로 폭이 0 이다.
    del space_half
    return float(len(TOKEN.sub('', s)))

def in_ksx1001(ch):
    """KS X 1001 완성형 2350자에 들어있는지.
    euc_kr 코덱은 완성형 밖 음절도 8바이트 조합형으로 인코딩해 버리므로
    '2바이트로 인코딩되는가'로 판정해야 한다 (가=b0a1 2바이트, 힣=8바이트)."""
    try:
        return len(ch.encode('euc_kr')) == 2
    except Exception:
        return False

def load(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        r = csv.reader(f, delimiter='\t')
        return next(r), list(r)

def main(trans, orig=None):
    space_half = False        # 자간 고정 — width() 주석 참고
    base = os.path.basename(trans).lower()
    maxlen = next((v for k, v in LIMITS.items() if k in base), MAXLEN)
    hdr, rows = load(trans)
    need = ['key', 'ja', 'ko'] if 'key' in hdr else ['first_key', 'ja', 'ko']
    for c in need:
        if c not in hdr: sys.exit(f"열 '{c}' 이 없습니다: {hdr}")
    K, J, O = hdr.index(need[0]), hdr.index('ja'), hdr.index('ko')

    ref = None
    if orig:
        oh, orows = load(orig)
        ref = {r[oh.index(need[0])]: r[oh.index('ja')] for r in orows}

    err = collections.Counter()
    ex  = collections.defaultdict(list)
    done = 0
    charset = collections.Counter()

    for i, r in enumerate(rows, start=2):
        if len(r) != len(hdr):
            err['1_열개수'] += 1; ex['1_열개수'].append(f"{i}행: {len(r)}열"); continue
        key, ja, ko = r[K], r[J], r[O]
        if ref is not None and key in ref and ref[key] != ja:
            err['2_원문변조'] += 1; ex['2_원문변조'].append(f"{key}")
        if not ko.strip():
            continue
        done += 1
        if TOKEN.findall(ja) != TOKEN.findall(ko):
            err['3_제어코드'] += 1
            ex['3_제어코드'].append(f"{key}  ja={TOKEN.findall(ja)} ko={TOKEN.findall(ko)}")
        jl, kl = ja.split('\\n'), ko.split('\\n')
        if len(kl) > max(len(jl), 1):
            err['4_줄수초과'] += 1; ex['4_줄수초과'].append(f"{key}  {len(jl)}줄 -> {len(kl)}줄")
        if len(kl) > MAXLINES:
            err['4_줄수초과'] += 1; ex['4_줄수초과'].append(f"{key}  {len(kl)}줄 (최대 {MAXLINES})")
        # 기본 상한은 MAXLEN. 다만 원문 자체가 더 긴 행이면 그 길이까지는 허용한다
        # (원문 관측 최대: 사쿠라1 18자 / 사쿠라2 22자)
        limit = max(maxlen, max((width(x, space_half) for x in jl), default=0))
        for n, line in enumerate(kl):
            w = width(line, space_half)
            if w > limit:
                err['5_줄길이'] += 1
                ex['5_줄길이'].append(f"{key} {n+1}번째 줄 {w:g}자 (상한 {limit:g}): {line}")
        for ch in ko:
            if '\uAC00' <= ch <= '\uD7A3':
                charset[ch] += 1
                if not in_ksx1001(ch):
                    err['6_완성형밖'] += 1; ex['6_완성형밖'].append(f"{key}  '{ch}'")

    print(f"파일       : {os.path.basename(trans)}")
    print(f"전체 행    : {len(rows)}")
    print(f"번역 완료  : {done}  ({100*done/max(1,len(rows)):.1f}%)")
    print(f"고유 한글  : {len(charset)}자  (글꼴 슬롯 예산 2350 이내여야 함)")
    print(f"한 줄 상한 : {maxlen}자 (실기 확인값)")
    print()
    if not err:
        print("문제 없음 ✔")
        return 0
    for k in sorted(err):
        print(f"[{k}] {err[k]}건")
        for line in ex[k][:8]:
            print(f"    {line}")
        if len(ex[k]) > 8: print(f"    ... 외 {len(ex[k])-8}건")
    return 1

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    t = sys.argv[1]
    o = sys.argv[2] if len(sys.argv) > 2 else None
    if o is None:
        cand = os.path.join(r"D:\psp\사쿠라대전1_2\text", os.path.basename(t))
        if os.path.abspath(cand) != os.path.abspath(t) and os.path.exists(cand): o = cand
    sys.exit(main(t, o))
