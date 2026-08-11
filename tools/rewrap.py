# -*- coding: utf-8 -*-
"""
줄 길이가 상한을 넘는 번역문의 **줄바꿈 위치만** 다시 잡는다.

  python rewrap.py [--dry]

번역 내용은 한 글자도 바꾸지 않는다. 띄어쓰기에서 다시 접을 뿐이다.

왜 필요한가
  게임 자간은 고정이라 한 글자가 한 칸이다. 사쿠라1 은 한 줄 21자,
  사쿠라2 는 14자까지 나오고 넘으면 잘린다. 번역기가 원문보다 길게 쓴 줄이
  전체의 3% 남짓 있었다.

규칙
  · 줄 수는 되도록 그대로 둔다. 안 들어가면 한 줄씩 늘리되 3줄까지만.
  · 원문(ja)이 반각을 쓰는 행은 선택지 ID 같은 메타데이터라 건드리지 않는다.
  · 제어 토큰(<XXXX> {XXXX})은 폭 0으로 보고 앞말에 붙여 둔다.
  · 한 낱말이 상한보다 길면 접을 수 없으므로 그대로 두고 보고한다.
"""
import os, sys, csv, io, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
csv.field_size_limit(1 << 24)
TEXT = r"D:\psp\사쿠라대전1_2\text"
FILES = [("sakura1_adv.tsv", 21), ("sakura1_slg.tsv", 21),
         ("sakura2_adv.tsv", 14), ("sakura2_evt.tsv", 14),
         ("sakura2_slg.tsv", 14)]
TOKEN = re.compile(r'<[0-9A-Fa-f]{2}>|<[0-9A-Fa-f]{4}>|\{[0-9A-Fa-f]{4}\}')
MAXLINES_HARD = 4      # 원문 관측 최대 줄 수
SP = '　'                                    # 전각 공백 (fix_chars 가 통일해 둠)

def has_half(s):
    s = TOKEN.sub('', s.replace('\\n', '\n'))
    return any('\x21' <= c <= '\x7e' for c in s)

def vis(s):
    """제어 토큰을 뺀 실제 글자 수 = 화면 폭"""
    return len(TOKEN.sub('', s))

def atoms(text):
    """공백으로 끊되 제어 토큰은 앞말에 붙여 하나의 덩어리로 만든다"""
    out, cur, i = [], '', 0
    while i < len(text):
        m = TOKEN.match(text, i)
        if m:
            cur += m.group(); i = m.end(); continue
        c = text[i]; i += 1
        if c == SP:
            if cur: out.append(cur); cur = ''
        else:
            cur += c
    if cur: out.append(cur)
    return out

def wrap(words, limit):
    """욕심껏 채워 접는다"""
    lines, cur = [], ''
    for w in words:
        cand = w if not cur else cur + SP + w
        if vis(cand) <= limit or not cur:
            cur = cand
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def refold(ko, ja, limit):
    """접기 다시. 안 되면 None

    쓸 수 있는 줄 수는 **원문이 쓰던 줄 수**까지로 본다. 원문이 3줄을 쓰는
    창이면 3줄은 확실히 보인다는 뜻이므로, 거기까지는 늘려도 안전하다."""
    cur_lines = ko.split('\\n')
    if all(vis(l) <= limit for l in cur_lines): return None      # 손댈 것 없음
    words = atoms(SP.join(cur_lines))
    if not words: return None
    if any(vis(w) > limit for w in words): return None           # 낱말 하나가 너무 김
    lines = wrap(words, limit)
    ja_n = len(ja.split('\\n'))
    allowed = max(len(cur_lines), ja_n)
    if ja_n >= 2:                       # 원문이 여러 줄 = 대사창. 3줄은 확실히 보인다
        allowed = max(allowed, 3)       # (원문 관측: 99% 가 3줄 이하, 최대 4줄)
    allowed = min(allowed, MAXLINES_HARD)
    if len(lines) > allowed: return None
    return '\\n'.join(lines)

def main():
    dry = '--dry' in sys.argv
    tot_fix = tot_left = 0
    left_ex = []
    for fn, lim in FILES:
        p = os.path.join(TEXT, fn)
        if not os.path.exists(p): continue
        with open(p, encoding='utf-8-sig', newline='') as f:
            rd = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
            hdr = next(rd); rows = list(rd)
        k_i, ja_i, ko_i = hdr.index('key'), hdr.index('ja'), hdr.index('ko')
        fixed = left = grew = 0
        for r in rows:
            if len(r) <= ko_i: continue
            ko = r[ko_i].strip()
            if not ko or has_half(r[ja_i]): continue
            if all(vis(l) <= lim for l in ko.split('\\n')): continue
            new = refold(ko, r[ja_i], lim)
            if new is None:
                left += 1
                if len(left_ex) < 8:
                    bad = [l for l in ko.split('\\n') if vis(l) > lim]
                    left_ex.append((r[k_i], lim, bad[0] if bad else ko))
                continue
            if len(new.split('\\n')) > len(ko.split('\\n')): grew += 1
            r[ko_i] = new; fixed += 1
        tot_fix += fixed; tot_left += left
        print(f"  {fn:<20} 상한{lim:>3}  다시접음 {fixed:>5}행 (줄 늘어남 {grew}) | 못　접음 {left}")
        if fixed and not dry:
            with open(p, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.writer(f, delimiter='\t', lineterminator='\n',
                               quoting=csv.QUOTE_NONE, escapechar=None)
                w.writerow(hdr); w.writerows(rows)
    print(f"\n다시 접은 행 {tot_fix}, 못 접은 행 {tot_left}" + (" (--dry)" if dry else ""))
    for k, lim, s in left_ex:
        print(f"   [{k}] 상한{lim}  {s}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
