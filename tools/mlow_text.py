# -*- coding: utf-8 -*-
"""
사쿠라 2 SLG(전략 파트) 대사 M##LOW.CMP 를 뽑고 되넣는다.

  python mlow_text.py --dump    text/sakura2_slg.tsv 로 뽑기 (기존 번역 자동 재사용)
  python mlow_text.py --check   되넣기 용량 점검
  python mlow_text.py           build/patched/ 에 패치된 .CMP 저장

구조는 EV*.MES 와 똑같다 — u32BE 개수 | 개수×u32BE 절대오프셋 | (4B 머리 + 텍스트).
텍스트도 16비트 리틀엔디안이라 s2_encode/s2_decode 를 그대로 쓴다.
다른 점은 통째로 .CMP 로 압축돼 있다는 것뿐이다.

문장 대부분이 본편(SK*.CMP)·이벤트(EV*.MES)와 겹치므로, 뽑을 때 원문이 같은
행의 번역을 그대로 가져다 채운다. 새로 번역할 것만 남는다.
"""
import os, sys, csv, io, struct, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
csv.field_size_limit(1 << 24)
from cmp import decompress, parse_header, _params as cmp_params
from cmp_compress import compress
from text_dump import parse_mes, s2_text
from encode import s2_encode
from build_iso import walk_iso, SRC_ISO, SECTOR

ROOT  = r"D:\psp\사쿠라대전1_2"
TEXT  = os.path.join(ROOT, "text")
BUILD = os.path.join(ROOT, "build", "patched")
TSV   = os.path.join(TEXT, "sakura2_slg.tsv")

_iso = open(SRC_ISO, 'rb'); _table = walk_iso(_iso)

def files():
    out = []
    for p in sorted(_table):
        b = os.path.basename(p).upper()
        if b.startswith('M') and b.endswith('LOW.CMP'): out.append((b[:-4], p))
    return out

def read(p):
    _, lba, sz = _table[p]; _iso.seek(lba*SECTOR); return _iso.read(sz)

def esc(s):  return s.replace('\n', '\\n').replace('\t', '\\t')
def unesc(s): return s.replace('\\n', '\n').replace('\\t', '\t')

def known_ko():
    """이미 번역한 네 TSV 에서 원문 -> 번역"""
    out = {}
    for fn in ("sakura1_adv.tsv", "sakura1_slg.tsv", "sakura2_adv.tsv", "sakura2_evt.tsv"):
        p = os.path.join(TEXT, fn)
        if not os.path.exists(p): continue
        with open(p, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                ko = (r.get('ko') or '').strip()
                if ko: out.setdefault(r['ja'], ko)
    return out

def do_dump():
    known = known_ko()
    old = {}
    if os.path.exists(TSV):
        with open(TSV, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                if (r.get('ko') or '').strip(): old[r['key']] = r['ko']
    rows, reuse, seen = [], 0, {}
    for stem, p in files():
        dec = decompress(read(p))[0]
        for i, hdr, body in parse_mes(dec):
            ja = esc(s2_text(body))
            if not ja: continue
            key = f"S2M:{stem}:{i}"
            ko = old.get(key) or known.get(ja, '')
            if ko and key not in old: reuse += 1
            flags = ''
            if ja in seen: flags = f"dup={seen[ja]}"
            else: seen[ja] = key
            rows.append([key, flags, ja, ko])
    with open(TSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n',
                       quoting=csv.QUOTE_NONE, escapechar=None)
        w.writerow(['key', 'flags', 'ja', 'ko']); w.writerows(rows)
    done = sum(1 for r in rows if r[3])
    print(f"  {os.path.basename(TSV)}  {len(rows)}행 (고유 {len(seen)})")
    print(f"  기존 번역 재사용 {reuse}행 -> 번역 완료 {done} ({done/max(1,len(rows))*100:.1f}%)")
    print(f"  남은 고유 미번역 {sum(1 for r in rows if not r[3] and not r[1])}행")

def load_ko():
    out = {}
    if not os.path.exists(TSV): return out
    with open(TSV, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
            ko = (r.get('ko') or '').strip()
            out[r['key']] = unesc(ko or r['ja'])
    return out

def build_one(dec, stem, texts):
    """MES 와 같은 방식. 립싱크 블록은 없지만 원래 크기를 지키려 애쓴다."""
    n = struct.unpack_from('>I', dec, 0)[0]
    ent = parse_mes(dec)
    base = 4 + n*4
    tail_at = max(struct.unpack_from(f'>{n}I', dec, 4)) if n else base
    # 마지막 메시지 끝 = 원래 텍스트 영역의 끝
    j = tail_at + 4
    while j + 1 < len(dec) and not (dec[j] == 0xFF and dec[j+1] == 0xFF): j += 2
    end = j + 2
    tail = dec[end:]

    blobs = [hdr + s2_encode(texts.get(f"S2M:{stem}:{i}", '')) + b'\xff\xff'
             for i, hdr, _ in ent]
    offs, cur, body = [], base, bytearray()
    for b in blobs:
        offs.append(cur); body += b; cur += len(b)
    out = bytearray(struct.pack('>I', n))
    for o in offs: out += struct.pack('>I', o)
    out += body
    out = bytearray(out.ljust(end, b'\x00')) + bytearray(tail) if len(out) <= end \
          else out + bytearray(tail)
    return bytes(out)

def do_build(check_only):
    texts = load_ko()
    if not texts: print("  번역 없음 — --dump 먼저"); return
    if not check_only: os.makedirs(BUILD, exist_ok=True)
    grew = []
    for stem, p in files():
        raw = read(p)
        dec = decompress(raw)[0]
        nd = build_one(dec, stem, texts)
        # 원본과 **같은 param** 으로 다시 압축해야 한다. M##LOW 는 param 3
        # (거리 9비트 / 길이 최대 130) 이라 param 0 으로 압축하면 33% 커진다.
        method, param, _, hdr_len = parse_header(raw)
        obits, bias = cmp_params(method, param)
        enc = compress(nd, obits, bias, header=raw[:hdr_len])
        chk = decompress(enc)[0]
        assert chk == nd, f"{stem} 재압축 왕복 실패"
        if len(enc) > len(raw): grew.append((stem, len(raw), len(enc)))
        if not check_only:
            open(os.path.join(BUILD, stem + '.CMP'), 'wb').write(enc)
    print(f"  파일 {len(files())}개 재구축, 원본보다 커진 것 {len(grew)}개")
    for s, a, b in sorted(grew, key=lambda r: r[1]-r[2])[:6]:
        print(f"    {s} {a} -> {b} (+{b-a})")
    if not check_only: print(f"  -> {BUILD}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if '--dump' in sys.argv: do_dump()
    else: do_build('--check' in sys.argv)
