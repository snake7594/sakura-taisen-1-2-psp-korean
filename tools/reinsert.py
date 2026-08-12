# -*- coding: utf-8 -*-
"""
번역된 TSV 를 게임 파일에 되넣는다.

  python reinsert.py --check    용량 점검만 (원문 그대로 재구축해 여유를 잰다)
  python reinsert.py            build/ 에 패치된 파일들을 만든다

번역문은 길이가 달라지므로 제자리 덮어쓰기가 아니라 **구조를 다시 만든다**.
오프셋 테이블을 새로 계산하고, 컨테이너(PFS)와 압축(.CMP)까지 다시 만든 뒤
원래 배정 공간에 들어가는지 확인한다.

  사쿠라1 tbl : u16BE 테이블워드수 | u16BE ? | n×{u16BE id, u16BE 오프셋(워드)} | 텍스트
                오프셋이 u16(워드) 이므로 텍스트 블록은 최대 128 KiB
  사쿠라2 SK  : u32LE 헤더 [2]=인덱스 [3]=텍스트 [4]=전체크기, 인덱스는 16비트 단위
  사쿠라2 MES : u32BE count | count×u32BE 절대오프셋 | 엔트리(4B 헤더+텍스트)
                뒤에 립싱크 블록이 붙어 있어 **원래 위치를 유지**해야 한다
"""
import os, sys, csv, struct, collections, io

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from encode import s1_encode, s2_encode, EncodeError
from pfs import entries as pfs_entries
from text_dump import parse_tbl, parse_mes
from sk_text import parse as parse_sk
from cmp import decompress
from cmp_compress import compress

ROOT  = r"D:\psp\사쿠라대전1_2"
SRC   = os.path.join(ROOT, "extract", "PSP_GAME", "USRDIR")
TEXT  = os.path.join(ROOT, "text")
BUILD = os.path.join(ROOT, "build", "patched")

