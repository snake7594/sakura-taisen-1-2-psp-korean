import struct, sys

class ELF:
    def __init__(self, path):
        self.d = d = open(path,'rb').read()
        assert d[:4] == b'\x7fELF'
        (self.e_type, self.e_machine, self.e_version, self.e_entry, self.e_phoff,
         self.e_shoff, self.e_flags, self.e_ehsize, self.e_phentsize, self.e_phnum,
         self.e_shentsize, self.e_shnum, self.e_shstrndx) = struct.unpack_from('<HHIIIIIHHHHHH', d, 16)
        self.phdrs, self.shdrs = [], []
        for i in range(self.e_phnum):
            o = self.e_phoff + i*self.e_phentsize
            if o + 32 > len(d): break
            t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<IIIIIIII', d, o)
            self.phdrs.append(dict(type=t, off=off, vaddr=va, filesz=fsz, memsz=msz, flags=fl))
        for i in range(self.e_shnum):
            o = self.e_shoff + i*self.e_shentsize
            if o + 40 > len(d): break
            nm, t, fl, va, off, sz, lk, inf, al, es = struct.unpack_from('<IIIIIIIIII', d, o)
            self.shdrs.append(dict(name=nm, type=t, flags=fl, addr=va, off=off, size=sz))
        # section name strings
        self.shstr = b''
        if self.e_shstrndx < len(self.shdrs):
            s = self.shdrs[self.e_shstrndx]
            self.shstr = d[s['off']: s['off']+s['size']]
        for s in self.shdrs:
            e = self.shstr.find(b'\0', s['name'])
            s['sname'] = self.shstr[s['name']:e].decode('ascii','replace') if e > 0 else ''

    def va_to_off(self, va):
        for p in self.phdrs:
            if p['type'] == 1 and p['vaddr'] <= va < p['vaddr']+p['filesz']:
                return p['off'] + (va - p['vaddr'])
        for s in self.shdrs:
            if s['addr'] and s['addr'] <= va < s['addr']+s['size'] and s['type'] != 8:
                return s['off'] + (va - s['addr'])
        return None

    def read_va(self, va, n):
        o = self.va_to_off(va)
        return self.d[o:o+n] if o is not None else None

if __name__ == '__main__':
    e = ELF(sys.argv[1])
    print(f"type={e.e_type} machine={e.e_machine} entry=0x{e.e_entry:08X} "
          f"phnum={e.e_phnum} shnum={e.e_shnum} size={len(e.d)}")
    print("\nPT_LOAD segments:")
    for p in e.phdrs:
        if p['type'] == 1:
            print(f"  off=0x{p['off']:08X} vaddr=0x{p['vaddr']:08X} filesz=0x{p['filesz']:X} memsz=0x{p['memsz']:X} flags={p['flags']}")
    print("\nsections (non-empty):")
    for s in e.shdrs[:40]:
        if s['size']:
            print(f"  {s['sname']:<22} type={s['type']:<4} addr=0x{s['addr']:08X} off=0x{s['off']:08X} size=0x{s['size']:X}")
