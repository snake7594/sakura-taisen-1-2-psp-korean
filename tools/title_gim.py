# -*- coding: utf-8 -*-
"""사쿠라 2 시작 화면(SK2TITLE.GIM)의 일본어/영어 라벨을 한글로 교체한다.

SK2TITLE.GIM은 압축되지 않은 인덱스 이미지 묶음이다. 3, 4, 5, 6, 7번
이미지는 각각 4bpp 문자 레이어이며, 이미지마다 별도 16색 팔레트를 가진다.
따라서 청크 구조와 파일 크기는 그대로 두고 글자 픽셀만 다시 그린다.

    python tools/title_gim.py
    python tools/title_gim.py --check

결과는 build/patched/SK2TITLE.GIM에 저장되고 build_iso.py가 같은 이름의
ISO 파일을 자동으로 찾아 교체한다.
"""
import os
import sys
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import gim
from build_iso import SRC_ISO, SECTOR, walk_iso

FONT = os.path.join(ROOT, "NanumSquareNeo-cBd.ttf")
BUILD = os.path.join(ROOT, "build", "patched")
ISO_PATH = "/PSP_GAME/USRDIR/SAKURA2/SK2TITLE.GIM"

# (이미지 번호, 번역문, 종류)
# 이미지 5와 6은 보통/선택 상태가 같은 문구를 서로 다른 팔레트로 가진다.
JOBS = [
    (3, "게임 시작", "outline"),            # ゲームをはじめる
    (4, "START 버튼을 누르세요", "button"),  # Press START button
    (5, "사쿠라대전 1로", "outline"),        # サクラ大戦1 へ
    (6, "사쿠라대전 1로", "outline"),        # 5 와 같은 문구, 선택 상태
    (7, "일러스트 감상", "small"),           # イラスト鑑賞 — 설정이 아니라 감상이다
]


def read_iso_file(path):
    with open(SRC_ISO, "rb") as f:
        table = walk_iso(f)
        rec = table[path]
        _, lba, size = rec
        f.seek(lba * SECTOR)
        return f.read(size)


def unpack4(raw):
    """4bpp 바이트 행을 low-nibble-left 픽셀 배열로 푼다."""
    out = np.empty((raw.shape[0], raw.shape[1] * 2), dtype=np.uint8)
    out[:, 0::2] = raw & 0x0F
    out[:, 1::2] = raw >> 4
    return out


def pack4(px):
    """unpack4의 역변환."""
    return ((px[:, 0::2] & 0x0F) | (px[:, 1::2] << 4)).astype(np.uint8)


def swizzle(a):
    """GIM pixelOrder=1의 16바이트 x 8행 블록 스위즐."""
    height, pitch = a.shape
    return a.reshape(height // 8, 8, pitch // 16, 16).transpose(
        0, 2, 1, 3
    ).reshape(-1)


def text_masks(text, width, height, stroke):
    """상자 중앙에 맞춘 외곽선/내부 글자 마스크를 만든다."""
    for size in range(min(32, height + 8), 5, -1):
        font = ImageFont.truetype(FONT, size)
        probe = ImageDraw.Draw(Image.new("L", (1, 1)))
        box = probe.textbbox((0, 0), text, font=font, stroke_width=stroke)
        if box[2] - box[0] <= width - 2 and box[3] - box[1] <= height - 2:
            break
    else:
        raise ValueError(f"문구가 상자에 들어가지 않습니다: {text!r} {width}x{height}")

    x = (width - (box[2] - box[0])) // 2 - box[0]
    y = (height - (box[3] - box[1])) // 2 - box[1]

    outer = Image.new("L", (width, height), 0)
    ImageDraw.Draw(outer).text(
        (x, y), text, font=font, fill=255,
        stroke_width=stroke, stroke_fill=255,
    )
    inner = Image.new("L", (width, height), 0)
    ImageDraw.Draw(inner).text((x, y), text, font=font, fill=255)
    return np.asarray(outer), np.asarray(inner), size


