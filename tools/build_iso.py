# -*- coding: utf-8 -*-
"""
패치된 파일을 넣어 ISO 를 다시 만든다.

  python build_iso.py                 폰트 + build/patched/ (있으면) 를 넣어 KR ISO 생성
  python build_iso.py --fonts-only    폰트만
  python build_iso.py --test          사쿠라 1 자(ruler) 빌드   (make_ruler_test.py  먼저)
  python build_iso.py --test2         사쿠라 2 이벤트 자 빌드   (make_ruler_test2.py 먼저)
  python build_iso.py --test3         사쿠라 2 본편+이벤트 자   (make_ruler_test3.py 먼저)
  python build_iso.py --check <iso>   결과 ISO 검증만

교체 파일이 원본보다 크지 않으면 전체 재빌드가 필요 없다. 원래 자리(LBA)에 덮어쓰고
디렉터리 레코드의 크기 필드만 고치면 된다. 다른 파일의 위치가 하나도 움직이지 않는다.

ISO9660 메모
  - 디렉터리 레코드 오프셋 10..17 = 데이터 길이 (LE u32 + BE u32, both-endian)
  - 이 디스크에는 Joliet(SVD)가 없어 트리가 하나뿐이다
"""
import os, sys, struct, shutil, collections

ROOT    = r"D:\psp\사쿠라대전1_2"
SRC_ISO = os.path.join(ROOT, "Sakura Taisen 1 and 2.iso")
BUILD   = os.path.join(ROOT, "build")
SECTOR  = 2048

FONTS = {
    "/PSP_GAME/USRDIR/SAKURA1/SAKURA0/FONT/FONTALL.FNT": os.path.join(BUILD, "FONTALL.FNT"),
    "/PSP_GAME/USRDIR/SAKURA2/FNT4B.CMP":                os.path.join(BUILD, "FNT4B.CMP"),
}

