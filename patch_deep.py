# -*- coding: utf-8 -*-
"""조사해서 직접 쓴 본문(DEEP)이 있으면 그걸 쓴다. ★앵커 1회 매치만."""
import io, sys
src = io.open("canibring_v1.py", encoding="utf-8").read()
if "DEEP" in src:
    print("이미 있다"); sys.exit(1)

OLD = "    body.append('<h2>What to do</h2><p>%s</p>' % e(DO[lvl]))"
NEW = ("    deep = DEEP.get(s)\n"
       "    if deep:\n"
       "        body.append(deep)      # ★1차 출처 읽고 직접 쓴 본문\n"
       "    else:\n"
       "        body.append('<h2>What to do</h2><p>%s</p>' % e(DO[lvl]))")
if src.count(OLD) != 1:
    print("실패: %d회 매치" % src.count(OLD)); sys.exit(1)
src = src.replace(OLD, NEW, 1)
print("  OK cb_page 분기")

src += u'''

# ══════════════════════════════════════════════════════════════
# 직접 쓴 본문. 자동 생성으로는 못 만드는 깊이를 여기에 둔다.
# ★규칙: 출처 없이 한 줄도 쓰지 않는다. 확인 못 한 건 안 쓴다.
#   사람이 공항에서 잡히는 주제다. 빈칸이 틀린 문장보다 낫다.
DEEP = {}

DEEP["adderall-to-japan"] = """
<h2>Why a prescription and a doctor's letter don't change this</h2>
<p>Japan sorts controlled medicines into separate legal regimes, and Adderall
falls into the one with no import route at all. Narcotics and psychotropics can
be imported for personal use with advance permission from the Director-General
of a Regional Bureau of Health and Welfare. Amphetamine and methamphetamine are
not narcotics under Japanese law &mdash; they are <em>stimulants</em> under the
Stimulants Control Law, and that law has no personal-import permission scheme to
apply for.</p>
<p>This is why the usual preparation fails. There is no form that makes it
lawful, so a prescription, a translated letter from your doctor and an original
labelled bottle do not help you. They establish that the amphetamine is yours.
They are not permission to bring it.</p>

<h2>What the import certificate does not cover</h2>
<p>Japan's Yunyu Kakunin-sho (import confirmation, formerly called Yakkan
Shoumei) exists for quantity, not for category. The Ministry of Health, Labour
and Welfare allows a one-month supply of prescription medicine and a two-month
supply of other medicines with no certificate at all; above those amounts you
apply for one. The certificate raises the ceiling on medicines you are already
allowed to carry. It cannot authorise a substance whose import is prohibited
outright.</p>

<h2>The penalty</h2>
<p>Under the Stimulants Control Law, use, possession, transfer or receipt of
stimulants is punishable by imprisonment with work for up to 20 years and a fine
of up to &yen;5 million, as published by the Okinawa Institute of Science and
Technology for its international staff and students. Study-abroad offices state
the practical consequence plainly: the Associated Kyoto Program tells students
that bringing ADHD stimulants into Japan &ldquo;for any reason&rdquo; risks
&ldquo;arrest and imprisonment.&rdquo;</p>

<h2>What you can actually do &mdash; it depends on how long you are staying</h2>
<p>Adderall is not prescribed in Japan, so the real question is whether you can
be treated there instead. The answer splits sharply by trip length, and most
guides do not make the distinction.</p>
<p><b>A short trip &mdash; days to a few weeks.</b> You cannot realistically
start treatment in Japan. Concerta and Vyvanse are governed by a
proper-distribution system in force since late 2019 that requires three separate
registrations: the prescribing doctor, the dispensing pharmacy, and the patient.
A diagnosis made abroad has to be re-confirmed by a doctor in Japan first, and
clinics describe two to four insured visits even for a straightforward case.
Plan the trip without the medication, and raise that with your own prescriber
before you go rather than after you land.</p>
<p><b>A long stay &mdash; a semester, a posting, a move.</b> Treatment is
available and the route is ordinary. Concerta (methylphenidate ER) is approved
for all ages through the registered pathway. Strattera (atomoxetine) and Intuniv
(guanfacine ER) are approved for all ages and need no special registration.
Vyvanse is approved only for ages 6 to 18, so an adult cannot start it in Japan.
Ritalin is available but licensed for narcolepsy, not ADHD. Bring your
diagnosis, testing and medication history; it shortens the re-assessment.</p>

<h2>The mistake people make on the same trip</h2>
<p>Travellers who correctly leave the Adderall at home often pack something else
that is also prohibited. Pseudoephedrine &mdash; Sudafed, Actifed and Vicks
inhalers &mdash; is controlled in Japan, and codeine-containing cough and pain
medicines are restricted. Check the cold and allergy medicines in your bag, not
only the prescription ones.</p>

<h2>Sources</h2>
<p><a href="https://www.mhlw.go.jp/english/policy/health-medical/pharmaceuticals/01.html" rel="noopener" target="_blank">Ministry of Health, Labour and Welfare &mdash; bringing medicines for personal use into Japan</a><br>
<a href="https://www.oist.jp/resource-center/drugs" rel="noopener" target="_blank">Okinawa Institute of Science and Technology &mdash; drugs and the law in Japan</a><br>
<a href="https://www.us.emb-japan.go.jp/itpr_en/bringing-medications-to-japan.html" rel="noopener" target="_blank">Embassy of Japan in the United States &mdash; bringing medications to Japan</a><br>
<a href="https://www.associatedkyotoprogram.org/bringing-medications-japan/" rel="noopener" target="_blank">Associated Kyoto Program &mdash; bringing medications into Japan</a><br>
<a href="https://misti.mit.edu/japan-preparation-and-training/japan-logistics/japan-bringing-medication" rel="noopener" target="_blank">MIT MISTI &mdash; bringing medication to Japan</a><br>
<a href="https://imhclinic.jp/en/articles/adhd-in-japan" rel="noopener" target="_blank">IMH Clinic Tokyo &mdash; ADHD diagnosis and medication in Japan</a></p>
<p style="opacity:.7">Last checked 2 October 2026. Japanese rules change without
notice. Where the official pages above disagree with this one, they are right
and we are out of date.</p>
"""
'''

io.open("canibring_v1.py", "w", encoding="utf-8").write(src)
print("기록 완료 (%d바이트)" % len(src))
