# -*- coding: utf-8 -*-
"""
삽입한 한글 폰트를 게임과 똑같은 경로로 렌더링해 검증한다.

  한글 문자열
    -> make_hangul_font.encode()  (SJIS 바이트열)
    -> 게임의 SJIS->글리프 변환
         사쿠라 1 : FONTALL.FNT 안의 FIDX 테이블을 그대로 조회
         사쿠라 2 : SAKURA2.ELF 의 변환 루틴을 MIPS 에뮬레이션 (fnt4b_map)
    -> 패치된 폰트에서 글리프 비트맵을 잘라 붙임

즉 폰트·매핑·인코더 전체 사슬을 검증한다. 글자가 제대로 읽히면 게임에서도 읽힌다.
"""
import struct, os, sys
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_hangul_font import encode, BUILD, ROOT, CELL
from cmp import decompress

# ------------------------------------------------------------ 사쿠라 1 폰트
class Sakura1:
    name = "사쿠라대전 1 (FONTALL.FNT)"
    def __init__(self, path):
        d = open(path, 'rb').read()
        fidx, fimg = d.find(b'FIDX'), d.find(b'FIMG')
        n = struct.unpack_from('>I', d, fidx+8)[0]
        self.idx = np.frombuffer(d[fidx+16: fidx+16+n*4], dtype='>u2').reshape(-1, 2)
        cnt = struct.unpack_from('>I', d, fimg+8)[0]
        self.raw = np.frombuffer(d[fimg+16: fimg+16+cnt*512], np.uint8).reshape(cnt, 512)
        o = np.empty(CELL*CELL, np.int64)
        for m in range(CELL*CELL):
            x = y = 0
            for b in range(5):
                y |= ((m >> (2*b)) & 1) << b
                x |= ((m >> (2*b+1)) & 1) << b
            o[m] = y*CELL + x
        self.order = o
    def glyph_index(self, sjis):
        code = sjis - 0x8000
        if not (0 <= code < self.idx.shape[0]): return None
        g = int(self.idx[code, 0])
        return None if g == 0xFFFF else g
    def metrics(self, sjis):
        """FIDX 엔트리의 { u8 xOffset, u8 width } — 게임이 자간 계산에 쓰는 값"""
        code = sjis - 0x8000
        v = int(self.idx[code, 1])
        return v >> 8, v & 0xFF
    def bitmap(self, g):
        r = self.raw[g]
        nb = np.empty(CELL*CELL, np.uint8)
        nb[0::2], nb[1::2] = r & 0xF, r >> 4          # 하위 니블 먼저
        img = np.empty(CELL*CELL, np.uint8); img[self.order] = nb
        return (15 - img.reshape(CELL, CELL)) / 15.0  # 0=잉크 -> 잉크강도