# ---------------------------------------------------------------- ISO9660 walk
def walk_iso(f):
    """{경로: (레코드 절대오프셋, LBA, 크기)}"""
    f.seek(16*SECTOR)
    pvd = f.read(SECTOR)
    assert pvd[1:6] == b'CD001' and pvd[0] == 1, "Primary Volume Descriptor 아님"
    root = pvd[156:190]
    root_lba = struct.unpack('<I', root[2:6])[0]
    root_len = struct.unpack('<I', root[10:14])[0]
    out = {}
    def rec(lba, length, path):
        f.seek(lba*SECTOR)
        data = f.read(((length + SECTOR - 1)//SECTOR)*SECTOR)
        o = 0
        while o < length:
            n = data[o]
            if n == 0:
                o = ((o//SECTOR)+1)*SECTOR
                if o >= length: break
                continue
            r = data[o:o+n]
            elba = struct.unpack('<I', r[2:6])[0]
            esz  = struct.unpack('<I', r[10:14])[0]
            flags, nl = r[25], r[32]
            nm = r[33:33+nl]
            if nm not in (b'\x00', b'\x01'):
                name = nm.decode('ascii', 'replace').split(';')[0]
                full = path + '/' + name
                if flags & 0x02: rec(elba, esz, full)
                else:            out[full] = (lba*SECTOR + o, elba, esz)
            o += n
    rec(root_lba, root_len, '')
    return out

def set_size(f, rec_off, size):
    f.seek(rec_off + 10)
    f.write(struct.pack('<I', size) + struct.pack('>I', size))

# ---------------------------------------------------------------- 교체 목록
# ISO 안에 같은 이름이 여러 개 있어도 **모두 같은 내용으로 덮어쓸** 파일들.
# 기본은 이름이 겹치면 멈추는 것이 맞다 — 어느 쪽을 고칠지 모르는 채로
# 아무 데나 쓰면 안 되니까. 아래 파일은 원본에서 사본끼리 바이트가 같고
# (SAKURA1/ 과 SAKURA2/) 게임이 상황에 따라 둘 중 하나를 읽으므로
# 양쪽 다 바꿔야 한다.
MULTI_PATH = {"PBOOK_FLB0.CMP"}

def from_dir(table, subdir, label, pattern=None):
    """build/<subdir>/ 의 파일을 ISO 안 같은 이름 파일에 자동으로 매칭한다."""
    d = os.path.join(BUILD, subdir)
    if not os.path.isdir(d): return {}
    by_name = collections.defaultdict(list)
    for p in table: by_name[p.rsplit('/', 1)[-1]].append(p)
    out, miss, amb = {}, [], []
    for fn in sorted(os.listdir(d)):
        if not os.path.isfile(os.path.join(d, fn)): continue
        if pattern and not fn.upper().endswith(pattern): continue
        c = by_name.get(fn, [])
        if len(c) == 1: out[c[0]] = os.path.join(d, fn)
        elif not c:     miss.append(fn)
        elif fn in MULTI_PATH:
            for q in c: out[q] = os.path.join(d, fn)
            print(f"    {label}: '{fn}' 을 {len(c)}곳에 씀 {c}")
        else:           amb.append((fn, c))
    if miss:
        print(f"    주의 [{label}] ISO 에 없는 이름 {len(miss)}개 무시: {miss[:4]}")
    if amb:
        for fn, c in amb: print(f"    오류 [{label}] '{fn}' 이 ISO 안에 여러 개: {c}")
        sys.exit("이름이 겹쳐 자동 매칭 불가")
    if out: print(f"    {label}: {len(out)}개")
    return out

def collect(table, mode):
    rep = dict(FONTS)
    print("교체 대상")
    print(f"    폰트: {len(rep)}개")
    if mode == 'normal':
        rep.update(from_dir(table, "patched", "번역 재삽입"))
    elif mode == 'test':
        rep.update(from_dir(table, ".", "사쿠라1 자", ".PFS"))
    elif mode == 'test2':
        rep.update(from_dir(table, "mes", "사쿠라2 이벤트 자", ".MES"))
    elif mode == 'test3':
        rep.update(from_dir(table, "mes", "사쿠라2 이벤트 자", ".MES"))
        rep.update(from_dir(table, "sk",  "사쿠라2 본편 자", ".CMP"))
    return rep

OUT_NAME = {'normal': "Sakura Taisen 1 and 2 (KR).iso",
            'fonts':  "Sakura Taisen 1 and 2 (KR).iso",
            'test':   "Sakura Taisen 1 and 2 (RULER TEST).iso",
            'test2':  "Sakura Taisen 1 and 2 (RULER TEST S2).iso",
            'test3':  "Sakura Taisen 1 and 2 (RULER TEST S2).iso"}

# ---------------------------------------------------------------- build
def build(mode):
    out_iso = os.path.join(ROOT, OUT_NAME[mode])
    with open(SRC_ISO, 'rb') as f:
        table = walk_iso(f)
    rep = collect(table, mode)

    plan, over = [], []
    for iso_path, new_path in rep.items():
        if not os.path.exists(new_path): sys.exit(f"교체 파일 없음: {new_path}")
        rec_off, lba, old_sz = table[iso_path]
        new_sz = os.path.getsize(new_path)
        alloc = ((old_sz + SECTOR - 1)//SECTOR)*SECTOR
        if new_sz > alloc: over.append((iso_path, new_sz, alloc)); continue
        plan.append((iso_path, new_path, rec_off, lba, new_sz, alloc))
    if over:
        print(f"\n배정 공간 초과 {len(over)}개 — 이 파일들은 전체 재빌드가 필요합니다")
        for p, n, a in over[:10]: print(f"    {p}: {n} > {a}")
        sys.exit(1)

    print(f"\nISO 복사 중... ({os.path.getsize(SRC_ISO)/2**30:.2f} GiB)")
    shutil.copyfile(SRC_ISO, out_iso)
    with open(out_iso, 'r+b') as f:
        for iso_path, new_path, rec_off, lba, new_sz, alloc in plan:
            data = open(new_path, 'rb').read()
            f.seek(lba*SECTOR)
            f.write(data)
            f.write(b'\x00' * (alloc - len(data)))
            set_size(f, rec_off, new_sz)
    print(f"  기록 완료: {len(plan)}개 파일")
    print(f"\n-> {out_iso}")
    return out_iso, rep

# ---------------------------------------------------------------- verify
def check(iso, rep=None):
    print(f"\n검증: {os.path.basename(iso)}")
    with open(iso, 'rb') as f:
        table = walk_iso(f)
        if rep is None: rep = collect(table, 'normal')
        bad = 0
        for iso_path, new_path in rep.items():
            rec_off, lba, sz = table[iso_path]
            f.seek(lba*SECTOR)
            want = open(new_path, 'rb').read()
            if sz != len(want) or f.read(sz) != want:
                bad += 1
                print(f"    불일치: {iso_path} (크기 {sz}, 기대 {len(want)})")
        print(f"    교체 파일 {len(rep)}개: {'모두 일치' if bad == 0 else f'{bad}개 불일치'}")
        with open(SRC_ISO, 'rb') as g:
            src = walk_iso(g)
            names = [p for p in table if p not in rep]
            step = max(1, len(names)//40)
            sample = names[::step]
            diff = sum(1 for p in sample if table[p] != src[p])
            print(f"    나머지 파일 표본 {len(sample)}개 위치·크기: "
                  f"{'모두 동일' if diff == 0 else f'{diff}개 다름'}")
        ok = bad == 0 and diff == 0
    print("  결과:", "정상 ✔" if ok else "문제 있음 ✘")
    return ok

if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--check':
        sys.exit(0 if check(a[1]) else 1)
    mode = ('fonts' if '--fonts-only' in a else
            'test'  if '--test'  in a else
            'test2' if '--test2' in a else
            'test3' if '--test3' in a else 'normal')
    iso, rep = build(mode)
    sys.exit(0 if check(iso, rep) else 1)
