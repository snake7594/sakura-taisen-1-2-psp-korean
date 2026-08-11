# -*- coding: utf-8 -*-
"""
번역문(ko 열)을 게임 글꼴에 맞게 손본다.

  python fix_chars.py                    text/ 의 네 TSV 를 손본다
  python fix_chars.py --dry              바꾸지 않고 무엇이 걸리는지만 본다

세 가지를 처리한다.

1. 유니코드가 다른 닮은꼴 문자
   번역기가 Shift-JIS 에 없는 비슷한 글자를 쓰는 일이 있다. 게임 글꼴은
   Shift-JIS 표의 글리프 + 한글로 대체한 ku16~ku40 뿐이라 그 밖의 문자는
   encode.py 에서 EncodeError 가 난다. SUBST 는 "생김새가 같고 Shift-JIS 에
   있는" 글자로만 잇는다. 뜻이 달라지는 치환은 하지 않는다.

2. 반각 ASCII -> 전각
   반각에는 글리프가 없어 화면에 **아무것도 안 나온다**(사쿠라2 자 테스트에서
   반각 숫자가 안 보이다가 전각으로 바꾸니 보였다). 자간은 고정이라 반각도
   한 칸을 먹으므로, 전각으로 바꿔도 줄 폭은 그대로고 글자만 보이게 된다.
   다만 원문이 반각을 쓰는 줄은 선택지 ID 같은 스크립트 메타데이터라
   건드리면 게임 로직이 깨진다. 그런 줄은 **줄 단위로 가려서** 남겨 둔다.
   공백은 어차피 안 보이므로 반각 그대로 둔다.

3. 한글이 가져간 슬롯과 겹치는 일본어 한자 알림
   한글 2350자가 ku16~ku40(JIS 1수준 한자) 자리를 쓰므로 그 자리 한자는
   글리프가 없다. 번역문에 남아 있으면 엉뚱한 한글이 화면에 뜬다.
   여기서는 찾아서 알리기만 한다 (무엇으로 바꿀지는 사람이 정해야 한다).
"""
import os, sys, csv, io, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
csv.field_size_limit(1 << 24)
from make_hangul_font import SJIS_OF, GAIJI
from encode import GAIJI_S2, TOKEN

TAKEN = set(SJIS_OF.values())        # 한글이 가져간 SJIS 코드 (원래 JIS 1수준 한자)

TEXT = r"D:\psp\사쿠라대전1_2\text"
FILES = [("sakura1_adv.tsv", GAIJI), ("sakura1_slg.tsv", GAIJI),
         ("sakura2_adv.tsv", GAIJI_S2), ("sakura2_evt.tsv", GAIJI_S2),
         ("sakura2_slg.tsv", GAIJI_S2)]

# 유니코드가 다를 뿐 같은 글자 -> Shift-JIS 에 있는 쪽
SUBST = {
    '\u00B7': '\u30FB',   # · 가운뎃점      -> ・ 전각 중점 (SJIS 0x8145)
    '\u2022': '\u30FB',   # • 불릿          -> ・
    '\u2219': '\u30FB',   # ∙ 연산자 점      -> ・
    '\u2014': '\u2015',   # — em dash       -> ― 가로줄 (SJIS 0x815C)
    '\u2012': '\u2015',   # ‒ figure dash   -> ―
    '\u2013': '\u2015',   # – en dash       -> ―
    '\u301C': '\uFF5E',   # 〜 물결표        -> ～ (SJIS 0x8160)
    '\u2212': '\uFF0D',   # − 빼기          -> － 전각 하이픈 (SJIS 0x817C)
    '\u00A0': '\u3000',   # 줄바꿈없는 공백  -> 전각 공백
}

def has_half(s):
    """제어 토큰과 이스케이프를 뺀 뒤 반각 출력 문자(공백 제외)가 있는지.

    공백을 빼는 이유: 원문에도 대사에도 흔해서 이것으로는 메타데이터를
    가려낼 수 없기 때문이다. 숫자·영문·문장부호만 본다."""
    s = TOKEN.sub('', s.replace('\\n', '\n').replace('\\t', '\t'))
    return any('\x21' <= c <= '\x7e' for c in s)

