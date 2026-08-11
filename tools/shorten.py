# -*- coding: utf-8 -*-
"""
줄바꿈을 다시 잡아도 상한을 못 맞추는 행을, **뜻을 바꾸지 않는 축약**으로 줄인다.

  python shorten.py [--dry]

rewrap.py 를 먼저 돌린 뒤에 쓴다. 여기서 줄이는 것은 글자 모양뿐이다.
    · 문장부호 옆의 군더더기 공백   「 앞, 」 뒤, ， 뒤 …
    · 말줄임표 ……  ->  …
    · 겹친 공백
한 단계씩 적용해 보고 상한에 들어가면 거기서 멈춘다. 그래도 안 되면 그대로 둔다.
번역 낱말 자체는 손대지 않는다 — 그건 사람이 정할 일이다.
"""
import os, sys, csv, io, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
csv.field_size_limit(1 << 24)
import rewrap

TEXT = r"D:\psp\사쿠라대전1_2\text"
FILES = rewrap.FILES
SP = rewrap.SP

# 위에서부터 차례로 적용한다 (앞이 더 안전하다)
STEPS = [
    (re.compile(SP + '{2,}'), SP),                    # 겹친 공백
    (re.compile(SP + '([」』）］】])'), r'\1'),        # 닫는 괄호 앞 공백
    (re.compile('([「『（［【])' + SP), r'\1'),        # 여는 괄호 뒤 공백
    (re.compile('([，、])' + SP), r'\1'),              # 쉼표 뒤 공백
    (re.compile('……'), '…'),                          # 말줄임표 줄이기
    (re.compile('([！？])' + SP), r'\1'),              # 느낌표·물음표 뒤 공백
]

def fits(ko, ja, lim):
    lines = ko.split('\\n')
    return all(rewrap.vis(l) <= lim for l in lines)

def try_shorten(ko, ja, lim):
    """단계를 하나씩 더해 가며 접기를 다시 해 본다. 되면 그 결과를 돌려준다."""
    cur = ko
    for pat, rep in STEPS:
        new = pat.sub(rep, cur)
        if new == cur: continue
        cur = new
        folded = rewrap.refold(cur, ja, lim)
        if folded is not None: return folded
        if fits(cur, ja, lim): return cur
    return None

def main():
    dry = '--dry' in sys.argv
    tot_fix = tot_left = 0
    for fn, lim in FILES:
        p = os.path.join(TEXT, fn)
        if not os.path.exists(p): continue
        with open(p, encoding='utf-8-sig', newline='') as f:
            rd = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
            hdr = next(rd); rows = list(rd)
        ja_i, ko_i = hdr.index('ja'), hdr.index('ko')
        fixed = left = 0
        for r in rows:
            if len(r) <= ko_i: continue
            ko = r[ko_i].strip()
            if not ko or rewrap.has_half(r[ja_i]): continue
            if fits(ko, r[ja_i], lim): continue
            new = try_shorten(ko, r[ja_i], lim)
            if new is None: left += 1; continue
            r[ko_i] = new; fixed += 1
        tot_fix += fixed; tot_left += left
        print(f"  {fn:<20} 상한{lim:>3}  줄임으로 해결 {fixed:>5}행 | 남음 {left}")
        if fixed and not dry:
            with open(p, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.writer(f, delimiter='\t', lineterminator='\n',
                               quoting=csv.QUOTE_NONE, escapechar=None)
                w.writerow(hdr); w.writerows(rows)
    print(f"\n해결 {tot_fix}행, 남은 초과 {tot_left}행" + (" (--dry)" if dry else ""))

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
