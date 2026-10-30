# -*- coding: utf-8 -*-
"""슈도에페드린→일본. ★공식 출처가 서로 다르면 다르다고 쓴다."""
import io, sys
src = io.open("canibring_v1.py", encoding="utf-8").read()
if "sudafed-to-japan" in src:
    print("이미 있다"); sys.exit(1)
if 'DEEP["adderall-to-japan"]' not in src:
    print("실패: DEEP 구조가 없다"); sys.exit(1)

src += u'''

DEEP["sudafed-to-japan"] = """
<h2>This is one of the few cases where the official sources disagree</h2>
<p>Most travel guides tell you flatly that pseudoephedrine cannot go to Japan.
The Japanese government&rsquo;s own documents are narrower than that, and they do
not quite agree with each other either. Because the downside here is an airport
detention, we show you what each one actually says instead of picking the
version we like.</p>
<p><b>Japan Customs</b> states that raw materials for stimulants are
&ldquo;prohibited from importation by ordinary individuals, except for cases
where the individual carries them into Japan in person as prescribed by a
physician.&rdquo; That is a conditional ban, not an absolute one.</p>
<p><b>A Ministry of Health, Labour and Welfare regional bureau</b> goes further
and sets a threshold: personal pharmaceutical use is allowed without advance
permission where the preparation contains no more than 10% ephedrine or
methylephedrine. Above that, an import licence is required.</p>
<p><b>Third-party guides</b>, including ones written for foreign residents, say
pseudoephedrine products such as Sudafed and Actifed cannot be imported for
personal use even with a prescription.</p>

<h2>What is not in dispute</h2>
<p>Three rules appear in every official source and none of them have exceptions:</p>
<p>You must carry it yourself. Someone else cannot bring it in for you.</p>
<p>It cannot arrive by post. Ordering it from overseas by international mail is
prohibited outright, and customs states that mail without the required licence is
neither imported nor returned to the sender.</p>
<p>It has to be prescribed. An over-the-counter box bought off a shelf does not
satisfy the condition Customs describes, even if the same drug would be
prescription-only somewhere else.</p>

<h2>Why &ldquo;just leave it at home&rdquo; is still reasonable advice</h2>
<p>The 10% threshold is a property of the product, not of the drug. It is on you
to know the concentration in the box you are carrying, to have the prescription
that the exemption assumes, and to explain both at a counter, possibly through an
interpreter. Study-abroad offices tell students not to bring it because that is
the advice that survives all three readings above. If you do not need the
medicine on the trip, the cheapest correct answer is to buy a Japanese cold
remedy after you land.</p>

<h2>Check the box, not the brand</h2>
<p>Brand names are not stable across borders. &ldquo;Sudafed&rdquo; is
pseudoephedrine in some countries and a different decongestant in others, and
combination cold remedies often add something else that is controlled
separately &mdash; codeine, for one, which Japan treats as a narcotic requiring
advance permission from a Regional Bureau Director-General with about two weeks
of processing. Read the active ingredients panel on the actual package you plan
to pack.</p>

<h2>Inhalers: unresolved, and we are saying so</h2>
<p>Nasal inhalers are repeatedly flagged in guidance for travellers to Japan on
the basis that they may contain stimulant-type ingredients. We were not able to
confirm from an official Japanese source which substance is at issue or how it is
classified, so we are not going to tell you either that they are fine or that
they are banned. Treat an inhaler as a separate question from your tablets, and
ask the Regional Bureau before you fly rather than assuming the rule above covers
it.</p>

<h2>Sources</h2>
<p><a href="https://www.customs.go.jp/tokyo/english/yuubin/mayakuoyobikouseisinyaku.htm" rel="noopener" target="_blank">Tokyo Customs &mdash; narcotics, psychotropic drugs and raw materials for stimulants</a><br>
<a href="https://kouseikyoku.mhlw.go.jp/kantoshinetsu/iji/documents/mayaku-keitaiyushutunyu28-eigo.pdf" rel="noopener" target="_blank">MHLW Kanto-Shinetsu Regional Bureau &mdash; import/export of narcotics by carrying (PDF)</a><br>
<a href="https://www.mhlw.go.jp/english/policy/health-medical/pharmaceuticals/01.html" rel="noopener" target="_blank">Ministry of Health, Labour and Welfare &mdash; bringing medicines for personal use into Japan</a><br>
<a href="https://www.accessible-japan.com/list-of-banned-and-restricted-medications-in-japan-late-2025-early-2026-guide/" rel="noopener" target="_blank">Accessible Japan &mdash; banned and restricted medications list</a><br>
<a href="https://www.associatedkyotoprogram.org/bringing-medications-japan/" rel="noopener" target="_blank">Associated Kyoto Program &mdash; bringing medications into Japan</a></p>
<p style="opacity:.7">Last checked 2 October 2026. Where the official pages above
disagree with this one, they are right and we are out of date. Where they
disagree with each other, ask the Regional Bureau.</p>
"""
'''

io.open("canibring_v1.py", "w", encoding="utf-8").write(src)
print("기록 완료 (%d바이트)" % len(src))
