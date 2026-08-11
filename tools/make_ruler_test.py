# -*- coding: utf-8 -*-
"""
실기 확인용 테스트 빌드.

두 가지를 한 번에 본다.
  A) 대사창에 한 줄 몇 글자가 들어가는가
     -> 전각 숫자 자를 넣는다. １２３４５６７８９０ 반복이라 ０ 이 10자 단위.
  B) FIDX 의 width 바이트가 실제 자간으로 쓰이는가
     -> Ａ~Ｚ 의 width 를 16(반각)으로 낮춘 뒤, 숫자 10개 / 알파벳 10개를
        두 줄로 나란히 출력한다. 아래 줄이 절반 길이면 width 가 동작하는 것.

전각 공백(0x8140)으로 시험했다가 실패한 이유:
  SAKURA1.ELF 0x08954358 이 로드할 때 아래 9자의 메트릭을 기본값으로 되쓴다.
      0x8140 　  0x8141 、  0x8142 。  0x8169 （  0x816A ）
      0x8175 「  0x8176 」  0x8177 『  0x8178 』
  (테이블 @0x08AAFE4C, u16 리틀엔디안)
  하필 첫 항목이 전각 공백이라 파일 수정이 무시됐다. 그래서 되쓰기 대상이 아닌
  Ａ~Ｚ 로 시험한다.

문자열은 원본과 같은 바이트 길이 안에서만 덮어쓰므로(남는 자리는 NUL) 오프셋
테이블을 건드릴 필요가 없다. 세 줄짜리 대사를 한 줄로 바꾸면 그만큼 긴 자를 넣을 수 있다.
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pfs import entries as pfs_entries

ROOT  = r"D:\psp\사쿠라대전1_2"
SRC   = os.path.join(ROOT, "extract", "PSP_GAME", "USRDIR")
BUILD = os.path.join(ROOT, "build")
NFILE = 8          # 앞쪽 시나리오 몇 개에 자를 넣을지

DIGITS = "１２３４５６７８９０"
ALPHA  = "ＡＢＣＤＥＦＧＨＩＪ"

def sjis(s): return s.encode('cp932')

def rulers(avail):
    """avail 바이트 안에 들어가는 두 종류의 자"""
    a = sjis((DIGITS * 6))[:avail // 2 * 2]                       # A: 최대한 긴 한 줄
    two = sjis(DIGITS) + b'$$' + sjis(ALPHA)                      # B: 숫자10 / 영문10
    return a, (two if len(two) <= avail else a)

def patch_tbl(d):
    """tbl.bin 한 개의 긴 문자열들을 자로 덮어쓴다 (제자리, 길이 불변)"""
    words = struct.unpack_from('>H', d, 0)[0]
    n = words // 2
    base = 4 + n*4
    ents = []
    for k in range(n):
        _, off = struct.unpack_from('>HH', d, 4 + k*4)
        ents.append(base + off*2)
    order = sorted(set(ents))
    nxt = {p: (order[i+1] if i+1 < len(order) else len(d)) for i, p in enumerate(order)}

    out = bytearray(d)
    made = 0
    for i, p in enumerate(order):
        avail = nxt[p] - p - 1                    # NUL 자리 하나 남김
        if avail < 60: continue
        a, b = rulers(avail)
        new = a if (made % 2 == 0) else b
        if len(new) > avail: continue
        out[p:p+len(new)] = new
        out[p+len(new): nxt[p]] = b'\x00' * (nxt[p] - p - len(new))
        made += 1
    return bytes(out), made

def patch_pfs(src_path, dst_path):
    d = bytearray(open(src_path, 'rb').read())
    mem = [m for m in pfs_entries(d) if m[0].lower().endswith('tbl.bin')]
    total = 0
    for name, off, sz in mem[:NFILE]:
        new, made = patch_tbl(bytes(d[off:off+sz]))
        assert len(new) == sz
        d[off:off+sz] = new
        print(f"    {name}: 문자열 {made}개를 자로 교체")
        total += made
    open(dst_path, 'wb').write(bytes(d))
    return total

def patch_font_widths(src_path, dst_path, width=16):
    """Ａ~Ｚ (SJIS 0x8260~0x8279) 의 자간을 반각으로 — 되쓰기 대상이 아닌 문자"""
    d = bytearray(open(src_path, 'rb').read())
    fidx = d.find(b'FIDX')
    n = 0
    for code in range(0x8260, 0x827A):
        ent = fidx + 16 + (code - 0x8000)*4
        g = struct.unpack_from('>H', d, ent)[0]
        if g == 0xFFFF: continue
        d[ent+3] = width
        n += 1
    # 전각 공백은 어차피 되쓰기 대상이라 원래대로(32) 돌려놓는다
    ent = fidx + 16 + (0x8140 - 0x8000)*4
    d[ent+3] = 32
    open(dst_path, 'wb').write(bytes(d))
    return n

if __name__ == '__main__':
    os.makedirs(BUILD, exist_ok=True)
    print("폰트: Ａ~Ｚ 자간을 16으로, 전각공백은 32로 복원")
    n = patch_font_widths(os.path.join(BUILD, "FONTALL.FNT"),
                          os.path.join(BUILD, "FONTALL.FNT"))
    print(f"    {n}자 수정")
    print(f"대사: ADVMACRO.PFS 앞쪽 {NFILE}개 시나리오에 자 삽입")
    t = patch_pfs(os.path.join(SRC, r"SAKURA1\SAKURA1\ADVMACRO.PFS"),
                  os.path.join(BUILD, "ADVMACRO.PFS"))
    print(f"    합계 {t}개")
    print(f"\n-> {BUILD}")
