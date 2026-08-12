# -*- coding: utf-8 -*-
"""사쿠라대전 고유명사를 용어사전대로 통일한다.

  python tools/glossary.py --check   바꿀 곳만 세어 본다
  python tools/glossary.py           text/*.tsv 의 ko 열을 실제로 고친다

번역할 때 작품 배경을 모른 채 한자를 한 자씩 읽어 버린 자리가 많다.
真宮寺(신구지)를 真-宮-寺 로 끊어 '마미야지'가 된 것이 대표적이다.

**부분 문자열이 겹치는 것을 조심해야 한다.** '이리스'는 이미 맞게 옮긴
'아이리스' 안에 들어 있어서, 그냥 바꾸면 '아아이리스'가 된다. 그래서
앞뒤를 보는 정규식으로 막는다. 맞은 표기와 틀린 표기가 섞여 있는 상태라
(아이리스 3,027 / 이리스 5,058) 한쪽만 보고 판단하면 안 된다.

RULES 는 (정규식, 바꿀말, 설명) 이고 위에서부터 차례로 적용한다.
"""
import os, re, sys, csv, io, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEXT = os.path.join(ROOT, "text")
csv.field_size_limit(1 << 24)

FILES = ['sakura1_adv', 'sakura1_slg', 'sakura2_adv', 'sakura2_evt',
         'sakura2_slg', 'mg_daif', 'elf_sakura1', 'elf_sakura2']

RULES = [
    # 인명 — 한자를 한 자씩 읽어 버린 것
    (r'마미야지',        '신구지',   '真宮寺 — 真:마 宮:미야 寺:지 로 끊어 읽은 오류'),
    # 大神 은 おおがみ. 장음을 살린다. '오오가미' 는 아직 한 번도 안 쓰였다.
    (r'오가미',          '오오가미', '大神'),
    # アイリス. 이미 맞게 쓴 '아이리스' 안의 '이리스' 는 건드리면 안 된다.
    (r'(?<!아)이리스',   '아이리스', 'アイリス'),
    # 조직·병기
    (r'꽃조',            '화조',     '花組'),
    (r'코부',            '광무',     '光武 — 코부(음독)가 아니라 광무'),
]

def apply(s):
    n = 0
    for pat, rep, _ in RULES:
        s, k = re.subn(pat, rep, s)
        n += k
    return s, n

def run(check_only=False):
    total = collections.Counter(); rows_changed = 0
    for fn in FILES:
        p = os.path.join(TEXT, fn + '.tsv')
        if not os.path.exists(p): continue
        with open(p, encoding='utf-8-sig', newline='') as f:
            rd = csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
            cols = rd.fieldnames
            rows = list(rd)
        hit = 0
        for r in rows:
            ko = r.get('ko') or ''
            if not ko: continue
            new, n = apply(ko)
            if n:
                r['ko'] = new; hit += 1
                for pat, rep, _ in RULES:
                    c = len(re.findall(pat, ko))
                    if c: total[rep] += c
        rows_changed += hit
        print(f"  {fn:<14} {hit:>6}행")
        if not check_only and hit:
            with open(p, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.DictWriter(f, cols, delimiter='\t', lineterminator='\n',
                                   quoting=csv.QUOTE_NONE, escapechar=None)
                w.writeheader(); w.writerows(rows)
    print(f"\n고친 행 {rows_changed:,}")
    for k, v in total.most_common(): print(f"    -> {k}  {v:,}회")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    run('--check' in sys.argv)
