# -*- coding: utf-8 -*-
"""
flags 열의 dup=<key> 를 따라 번역을 복사합니다.

  python propagate_dups.py sakura1_adv.tsv [sakura1_slg.tsv ...]

같은 원문이 여러 번 나오는 행은 번역하지 않고 비워 두면 되고,
이 스크립트가 최초 출현 행의 ko 를 그대로 채워 넣습니다.
파일을 여러 개 주면 파일 사이의 중복도 함께 처리합니다.
"""
import csv, sys, os, shutil

def load(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        r = csv.reader(f, delimiter='\t')
        return next(r), list(r)

def save(p, hdr, rows):
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n',
                       quoting=csv.QUOTE_NONE, escapechar=None)
        w.writerow(hdr); w.writerows(rows)

def main(paths):
    files = []
    for p in paths:
        hdr, rows = load(p)
        for c in ('key', 'flags', 'ja', 'ko'):
            if c not in hdr: sys.exit(f"{p}: '{c}' 열이 없습니다")
        files.append((p, hdr, rows))

    # key -> ko  와  ja -> ko  두 가지 색인
    by_key, by_ja = {}, {}
    for p, hdr, rows in files:
        K, J, O = hdr.index('key'), hdr.index('ja'), hdr.index('ko')
        for r in rows:
            if len(r) == len(hdr) and r[O].strip():
                by_key[r[K]] = r[O]
                by_ja.setdefault(r[J], r[O])

    total = 0
    for p, hdr, rows in files:
        K, F, J, O = (hdr.index('key'), hdr.index('flags'),
                      hdr.index('ja'), hdr.index('ko'))
        n = 0
        for r in rows:
            if len(r) != len(hdr) or r[O].strip(): continue
            src = None
            for part in r[F].split(';'):
                if part.startswith('dup='):
                    src = by_key.get(part[4:]); break
            if src is None: src = by_ja.get(r[J])
            if src:
                r[O] = src; n += 1
        if n:
            shutil.copy2(p, p + '.bak')
            save(p, hdr, rows)
        print(f"  {os.path.basename(p):<24} {n:6d}행 채움")
        total += n
    print(f"합계 {total}행")

if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1:])
