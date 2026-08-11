# -*- coding: utf-8 -*-
"""
ELF 안에 하드코딩된 일본어 문자열을 뽑고 되넣는다.

  python elf_text.py --dump     text/elf_sakura1.tsv 로 뽑기
  python elf_text.py --check    번역문이 원래 자리에 들어가는지만 검사
  python elf_text.py            build/patched/ 에 패치된 ELF 저장

메뉴 항목·저장 화면 문구·미니게임 대사가 ELF 안에 NUL 종료 문자열로 박혀 있다.
포인터를 건드리지 않으려면 **원래 자리에 원래 길이 이하로** 써야 한다.
남는 자리는 NUL 로 채운다.

인코딩이 두 가지 섞여 있다.
  sjis : 게임이 자기 글꼴로 그리는 문구. 한글은 ku16~ku40 으로 재배치한 코드.
  utf8 : PSP 세이브 목록에 뜨는 문구. PSP 시스템 글꼴이 그리므로 그냥 UTF-8.

키는 파일 오프셋(16진)이다. ELF 가 바뀌지 않는 한 안정적이다.
"""
import os, sys, csv, io, re, struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
csv.field_size_limit(1 << 24)
from make_hangul_font import encode as kencode

ROOT  = r"D:\psp\사쿠라대전1_2"
SRC   = os.path.join(ROOT, "extract", "PSP_GAME", "USRDIR")
TEXT  = os.path.join(ROOT, "text")
BUILD = os.path.join(ROOT, "build", "patched")
ELFS  = {"sakura1": os.path.join(SRC, r"SAKURA1\SAKURA1.ELF"),
         "sakura2": os.path.join(SRC, r"SAKURA2\SAKURA2.ELF")}

# 문자열 후보: 인쇄 가능 바이트가 이어지다 NUL 로 끝나는 것
# Shift-JIS 규칙 그대로: 반각 ASCII 또는 (선두 0x81~0x9F/0xE0~0xEF + 후행 0x40~0xFC)
# 1글자짜리도 받는다 — 「遅」「速」 처럼 한 글자로 된 옵션 항목이 있다.
CAND = re.compile(rb'(?:[\x20-\x7e]|[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc]){1,200}\x00')
JP   = re.compile(r'[ぁ-んァ-ヶ一-龥０-９Ａ-Ｚａ-ｚ　、。・「」（）！？…ー～％]')
KANA = re.compile(r'[ぁ-んァ-ヶ]')

def is_jp(s):
    """진짜 문구인지. 코드 영역의 우연한 바이트열을 걸러낸다.

    가나가 2자 이상이어야 한다 — 한자만 이어진 것은 거의 다 기계어를
    잘못 읽은 것이다. 그리고 문자열의 대부분이 일본어여야 한다."""
    if len(s) < 2: return False
    return len(KANA.findall(s)) >= 2 and len(JP.findall(s)) / len(s) >= 0.7

def is_jp_utf8(s):
    """UTF-8 쪽 판정은 느슨해도 된다.

    3바이트 UTF-8 이 줄줄이 이어져 일본어로 풀리는 것 자체가 이미 강한 신호다.
    sjis 처럼 '가나 2자 이상'을 요구하면 「第一話～帝都・花の華撃団～」처럼
    가나가 「の」 하나뿐인 화 제목을 통째로 놓친다."""
    return len(s) >= 3 and len(JP.findall(s)) / len(s) >= 0.8

def find_utf8(d):
    """UTF-8 로 저장된 일본어 (PSP 세이브 목록용)"""
    out = []
    for m in re.finditer(rb'[\xe0-\xef][\x80-\xbf]{2}'
                         rb'(?:[\x20-\x7e]|[\xe0-\xef][\x80-\xbf]{2}){0,80}\x00', d):
        try: s = m.group()[:-1].decode('utf-8')
        except Exception: continue
        if is_jp_utf8(s): out.append((m.start(), s, 'utf8', len(m.group())-1))
    return out

def find_sjis(d):
    """두 번 훑는다.

    1) 빡빡하게 — 앞 바이트가 NUL 이고 가나가 2자 이상. 이러면 기계어를
       잘못 읽은 후보가 거의 다 걸러지지만, 「決定」「防御」처럼 한자만 있는
       짧은 메뉴 항목도 같이 걸러진다.
    2) 1)에서 찾은 자리 둘레(±0x400)를 '문자열 표 구역'으로 보고, 그 안에서는
       일본어가 한 자만 있어도 받는다. 진짜 표는 문자열이 촘촘히 모여 있다."""
    # 문자열이 시작할 수 있는 자리: 앞이 NUL 이거나 **4바이트 경계**.
    # 포인터 표(u32) 바로 뒤에 문자열이 붙는 곳이 있어서, NUL 만 보면
    # 「カーソル速度」「遅」「速」 같은 옵션 항목을 통째로 놓친다.
    cands = []
    for m in CAND.finditer(d):
        raw = m.group()[:-1]
        try: s = raw.decode('cp932')
        except Exception: continue
        o = m.start()
        start_ok = (o == 0) or (d[o-1] == 0) or (o % 4 == 0)
        cands.append((o, s, len(raw), start_ok))

    seeds = [c[0] for c in cands if c[3] and is_jp(c[1])]
    regions = []
    for o in seeds:
        if regions and o - regions[-1][1] <= 0x400: regions[-1][1] = o + 0x400
        else: regions.append([o - 0x400, o + 0x400])

    def in_region(o):
        for a, b in regions:
            if a <= o <= b: return True
        return False

    out = []
    for off, s, n, nul_before in cands:
        ok = (nul_before and is_jp(s)) or (
            nul_before and in_region(off) and len(JP.findall(s)) >= 1
            and len(JP.findall(s)) / len(s) >= 0.7 and len(s) >= 1)
        if ok: out.append((off, s, 'sjis', n))
    return out

