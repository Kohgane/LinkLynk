# -*- coding: utf-8 -*-
"""코데인→UAE 영/한 동시. ★새 DEEP 은 검증 루프 앞에 꽂아야 검증된다."""
import io, sys
src = io.open("canibring_v1.py", encoding="utf-8").read()
if "codeine-to-united-arab-emirates" in src:
    print("이미 있다"); sys.exit(1)

fail=[]
def sub(tag, old, new):
    global src
    if src.count(old) != 1:
        fail.append("%s — %d회" % (tag, src.count(old))); return
    src = src.replace(old, new, 1); print("  OK %s" % tag)

sub("사실 추가", '    "checked":   {"en": "2 October 2026",    "ko": "2026년 10월 2일"},',
'''    "uae_qty":   {"en": "for the period of stay or a maximum of three months&rsquo; use, whichever is less",
                  "ko": "체류 기간분 또는 최대 3개월분 중 더 짧은 쪽"},
    "uae_rxage": {"en": "issued within the last three months and stamped by the issuing facility",
                  "ko": "3개월 이내 발급 + 의료기관 직인"},
    "cod_cls":   {"en": "Narcotic Schedule II", "ko": "마약 스케줄 II"},
    "uae_listd": {"en": "15 September 2022",    "ko": "2022년 9월 15일"},
    "checked":   {"en": "2 October 2026",    "ko": "2026년 10월 2일"},''')

sub("출처세트 추가", ' ],\n}\n\n_SRCFOR = {',
''' ],
 "uae": [
  ("https://u.ae/en/information-and-services/health-and-fitness/Health-and-wellbeing/drugs-and-controlled-medicines",
   {"en": "UAE Government portal &mdash; drugs and controlled medicines",
    "ko": "UAE 정부 포털 — 약물과 통제 의약품"}),
  ("https://www.ede.gov.ae/documents/61005/0/Controlled+and+semi-controlled+medicines+list.pdf",
   {"en": "Emirates Drug Establishment &mdash; alphabetical list of INCB and EDE controlled substances (PDF)",
    "ko": "에미리트 의약품청(EDE) — INCB·EDE 통제물질 알파벳 목록 (PDF)"}),
  ("https://mohap.gov.ae/en/w/issue-of-permit-to-import-medicines-for-personal-use",
   {"en": "Ministry of Health and Prevention &mdash; permit to import medicines for personal use",
    "ko": "보건예방부(MOHAP) — 개인용 의약품 반입 허가 신청"}),
  ("https://www.uae-embassy.org/permitted-prescriptionsdrugs-while-entering-uae",
   {"en": "UAE Embassy &mdash; permitted prescriptions when entering the UAE",
    "ko": "주미 UAE 대사관 — 입국 시 허용 처방약 안내"}),
 ],
}

_SRCFOR = {''')

sub("출처 매핑", '"애더럴-일본": "jp", "감기약-슈도에페드린-일본": "jp", "CBD-일본": "jp_cbd",',
    '"애더럴-일본": "jp", "감기약-슈도에페드린-일본": "jp", "CBD-일본": "jp_cbd",\n'
    ' "codeine-to-united-arab-emirates": "uae", "코데인-UAE": "uae",')

BODY_EN = '''
DEEP["codeine-to-united-arab-emirates"] = """
<h2>Not banned &mdash; permitted, but only with a permit you apply for first</h2>
<p>Most pages about Dubai put codeine on a list of banned drugs. That is not what the
UAE&rsquo;s own documents say. Codeine is admissible, with prior approval, and the
approval is free. What catches people is that the approval has to exist before they
land, and that codeine sits in a stricter category than they assume.</p>

<h2>Codeine is a narcotic here, not a cough medicine</h2>
<p>The Emirates Drug Establishment&rsquo;s list of controlled substances classifies
codeine as <b>{{cod_cls}}</b>. That is the same tier the UAE applies to the
morphine-class opioids, not the tier it applies to ordinary prescription medicine.
The product in your bag may be a bottle of cough syrup sold over the counter at home;
the classification follows the ingredient, not the packaging or the shelf it came from.</p>

<h2>The quantity rule almost nobody quotes</h2>
<p>The controlled list states the allowance as a quantity {{uae_qty}}. The second half
of that sentence is the part that gets left out. A traveller on a five-day trip is
allowed five days&rsquo; worth, not three months&rsquo; worth, and arriving with a full
repeat prescription for a short visit is not covered by the three-month figure people
remember.</p>

<h2>What the permit actually requires</h2>
<p>The application runs through the Ministry of Health and Prevention and costs nothing.
What it needs is a prescription {{uae_rxage}}, naming the patient, the medicine with its
dose and dosage form, the duration of treatment, the date of issue and the prescribing
physician. A medical report meeting the same description, issued within the last year,
can be supplied as well. Apply before you travel &mdash; this is not something that can
be produced at the border.</p>

<h2>Where the official information currently lives</h2>
<p>The UAE is moving pharmaceutical regulation from the Ministry of Health and Prevention
to the Emirates Drug Establishment, and during the transition the two hold different
halves of this. The controlled substances list is published by EDE, last updated
{{uae_listd}}. The permit application still runs on the MoHAP service. If a guide sends
you to only one of them, it is describing one half of a system that currently has two.</p>

<h2>The trap is the medicine you did not think about</h2>
<p>Codeine reaches travellers mostly through combination products &mdash; cough syrups,
and painkillers that pair it with paracetamol or ibuprofen. In several countries those
are sold without a prescription, which is exactly why they get packed without a thought.
Read the active ingredients on the box rather than the brand on the front.</p>

<h2>What we are not telling you</h2>
<p>You will find pages stating specific prison terms and fines for arriving without
approval. None of the four official UAE sources we read state a penalty, so we are not
going to repeat numbers we cannot trace to one. The accurate statement is narrower and
sufficient: the medicine is controlled, approval is required in advance, it is free, and
it takes a prescription you probably already have.</p>
'''

