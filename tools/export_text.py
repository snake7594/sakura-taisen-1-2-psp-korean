# -*- coding: utf-8 -*-
"""
Sakura Taisen 1&2 (PSP) -- export all dialogue to translation TSVs.

  python export_text.py            reads the ISO, writes D:\...\text\*.tsv

Output (UTF-8 with BOM, tab separated, one row per string):

    key      stable identifier, e.g.  S1A:0100tbl:12
    file     source member / file
    index    entry index inside that file
    id       entry id (Sakura 1) or 4-byte entry header (Sakura 2)
    flags    'dup=<key>'  identical text already seen at that key
             'gaiji=XXXX' line uses a custom glyph (see README)
    ja       original text; a line break inside a message is written \\n
    ko       empty -- put the translation here

Also writes unique_strings.tsv: every distinct line once, with its occurrence
count. Translate that file and the duplicates follow automatically.
"""
import struct, sys, io, os, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from text_dump import parse_tbl, parse_mes
from pfs import entries as pfs_entries
from cmp import decompress
from sk_text import parse as parse_sk

ISO = r"D:\psp\사쿠라대전1_2\Sakura Taisen 1 and 2.iso"
OUT = r"D:\psp\사쿠라대전1_2\text"
SECTOR = 2048

# custom glyphs -- the font draws something other than the nominal SJIS char.
# All of these were confirmed against the glyph bitmap and script context.
S1_GAIJI = {0x81AC: '⁉', 0x81B8: '‼', 0x81B9: 'マ', 0x81BA: 'ザ',
            0x81BB: 'ー', 0x81BC: 'グ', 0x81BD: 'ー', 0x81BE: 'ス'}
S2_GAIJI = dict(S1_GAIJI)
S2_GAIJI.update({0x81BF: '翔', 0x81DC: '冑', 0x81E5: '璧'})
# Sakura 2 has 21 more gaiji cells in the font that no script actually uses;
# if one ever turns up it is emitted as {XXXX} rather than guessed.
S2_GAIJI_UNKNOWN = (set(range(0x81C8, 0x81CF)) | set(range(0x81DA, 0x81E7))
                    | {0x81BF, 0x81DC, 0x81E5}) - set(S2_GAIJI)

