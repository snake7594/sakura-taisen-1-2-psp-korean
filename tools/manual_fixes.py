# -*- coding: utf-8 -*-
"""
손으로 정한 번역 수정을 TSV 에 적용한다.

  python manual_fixes.py [--dry]

한글 2350자가 SJIS ku16~ku40(JIS 1수준 한자) 자리를 쓰기 때문에, 그 자리의
한자는 글리프가 없어 화면에 엉뚱한 한글이 뜬다. fix_chars.py 가 찾아 주는
그런 행들을 여기서 사람이 정한 문장으로 바꾼다.

두 갈래다.
  · 번역문에 일본어가 남은 행  — 한국어로 옮긴다
  · 아직 번역이 안 된 행        — 원문이 그대로 들어가 깨지므로 번역을 채운다
    (선택지 ID 같은 메타데이터 줄은 반각 그대로 보존한다)

「師走」(12월의 옛 이름) 대화는 한자를 보여 주는 것이 말장난의 핵심이라
그 한자를 못 쓰는 이상 그대로 옮길 수 없다. 한국 한자음 「사주」로 바꿔
"「사주」라고 쓰고 「시와스」라고 읽는다" 구조를 살렸다.
"""
import os, sys, csv, io, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
csv.field_size_limit(1 << 24)
TEXT = r"D:\psp\사쿠라대전1_2\text"
FILES = ["sakura1_adv.tsv", "sakura1_slg.tsv", "sakura2_adv.tsv", "sakura2_evt.tsv"]

