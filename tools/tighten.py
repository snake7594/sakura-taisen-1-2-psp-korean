# -*- coding: utf-8 -*-
"""
원문보다 줄이 늘어난 행을, 들어간다면 원문 줄 수로 되돌린다.

  python tighten.py [--dry]

rewrap.py 가 길이를 맞추려고 줄을 하나 늘린 행들이 있다. 그 뒤 fit_lines.py 로
문장이 짧아졌으니, 이제 원래 줄 수에 다시 담기는 것들이 생긴다.
담기지 않으면 그대로 둔다 — 길이 초과가 줄 수 초과보다 나쁘기 때문이다.
"""
import os, sys, csv, io

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
csv.field_size_limit(1 << 24)
import rewrap, shorten

TEXT = r"D:\psp\사쿠라대전1_2\text"
NL = '\\n'

def fold(text, lim, jn):
    """text 를 jn 줄에 담아 본다. 되면 접은 결과, 안 되면 None"""
    words = rewrap.atoms(rewrap.SP.join(text.split(NL)))
    if not words: return None
    lines = rewrap.wrap(words, lim)
    if len(lines) <= jn and all(rewrap.vis(x) <= lim for x in lines):
        return NL.join(lines)
    return None

def main():
    dry = '--dry' in sys.argv
    tot = left = 0
    for fn, lim in rewrap.FILES:
        p = os.path.join(TEXT, fn)
        if not os.path.exists(p): continue
        with open(p, encoding='utf-8-sig', newline='') as f:
            rd = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
            hdr = next(rd); rows = list(rd)
        ja_i, ko_i = hdr.index('ja'), hdr.index('ko')
        n = l = 0
        for r in rows:
            if len(r) <= ko_i: continue
            ko = r[ko_i].strip()
            if not ko or rewrap.has_half(r[ja_i]): continue
            kn, jn = len(ko.split(NL)), len(r[ja_i].split(NL))
            if kn <= jn: continue
            got = fold(ko, lim, jn)
            if got is None:
                # shorten.py 의 기계적 축약을 하나씩 더해 가며 다시 시도한다.
                # 그 도구는 '길이가 넘친 줄'만 손보므로 여기까지는 닿지 않았다.
                cur = ko
                for pat, rep in shorten.STEPS:
                    new = pat.sub(rep, cur)
                    if new == cur: continue
                    cur = new
                    got = fold(cur, lim, jn)
                    if got is not None: break
            if got is not None:
                r[ko_i] = got; n += 1
            else:
                l += 1
        tot += n; left += l
        print(f"  {fn:<20} 줄 수 되돌림 {n:>4}행 | 그대로 둠 {l}")
        if n and not dry:
            with open(p, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.writer(f, delimiter='\t', lineterminator='\n',
                               quoting=csv.QUOTE_NONE, escapechar=None)
                w.writerow(hdr); w.writerows(rows)
    print(f"\n되돌림 {tot}행, 남은 줄 수 초과 {left}행" + (" (--dry)" if dry else ""))

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