def draw_outline(text, width, height, stroke=2):
    """인덱스 0 배경 + 1~7 외곽선 + 8~15 밝은 내부 글자."""
    outer, inner, size = text_masks(text, width, height, stroke=stroke)
    out = np.zeros((height, width), dtype=np.uint8)
    q_outer = np.clip(1 + np.rint(outer.astype(np.float32) * 6 / 255), 1, 7)
    q_inner = np.clip(8 + np.rint(inner.astype(np.float32) * 7 / 255), 8, 15)
    out[outer > 0] = q_outer[outer > 0].astype(np.uint8)
    out[inner > 0] = q_inner[inner > 0].astype(np.uint8)
    return out, size


def draw_button(base, text, width, height):
    """흰 버튼 배경은 보존하고 분홍색 문구만 다시 그린다."""
    # 팔레트 4는 0~1=검정, 2~6=분홍, 7~15=흰색이다.
    base[(base >= 2) & (base <= 6)] = 15
    mask, _, size = text_masks(text, width, height, stroke=1)
    # 흰색(15)에서 진분홍(2)으로 알파를 보간한다.
    q = np.clip(15 - np.rint(mask.astype(np.float32) * 13 / 255), 2, 15)
    reg = base[:height, :width]
    reg[mask > 0] = q[mask > 0].astype(np.uint8)
    return base, size


def patch(data):
    """원본 GIM의 지정된 4bpp 이미지 청크를 수정한 바이트열을 반환한다."""
    d = bytearray(data)
    images = gim._find(d, 0x10, len(d), 4)
    if len(images) < 8:
        raise ValueError(f"SK2TITLE 이미지 수가 예상보다 적습니다: {len(images)}")

    reports = []
    for image_no, text, kind in JOBS:
        off = images[image_no]
        w, h, fmt, raw_view = gim._read_block(d, off)
        if fmt != 4:
            raise ValueError(f"이미지 {image_no}가 4bpp가 아닙니다: fmt={fmt}")
        raw = np.array(raw_view, dtype=np.uint8, copy=True)
        px = unpack4(raw)
        if kind == "button":
            new_px, size = draw_button(px, text, w, h)
        else:
            logical, size = draw_outline(text, w, h, stroke=1 if kind == "small" else 2)
            # 4bpp 행은 4바이트 정렬되어 논리 폭보다 넓을 수 있다.
            new_px = np.zeros_like(px)
            new_px[:h, :w] = logical

        # 논리적 폭 밖의 정렬용 픽셀은 투명/배경으로 정리한다.
        if kind != "button":
            new_px[:, w:] = 0
        raw[:] = pack4(new_px)

        header = off + 0x10
        order = struct.unpack_from("<H", d, header + 0x06)[0]
        pixels_offset, pixels_end = struct.unpack_from("<II", d, header + 0x1C)
        start = header + pixels_offset
        end = header + pixels_end
        if end - start != raw.nbytes:
            raise ValueError(
                f"이미지 {image_no} 픽셀 길이 불일치: 청크={end-start}, 계산={raw.nbytes}"
            )
        disk = swizzle(raw) if order == 1 else raw.reshape(-1)
        if disk.nbytes != end - start:
            raise ValueError(f"이미지 {image_no} 스위즐 길이 불일치")
        d[start:end] = disk.tobytes()
        reports.append((image_no, w, h, text, size))
    return bytes(d), reports


def main(check_only=False):
    original = read_iso_file(ISO_PATH)
    patched, reports = patch(original)
    assert len(patched) == len(original), "GIM 파일 크기가 바뀌었습니다"
    print(f"원본: {len(original)} 바이트, 수정: {len(patched)} 바이트")
    for image_no, w, h, text, size in reports:
        print(f"  IMG{image_no}: {w}x{h}, {size}px, {text}")

    # GIM 디코더로 청크 트리와 이미지 수를 다시 확인한다.
    decoded = gim.decode(patched)
    assert len(decoded) == 15, f"재검증 이미지 수 오류: {len(decoded)}"
    print("재검증: GIM 디코드 통과 (15장)")
    if not check_only:
        os.makedirs(BUILD, exist_ok=True)
        out = os.path.join(BUILD, "SK2TITLE.GIM")
        with open(out, "wb") as f:
            f.write(patched)
        print(f"  -> {out}")


if __name__ == "__main__":
    main("--check" in sys.argv)
