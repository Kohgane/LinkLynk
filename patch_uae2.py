# -*- coding: utf-8 -*-
"""트라마돌→UAE (영문만 — 한글 쌍이 없다). ★검증 루프 앞에 꽂는다."""
import io, sys
src = io.open("canibring_v1.py", encoding="utf-8").read()
if "tramadol-to-united-arab-emirates" in src:
    print("이미 있다"); sys.exit(1)

fail=[]
def sub(tag, old, new):
    global src
    if src.count(old) != 1:
        fail.append("%s — %d회" % (tag, src.count(old))); return
    src = src.replace(old, new, 1); print("  OK %s" % tag)

sub("사실 추가", '    "cod_cls":   {"en": "Narcotic Schedule II", "ko": "마약 스케줄 II"},',
'''    "cod_cls":   {"en": "Narcotic Schedule II", "ko": "마약 스케줄 II"},
    "tram_cls":  {"en": "a controlled drug (CD)", "ko": "통제 의약품(CD)"},
    "uae_count": {"en": "more than two hundred", "ko": "200개가 넘는"},''')

sub("출처 매핑", '"codeine-to-united-arab-emirates": "uae", "코데인-UAE": "uae",',
    '"codeine-to-united-arab-emirates": "uae", "코데인-UAE": "uae",\n'
    ' "tramadol-to-united-arab-emirates": "uae",')

BODY = '''
DEEP["tramadol-to-united-arab-emirates"] = """
<h2>A lower tier than codeine &mdash; and it changes nothing for you</h2>
<p>The Emirates Drug Establishment&rsquo;s list classifies tramadol as
<b>{{tram_cls}}</b>, a step below the Narcotic Schedule II tier it applies to codeine.
Travellers reasonably read that as the easier case. It is not. The permit a traveller
needs is the same one, from the same ministry, with the same documents and the same
quantity ceiling. The tiers exist to govern how these medicines are registered,
stocked and prescribed inside the UAE. They do not sort travellers into a strict lane
and a relaxed lane.</p>
<p>If you take anything useful from this page, take that. People get caught by
assuming the class of their medicine tells them how much care to apply at the border.
It does not.</p>

<h2>What you actually have to do</h2>
<p>Apply to the Ministry of Health and Prevention before you fly. The permit is free.
It wants a prescription {{uae_rxage}}, naming the patient, the medicine with its dose
and dosage form, the duration of treatment, the date of issue and the prescribing
physician. A medical report issued within the last year can be supplied alongside it,
and you will need your passport. The allowance is {{uae_qty}}.</p>

<h2>Why tramadol specifically catches people out</h2>
<p>Tramadol is prescribed casually in much of the world &mdash; after dental work, for
back pain, for a sports injury &mdash; and it is rarely described to the patient as an
opioid. It ends up in a wash bag the way ibuprofen does, and the person carrying it has
never once thought of it as a controlled substance. The UAE has thought about it a
great deal. That gap between how the medicine is treated where it was prescribed and
how it is treated on arrival is where the trouble sits, and it is a gap no amount of
good faith closes at the counter.</p>

<h2>Do not reason from the class. Check the list.</h2>
<p>The controlled and semi-controlled list runs to {{uae_count}} entries, last updated
{{uae_listd}}. It is published by the Emirates Drug Establishment, while the permit
application still runs on the Ministry of Health and Prevention service &mdash; the UAE
is moving pharmaceutical regulation between the two, and for now each holds a different
half. Look your own medicine up by its active ingredient in that list rather than
deciding by category, and if a guide points you at only one of the two bodies, it is
describing half of the system.</p>

<h2>What we are not telling you</h2>
<p>Pages about Dubai routinely attach specific prison terms to arriving without
approval. None of the official UAE sources we read state a penalty, so we are not
repeating figures we cannot trace to one. The accurate version is narrow and enough to
act on: tramadol is controlled, advance approval is required, the approval costs
nothing, and the paperwork is a prescription you most likely already hold.</p>
'''

sub("본문 삽입", "# ── 배포 시점 검증. 키를 틀리면 여기서 죽는다.",
    BODY + '"""\n\n# ── 배포 시점 검증. 키를 틀리면 여기서 죽는다.')

if fail:
    print("\n실패 — 아무것도 안 바꿨다:")
    for f in fail: print("   ", f)
    sys.exit(1)

io.open("canibring_v1.py", "w", encoding="utf-8").write(src)
print("기록 완료 (%d바이트)" % len(src))
