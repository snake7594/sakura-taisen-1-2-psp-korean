# -*- coding: utf-8 -*-
"""
미니게임(대부호) 대사 MG0000DAIF.BIN 을 뽑고 되넣는다.

  python mg_text.py --dump    text/mg_daif.tsv 로 뽑기
  python mg_text.py --check   용량 점검
  python mg_text.py           build/patched/ 에 패치된 .BIN 저장

'MWo3' 컨테이너 구조
    표      0x29300 부터 u32LE 오프셋 167개 — **표 자신의 위치가 기준(base)**
    텍스트  0x2959C 부터 NUL 종료 문자열 219개
            빅엔디안 Shift-JIS, 줄바꿈은 '//' 두 바이트,
            끝의 홑 알파벳(B c H I Z …)은 제어 코드 — 반각 그대로 둔다
    표 항목 167개 가운데 166개가 문자열 첫머리를 가리킨다.

되넣을 때는 문자열을 다시 이어 붙이고 **옛 위치 -> 새 위치** 표를 만들어
오프셋 표를 고친다. 뒤에 다른 자료가 붙어 있으므로 원래 구역을 넘기면 안 된다.

주의: 뽑을 때는 cp932 로 읽어야 한다. s1_decode 는 ku16~ku40 을 한글로 되돌리므로
      원문 한자가 엉뚱한 한글로 보인다 (그 자리를 한글이 가져갔기 때문).
"""
import os, sys, csv, io, re, struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
csv.field_size_limit(1 << 24)
from encode import s1_encode
from build_iso import walk_iso, SRC_ISO, SECTOR

ROOT  = r"D:\psp\사쿠라대전1_2"
TEXT  = os.path.join(ROOT, "text")
BUILD = os.path.join(ROOT, "build", "patched")
TSV   = os.path.join(TEXT, "mg_daif.tsv")
NAME  = "MG0000DAIF.BIN"
TBL, NENT, T0 = 0x29300, 167, 0x2959C      # 표 위치·항목 수·텍스트 시작

_iso = open(SRC_ISO, 'rb'); _table = walk_iso(_iso)
_p = [p for p in _table if os.path.basename(p).upper() == NAME][0]

def read():
    _, lba, sz = _table[_p]; _iso.seek(lba*SECTOR); return _iso.read(sz)

def strings(d):
    """텍스트 구역의 (시작위치, 원시바이트) 목록. 뒤쪽 비어 있는 자리에서 멈춘다."""
    out, p = [], T0
    while True:
        e = d.find(b'\x00', p)
        if e < 0: break
        raw = d[p:e]
        # 텍스트 구역 끝: 빈 문자열이 잇달아 나오면 자료가 아니다
        if not raw and out and not out[-1][1]: break
        out.append((p, raw)); p = e + 1
    while out and not out[-1][1]: out.pop()
    return out

def dec(raw):
    return raw.decode('cp932', 'replace').replace('//', '\n')

def enc(s):
    return b'//'.join(s1_encode(x) for x in s.split('\n'))

def do_dump():
    d = read()
    ss = strings(d)
    old = {}
    if os.path.exists(TSV):
        with open(TSV, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                if (r.get('ko') or '').strip(): old[r['key']] = r['ko']
    rows = []
    for i, (p, raw) in enumerate(ss):
        k = f"MG:{i}"
        rows.append([k, dec(raw).replace('\n', '\\n'), old.get(k, '')])
    with open(TSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n',
                       quoting=csv.QUOTE_NONE, escapechar=None)
        w.writerow(['key', 'ja', 'ko']); w.writerows(rows)
    span = ss[-1][0] + len(ss[-1][1]) + 1 - T0
    print(f"  {os.path.basename(TSV)}  {len(ss)}행, 번역 {sum(1 for r in rows if r[2])}")
    print(f"  텍스트 0x{T0:X}, {span}바이트")

def do_build(check_only):
    d = bytearray(read())
    ss = strings(d)
    room = ss[-1][0] + len(ss[-1][1]) + 1 - T0
    ko = {}
    if os.path.exists(TSV):
        with open(TSV, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                ko[r['key']] = ((r.get('ko') or '').strip() or r['ja']).replace('\\n', '\n')
    if not ko: print("  번역 없음 — --dump 먼저"); return

    blob, remap, pos = bytearray(), {}, T0
    for i, (p, raw) in enumerate(ss):
        b = enc(ko.get(f"MG:{i}", dec(raw))) + b'\x00'
        remap[p] = pos; blob += b; pos += len(b)
    print(f"  텍스트 {len(blob)} / 자리 {room}바이트  ({len(blob)-room:+d})")
    if len(blob) > room:
        print("  자리 부족 — 번역을 줄여야 한다"); return

    d[T0:T0+len(blob)] = blob
    for k in range(len(blob), room): d[T0+k] = 0
    offs = list(struct.unpack_from(f'<{NENT}I', d, TBL))
    moved = 0
    for k, o in enumerate(offs):
        tgt = TBL + o
        if tgt in remap:
            offs[k] = remap[tgt] - TBL; moved += 1
    struct.pack_into(f'<{NENT}I', d, TBL, *offs)
    print(f"  오프셋 표 {moved}/{NENT}개 갱신")
    if not check_only:
        os.makedirs(BUILD, exist_ok=True)
        q = os.path.join(BUILD, NAME)
        open(q, 'wb').write(bytes(d))
        print(f"  -> {q}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if '--dump' in sys.argv: do_dump()
    else: do_build('--check' in sys.argv)