# ---------------------------------------------------------------- 번역문 적재
def load_text():
    """key -> 넣을 문자열. ko 가 비어 있으면 원문 ja 를 그대로 쓴다."""
    out, n_ko = {}, 0
    for fn in ("sakura1_adv.tsv", "sakura1_slg.tsv", "sakura2_adv.tsv", "sakura2_evt.tsv"):
        p = os.path.join(TEXT, fn)
        if not os.path.exists(p): continue
        with open(p, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                ko = (r.get('ko') or '').strip()
                if ko: n_ko += 1
                out[r['key']] = (ko or r['ja']).replace('\\n', '\n').replace('\\t', '\t')
    return out, n_ko

# ---------------------------------------------------------------- 사쿠라 1
def build_tbl(orig, keyfmt, texts):
    """tbl.bin 재구축. 같은 문장은 한 번만 저장해 공간을 아낀다.

    **텍스트 뒤에 딸린 자료를 반드시 원래 자리에 그대로 둬야 한다.**
    처음에는 헤더+표+텍스트만 새로 쓰고 나머지를 버렸는데, 그 뒤에
    립싱크 음소 열(`.ea.aeeennnnnn` 같은 a/e/i/o/u/n 문자열)이 들어 있다.
    이걸 날리면 **사쿠라1 음성이 하나도 안 나오고**, 게임이 그 자리를
    읽으려다 장면 전환에서 멈춘다. 0100tbl.bin 기준 14,669 바이트다.

    그래서 원본에서 마지막 문장이 끝나는 자리를 찾아 그 뒤를 꼬리로 떼어
    두고, 새 텍스트는 그 앞까지만 채운 뒤 꼬리를 **같은 절대 위치**에 붙인다.
    """
    words = struct.unpack_from('>H', orig, 0)[0]
    n = words // 2
    unk = struct.unpack_from('>H', orig, 2)[0]
    ids = [struct.unpack_from('>HH', orig, 4 + k*4)[0] for k in range(n)]

    # 원본 꼬리 잘라내기: 가장 뒤쪽 문장의 NUL 다음부터 파일 끝까지
    base0 = 4 + n*4
    o_offs = [struct.unpack_from('>HH', orig, 4 + k*4)[1] for k in range(n)]
    last = base0 + max(o_offs)*2
    tail_at = orig.find(b'\x00', last) + 1 if last < len(orig) else len(orig)
    if tail_at <= 0: tail_at = len(orig)
    tail = orig[tail_at:]

    blob, pos = bytearray(), {}
    offs = []
    for k in range(n):
        t = texts.get(keyfmt(k))
        if t is None:                       # TSV 에 없던 빈 엔트리
            offs.append(0 if not blob else offs[0]); continue
        if t not in pos:
            if len(blob) % 2: blob += b'\x00'
            pos[t] = len(blob)
            blob += s1_encode(t) + b'\x00'
        offs.append(pos[t])
    if len(blob) % 2: blob += b'\x00'

    base = 4 + n*4
    for o in offs:
        if o // 2 > 0xFFFF:
            raise EncodeError(f"텍스트 블록이 u16 워드 오프셋 한계(128 KiB)를 넘음")
    out = bytearray(struct.pack('>HH', words, unk))
    for i, o in zip(ids, offs):
        out += struct.pack('>HH', i, o // 2)
    assert len(out) == base
    out += blob
    if tail:
        if len(out) > tail_at:
            raise EncodeError(f"번역문이 원본 텍스트 구역({tail_at-base:,}B)을 넘어 "
                              f"립싱크 자료를 밀어낸다 ({len(out)-base:,}B)")
        out = bytearray(bytes(out).ljust(tail_at, b'\x00')) + tail
    return bytes(out)

def build_pfs(src_path, member_filter, keyprefix, texts, report):
    d = open(src_path, 'rb').read()
    mem = pfs_entries(d)
    SECT = 2048
    new_members = []
    for name, off, sz in mem:
        body = d[off:off+sz]
        if member_filter(name.lower()):
            stem = os.path.splitext(name)[0]
            body = build_tbl(body, lambda k, s=stem: f"{keyprefix}:{s}:{k}", texts)
        new_members.append((name, body))
    head = 0x10 + len(mem)*24
    cur = ((head + SECT - 1)//SECT)*SECT
    out = bytearray(b'PAKFILE\x00' + struct.pack('>II', len(mem), 0))
    blobs = []
    for name, body in new_members:
        out += name.encode('ascii').ljust(16, b'\x00') + struct.pack('>II', cur//SECT, len(body))
        blobs.append((cur, body))
        cur += ((len(body) + SECT - 1)//SECT)*SECT
    out = bytearray(out.ljust(blobs[0][0], b'\x00'))
    for at, body in blobs:
        out = out.ljust(at, b'\x00') + bytearray(body)
    out = out.ljust(cur, b'\x00')
    report(os.path.basename(src_path), len(d), len(out))
    return bytes(out)

# ---------------------------------------------------------------- 사쿠라 2 SK
def build_sk(raw, stem, texts, report):
    dec, *_ = decompress(raw)
    r = parse_sk(dec)
    if r is None: return raw
    tbl, txt, _ = r
    # parse_sk 는 범위를 벗어난 엔트리를 걸러내므로, 인덱스 테이블을 직접 읽는다
    n = (txt - tbl)//4
    blob, pos, offs = bytearray(), {}, []
    for i in range(n):
        t = texts.get(f"S2A:{stem}:{i}")
        if t is None: t = ''
        if t not in pos:
            pos[t] = len(blob)
            blob += s2_encode(t) + b'\xff\xff'
        offs.append(pos[t] // 2)
    out = bytearray(dec[:tbl])
    for o in offs: out += struct.pack('<I', o)
    assert len(out) == txt
    out += blob
    struct.pack_into('<I', out, 16, len(out))          # 헤더[4] = 전체 크기
    enc = compress(bytes(out))
    report(stem + '.CMP', len(raw), len(enc))
    return enc

# ---------------------------------------------------------------- 사쿠라 2 MES
def build_mes(d, stem, texts, report):
    n = struct.unpack_from('>I', d, 0)[0]
    if n == 0 or 4 + n*4 > len(d):
        return d                              # 메시지가 없는 파일은 그대로
    offs = list(struct.unpack_from(f'>{n}I', d, 4))
    ent = parse_mes(d)
    # 립싱크 블록: 마지막 메시지의 0xFFFF 뒤부터 파일 끝까지
    last = max(offs)
    j = last + 4
    while j + 1 < len(d) and not (d[j] == 0xFF and d[j+1] == 0xFF): j += 2
    tail_at = j + 2
    tail = d[tail_at:]

    base = 4 + n*4
    blobs = [hdr + s2_encode(texts.get(f"S2:{stem}:{i}", '')) + b'\xff\xff'
             for i, hdr, _ in ent]

    # 립싱크 블록은 **원래 절대 위치를 반드시 지킨다**. 게임이 그 위치를 알고 있을 수
    # 있어서다. 메시지 오프셋 표는 절대값이라 메시지가 이어 붙어 있을 필요가 없으므로,
    #   1) 립싱크 앞 빈 자리에 들어가는 메시지를 먼저 채우고
    #   2) 넘치는 메시지는 립싱크 **뒤에** 둔다
    # 한 개가 안 들어간다고 멈추지 않고 계속 훑어 앞 공간을 최대한 쓴다.
    new_offs = [0]*n
    gap, cur, spill = bytearray(), base, []
    for k, b in enumerate(blobs):
        if cur + len(b) <= tail_at:
            new_offs[k] = cur; gap += b; cur += len(b)
        else:
            spill.append(k)

    out = bytearray(struct.pack('>I', n) + b'\x00'*(n*4) + bytes(gap))
    out = bytearray(out.ljust(tail_at, b'\x00')) + bytearray(tail)
    for k in spill:
        new_offs[k] = len(out); out += blobs[k]
    for k, o in enumerate(new_offs):
        struct.pack_into('>I', out, 4 + k*4, o)

    report(stem + '.MES', len(d), len(out),
           '' if not spill else f'{len(spill)}개 메시지를 립싱크 뒤로')
    return bytes(out)

# ---------------------------------------------------------------- main
def main(check_only):
    texts, n_ko = load_text()
    print(f"번역문 적재: {len(texts)}행 (ko 채워진 행 {n_ko})")
    if not check_only: os.makedirs(BUILD, exist_ok=True)

    rows = []
    def rep(name, old, new, note=''):
        rows.append((name, old, new, note))

    jobs = [
        ("ADVMACRO.PFS", os.path.join(SRC, r"SAKURA1\SAKURA1\ADVMACRO.PFS"),
         lambda: build_pfs(os.path.join(SRC, r"SAKURA1\SAKURA1\ADVMACRO.PFS"),
                           lambda s: s.endswith('tbl.bin'), 'S1A', texts, rep)),
        ("SLGMAP.PFS", os.path.join(SRC, r"SAKURA1\SAKURA2\SLGMAP.PFS"),
         lambda: build_pfs(os.path.join(SRC, r"SAKURA1\SAKURA2\SLGMAP.PFS"),
                           lambda s: s.endswith('mes.bin'), 'S1S', texts, rep)),
    ]
    for name, path, fn in jobs:
        if not os.path.exists(path):
            print(f"  건너뜀 {name} (원본 없음 — iso_extract.py 로 추출 필요)"); continue
        data = fn()
        if not check_only: open(os.path.join(BUILD, name), 'wb').write(data)

    skdir = os.path.join(SRC, "SAKURA2", "SAKURA1")
    for fn in sorted(os.listdir(skdir)) if os.path.isdir(skdir) else []:
        if not (fn.startswith('SK') and fn.upper().endswith('.CMP')): continue
        raw = open(os.path.join(skdir, fn), 'rb').read()
        data = build_sk(raw, os.path.splitext(fn)[0], texts, rep)
        if not check_only: open(os.path.join(BUILD, fn), 'wb').write(data)

    mesdir = os.path.join(SRC, "SAKURA2", "SAKURA2")
    for fn in sorted(os.listdir(mesdir)) if os.path.isdir(mesdir) else []:
        if not fn.upper().endswith('.MES'): continue
        d = open(os.path.join(mesdir, fn), 'rb').read()
        data = build_mes(d, os.path.splitext(fn)[0], texts, rep)
        if not check_only: open(os.path.join(BUILD, fn), 'wb').write(data)

    grew = [r for r in rows if r[2] > r[1]]
    warn = [r for r in rows if r[3]]
    print(f"\n재구축 {len(rows)}개 파일")
    print(f"  원본보다 커진 파일 {len(grew)}개")
    for name, old, new, note in sorted(grew, key=lambda r: r[1]-r[2])[:8]:
        print(f"    {name:<18} {old:8d} -> {new:8d}  (+{new-old})")
    if warn:
        print(f"  경고 {len(warn)}개")
        for name, old, new, note in warn[:8]: print(f"    {name}: {note}")
    if not check_only: print(f"\n-> {BUILD}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main('--check' in sys.argv)