# ------------------------------------------------------------ 사쿠라 2 폰트
class Sakura2:
    name = "사쿠라대전 2 (FNT4B.CMP)"
    def __init__(self, path):
        raw, *_ = decompress(open(path, 'rb').read())
        W, H = struct.unpack('>HH', raw[:4])
        a = np.frombuffer(raw[4:4+W*H//2], np.uint8).reshape(H, W//2)
        img = np.empty((H, W), np.uint8)
        img[:, 0::2], img[:, 1::2] = a >> 4, a & 0xF   # 상위 니블이 왼쪽 픽셀
        self.img, self.W, self.H = img, W, H
        import numpy as _np
        tpl = open(os.path.join(ROOT, "extract", "PSP_GAME", "USRDIR",
                                "SAKURA2", "FNT4B.TPL"), 'rb').read()
        pal = _np.frombuffer(tpl[4:36], dtype='>u2')
        lum = _np.array([((c >> 10) & 0x1F)*255/31 for c in pal])
        self.ink = (255 - lum)/255          # 인덱스 -> 잉크 농도 (비선형)
        import fnt4b_map
        self._lookup = fnt4b_map.glyph_of              # 게임 코드 에뮬레이션
    def glyph_index(self, sjis):
        g = self._lookup(sjis)
        return g if 0 < g < (self.H//CELL)*32 else (0 if sjis == 0x8140 else None)
    def bitmap(self, g):
        gy, gx = (g//32)*CELL, (g % 32)*CELL
        return self.ink[self.img[gy:gy+CELL, gx:gx+CELL]]   # 팔레트로 농도 변환

# ------------------------------------------------------------ 그리기
def draw_line(font, text, canvas, x, y):
    b = encode(text)
    i = 0
    while i < len(b):
        if 0x81 <= b[i] <= 0x9F or 0xE0 <= b[i] <= 0xEF:
            sjis = (b[i] << 8) | b[i+1]; i += 2
        else:
            sjis = 0x8140; i += 1                      # 반각은 이 테스트에선 공백 처리
        g = font.glyph_index(sjis)
        adv = CELL
        if hasattr(font, 'metrics'):
            off, w = font.metrics(sjis)
            if w: adv = w
        if g is None:
            canvas[y:y+CELL, x:x+CELL] = 0.15          # 미매핑은 회색 박스
        else:
            canvas[y:y+CELL, x:x+CELL] = np.maximum(canvas[y:y+CELL, x:x+CELL],
                                                    font.bitmap(g))
        x += adv
    return x

def sheet(font, blocks, out_png, scale=2):
    rows = sum(len(b[1]) for b in blocks) + len(blocks)
    W = 34*CELL
    canvas = np.zeros((rows*CELL + 8, W), np.float32)
    labels = []
    y = 0
    for title, lines in blocks:
        labels.append((y, title))
        y += CELL
        for ln in lines:
            draw_line(font, ln, canvas, 0, y)
            y += CELL
    img = Image.fromarray(((1-canvas)*255).astype(np.uint8), 'L').convert('RGB')
    img = img.resize((img.width*scale, img.height*scale), Image.NEAREST)
    dr = ImageDraw.Draw(img)
    for yy, t in labels:
        dr.rectangle([0, yy*scale, img.width, (yy+CELL)*scale-1], fill=(232, 236, 246))
        dr.text((6, yy*scale + 8), f"{t}", fill=(30, 40, 110))
    img.save(out_png)
    print(f"  -> {os.path.basename(out_png)}  {img.size}")

BLOCKS = [
    ("[대사] 사쿠라 브로마이드", [
        "사쿠라의 브로마이드다.",
        "가만히 이쪽을 바라보고 있다.",
        "무슨 생각을 하는 걸까……"]),
    ("[대사] 전투 개시", [
        "제국화격단, 등장‼",
        "무사한가, 오리히메!",
        "모두, 가자! 전투 개시‼"]),
    ("[대사] 오리히메 말투", [
        "괜찮아요~!",
        "이 정도는 식은 죽 먹기,",
        "라는 느낌!"]),
    ("[혼합] 숫자·기호·외자", [
        "태정 12년, 제도 도쿄.",
        "지금 뭐라고 했어요⁉",
        "영자갑주 「광무」 출격!"]),
    ("[길이] 16자 상한 확인", [
        "1234567890123456",
        "가나다라마바사아자차카타파하가나",
        "짧은 줄"]),
]

if __name__ == '__main__':
    os.makedirs(os.path.join(ROOT, "test_render"), exist_ok=True)
    for cls, fname in ((Sakura1, "FONTALL.FNT"), (Sakura2, "FNT4B.CMP")):
        p = os.path.join(BUILD, fname)
        if not os.path.exists(p):
            print(f"{fname} 없음 - make_hangul_font.py 를 먼저 실행하세요"); continue
        f = cls(p)
        print(f.name)
        sheet(f, BLOCKS, os.path.join(ROOT, "test_render",
              f"render_{fname.split('.')[0]}.png"))
