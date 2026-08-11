import struct, sys, os, re

ISO = r"D:\psp\사쿠라대전1_2\Sakura Taisen 1 and 2.iso"
SECTOR = 2048
OUT = r"D:\psp\사쿠라대전1_2\extract"

f = open(ISO, 'rb')

def read_at(lba, length):
    f.seek(lba * SECTOR)
    return f.read(length)

pvd = read_at(16, SECTOR)
root_dr = pvd[156:156+34]
root_lba = struct.unpack('<I', root_dr[2:6])[0]
root_len = struct.unpack('<I', root_dr[10:14])[0]

def parse_dir(lba, length):
    data = read_at(lba, ((length + SECTOR - 1)//SECTOR)*SECTOR)
    entries, off = [], 0
    while off < length:
        rec_len = data[off]
        if rec_len == 0:
            off = ((off // SECTOR) + 1) * SECTOR
            if off >= length: break
            continue
        rec = data[off:off+rec_len]
        ext_lba = struct.unpack('<I', rec[2:6])[0]
        ext_len = struct.unpack('<I', rec[10:14])[0]
        flags = rec[25]
        nl = rec[32]
        name = rec[33:33+nl]
        if name == b'\x00': name = '.'
        elif name == b'\x01': name = '..'
        else:
            name = name.decode('ascii','replace').split(';')[0]
        entries.append((name, ext_lba, ext_len, flags))
        off += rec_len
    return entries

files = []   # (fullpath, lba, len)
def walk(lba, length, path=''):
    for name, elba, elen, flags in parse_dir(lba, length):
        if name in ('.','..'): continue
        full = path + '/' + name
        if flags & 0x02:
            walk(elba, elen, full)
        else:
            files.append((full, elba, elen))
walk(root_lba, root_len)

pattern = sys.argv[1] if len(sys.argv) > 1 else None
count = 0
for full, lba, elen in files:
    if pattern and not re.search(pattern, full, re.I):
        continue
    dst = os.path.join(OUT, full.lstrip('/').replace('/', os.sep))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    f.seek(lba*SECTOR)
    data = f.read(elen)
    with open(dst, 'wb') as o:
        o.write(data)
    print(f"{elen:10d}  {full}")
    count += 1
print("extracted:", count)
