# -*- coding: utf-8 -*-
"""
사쿠라대전 2 실기 확인용 자(ruler) 삽입.

`.MES` 는 { u32BE count, count x u32BE 절대오프셋, 엔트리들 } 이고
엔트리 = 4바이트 헤더(화자/음성 ID) + 텍스트다. 텍스트는 **16비트 리틀엔디안** 단위에
Shift-JIS 쌍을 담으므로 바이트를 뒤집어 써야 한다. 0xFFFE=줄바꿈, 0xFFFF=끝.

각 엔트리의 기존 0xFFFF 종료 지점까지만 덮어쓴다. `EV*.MES` 는 메시지 뒤에 립싱크
데이터가 붙어 있는데, 이렇게 하면 절대 건드리지 않는다. 헤더 4바이트도 보존한다.
오프셋 테이블을 안 건드리므로 파일 크기가 그대로다.
"""
import os, sys, struct

ROOT  = r"D:\psp\사쿠라대전1_2"
SRC   = os.path.join(ROOT, "extract", "PSP_GAME", "USRDIR", "SAKURA2", "SAKURA2")
BUILD = os.path.join(ROOT, "build", "mes")
DIGITS = "１２３４５６７８９０"
MINCH  = 26          # 이 글자 수 이상 들어가는 엔트리만 자로 교체

def enc_le(text):
    """문자열 -> 16비트 리틀엔디안 SJIS 바이트열"""
    out = bytearray()
    for ch in text:
        b = ch.encode('cp932')
        assert len(b) == 2, ch
        out += bytes((b[1], b[0]))       # 바이트 뒤집기
    return bytes(out)

END = b'\xff\xff'

def patch_mes(d):
    n = struct.unpack_from('>I', d, 0)[0]
    if 4 + n*4 > len(d): return d, 0
    offs = list(struct.unpack_from(f'>{n}I', d, 4))
    out = bytearray(d)
    made = 0
    for i, o in enumerate(offs):
        body = o + 4                                  # 헤더 4바이트 건너뜀
        # 기존 종료(0xFFFF) 위치 찾기
        end = None
        j = body
        limit = offs[i+1] if i+1 < n else len(d)
        while j + 1 < limit:
            if d[j] == 0xFF and d[j+1] == 0xFF:
                end = j; break
            j += 2
        if end is None: continue
        avail = end + 2 - body                        # 0xFFFF 자리 포함
        nch = (avail - 2)//2
        if nch < MINCH: continue
        ruler = enc_le((DIGITS * ((nch//10)+2))[:nch]) + END
        assert len(ruler) <= avail
        out[body:body+len(ruler)] = ruler
        out[body+len(ruler): end+2] = b'\x00' * (end + 2 - body - len(ruler))
        made += 1
    return bytes(out), made

if __name__ == '__main__':
    os.makedirs(BUILD, exist_ok=True)
    files = sorted(f for f in os.listdir(SRC) if f.upper().endswith('.MES'))
    if not files:
        sys.exit(f"{SRC} 에 .MES 가 없습니다 — 먼저 ISO 에서 추출하세요")
    total = done = 0
    longest = 0
    for fn in files:
        d = open(os.path.join(SRC, fn), 'rb').read()
        new, made = patch_mes(d)
        assert len(new) == len(d)
        if made:
            open(os.path.join(BUILD, fn), 'wb').write(new)
            done += 1; total += made
    print(f"{len(files)}개 중 {done}개 파일, 엔트리 {total}개를 자로 교체")
    print(f"-> {BUILD}")