# ---------------------------------------------------------------- ISO walk
f = open(ISO, 'rb')
def read_at(lba, n): f.seek(lba*SECTOR); return f.read(n)
def _dir(lba, length):
    d = read_at(lba, ((length+SECTOR-1)//SECTOR)*SECTOR); out = []; o = 0
    while o < length:
        n = d[o]
        if n == 0:
            o = ((o//SECTOR)+1)*SECTOR
            if o >= length: break
            continue
        r = d[o:o+n]
        el = struct.unpack('<I', r[2:6])[0]; ez = struct.unpack('<I', r[10:14])[0]
        fl = r[25]; nl = r[32]; nm = r[33:33+nl]
        nm = '.' if nm == b'\x00' else '..' if nm == b'\x01' else nm.decode('ascii','replace').split(';')[0]
        out.append((nm, el, ez, fl)); o += n
    return out
FILES = []
def _walk(lba, ln, p=''):
    for nm, el, ez, fl in _dir(lba, ln):
        if nm in ('.', '..'): continue
        if fl & 2: _walk(el, ez, p+'/'+nm)
        else: FILES.append((p+'/'+nm, el, ez))
_pvd = read_at(16, SECTOR); _root = _pvd[156:190]
_walk(struct.unpack('<I', _root[2:6])[0], struct.unpack('<I', _root[10:14])[0])

# ---------------------------------------------------------------- decoders
def s1_render(raw):
    """big-endian Shift-JIS, '$$' = line break"""
    s, i, gj = [], 0, set()
    while i < len(raw):
        b = raw[i]
        if b == 0x24 and i+1 < len(raw) and raw[i+1] == 0x24:
            s.append('\n'); i += 2; continue
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF:
            if i+1 < len(raw):
                w = (b << 8) | raw[i+1]
                if w in S1_GAIJI:
                    s.append(S1_GAIJI[w]); gj.add(w); i += 2; continue
                try:
                    s.append(raw[i:i+2].decode('cp932')); i += 2; continue
                except Exception: pass
        if 0x20 <= b < 0x7F: s.append(chr(b)); i += 1; continue
        s.append(f'<{b:02X}>'); i += 1
    return ''.join(s), gj

def s2_render(body):
    """16-bit little-endian units; FFFE = line break, FFFF = end"""
    s, gj = [], set()
    for i in range(0, len(body)-1, 2):
        w = body[i] | (body[i+1] << 8)
        if w == 0xFFFF: break
        if w == 0xFFFE: s.append('\n'); continue
        if w == 0: continue
        if w in S2_GAIJI: s.append(S2_GAIJI[w]); gj.add(w); continue
        if w in S2_GAIJI_UNKNOWN: s.append(f'{{{w:04X}}}'); gj.add(w); continue
        b0, b1 = w >> 8, w & 0xFF
        if 0x81 <= b0 <= 0x9F or 0xE0 <= b0 <= 0xEF:
            try: s.append(bytes([b0, b1]).decode('cp932')); continue
            except Exception: pass
        s.append(f'<{w:04X}>')
    return ''.join(s), gj

# ---------------------------------------------------------------- collect
rows = []            # (key, file, index, id, gaiji, text)
def add(key, fname, idx, ident, text, gj):
    if text.strip(): rows.append((key, fname, idx, ident, gj, text))

def do_pfs(iso_path, tag, member_filter):
    for path, lba, sz in FILES:
        if path != iso_path: continue
        d = read_at(lba, sz)
        for name, off, msz in pfs_entries(d):
            if not member_filter(name.lower()): continue
            stem = os.path.splitext(name)[0]
            try: ent = parse_tbl(d[off:off+msz])
            except Exception: continue
            for k, idv, raw in ent:
                if not raw: continue
                t, gj = s1_render(raw)
                add(f"{tag}:{stem}:{k}", name, k, f"0x{idv:04X}", t, gj)

do_pfs('/PSP_GAME/USRDIR/SAKURA1/SAKURA1/ADVMACRO.PFS', 'S1A',
       lambda n: n.endswith('tbl.bin'))
n_adv = len(rows)
do_pfs('/PSP_GAME/USRDIR/SAKURA1/SAKURA2/SLGMAP.PFS', 'S1S',
       lambda n: n.endswith('mes.bin'))
n_slg = len(rows) - n_adv

for path, lba, sz in FILES:
    if not path.upper().endswith('.MES'): continue
    name = path.split('/')[-1]; stem = os.path.splitext(name)[0]
    d = read_at(lba, sz)
    try: ent = parse_mes(d)
    except Exception: continue
    for i, hdr, body in ent:
        t, gj = s2_render(body)
        add(f"S2:{stem}:{i}", name, i, hdr.hex(), t, gj)
n_s2 = len(rows) - n_adv - n_slg

# ---- 사쿠라 2 본편(ADV): SK####.CMP ----
for path, lba, sz in FILES:
    if '/SAKURA2/SAKURA1/SK' not in path or not path.upper().endswith('.CMP'):
        continue
    name = path.split('/')[-1]; stem = os.path.splitext(name)[0]
    try:
        dec, *_ = decompress(read_at(lba, sz))
        r = parse_sk(dec)
    except Exception:
        continue
    if r is None: continue
    for i, off, raw in r[2]:
        t, gj = s2_render(raw)
        add(f"S2A:{stem}:{i}", name, i, f"@{off:#x}", t, gj)
n_s2a = len(rows) - n_adv - n_slg - n_s2

# ---------------------------------------------------------------- write
os.makedirs(OUT, exist_ok=True)
esc = lambda s: s.replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t')

first, counts = {}, collections.Counter()
for key, fn, idx, ident, gj, t in rows:
    counts[t] += 1
    first.setdefault(t, key)

def write(fname, subset):
    p = os.path.join(OUT, fname)
    with open(p, 'w', encoding='utf-8-sig', newline='') as fh:
        fh.write("key\tfile\tindex\tid\tflags\tja\tko\n")
        for key, fn, idx, ident, gj, t in subset:
            flags = []
            if first[t] != key: flags.append(f"dup={first[t]}")
            if gj: flags.append("gaiji=" + ','.join(f"{w:04X}" for w in sorted(gj)))
            fh.write(f"{key}\t{fn}\t{idx}\t{ident}\t{';'.join(flags)}\t{esc(t)}\t\n")
    print(f"  {fname:<24} {len(subset):6d} rows")

write("sakura1_adv.tsv", rows[:n_adv])
write("sakura1_slg.tsv", rows[n_adv:n_adv+n_slg])
write("sakura2_evt.tsv", rows[n_adv+n_slg:n_adv+n_slg+n_s2])
write("sakura2_adv.tsv", rows[n_adv+n_slg+n_s2:])

uniq = sorted(counts.items(), key=lambda kv: -kv[1])
with open(os.path.join(OUT, "unique_strings.tsv"), 'w', encoding='utf-8-sig', newline='') as fh:
    fh.write("count\tfirst_key\tja\tko\n")
    for t, c in uniq:
        fh.write(f"{c}\t{first[t]}\t{esc(t)}\t\n")
print(f"  {'unique_strings.tsv':<24} {len(uniq):6d} rows")

chars = sum(len(t) for _, _, _, _, _, t in rows)
uchars = sum(len(t) for t, _ in uniq)
print(f"\ntotal {len(rows)} strings / {chars} chars"
      f"   ->  {len(uniq)} unique / {uchars} chars"
      f"  ({100*uchars/chars:.1f}% of the work)")