def scan(path):
    d = open(path, 'rb').read()
    rows = find_sjis(d) + find_utf8(d)
    # 겹치는 것 정리 (utf8 이 sjis 후보와 겹칠 수 있다)
    rows.sort()
    out, last_end = [], -1
    for off, s, enc, n in rows:
        if off < last_end: continue
        # 쓸 수 있는 자리 = 문자열 + 뒤에 이어지는 NUL 채움.
        # 문자열들은 4바이트에 맞춰 놓여 있어 뒤에 남는 NUL 이 흔한데,
        # 문자열 길이만 예산으로 잡으면 번역이 공연히 자리 부족이 된다.
        # 종료 NUL 한 바이트는 남겨 둔다.
        e = off + n
        while e < len(d) and d[e] == 0: e += 1
        room = max(n, (e - off) - 1)
        out.append((off, s, enc, room)); last_end = e
    return d, out

FMT = re.compile(r'%[-+ #0]*[0-9]*(?:\.[0-9]+)?[a-zA-Z]')

def enc_bytes(s, enc):
    """sjis 는 게임 글꼴 코드로. printf 서식(%s %d …)은 반각 그대로 둔다 —
    전각으로 바뀌면 게임이 서식을 못 알아본다."""
    if enc != 'sjis':
        return s.encode('utf-8')
    out, i = bytearray(), 0
    for m in FMT.finditer(s):
        out += kencode(s[i:m.start()]) + m.group().encode('ascii')
        i = m.end()
    return bytes(out + kencode(s[i:]))

# ------------------------------------------------------------------ 명령
def do_dump():
    for name, path in ELFS.items():
        if not os.path.exists(path): print(f"  {name}.ELF 없음"); continue
        d, rows = scan(path)
        p = os.path.join(TEXT, f"elf_{name}.tsv")
        old = {}
        if os.path.exists(p):
            with open(p, encoding='utf-8-sig', newline='') as f:
                for r in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                    old[r['key']] = r.get('ko', '')
        with open(p, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f, delimiter='\t', lineterminator='\n',
                           quoting=csv.QUOTE_NONE, escapechar=None)
            w.writerow(['key', 'enc', 'maxbytes', 'ja', 'ko'])
            for off, s, enc, n in rows:
                k = f"{off:08X}"
                w.writerow([k, enc, n, s, old.get(k, '')])
        print(f"  {os.path.basename(p)}  {len(rows)}개  (sjis "
              f"{sum(1 for r in rows if r[2]=='sjis')}, utf8 "
              f"{sum(1 for r in rows if r[2]=='utf8')})")

def load_ko(name):
    p = os.path.join(TEXT, f"elf_{name}.tsv")
    out = {}
    if not os.path.exists(p): return out
    with open(p, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
            ko = (r.get('ko') or '').strip()
            if ko: out[int(r['key'], 16)] = (ko, r['enc'], int(r['maxbytes']), r['ja'])
    return out

def do_patch(check_only):
    os.makedirs(BUILD, exist_ok=True)
    for name, path in ELFS.items():
        if not os.path.exists(path): continue
        ko = load_ko(name)
        if not ko: print(f"  {name}: 번역 없음 — 건너뜀"); continue
        d = bytearray(open(path, 'rb').read())
        done = over = 0
        for off, (s, enc, n, ja) in sorted(ko.items()):
            # 원문이 그 자리에 그대로 있는지 확인 (오프셋이 어긋나면 덮어쓰면 안 된다).
            # 다시 인코딩해 견주면 안 된다 — 반각 공백처럼 인코더가 바꾸는 문자가
            # 있어서 멀쩡한 문자열도 어긋난 것으로 보인다. 그 자리를 **디코딩**해 견준다.
            # maxbytes 에는 뒤쪽 NUL 채움까지 들어 있으므로, 견줄 때는
            # 첫 NUL 앞까지만 잘라서 본다.
            try:
                raw = bytes(d[off:off+n])
                cur = raw.split(b'\x00', 1)[0].decode('cp932' if enc == 'sjis' else 'utf-8')
            except Exception:
                cur = None
            if cur != ja:
                print(f"    ! 0x{off:08X} 원문 불일치 — 건너뜀 ({ja[:16]})"); continue
            b = enc_bytes(s, enc)
            if len(b) > n:
                over += 1
                print(f"    ! 0x{off:08X} 너무 김 {len(b)}>{n}  {s[:20]}")
                continue
            d[off:off+n] = b + b'\x00'*(n-len(b))
            done += 1
        print(f"  {name}.ELF : 교체 {done}개" + (f", 자리 부족 {over}개" if over else ""))
        if not check_only and done:
            q = os.path.join(BUILD, os.path.basename(path))
            open(q, 'wb').write(bytes(d))
            print(f"      -> {q}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if '--dump' in sys.argv: do_dump()
    else: do_patch('--check' in sys.argv)
