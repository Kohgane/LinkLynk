# -*- coding: utf-8 -*-
"""사실을 한 곳에 모은다. ★언어별 산문은 그대로 두고, 숫자·출처·날짜만 단일화."""
import io, sys
src = io.open("canibring_v1.py", encoding="utf-8").read()
if "_FACT" in src:
    print("이미 있다"); sys.exit(1)

fail = []
def sub(tag, old, new, expect=1):
    global src
    n = src.count(old)
    if n != expect:
        fail.append("%s — %d회 (기대 %d)" % (tag, n, expect)); return
    src = src.replace(old, new); print("  OK %s (%d곳)" % (tag, n))

# ── 1) 렌더 분기를 _fill 경유로
sub("영문 분기", "body.append(deep)      # ★1차 출처 읽고 직접 쓴 본문",
    'body.append(_fill(s, deep, "en"))')
sub("한글 분기", "html += kdeep      # ★1차 출처 읽고 직접 쓴 본문",
    'html += _fill(s, kdeep, "ko")')

# ── 2) 영문 전용 표현
sub("EN 형량", "imprisonment with work for up to 20 years and a fine\nof up to &yen;5 million", "{{stim_pen}}")
sub("EN 수량", "allows a one-month supply of prescription medicine and a two-month\nsupply of other medicines",
    "allows a {{qty_rx}} of prescription medicine and a {{qty_other}}\nsupply of other medicines")
sub("EN 진료횟수", "two to four insured visits", "{{visits}}")
sub("EN 10퍼센트", "no more than 10% ephedrine or\nmethylephedrine", "no more than {{pse_pct}} ephedrine or\nmethylephedrine")
sub("EN 헴프", "no more than 0.3% THC", "no more than {{hemp_pct}} THC")
sub("EN 환산", "0.3% is 3,000 ppm", "{{hemp_pct}} is {{hemp_ppm}}")

# ── 3) 한글 전용 표현
sub("KO 형량", "징역 20년 이하, 벌금 500만엔 이하", "{{stim_pen}}")
sub("KO 수량", "처방약 1개월분, 그 외 의약품 2개월분까지는", "처방약 {{qty_rx}}, 그 외 의약품 {{qty_other}}까지는")
sub("KO 진료횟수", "보험 진료 2~4회", "{{visits}}")
sub("KO 10퍼센트", "10% 이하로 함유한 제제", "{{pse_pct}} 이하로 함유한 제제")
sub("KO 헴프", "THC 0.3% 이하를 헴프로", "THC {{hemp_pct}} 이하를 헴프로")
sub("KO 환산", "0.3%는 <b>3,000 ppm</b>", "{{hemp_pct}}는 <b>{{hemp_ppm}}</b>")

# ── 4) 양쪽에서 글자가 같은 수치 — 규칙 하나가 두 언어를 덮는다
sub("THC 유지",   "10 ppm (0.001%)",    "{{thc_oil}}",   expect=2)
sub("THC 수용액", "0.1 ppm (0.00001%)", "{{thc_aq}}",    expect=2)
sub("THC 기타",   "1 ppm (0.0001%)",    "{{thc_other}}", expect=2)

if fail:
    print("\n실패 — 아무것도 안 바꿨다:")
    for f in fail: print("   ", f)
    sys.exit(1)

