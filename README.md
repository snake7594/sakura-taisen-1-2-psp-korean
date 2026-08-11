# 사쿠라대전 1&2 (PSP) 한글 패치

PSP용 『サクラ大戦1&2』(ULJM05109) 한글화 패치입니다.
대사 전문, 시스템 문자열, 메뉴 이미지를 한국어로 옮겼습니다.

배포는 **xdelta 차분 패치**로만 합니다. 게임 파일은 이 저장소에 없습니다.
직접 덤프한 ISO 를 준비하셔야 합니다.

---

## 1. 원본 ISO 확인

패치는 **정확히 이 덤프에만** 적용됩니다. 먼저 해시부터 맞춰 보세요.

| 항목 | 값 |
|---|---|
| 파일명 | `Sakura Taisen 1 and 2.iso` |
| 크기 | 1,756,037,120 바이트 |
| **MD5** | **`B8B4D8F10B99E610A085845E35FB358E`** |
| SHA1 | `62AEEC46C4174C024A7B743DDC8ACF1ABA2EDAF2` |

해시 확인 방법:

```bash
certutil -hashfile "Sakura Taisen 1 and 2.iso" MD5
```

```bash
md5sum "Sakura Taisen 1 and 2.iso"
```

**MD5 가 다르면 패치가 적용되지 않습니다.** 다른 리전이거나, 다시 압축된
덤프이거나, CSO 로 변환된 파일입니다. CSO 라면 먼저 ISO 로 되돌리세요.

---

## 2. 패치 적용

[Releases](../../releases) 에서 `Sakura Taisen 1 and 2 (KR).xdelta` 를 받으세요.

### 방법 A — xdelta3 명령줄

```bash
xdelta3 -d -s "Sakura Taisen 1 and 2.iso" "Sakura Taisen 1 and 2 (KR).xdelta" "Sakura Taisen 1 and 2 (KR).iso"
```

`-s` 뒤가 **원본**, 그다음이 **패치 파일**, 마지막이 **만들어질 파일**입니다.
순서를 바꾸면 엉뚱한 결과가 나옵니다.

### 방법 B — xdeltaUI (그래픽)

1. `Apply Patch` 탭 선택
2. **Patch** : `Sakura Taisen 1 and 2 (KR).xdelta`
3. **Source File** : 원본 `Sakura Taisen 1 and 2.iso`
4. **Output File** : 원하는 이름 (예: `사쿠라대전1_2 한글.iso`)
5. `Apply` 클릭

### 적용 결과 확인

| 항목 | 값 |
|---|---|
| 크기 | 1,756,037,120 바이트 (원본과 같음) |
| MD5 | `271328C8F54B574B6F94C771C38419AA` |
| SHA1 | `3F99137C3CB915D0A385D7ADCAC80A4F1C6B7EFB` |

이 값이 나오면 정상입니다.

### 실행

PPSSPP 또는 CFW 가 올라간 실기에서 그대로 실행하면 됩니다.
별도 설정은 필요 없습니다. **텍스처 교체(HD 텍스처 팩)를 쓰지 않습니다** —
모든 패치가 ISO 안에 들어 있습니다.

---

## 3. 패치 내용

| 분류 | 내용 |
|---|---|
| 대사 | 사쿠라1·2 본편, 이벤트, SLG 전투 파트, 미니게임 — 86,376행 |
| 시스템 문자열 | ELF 하드코딩 문자열 423개 (저장/불러오기, 타이틀, 옵션, 전투 명령, 사운드 테스트) |
| 메뉴 이미지 | 명령 라벨, 화투 미니게임, 시스템 창, 사쿠라2 명령창 — 33장 |
| 지도 화면 | 방 이름 표지판 63장, 오른쪽 세로 패널 26장 |
| 미니게임 | `MG0000DAIF.BIN` 166개 문자열 |
| 저장 대화상자 | 덮어쓸까요? / 저장할까요? / 복사할까요? / 지울까요? / 불러올까요? |
| 글꼴 | 나눔스퀘어네오 Bold 를 완성형 2350자로 삽입 |

