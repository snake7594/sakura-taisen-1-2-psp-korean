# -*- coding: utf-8 -*-
"""용어사전을 적용한 뒤 한 칸씩 넘친 줄을 맞춘다.

  python tools/fit_after_glossary.py [--dry]

'오가미'→'오오가미', '이리스'→'아이리스' 로 글자가 한 칸 늘면서 사쿠라2
(한 줄 14자)에서 15자가 된 줄이 생겼다. 뜻을 건드리지 않고 **전각 공백을
하나 덜어** 맞춘다. 쉼표 뒤 공백을 먼저 지운다 — 거기가 가장 덜 어색하다.

줄 수가 늘어난 것(2줄 -> 3줄)은 rewrap 이 접어 놓은 것이라, 공백을 덜어
다시 두 줄에 들어가면 원래대로 돌아간다.
"""
import os, re, sys, csv, io

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT = os.path.join(os.path.dirname(HERE), "text")
csv.field_size_limit(1 << 24)
TOK = re.compile(r'<[^>]*>')
NL  = '\\n'                      # TSV 안에서는 두 글자로 들어 있다

FILES = {'sakura2_adv': 14, 'sakura2_evt': 14, 'sakura1_slg': 21}

def width(s): return len(TOK.sub('', s))

def squeeze(line, lim):
    """전각 공백을 하나씩 덜어 상한에 맞춘다. 쉼표·마침표 뒤부터."""
    order = [r'([，．！？])　', r'(　)']          # 앞엣것부터 지운다
    while width(line) > lim:
        for pat in order:
            new = re.sub(pat, lambda m: m.group(1) if m.lastindex and
                         m.group(1) not in '　' else '', line, count=1)
            if new != line:
                line = new; break
        else:
            return line, False                    # 더 뺄 공백이 없다
    return line, True

def run(dry=False):
    for fn, lim in FILES.items():
        p = os.path.join(TEXT, fn + '.tsv')
        if not os.path.exists(p): continue
        with open(p, encoding='utf-8-sig', newline='') as f:
            rd = csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
            cols = rd.fieldnames; rows = list(rd)
        fixed = stuck = 0
        for r in rows:
            ko = r.get('ko') or ''
            if not ko: continue
            ja = r.get('ja') or ''
            lines = ko.split(NL)
            out, ok_all = [], True
            for l in lines:
                if width(l) <= lim: out.append(l); continue
                nl, ok = squeeze(l, lim)
                out.append(nl); ok_all &= ok
            new = NL.join(out)
            # 줄 수가 원문보다 늘었으면 다시 붙여 본다
            if len(out) > len(ja.split(NL)) and len(out) >= 2:
                merged = out[:-2] + [out[-2] + out[-1]]
                if width(merged[-1]) <= lim: new = NL.join(merged)
            if new != ko:
                r['ko'] = new
                fixed += 1
                if not ok_all: stuck += 1
        print(f"  {fn:<14} 손본 행 {fixed:>4}" + (f"  (못 맞춘 줄 있음 {stuck})" if stuck else ""))
        if not dry and fixed:
            with open(p, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.DictWriter(f, cols, delimiter='\t', lineterminator='\n',
                                   quoting=csv.QUOTE_NONE, escapechar=None)
                w.writeheader(); w.writerows(rows)

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    run('--dry' in sys.argv)