BODY_KO = '''
KO_DEEP["코데인-UAE"] = """
<h2>금지가 아니라, 미리 받아두는 허가제입니다</h2>
<p>두바이 관련 글 대부분이 코데인을 금지 약물 목록에 넣습니다. UAE 공식 문서는 그렇게
쓰지 않습니다. 코데인은 <b>사전 승인을 받으면 반입할 수 있고, 그 승인은 무료</b>입니다.
사람들이 걸리는 지점은 그 승인이 도착 전에 이미 있어야 한다는 것, 그리고 코데인이
생각보다 훨씬 엄격한 칸에 들어 있다는 것입니다.</p>

<h2>여기서 코데인은 감기약이 아니라 마약입니다</h2>
<p>에미리트 의약품청(EDE)의 통제물질 목록은 코데인을 <b>{{cod_cls}}</b>로 분류합니다.
UAE가 모르핀 계열 오피오이드에 적용하는 것과 같은 등급이지, 일반 처방약에 적용하는
등급이 아닙니다. 가방에 든 건 본국 약국에서 처방전 없이 산 기침 시럽일 수 있지만,
분류는 포장이 아니라 <b>성분</b>을 따라갑니다.</p>

<h2>거의 아무도 인용하지 않는 수량 규칙</h2>
<p>통제 목록은 허용량을 <b>{{uae_qty}}</b>으로 정합니다. 뒷부분이 빠진 채 인용되는 일이
많습니다. 5일 일정이면 5일분이 허용되는 것이지 3개월분이 아닙니다. 짧은 방문에 장기
처방을 통째로 들고 가는 건, 사람들이 기억하는 그 &ldquo;3개월&rdquo;로 덮이지 않습니다.</p>

<h2>허가에 실제로 필요한 것</h2>
<p>신청은 보건예방부(MOHAP)를 통하고 비용은 없습니다. 필요한 건 <b>{{uae_rxage}}</b>된
처방전이고, 환자 이름·약품명과 용량·제형·치료 기간·발급일·처방 의사가 적혀 있어야
합니다. 같은 내용을 담은 1년 이내 발급 의료 소견서도 함께 낼 수 있습니다. 출국 전에
신청하세요. 공항에서 만들 수 있는 서류가 아닙니다.</p>

<h2>공식 정보가 지금 어디에 있는가</h2>
<p>UAE는 의약품 규제를 보건예방부에서 에미리트 의약품청으로 옮기는 중이고, 이행 기간
동안 두 기관이 이 일의 서로 다른 절반을 들고 있습니다. <b>통제물질 목록은 EDE가
발행</b>하며 최종 갱신은 {{uae_listd}}입니다. <b>허가 신청은 아직 MOHAP 서비스</b>에서
돌아갑니다. 둘 중 한쪽만 알려주는 안내는 지금 두 개로 나뉜 제도의 절반만 설명하고
있는 겁니다.</p>

<h2>진짜 함정은 생각도 안 한 그 약입니다</h2>
<p>코데인은 대개 복합제로 여행자 가방에 들어갑니다 &mdash; 기침 시럽, 그리고 아세트아미노펜이나
이부프로펜과 섞인 진통제입니다. 여러 나라에서 이것들은 처방전 없이 팔리고, 그래서 아무
생각 없이 챙겨집니다. 앞면의 브랜드가 아니라 상자의 성분표를 읽으세요.</p>

<h2>우리가 쓰지 않는 것</h2>
<p>승인 없이 입국하면 징역 몇 년, 벌금 얼마라고 적은 페이지들이 있습니다. 우리가 읽은
UAE 공식 출처 네 곳 중 어디도 형량을 명시하지 않습니다. 그래서 출처를 댈 수 없는 숫자를
옮겨 적지 않겠습니다. 정확한 문장은 더 좁고, 그걸로 충분합니다 &mdash; 통제 대상이고,
사전 승인이 필요하고, 무료이며, 아마 이미 갖고 있을 처방전이면 됩니다.</p>
'''

sub("본문 삽입", "# ── 배포 시점 검증. 키를 틀리면 여기서 죽는다.",
    BODY_EN + '"""\n' + BODY_KO + '"""\n\n# ── 배포 시점 검증. 키를 틀리면 여기서 죽는다.')

if fail:
    print("\n실패 — 아무것도 안 바꿨다:")
    for f in fail: print("   ", f)
    sys.exit(1)

io.open("canibring_v1.py", "w", encoding="utf-8").write(src)
print("기록 완료 (%d바이트)" % len(src))