# key -> 넣을 ko (TSV 그대로, 줄바꿈은 \n 두 글자, 공백은 전각)
FIXES = {
    # ---- 번역문에 일본어가 남은 행 ----
    "S1A:0900tbl:532":
        "오늘　공연하는　『대공룡섬』은\\n상당히　큰　규모인\\n모양이던데……",
    "S1A:0900tbl:642":
        "이번　공연은　『소극』이라서\\n아이들이　꽤　많이　왔네．",
    "S1A:0900tbl:660":
        "이　연산기는　「기노후다」라는\\n프로그램　카드를　본체에\\n넣어서　사용하는　거였지．",
    "S1A:0904tbl:211":
        "１주년　기념　공연　『춘희의　밤』\\n성황리에　끝났다고　한다．　이　성공으로\\n극장　영업도　안정되겠지．",
    "S1A:0904tbl:404":
        "『대공룡섬』의　관객으로\\n북적이던　곳이\\n거짓말처럼　고요하군……",
    "S2A:SK0307:1734": "처음으로　돌아가기",
    "S2A:SK0902:313":  "일본　달력，\\n１２월에　「사주」라고\\n적혀　있던데요．",
    "S2A:SK0902:321":  "그건　「사주」라고　쓰고\\n「시와스」라고　읽어요．",
    "S2A:SK0902:329":  "그건　「사주」라고　쓰고\\n「시와스」라고　읽어요．",
    "S2A:SK0902:333":  "그건　「사주」라고　쓰고\\n「시와스」라고　읽어요．",
    "S2A:SK0902:338":  "「사주」는　스승이\\n뛰어다닐　만큼　바빠서라고\\n들었는데，　정말일까요．",

    # ---- 미번역이라 원문이 그대로 들어가 깨지는 행 ----
    # 앞부분이 제어 코드로 붙는 조각이라 조사·어미로 시작하는 것이 여럿 있다.
    "S1S:m16mes:76":   "296\\n.n.nN.nN.nN.nN.nn\\n3163\\n제국화격단，　등장！",
    "S2A:SK0103:0":    "그럼．\\n１３７００으로，\\n다시　통신할게．",
    "S2A:SK0304:0":    "검」은，\\n아직　안　고쳐졌겠지．",
    "S2A:SK0402:686":  "를　만나러\\n안뜰에　가　볼까．",
    "S2A:SK0501:491":  "……에서……야．\\n……바다…………해서……\\n그　뒤……한다……",
    "S2A:SK0503:0":    "스와\\n교대해　주지　않겠나？",
    "S2A:SK0504:0":    "준비를　할까．",
    "S2A:SK0702:280":  "개　값　이상．\\n이상이상이상이상이상．\\n대입필요대입필요대입……",
    "S2A:SK0804:0":    "님．\\n같은　사람　것은　한　장씩만\\n팔　수　있어요오．",
    "S2A:SK0806:0":    "님．\\n같은　사람　것은　한　장씩만\\n팔　수　있어요오．",
    "S2A:SK0901:0":    "구나，\\n제법　다르네에．",
    "S2A:SK0902:0":    "의，　매점　근무구나．",
    "S2A:SK0902:411":  "개　플래그　값이　이상．",
    "S2A:SK0902:426":  "개　플래그　값이　이상．",
    "S2A:SK0905:0":    "\\n　조금　더，　생각하자）",
    "S2A:SK0905:148":  "의　연출이다．",
    "S2A:SK0906:0":    "\\n무대에서　전체　연습……",
    "S2A:SK0907:0":    "해도……\\n아직　몸　속이　뜨겁다．",
    "S2A:SK0907:96":   "오가미　씨……\\n저……",
    "S2A:SK1003:0":    "권해　주셔서……\\n정말　좋았어요．",
    "S2A:SK1004:692":  "，\\n나는　잠깐\\n나갔다　올　건데……",
    "S2A:SK1004:847":  "주역의",
    "S2A:SK1004:856":  "도\\n정말　아름다웠어요……",
    "S2A:SK1101:0":    "서\\n행동해야만　한다．",
    "S2A:SK1104:147":  "오가미　씨가　있으니까……\\n저……",
    "S2A:SK1104:553":  "오가미　씨，\\n",
    "S2A:SK1106:1":    "간이　ＳＮＣ　체커\\nＤＩＳＣ３\\n시작합니다．",
    "S2A:SK1106:29":   "ＳＰＣ３３１７\\n야마구치",
    "S2A:SK1106:31":   "ＳＰＣ３３１７\\n하나코지",
    "S2A:SK1106:67":   "ＳＰＣ３３３４\\n코란",
    "S2A:SK1106:71":   "ＳＰＣ３３３６\\n오리히메",
    "S2A:SK1106:73":   "ＳＰＣ３３３６\\n오가미",
    "S2A:SK1204:0":    "그런　말　해도\\n도저히　못　맞춰요오！",
    "S2A:SK1205:516":  "오……\\n이　목소리는，",
    "S2A:SK1205:525":  "녀석，\\n어디　갔을까？",
    "S2:SYS05:36":     "마조기병，　팔엽．\\n오행집　「」이　타는　기체．\\n６개의　팔로　연속　공격．",
    "S2:SYS15:17":     "문　밖으로　나가서，\\n를　격파하는　거야！",
}

def main():
    dry = '--dry' in sys.argv
    seen = set()
    for fn in FILES:
        p = os.path.join(TEXT, fn)
        if not os.path.exists(p): continue
        with open(p, encoding='utf-8-sig', newline='') as f:
            rd = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
            hdr = next(rd); rows = list(rd)
        k_i, ko_i = hdr.index('key'), hdr.index('ko')
        n = 0
        for r in rows:
            if len(r) <= ko_i: continue
            v = FIXES.get(r[k_i])
            if v is None or r[ko_i] == v: continue
            r[ko_i] = v; n += 1; seen.add(r[k_i])
        print(f"  {fn:<20} {n:>3}행 수정")
        if n and not dry:
            with open(p, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.writer(f, delimiter='\t', lineterminator='\n',
                               quoting=csv.QUOTE_NONE, escapechar=None)
                w.writerow(hdr); w.writerows(rows)
    miss = set(FIXES) - seen
    print(f"\n적용 {len(seen)}행" + (" (--dry)" if dry else ""))
    if miss: print(f"키를 못 찾음 {len(miss)}개: {sorted(miss)[:8]}")

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
