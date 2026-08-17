# -*- coding: utf-8 -*-
"""대사를 창 너비에 맞춰 다시 접는다.

  python tools/fit_lines.py --dry    검사만
  python tools/fit_lines.py          text/*.tsv 를 고친다

**창마다 한 줄 글자 수가 다르다.** 이걸 몰라서 두 번 사고를 냈다.

    사쿠라1 대사창   18자 x 3줄
    사쿠라1 전투창   17자 x 3줄
    사쿠라2          14자 x 3줄

대사창을 21자로 알고 있었다. 실기 사진에서

    오오가미　이치로，　분골쇄신의　각오로   (19자)

가 18자에서 접히고, 그 바람에 줄이 하나 밀려 마지막 줄이 화면 밖으로
나갔다. 얼굴 그림이 붙은 대사창은 글자 시작 위치가 오른쪽으로 밀려서
21자가 아니라 18자만 들어간다.

**가장 믿을 만한 근거는 원문이다.** 원문 한 줄의 최대 길이를 세어 보면

    sakura1_adv  최대 18자 (18자 2줄, 17자 3줄, 16자 13줄, 나머지는 15자 이하)
    sakura1_slg  최대 17자
    sakura2_adv  최대 15자

일본어 대본 자체가 그 폭에 맞춰 쓰여 있다. 창 너비를 재는 것보다 이게 낫다.

띄어쓰기에서 다시 접기만 한다. 그래도 3줄에 안 들어가면 손으로 줄여야
하므로 목록을 찍어 준다.
"""
import os, re, sys, io

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tsvio

TEXT = os.path.join(os.path.dirname(HERE), "text")
TOK  = re.compile(r'<[^>]*>')
NL   = chr(92) + 'n'
MAXL = 3

# 파일 -> 한 줄 최대 글자 수
LIMITS = {
    'sakura1_adv.tsv': 18,
    'sakura1_slg.tsv': 17,
    'sakura2_adv.tsv': 14,
    'sakura2_evt.tsv': 14,
    'sakura2_slg.tsv': 14,
}

def width(s): return len(TOK.sub('', s))

def wrap(text, lim):
    """전각 공백에서 접는다. 토큰은 폭 0 이라 그대로 따라간다."""
    words = text.split('　')
    out, cur = [], ''
    for w in words:
        cand = w if not cur else cur + '　' + w
        if width(cand) <= lim or not cur:
            cur = cand
        else:
            out.append(cur); cur = w
    if cur: out.append(cur)
    return out

def run(dry=False):
    for fn, lim in LIMITS.items():
        p = os.path.join(TEXT, fn)
        if not os.path.exists(p): continue
        cols, rows = tsvio.read(p)
        fixed, stuck = [], []
        for r in rows:
            ko = r.get('ko') or ''
            if not ko: continue
            ls = ko.split(NL)
            if all(width(l) <= lim for l in ls) and len(ls) <= MAXL: continue
            merged = '　'.join(l.strip('　') for l in ls if l)
            new = wrap(merged, lim)
            if len(new) <= MAXL and all(width(l) <= lim for l in new):
                r['ko'] = NL.join(new); fixed.append(r['key'])
            else:
                stuck.append((r['key'], len(new), max(width(l) for l in new), merged))
        print(f"  {fn:<18} {lim}자  다시 접어 해결 {len(fixed)}행,  못 맞춘 것 {len(stuck)}행")
        for k, n, w, s in stuck[:12]:
            print(f"      {k}  {n}줄 최장{w}자  {s[:46]}")
        if not dry and fixed:
            tsvio.write(p, cols, rows)

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    run('--dry' in sys.argv)
