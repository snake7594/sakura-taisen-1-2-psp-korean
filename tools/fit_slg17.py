# -*- coding: utf-8 -*-
"""사쿠라1 전투(SLG) 대사를 한 줄 17자에 맞춘다.

  python tools/fit_slg17.py [--dry]

**전투 대사창은 ADV 대사창보다 좁다.** 제보 스크린샷에서
「한 번에 두 행동을 할 수 있습」 이 17자에서 접히고, 그 바람에 줄이 하나
밀려 마지막 줄이 화면 밖으로 나갔다. 여태 21자로 검사해 와서 못 잡았다.

  ADV  21자 x 3줄
  전투 17자 x 3줄   <- 이 파일이 다루는 것

접히면 4줄이 되는 행이 118개 있었다. 게임이 스스로 접기 때문에 TSV 에서
3줄이어도 화면에서는 4줄이 되어 마지막 줄이 잘린다.

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
LIM, MAXL = 17, 3

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
    p = os.path.join(TEXT, 'sakura1_slg.tsv')
    cols, rows = tsvio.read(p)
    fixed, stuck = [], []
    for r in rows:
        ko = r.get('ko') or ''
        if not ko: continue
        ls = ko.split(NL)
        # 이미 17자 안이고 줄 수도 괜찮으면 건드리지 않는다
        if all(width(l) <= LIM for l in ls) and len(ls) <= MAXL: continue
        merged = '　'.join(l.strip('　') for l in ls if l)
        new = wrap(merged, LIM)
        if len(new) <= MAXL and all(width(l) <= LIM for l in new):
            r['ko'] = NL.join(new); fixed.append(r['key'])
        else:
            stuck.append((r['key'], len(new), max(width(l) for l in new), merged))
    print(f"  다시 접어 해결 {len(fixed)}행,  못 맞춘 것 {len(stuck)}행")
    for k, n, w, s in stuck[:14]:
        print(f"    {k}  {n}줄 최장{w}자  {s[:44]}")
    if not dry and fixed:
        tsvio.write(p, cols, rows)
        print(f"      -> {p}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    run('--dry' in sys.argv)