def to_full(s):
    """반각 ASCII -> 전각. 공백도 전각 공백으로. 제어 토큰은 그대로 둔다.

    사쿠라1 의 FIDX 는 `sjis - 0x8000` 으로 색인하고 사쿠라2 의 drawChar 는
    0x8140~0xEAA4 만 받으므로, 반각 코드(0x20~0x7E)는 양쪽 다 글리프가 없다.
    공백까지 전각으로 바꿔야 띄어쓰기가 확실히 한 칸을 차지한다."""
    out, i = [], 0
    while i < len(s):
        if s.startswith('\\n', i) or s.startswith('\\t', i):
            out.append(s[i:i+2]); i += 2; continue
        m = TOKEN.match(s, i)
        if m:
            out.append(m.group()); i = m.end(); continue
        c = s[i]; i += 1
        if c == ' ':                       out.append('　')
        elif '\x21' <= c <= '\x7e':        out.append(chr(ord(c) + 0xFEE0))
        else:                              out.append(c)
    return ''.join(out)

def widen(ja, ko):
    """ko 의 반각을 전각으로. 원문이 반각을 쓰는 줄(메타데이터)은 남긴다."""
    if not has_half(ja):
        return to_full(ko)
    jl, kl = ja.split('\\n'), ko.split('\\n')
    if len(jl) != len(kl):
        return ko                       # 줄이 어긋나면 손대지 않는다
    return '\\n'.join(k if has_half(j) else to_full(k) for j, k in zip(jl, kl))

def unencodable(text, gaiji):
    """폰트로 못 넣는 문자들"""
    out, i = [], 0
    while i < len(text):
        m = TOKEN.match(text, i)
        if m: i = m.end(); continue
        ch = text[i]; i += 1
        if ch == '\n' or ch in gaiji or ch in SJIS_OF: continue
        if ' ' <= ch <= '~': continue
        try:
            if len(ch.encode('cp932')) != 2: out.append(ch)
        except Exception:
            out.append(ch)
    return out

def clashes(s):
    """한글이 가져간 슬롯(ku16~ku40)과 겹쳐 글리프가 없는 문자"""
    out = []
    for ch in s:
        if '가' <= ch <= '힣': continue
        try: b = ch.encode('cp932')
        except Exception: continue
        if len(b) == 2 and ((b[0] << 8) | b[1]) in TAKEN: out.append(ch)
    return out

def main():
    dry = '--dry' in sys.argv
    grand = collections.Counter(); left = collections.Counter()
    n_wide = 0; clash_rows = []
    for fn, gj in FILES:
        p = os.path.join(TEXT, fn)
        if not os.path.exists(p): continue
        with open(p, encoding='utf-8-sig', newline='') as f:
            rd = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
            hdr = next(rd); rows = list(rd)
        ko_i, ja_i, k_i = hdr.index('ko'), hdr.index('ja'), hdr.index('key')
        hit = collections.Counter(); nw = 0
        for r in rows:
            if len(r) <= ko_i: continue
            s = r[ko_i]
            if not s: continue
            new = s
            for a, b in SUBST.items():
                if a in new:
                    hit[a] += new.count(a); new = new.replace(a, b)
            w = widen(r[ja_i], new)
            if w != new: nw += 1
            new = w
            if new != s: r[ko_i] = new
            for ch in unencodable(new.replace('\\n', '\n'), gj):
                left[ch] += 1
            c = clashes(new)
            if c: clash_rows.append((r[k_i], ''.join(sorted(set(c))), new[:60]))
        grand.update(hit); n_wide += nw
        print(f"  {fn:<20} 닮은꼴 치환 {sum(hit.values()):>5}자 | 전각화 {nw:>6}행")
        if not dry and (hit or nw):
            with open(p, 'w', encoding='utf-8-sig', newline='') as f:
                w2 = csv.writer(f, delimiter='\t', lineterminator='\n',
                                quoting=csv.QUOTE_NONE, escapechar=None)
                w2.writerow(hdr); w2.writerows(rows)
    print(f"\n닮은꼴 치환 {sum(grand.values())}자, 전각화 {n_wide}행"
          + (" (--dry, 저장 안 함)" if dry else ""))
    if left:
        print("아직 넣을 수 없는 문자:")
        for ch, n in left.most_common():
            print(f"   {ch!r} U+{ord(ch):04X}  {n}회")
    else:
        print("남은 인코딩 불가 문자 없음 ✔")
    if clash_rows:
        print(f"\n한글 슬롯과 겹쳐 깨지는 일본어가 남은 행 {len(clash_rows)}개:")
        for k, c, s in clash_rows[:20]:
            print(f"   [{k}] {c}  {s}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
