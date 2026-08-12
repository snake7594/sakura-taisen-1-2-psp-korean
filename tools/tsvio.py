# -*- coding: utf-8 -*-
"""TSV 를 안전하게 읽고 쓴다.

csv.DictWriter 에 QUOTE_NONE + escapechar 없이 쓰다가 파일이 중간에서
잘린 적이 있다. 필드 안에 따옴표가 하나라도 있으면 writerows 가 예외를
던지는데, 그때는 이미 앞부분이 파일에 쓰인 뒤라 결과가 반쪽짜리로 남는다.

이 TSV 는 줄바꿈을 두 글자 `\\n` 으로 적어 두므로 필드에 진짜 탭이나
개행이 들어갈 일이 없다. 그래서 그냥 탭으로 이어 붙여 쓴다. 대신
**쓰기 전에 검사하고, 임시 파일에 다 쓴 뒤 한 번에 바꿔치기한다.**
그러면 도중에 실패해도 원본이 남는다.
"""
import os, csv

csv.field_size_limit(1 << 24)

def read(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
        return rd.fieldnames, list(rd)

def write(path, cols, rows):
    for i, r in enumerate(rows):
        for c in cols:
            v = r.get(c) or ''
            if '\t' in v or '\n' in v or '\r' in v:
                raise ValueError(f"{path} {i}행 {c} 열에 탭/개행이 들어 있다")
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8-sig', newline='') as f:
        f.write('\t'.join(cols) + '\n')
        for r in rows:
            f.write('\t'.join((r.get(c) or '') for c in cols) + '\n')
    os.replace(tmp, path)          # 다 쓴 뒤 한 번에 바꾼다
