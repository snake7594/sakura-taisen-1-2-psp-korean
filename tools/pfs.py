# -*- coding: utf-8 -*-
"""
Sakura Taisen 1 (PSP) ".PFS" archive ("PAKFILE").

    char  magic[8]   "PAKFILE\0"
    u32BE count
    u32BE reserved
    count x {
        char  name[16]      NUL padded
        u32BE offset        in 2048-byte sectors
        u32BE size          in bytes
    }

  python pfs.py <file.pfs> [outdir]     unpack (no outdir = just list)
"""
import struct, sys, os

SECTOR = 2048

def entries(d):
    assert d[:7] == b'PAKFILE', "not a PAKFILE archive"
    n = struct.unpack_from('>I', d, 8)[0]
    out = []
    for i in range(n):
        o = 0x10 + i*24
        name = d[o:o+16].split(b'\0')[0].decode('ascii', 'replace')
        off, size = struct.unpack_from('>II', d, o+16)
        out.append((name, off*SECTOR, size))
    return out

if __name__ == '__main__':
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else None
    d = open(path, 'rb').read()
    ent = entries(d)
    print(f"{os.path.basename(path)}: {len(ent)} members")
    for name, off, size in ent:
        print(f"  {name:<20} @0x{off:08X}  {size:9d}")
        if outdir:
            os.makedirs(outdir, exist_ok=True)
            open(os.path.join(outdir, name), 'wb').write(d[off:off+size])
    if outdir:
        print(f"-> {outdir}")
