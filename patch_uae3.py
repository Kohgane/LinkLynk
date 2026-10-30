# -*- coding: utf-8 -*-
"""자낙스→UAE 영/한. ★처방전 명의가 이 페이지의 축."""
import io, sys
src = io.open("canibring_v1.py", encoding="utf-8").read()
if "xanax-to-united-arab-emirates" in src:
    print("이미 있다"); sys.exit(1)

fail=[]
def sub(tag, old, new):
    global src
    if src.count(old) != 1:
        fail.append("%s — %d회" % (tag, src.count(old))); return
    src = src.replace(old, new, 1); print("  OK %s" % tag)

sub("사실 추가", '    "tram_cls":  {"en": "a controlled drug (CD)", "ko": "통제 의약품(CD)"},',
'''    "tram_cls":  {"en": "a controlled drug (CD)", "ko": "통제 의약품(CD)"},
    "benz_cls":  {"en": "a controlled drug (CD), additionally listed under Psychotropic Schedule IV",
                  "ko": "통제 의약품(CD)이자 향정신성 스케줄 IV"},''')

sub("출처 매핑", ' "tramadol-to-united-arab-emirates": "uae",',
    ' "tramadol-to-united-arab-emirates": "uae",\n'
    ' "xanax-to-united-arab-emirates": "uae", "자낙스-UAE": "uae",')

EN = '''
DEEP["xanax-to-united-arab-emirates"] = """
<h2>The problem is usually whose name is on the prescription</h2>
<p>Alprazolam is {{benz_cls}} on the Emirates Drug Establishment&rsquo;s list, and
the import permit for it is free and routine. What stops people is not the class.
It is that the Ministry of Health and Prevention asks for a prescription carrying the
patient&rsquo;s full name, and a great many of the benzodiazepine tablets that travel
in wash bags were prescribed to somebody else.</p>
<p>Two from a partner&rsquo;s packet for the flight, a few left over from a relative&rsquo;s
course, a strip someone handed you before a long haul &mdash; these are ordinary,
well-intentioned, and they cannot be made lawful by any application. There is no
version of the form where the name does not have to be yours.</p>

<h2>The same tier covers more of your bag than you think</h2>
<p>Alprazolam, zolpidem and diazepam &mdash; Xanax, Ambien and Valium &mdash; sit in the
same place on the UAE list. If you are carrying one of them you are quite likely
carrying another, because they get prescribed for the same cluster of problems:
anxiety, sleep, the flight itself. Clear all of them at once rather than discovering
the second one at the counter.</p>

<h2>What the permit takes</h2>
<p>Apply to the Ministry of Health and Prevention before departure; it is free. You
need a prescription {{uae_rxage}} showing the patient&rsquo;s name, the medicine with
dose and dosage form, the duration of treatment, the date and the prescribing
physician. A medical report from the past year can accompany it, and bring your
passport. The quantity allowed is {{uae_qty}}.</p>

<h2>The list is the authority, not the category</h2>
<p>The controlled and semi-controlled list has {{uae_count}} entries and was last
updated {{uae_listd}}. It is published by the Emirates Drug Establishment; the permit
service still runs at the Ministry of Health and Prevention, because the UAE is moving
pharmaceutical regulation between the two. Look up your own medicine by active
ingredient. Brand names and drug classes are both poor proxies for what the list
actually says.</p>

<h2>What we are not telling you</h2>
<p>We are not quoting prison terms. None of the official UAE sources we read state a
penalty for arriving without approval, and we are not going to launder numbers from
secondary pages into something that looks sourced. What is certain is narrower and
enough: the medicine is controlled, approval must exist before you land, it costs
nothing, and it has to be in your name.</p>
'''

KO = '''
KO_DEEP["자낙스-UAE"] = """
<h2>막히는 건 등급이 아니라 처방전에 적힌 이름입니다</h2>
<p>알프라졸람은 에미리트 의약품청 목록에서 <b>{{benz_cls}}</b>이고, 반입 허가는
무료이며 절차도 평범합니다. 사람들이 걸리는 건 등급이 아닙니다. 보건예방부가
<b>환자 본인 성명이 적힌 처방전</b>을 요구하는데, 여행 가방에 들어가는 벤조디아제핀
상당수가 다른 사람 앞으로 처방된 약이라는 점입니다.</p>
<p>비행기 타려고 배우자 약에서 두 알, 가족이 먹다 남긴 것, 장거리 간다니까 누가
쥐여준 한 판 &mdash; 전부 흔하고 악의도 없지만, <b>어떤 신청서로도 합법이 되지
않습니다.</b> 이름이 본인이 아니어도 되는 양식은 없습니다.</p>

<h2>같은 칸이 생각보다 가방을 넓게 덮습니다</h2>
<p>알프라졸람·졸피뎀·디아제팜 &mdash; 자낙스·앰비엔·바리움 &mdash; 은 UAE 목록에서
같은 자리에 있습니다. 하나를 들고 간다면 다른 하나도 들고 있을 가능성이 높습니다.
불안, 불면, 비행 그 자체라는 같은 묶음으로 처방되니까요. 창구에서 두 번째 약을
발견하지 말고 출국 전에 한꺼번에 정리하세요.</p>

<h2>허가에 필요한 것</h2>
<p>출국 전 보건예방부에 신청하고, 비용은 없습니다. <b>{{uae_rxage}}</b>된 처방전에
환자 이름·약품명과 용량·제형·치료 기간·발급일·처방 의사가 적혀 있어야 합니다. 1년
이내 의료 소견서를 함께 낼 수 있고, 여권이 필요합니다. 허용량은 <b>{{uae_qty}}</b>
입니다.</p>

<h2>근거는 등급이 아니라 목록입니다</h2>
<p>통제·준통제 목록은 {{uae_count}} 품목이고 최종 갱신은 {{uae_listd}}입니다.
발행은 에미리트 의약품청, 허가 신청은 아직 보건예방부 &mdash; UAE가 의약품 규제를
두 기관 사이에서 옮기는 중이라 그렇습니다. 본인 약을 <b>성분명</b>으로 그 목록에서
찾아보세요. 브랜드명도 약효 분류도 목록이 실제로 뭐라고 적었는지를 대신해 주지
못합니다.</p>

<h2>우리가 쓰지 않는 것</h2>
<p>징역 몇 년이라는 숫자는 쓰지 않습니다. 우리가 읽은 UAE 공식 출처 어디도 승인 없이
입국했을 때의 형량을 명시하지 않고, 2차 페이지의 숫자를 출처 있는 것처럼 세탁하지
않겠습니다. 확실한 건 더 좁고, 그걸로 충분합니다 &mdash; 통제 대상이고, 착륙 전에
승인이 있어야 하고, 무료이며, <b>본인 명의</b>여야 합니다.</p>
'''

sub("본문 삽입", "# ── 배포 시점 검증. 키를 틀리면 여기서 죽는다.",
    EN + '"""\n' + KO + '"""\n\n# ── 배포 시점 검증. 키를 틀리면 여기서 죽는다.')

if fail:
    print("\n실패 — 아무것도 안 바꿨다:")
    for f in fail: print("   ", f)
    sys.exit(1)

io.open("canibring_v1.py", "w", encoding="utf-8").write(src)
print("기록 완료 (%d바이트)" % len(src))
