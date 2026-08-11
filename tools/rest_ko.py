# -*- coding: utf-8 -*-
"""
마지막까지 남아 있던 미번역 행의 번역표.

  python rest_ko.py [--dry]

대부분 앞부분이 제어 코드(이름 등)로 붙는 **문장 조각**이라 조사·어미로 시작한다.
한국어도 같은 자리에 이어 붙도록 조사·어미로 시작하게 옮겼다.

번역하지 않는 것
  ・ＢＧ３０３６（＋ＢＧ２０３６） 같은 배경 자산 ID
  ・ＳＰＣ３３３７ 같은 음성 ID
  ・…「」『』（）・。、！？⁉‼　  문장부호 견본
  건드리면 자산 조회가 깨질 수 있고, 어차피 한글로 옮길 것이 없다.
"""
import os, sys, csv, io

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
csv.field_size_limit(1 << 24)

TEXT = r"D:\psp\사쿠라대전1_2\text"
FILES = ["sakura1_adv.tsv", "sakura1_slg.tsv", "sakura2_adv.tsv",
         "sakura2_evt.tsv", "sakura2_slg.tsv"]

KO = {
"もいっしょか。": "도　함께인가．",
"あっ！\\nつぼみちゃんに、\\n": "앗！\\n츠보미　양에게，\\n",
"じゃないか！": "잖아！",
"だみー": "더미",
"、ないですよね⁉": "，　없죠⁉",
"わたし…………\\nどうか…………\\n…………ように。": "저…………\\n부디…………\\n…………하기를．",
"んねー！": "네요ー！",
"ハハハ、\\n": "하하하，\\n",
"みがいるんじゃないか！": "가　있잖아！",
"は\\n忘れてくださ～い！": "는\\n잊어　주세요～！",
"た……": "다……",
"たねー！": "었네요ー！",
"くん……": "　군……",
"てきた！": "왔다！",
"そして、いよいよ……\\nヒロイン役の\\n": "그리고　드디어……\\n주인공　역의\\n",
"すか……": "니까……",
"るので\\nあたし、そろそろ……": "라서\\n저，　슬슬……",
"！\\nあけまして、おめでとう。": "！\\n새해　복　많이　받아．",
"たちは\\nやましいことを\\nしたわけではありません。":
    "들은\\n떳떳하지　못한　짓을\\n한　게　아닙니다．",
"いなごいくさぬさちば……": "이나고이쿠사누사치바……",
"ています！": "있습니다！",
"\\nありがとう。": "\\n고마워．",
"３０３３から": "３０３３부터",
"３３２７から": "３３２７부터",
"３３３７から": "３３３７부터",
"３３５０から": "３３５０부터",
"３３６２から": "３３６２부터",
"３３７３から": "３３７３부터",
"４０７６から": "４０７６부터",
"て、こんな……": "서，　이런……",
"ちがやって\\nくれちゃったのかしら？": "들이　해\\n버린　걸까？",
"だな！": "구나！",
"……あれ？\\n": "……어라？\\n",
"うこったろうな。": "런　거겠지．",
"なりませんか？": "않겠습니까？",
}

def main():
    dry = '--dry' in sys.argv
    tot = 0
    for fn in FILES:
        p = os.path.join(TEXT, fn)
        if not os.path.exists(p): continue
        with open(p, encoding='utf-8-sig', newline='') as f:
            rd = csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
            hdr = next(rd); rows = list(rd)
        ja_i, ko_i = hdr.index('ja'), hdr.index('ko')
        n = 0
        for r in rows:
            if len(r) <= ko_i or r[ko_i].strip(): continue
            v = KO.get(r[ja_i])
            if v: r[ko_i] = v; n += 1
        tot += n
        print(f"  {fn:<20} {n:>3}행 채움")
        if n and not dry:
            with open(p, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.writer(f, delimiter='\t', lineterminator='\n',
                               quoting=csv.QUOTE_NONE, escapechar=None)
                w.writerow(hdr); w.writerows(rows)
    print(f"\n합계 {tot}행" + (" (--dry)" if dry else ""))

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    main()