src += u'''

# ══════════════════════════════════════════════════════════════
# 사실을 한 곳에 모은다.
#
# ★왜: 같은 숫자를 영문·한글 두 본문에 손으로 써두면, 일본이 규정을 바꿀 때
#   한쪽만 고쳐도 아무 에러가 안 난다. 조용히 틀린 채로 서 있는다.
#   죽은 출처 링크를 두 군데서 고친 게 정확히 그 버그였다.
# ★안 하는 것: 산문은 단일화하지 않는다. 그건 기계번역이고, 이 주제에서
#   "조건부 금지"가 "금지"로 눌리는 순간 사람이 공항에서 잡힌다.
_FACT = {
    "stim_pen":  {"en": "imprisonment with work for up to 20 years and a fine of up to &yen;5 million",
                  "ko": "징역 20년 이하, 벌금 500만엔 이하"},
    "qty_rx":    {"en": "one-month supply",  "ko": "1개월분"},
    "qty_other": {"en": "two-month",         "ko": "2개월분"},
    "visits":    {"en": "two to four insured visits", "ko": "보험 진료 2~4회"},
    "pse_pct":   {"en": "10%",               "ko": "10%"},
    "thc_oil":   {"en": "10 ppm (0.001%)",   "ko": "10 ppm (0.001%)"},
    "thc_aq":    {"en": "0.1 ppm (0.00001%)","ko": "0.1 ppm (0.00001%)"},
    "thc_other": {"en": "1 ppm (0.0001%)",   "ko": "1 ppm (0.0001%)"},
    "hemp_pct":  {"en": "0.3%",              "ko": "0.3%"},
    "hemp_ppm":  {"en": "3,000 ppm",         "ko": "3,000 ppm"},
    "checked":   {"en": "2 October 2026",    "ko": "2026년 10월 2일"},
}

_SRCSET = {
 "jp": [
  ("https://www.customs.go.jp/tokyo/english/yuubin/mayakuoyobikouseisinyaku.htm",
   {"en": "Tokyo Customs &mdash; narcotics, psychotropic drugs and raw materials for stimulants",
    "ko": "도쿄세관 — 마약·향정신성의약품·각성제원료"}),
  ("https://kouseikyoku.mhlw.go.jp/kantoshinetsu/iji/documents/mayaku-keitaiyushutunyu28-eigo.pdf",
   {"en": "MHLW Kanto-Shinetsu Regional Bureau &mdash; import/export of narcotics by carrying (PDF)",
    "ko": "후생노동성 간토신에쓰 지방후생국 — 휴대에 의한 마약 수출입 (PDF)"}),
  ("https://jetprogramusa.org/wp-content/uploads/2025/03/2025-Yunyu-Kakuninsho-Import-of-Medication-Certification-Guide.pdf",
   {"en": "Yunyu Kakunin-sho import-of-medication guide, reproducing the MHLW quantity rules (PDF)",
    "ko": "수입확인증 안내서 — 후생노동성 수량 규정 수록 (PDF)"}),
  ("https://www.oist.jp/resource-center/drugs",
   {"en": "Okinawa Institute of Science and Technology &mdash; drugs and the law in Japan",
    "ko": "오키나와과학기술대학원대학 — 일본의 약물 관련 법"}),
  ("https://www.associatedkyotoprogram.org/bringing-medications-japan/",
   {"en": "Associated Kyoto Program &mdash; bringing medications into Japan",
    "ko": "Associated Kyoto Program — 일본 반입 의약품 안내"}),
  ("https://imhclinic.jp/en/articles/adhd-in-japan",
   {"en": "IMH Clinic Tokyo &mdash; ADHD diagnosis and medication in Japan",
    "ko": "IMH 클리닉 도쿄 — 일본의 ADHD 진단과 약물"}),
 ],
 "jp_cbd": [
  ("https://www.mhlw.go.jp/stf/newpage_43079.html",
   {"en": "Ministry of Health, Labour and Welfare &mdash; phased enforcement of the revised Cannabis Control Act",
    "ko": "후생노동성 — 개정 대마단속법 단계별 시행 안내"}),
  ("https://health-beauty-soleil.jp/news/%E3%80%90thc%E6%AE%8B%E7%95%99%E9%99%90%E5%BA%A6%E5%80%A4%E7%99%BA%E8%A1%A8%E3%80%91%E3%80%8C%E5%A4%A7%E9%BA%BB%E5%8F%96%E7%B7%A0%E6%B3%95%E5%8F%8A%E3%81%B3%E9%BA%BB%E8%96%AC%E5%8F%8A%E3%81%B3/",
   {"en": "Marunouchi Soleil Law Office &mdash; THC residual limit values and the 12 December 2024 date",
    "ko": "마루노우치 소레이유 법률사무소 — THC 잔류 한도치와 2024년 12월 12일 시행"}),
  ("https://www.customs.go.jp/tokyo/english/yuubin/mayakuoyobikouseisinyaku.htm",
   {"en": "Tokyo Customs &mdash; narcotics, psychotropic drugs and raw materials for stimulants",
    "ko": "도쿄세관 — 마약·향정신성의약품·각성제원료"}),
  ("https://www.associatedkyotoprogram.org/bringing-medications-japan/",
   {"en": "Associated Kyoto Program &mdash; bringing medications into Japan",
    "ko": "Associated Kyoto Program — 일본 반입 의약품 안내"}),
 ],
}

_SRCFOR = {
 "adderall-to-japan": "jp", "sudafed-to-japan": "jp", "cbd-to-japan": "jp_cbd",
 "애더럴-일본": "jp", "감기약-슈도에페드린-일본": "jp", "CBD-일본": "jp_cbd",
}

_NOTE = {
 "en": ('<p style="opacity:.7">Last checked %s. Where the official pages above '
        'disagree with this one, they are right and we are out of date.</p>'),
 "ko": ('<p style="opacity:.7">최종 확인 %s. 위 공식 안내와 이 페이지가 다르면 '
        '공식 안내가 맞고 이 페이지가 낡은 것입니다.</p>'),
}


def _srcblk(slug, lang):
    key = _SRCFOR.get(slug)
    if not key:
        return ""
    head = "Sources" if lang == "en" else "출처"
    rows = "<br>".join('<a href="%s" rel="noopener" target="_blank">%s</a>' % (u, lab[lang])
                       for u, lab in _SRCSET[key])
    return "<h2>%s</h2><p>%s</p>%s" % (head, rows, _NOTE[lang] % _FACT["checked"][lang])


def _fill(slug, tpl, lang):
    """{{키}} 를 채우고 출처 블록을 정본으로 갈아끼운다.
       ★없는 키는 조용히 넘기지 않고 터뜨린다. 그게 이 리팩터의 핵심."""
    import re as _re
    for h in ("<h2>Sources</h2>", "<h2>출처</h2>"):
        i = tpl.find(h)
        if i >= 0:
            tpl = tpl[:i]
            break
    tpl = tpl + _srcblk(slug, lang)

    def rep(m):
        k = m.group(1)
        if k not in _FACT:
            raise KeyError("본문에 없는 사실 키: %s (%s/%s)" % (k, slug, lang))
        return _FACT[k][lang]
    return _re.sub(r"\\{\\{([a-z_]+)\\}\\}", rep, tpl)


# ── 배포 시점 검증. 키를 틀리면 여기서 죽는다.
for _s, _t in list(DEEP.items()):
    _fill(_s, _t, "en")
for _s, _t in list(KO_DEEP.items()):
    _fill(_s, _t, "ko")
'''

io.open("canibring_v1.py", "w", encoding="utf-8").write(src)
print("기록 완료 (%d바이트)" % len(src))