### 알려진 한계

- **일부 자산 이름에 한자가 남아 있으면 엉뚱한 한글로 보입니다.** 글꼴을
  JIS 1수준 한자 자리(ku16~ku40)에 한글로 덮어썼기 때문입니다. 화면에
  나오는 대사에는 해당하지 않습니다.
- **화 제목 영상**은 일본어 그대로입니다. 480×256 H.264 PMF 동영상이라
  재인코딩 + PSMF 리먹스가 필요한데 여유 용량이 사실상 없습니다.
- **사쿠라2 메뉴책 일부**가 일본어로 남아 있습니다. 형식은 해독했고
  ([tools/pbook.py](tools/pbook.py)) 저장 대화상자는 적용했지만,
  낱장별 덧그리기가 아직 남았습니다.
- `SLGTAB.PFS` 는 개발용 애니메이션 표 라벨이라 화면에 안 나옵니다. 그대로 뒀습니다.

---

## 4. 직접 빌드하기

패치를 고치거나 다시 만들고 싶다면.

### 준비물

- Python 3.11+ (`numpy`, `Pillow`)
- 원본 ISO (위 MD5 와 일치하는 것)
- [xdelta3](https://github.com/jmacd/xdelta) — 배포 패치를 만들 때만

```bash
pip install numpy Pillow
```

### 경로 설정

`tools/build_iso.py` 의 `SRC_ISO` 를 원본 ISO 경로로 맞추세요.
작업 폴더 기준으로 다음 구조를 씁니다.

```
사쿠라대전1_2/
├── Sakura Taisen 1 and 2.iso   <- 직접 준비 (저장소에 없음)
├── text/                        <- 원문·번역문 TSV
├── tools/                       <- 도구 일체
├── NanumSquareNeo-*.ttf         <- 글꼴
├── extract/                     <- ISO 에서 뽑은 게임 파일 (생성됨)
└── build/patched/               <- 패치된 게임 파일 (생성됨)
```

### 순서

```bash
python tools/iso_extract.py
```

원본 ISO 에서 게임 파일을 `extract/` 로 풉니다.

```bash
python tools/make_hangul_font.py
```

나눔스퀘어네오 Bold 로 게임 글꼴을 만듭니다.

```bash
python tools/reinsert.py
```

`text/*.tsv` 의 번역문을 게임 텍스트 컨테이너에 되넣습니다.

```bash
python tools/elf_text.py
```

ELF 안의 하드코딩 문자열을 바꿉니다.

```bash
python tools/menu_images.py && python tools/map_signs.py && python tools/book_text.py
```

메뉴 이미지, 지도 표지판, 저장 대화상자를 다시 그립니다.

```bash
python tools/build_iso.py
```

`build/patched/` 의 결과물을 원본 ISO 에 덮어써 한글판 ISO 를 만듭니다.
파일은 **원래 LBA 자리에 그대로** 씁니다. 그래서 크기가 안 변하고
원본보다 커지면 안 됩니다.

```bash
python tools/check_translation.py
```

줄 길이·줄 수가 넘치는 행을 검사합니다.

---

## 5. 번역문 고치기

`text/*.tsv` 는 탭으로 나뉜 표입니다. **`ko` 열만** 고치면 됩니다.

| 파일 | 대상 |
|---|---|
| `sakura1_adv.tsv` | 사쿠라1 본편 (`ADVMACRO.PFS`) |
| `sakura1_slg.tsv` | 사쿠라1 SLG 파트 (`SLGMAP.PFS`) |
| `sakura2_adv.tsv` | 사쿠라2 본편 (`SK*.CMP`) |
| `sakura2_evt.tsv` | 사쿠라2 이벤트 (`EV*.MES`, `SYS*.MES`) |
| `sakura2_slg.tsv` | 사쿠라2 SLG 파트 (`M*LOW.CMP`) |
| `mg_daif.tsv` | 미니게임 (`MG0000DAIF.BIN`) |
| `elf_sakura1.tsv` / `elf_sakura2.tsv` | ELF 하드코딩 문자열 |

### 지켜야 할 제약

**글자 수 제한이 있습니다.** 글자 폭이 고정(한 칸에 한 글자)이라
줄 길이가 곧 글자 수입니다.

| 게임 | 한 줄 | 줄 수 |
|---|---|---|
| 사쿠라1 | 21자 | 3줄 |
| 사쿠라2 | 14자 | 3줄 |

**반각 문자는 글꼴에 없습니다.** ASCII 를 그냥 쓰면 안 보입니다.
`tools/fix_chars.py` 가 전각으로 바꿔 줍니다.

**제어 토큰은 건드리지 마세요.** `<...>` 형태로 들어 있는 것들은
줄바꿈·색·대기 같은 게임 명령입니다.

ELF 문자열은 **원래 바이트 수를 넘으면 안 됩니다.** `maxbytes` 열이 한도입니다.
`enc` 열이 `sjis` 면 게임 글꼴로 그려지고, `utf8` 이면 PSP 시스템 글꼴로
그려집니다 (세이브 목록 등).

고친 뒤:

```bash
python tools/fix_chars.py && python tools/check_translation.py
```

---

## 6. 개발 내역

작업하며 알아낸 것들입니다. 같은 게임을 만지실 분께 도움이 되길.

### 글꼴

게임 글꼴에는 한글이 없습니다. **KS X 1001 완성형 2350자**를 Shift-JIS 의
**JIS 1수준 한자 자리(ku16~ku40)** 에 밀어 넣었습니다. 한자 영역을 통째로
한글로 바꾼 셈이라, 번역이 안 된 곳에 한자가 남아 있으면 엉뚱한 한글로 보입니다.

두 게임 모두 **반각 ASCII 글리프가 없습니다.** 사쿠라1 의 FIDX 는
`sjis - 0x8000` 으로 색인하고, 사쿠라2 의 `drawChar` 는 `0x8140~0xEAA4`
범위만 받습니다. 글자 폭은 고정이라 한 글자가 한 칸입니다.

### 텍스트 컨테이너

| 컨테이너 | 내용 |
|---|---|
| `ADVMACRO.PFS` (`tbl.bin`) | 사쿠라1 본편 |
| `SLGMAP.PFS` (`mes.bin`) | 사쿠라1 SLG |
| `SK*.CMP` | 사쿠라2 본편 |
| `EV*.MES`, `SYS*.MES` | 사쿠라2 이벤트 |
| `M*LOW.CMP` | 사쿠라2 SLG (MES 형식) |
| `MG0000DAIF.BIN` | 미니게임 (`MWo3` 컨테이너) |

MES 파일에는 **립싱크 데이터가 절대 오프셋으로** 붙어 있습니다. 텍스트를
앞에서부터 다시 채우면 립싱크가 밀립니다. `tools/reinsert.py` 의 `build_mes`
는 립싱크를 원래 자리에 고정하고, 넘치는 텍스트만 그 뒤로 흘려보냅니다.

### CMP 압축

헤더 바이트0: 비트7 = 짧은/긴 헤더, 비트6\~4 = method, 비트3\~0 = param.
param 이 (오프셋 비트수, 길이 보정)을 정합니다 — method 0 기준
param 0 = (12, 3), param 1 = (11, 3), param 3 = (9, 3).

**되압축할 때 같은 param 을 써야 합니다.** 안 그러면 파일이 33% 쯤 커져서
원래 자리에 안 들어갑니다. 자세한 건 [tools/CMP_FORMAT.md](tools/CMP_FORMAT.md).

### 이미지 형식

`SPR` — `SEGA SPRED` 서명, 청크 표는 빅엔디언. 이미지 항목은
`[u16 w][u16 h][u16 fmt][u16 ?][u32 off][u32 size]`. fmt 하위 니블이
색 형식(1→4bpp, 4→8bpp, 5→16bpp), 상위 니블이 LZSS 압축 여부.
16bpp 는 ABGR1555 입니다.

`PBOOK*` (사쿠라2 메뉴책) — 이게 제일 오래 걸렸습니다. 실마리는
`PBOOK_BG.GIM` 이었습니다. 압축 안 된 **소니 표준 GIM** 파일이 하나 섞여
있었는데, 헤더에 형식이 그대로 적혀 있습니다 — INDEX8, 스위즐,
pitchAlign 16 / heightAlign 8, 팔레트 RGBA8888. 즉 **PSP 스위즐은
16바이트 × 8행 블록**입니다.

압축 해제기는 `PBOOK_FL83` 으로 검증했습니다. 이 자산만 `.CMP`(압축)와
`.PCG`(비압축)가 둘 다 들어 있어서, `decompress(CMP) == PCG` 를 바이트
단위로 맞춰 볼 수 있습니다. 완전히 일치했습니다.

남은 미지수는 **행 폭** 하나였는데 어디에도 안 적혀 있습니다. 자기상관으로
쟀습니다 — `b[i+P]` 와 `b[i]` 의 평균 절대차가 최소인 `P` 가 실제 폭입니다.
위아래로 붙은 픽셀은 서로 비슷하기 때문입니다. 실제 값은 496·384·352·
208·128·112·72 처럼 **2의 거듭제곱이 아니어서** 오래 헤맸습니다.

`PBOOK_FL4` 는 한술 더 떠서 **문구마다 낱장이 따로**입니다. 낱장 폭 =
글자수 × 32픽셀, 4bpp. 파일 하나에 폭이 여러 개 섞여 있습니다.

`.PVN` 은 타일 배치표입니다 — 32×32 타일, 격자 20×14 → 640×448,
`0x28` 부터 u32 바이트 오프셋 280개.

### ISO 빌드

`tools/build_iso.py` 는 파일을 **원래 LBA 자리에 그대로 덮어씁니다.**
쓸 수 있는 크기는 `ceil(원본크기 / 2048) * 2048` 입니다. 파일 표를 다시
쓰지 않으므로 원본보다 커지면 안 됩니다.

---

## 7. 저장소 구성

| 경로 | 내용 |
|---|---|
| `tools/` | 도구 일체 (추출·번역 삽입·이미지·글꼴·빌드) |
| `text/` | 원문 + 번역문 TSV |
| `NanumSquareNeo-*.ttf` | 글꼴 원본 |
| `tools/CMP_FORMAT.md` | CMP 압축 형식 문서 |

게임에서 뽑은 파일(`extract/`), 빌드 결과물(`build/`), 확인용 렌더
(`test_render/`), ISO 는 **저장소에 넣지 않습니다.**

---

## 8. 문제가 보이면

어느 장면인지 알려 주시면 고칠 수 있습니다.
PPSSPP 스크린샷(F12)이 있으면 가장 좋습니다.

---

## 라이선스 / 권리

- **도구 소스**는 자유롭게 쓰셔도 됩니다.
- **글꼴**은 네이버 나눔스퀘어네오입니다. 저작권은 NAVER Corp. 에 있으며
  자유 배포가 허용된 글꼴입니다.
- **게임 데이터의 권리는 세가(SEGA) 및 레드 엔터테인먼트에 있습니다.**
  이 저장소는 게임 파일을 배포하지 않습니다. 패치는 정식으로 구매한
  게임의 덤프에만 적용하세요.
- 비영리 팬 번역입니다. 판매하거나 게임 파일과 함께 배포하지 마세요.
