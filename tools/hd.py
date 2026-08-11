import sys

def hexdump(data, base=0, limit=None):
    if limit: data = data[:limit]
    out = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hx = ' '.join(f'{b:02X}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        out.append(f'{base+i:08X}  {hx:<47}  |{asc}|')
    return '\n'.join(out)

if __name__ == '__main__':
    path = sys.argv[1]
    off = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
    ln  = int(sys.argv[3], 0) if len(sys.argv) > 3 else 256
    with open(path, 'rb') as f:
        f.seek(off)
        print(hexdump(f.read(ln), off))
