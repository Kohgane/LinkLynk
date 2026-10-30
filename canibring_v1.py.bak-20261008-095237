# -*- coding: utf-8 -*-
"""Can I bring X to Y — 영어권 검색 유입용 페이지.
   2,900개 자동 생성은 얇은 페이지로 스팸 판정받는다. 실제 검색 수요가 있는
   조합만 큐레이션하고, 조합마다 고유 설명을 붙인다. 판정 엔진은 next_v1 재사용.
"""
import re, html as _h
from flask import Blueprint, Response
from next_v1 import verdict
from borderrx_v1 import COUNTRIES, SRC

cb_bp = Blueprint("canibring", __name__)
BASE = "https://canibringmeds.com"
_CC = {c[0]: c[3] for c in COUNTRIES}

# (약, 국가코드) — 실제 검색 수요가 있는 조합만
PAIRS = [
    ("Sudafed", "JP"), ("Sudafed", "TH"),
    ("Adderall", "JP"), ("Adderall", "SG"), ("Adderall", "AE"),
    ("Adderall", "TH"), ("Adderall", "SA"),
    ("codeine", "AE"), ("codeine", "SA"), ("codeine", "SG"),
    ("tramadol", "AE"), ("tramadol", "SA"),
    ("Xanax", "AE"), ("Ambien", "AE"), ("Ambien", "SG"), ("Valium", "AE"),
    ("CBD", "SG"), ("CBD", "AE"), ("CBD", "JP"), ("CBD", "CN"),
    ("melatonin", "GB"), ("melatonin", "DE"),
    ("Concerta", "JP"),
    ("codeine", "JP"),
    ("Ambien", "JP"),
    ("tramadol", "JP"),
    ("Xanax", "JP"),
    ("Valium", "JP"),
]

# 조합별 고유 설명 — 얇은 페이지 방지의 핵심. 보수적으로 쓴다.
WHY = {
    ("methylphenidate", "JP"): "Japan classifies methylphenidate as a psychotropic, not a stimulant. The Narcotics Control Department lists it among the substances that need no import permission at all, alongside zolpidem and alprazolam. What still applies is the ordinary ceiling on prescription medicines: up to one month's supply without an import certificate. Adderall is the opposite case under Japanese law, and the two are constantly confused.",
    ("codeine", "JP"): "Codeine is a narcotic in Japan, so the ordinary import-certificate route does not cover it: you apply to the Narcotics Control Department for permission before you travel. One threshold decides many cases - preparations containing 1% or less of codeine are excluded from control, which is why some low-dose cough preparations pass and prescription-strength ones do not.",
    ("zolpidem", "JP"): "Zolpidem is a psychotropic in Japan and needs no advance permission. The limit that applies is the general one for prescription medicines: one month's supply without an import certificate. Carry the prescription and the original packaging.",
    ("tramadol", "JP"): "Japan's Narcotics Control Department states plainly that tramadol is not a narcotic, and it does not appear on the controlled substances list. That makes it an ordinary prescription medicine: up to one month's supply without an import certificate. Several Gulf states take the opposite view, so a traveller routing through Dubai or Riyadh faces a different rule on the same pills.",
    ("alprazolam", "JP"): "Alprazolam is a psychotropic in Japan and needs no advance permission from the Narcotics Control Department. The ordinary prescription-medicine ceiling applies: one month's supply without an import certificate.",
    ("diazepam", "JP"): "Diazepam is a psychotropic in Japan and needs no advance permission. Up to one month's supply may be brought in without an import certificate. Carry the prescription.",
    ("pseudoephedrine", "JP"): "Japan controls pseudoephedrine as a stimulant raw material, which puts it under the Narcotics Control Department rather than the ordinary import-certificate route: permission has to be obtained before you travel. One threshold decides many cases - preparations containing 10% or less of ephedrine or pseudoephedrine are excluded from control. Standard Sudafed tablets sit above that line, so for most travellers the practical answer is to leave them at home and buy a Japanese cold medicine on arrival.",
    ("pseudoephedrine", "TH"): "Thailand lists pseudoephedrine as a Category 2 psychotropic substance, not a banned drug: up to 30 days' supply is allowed with a prescription, and no permit is required. The problem is that pseudoephedrine cold medicine is usually bought over the counter, so most travellers carry it with no prescription at all.",
    ("dextroamphetamine", "JP"): "Amphetamine-based ADHD medication is prohibited in Japan and cannot be imported even with a doctor's prescription. Possession is a criminal offence.",
    ("dextroamphetamine", "SG"): "Amphetamine is strictly controlled in Singapore. Personal import is generally not permitted.",
    ("dextroamphetamine", "AE"): "Amphetamine-based ADHD medication is not banned from the UAE. The Emirates Drug Establishment lists dexamfetamine under Psychotropic Schedule II and allows travellers to carry it for the length of the stay or three months, whichever is shorter. The condition is documentary and it is strict: a medical prescription, or a medical report attested by your health provider, has to travel with the medicine. Without that paperwork the same pills are handled as a narcotics matter, which is where the detention stories come from. A free online pre-approval is also available; it is optional, and worth having anyway.",
    ("dextroamphetamine", "TH"): "Amphetamine is a Category 1 narcotic in Thailand. Personal import is not permitted.",
    ("dextroamphetamine", "SA"): "Amphetamine is prohibited in Saudi Arabia.",
    ("codeine", "AE"): "Codeine is not banned from the UAE. The Emirates Drug Establishment classifies it as Narcotic Schedule II and allows travellers to carry it for the length of the stay or three months, whichever is shorter, provided a medical prescription or an attested medical report travels with it. The detentions that get reported involve codeine painkillers and cough syrups carried without that paperwork. A free online pre-approval is available and is the safer route.",
    ("codeine", "SA"): "Codeine is treated as a narcotic in Saudi Arabia. Carrying it without authorisation risks detention.",
    ("codeine", "SG"): "Singapore requires prior approval from the Health Sciences Authority to bring in codeine-containing medicine.",
    ("tramadol", "AE"): "Tramadol is not banned from the UAE. The Emirates Drug Establishment lists it as a controlled drug and allows travellers to carry it for the length of the stay or three months, whichever is shorter, with a medical prescription or an attested medical report. Carrying it without that documentation is what turns a prescription painkiller into a narcotics case at the border. The free online pre-approval is optional and worth doing.",
    ("tramadol", "SA"): "Tramadol is controlled as a narcotic in Saudi Arabia.",
    ("alprazolam", "AE"): "Alprazolam is a controlled psychotropic in the UAE and requires prior approval.",
    ("zolpidem", "AE"): "Zolpidem is a controlled sleep medication in the UAE. A prescription and prior approval are required.",
    ("zolpidem", "SG"): "Singapore requires prior approval for zolpidem.",
    ("diazepam", "AE"): "Diazepam is a controlled psychotropic in the UAE and requires prior approval.",
    ("cannabidiol", "SG"): "Singapore bans cannabis derivatives including CBD, regardless of THC content.",
    ("cannabidiol", "AE"): "The UAE prohibits CBD products. Even trace amounts can lead to prosecution.",
    ("cannabidiol", "JP"): "Japan allows only CBD products with zero detectable THC. Many foreign CBD products do not meet this standard.",
    ("cannabidiol", "CN"): "China prohibits CBD products.",
    ("melatonin", "GB"): "Melatonin is a prescription-only medicine in the UK.",
    ("melatonin", "DE"): "In Germany, higher-dose melatonin is treated as a prescription medicine.",
}

DO = {
    "PROHIBITED": "Leave it at home. Ask your doctor about an alternative that is legal at your destination, and carry a doctor's letter describing your condition.",
    "PERMIT": "Apply for approval from the destination's health authority well before you travel. Carry the prescription, a doctor's letter and the original packaging.",
    "DECLARE": "Declare it at customs. Carry the prescription and keep the medicine in its original labelled packaging.",
    "LIMIT": "Check the permitted quantity and formulation before you pack. Carry the prescription and original packaging.",
    "OK": "No specific restriction appears in our data, but rules change. Carry the prescription and original packaging.",
}
LV = {"PROHIBITED": "Banned or restricted", "PERMIT": "Permit required",
      "DECLARE": "Must be declared", "LIMIT": "Quantity or type limited", "OK": "No specific restriction found"}
COL = {"PROHIBITED": "#ff5c50", "PERMIT": "#f0b04c", "DECLARE": "#7fb6e8",
       "LIMIT": "#a89ae8", "OK": "#6edcb4"}


def slug(drug, cc):
    c = _CC.get(cc, cc).lower().replace(" ", "-")
    return "%s-to-%s" % (re.sub(r"[^a-z0-9]+", "-", drug.lower()).strip("-"), c)


_BY_SLUG = {slug(d, c): (d, c) for d, c in PAIRS}


def _why(ings, cc, row):
    for i in ings:
        for (k, c), txt in WHY.items():
            if c == cc and (k in i or i in k):
                return txt
    return ""


CSS = """*{box-sizing:border-box}body{margin:0;background:#0b0d12;color:#e9eef5;
font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.w{max-width:680px;margin:0 auto;padding:30px 18px 70px}
h1{font-size:30px;line-height:1.25;margin:0 0 8px;letter-spacing:-.5px}
.lede{color:#8b98a8;font-size:14px;margin:0 0 22px}
.ans{border-radius:14px;padding:20px;background:#111620;border:1px solid #27323f;margin:0 0 22px}
.ans .k{font-size:13px;color:#8b98a8}.ans .v{font-size:26px;font-weight:800;margin:4px 0}
h2{font-size:19px;margin:28px 0 8px}
p{margin:0 0 14px;color:#c9d4e0}
.ing{color:#b9c6d4}
a{color:#5ec8bb}
.cta{display:block;text-align:center;background:#1ab2aa;color:#04211f;font-weight:700;
border-radius:12px;padding:15px;text-decoration:none;margin:26px 0 8px}
.rel{margin-top:30px}.rel a{display:inline-block;margin:0 10px 8px 0;font-size:14px}
.warn{margin-top:30px;font-size:13px;color:#7d8a99;border-top:1px solid #1a212c;padding-top:18px}
.warn b{color:#cfdae6}"""


@cb_bp.route("/can-i-bring/<path:s>")
def cb_page(s):
    s = s.strip("/").lower()
    _k = cb_kit(s, "en")
    if _k is not None:
        return _k
    if s not in _BY_SLUG:
        return Response("Not found", status=404)
    drug, cc = _BY_SLUG[s]
    cname = _CC.get(cc, cc)
    d = verdict(drug)
    row = next((r for r in d.get("rows", []) if r["code"] == cc), None)
    lvl = row["level"] if row else "OK"
    why = _why(d.get("ings", []), cc, row)
    ing = ", ".join(d.get("ings", [])[:3]) or drug
    incb = bool(d.get("incb"))
    title = "Can I bring %s to %s? (2026 rules)" % (drug, cname)
    desc = "%s in %s: %s. What's in it, why, and what to do before you fly." % (drug, cname, LV[lvl].lower())
    others = [x for x in PAIRS if x[0] == drug and x[1] != cc]
    same_c = [x for x in PAIRS if x[1] == cc and x[0] != drug]
    e = _h.escape
    body = []
    body.append('<h1>Can I bring %s to %s?</h1>' % (e(drug), e(cname)))
    body.append('<p class="lede">Checked against UN INCB controlled substance lists and %s rules.</p>' % e(cname))
    body.append('<div class="ans"><div class="k">Short answer</div>'
                '<div class="v" style="color:%s">%s</div>'
                '<div class="ing">Active ingredient: %s</div></div>' % (COL[lvl], LV[lvl], e(ing)))
    if why:
        body.append('<h2>Why</h2><p>%s</p>' % e(why))
    if incb:
        body.append('<p>%s contains a substance on the UN International Narcotics Control Board lists. '
                    'Most countries that signed the UN drug conventions expect you to carry a prescription '
                    'and declare it.</p>' % e(drug))
    deep = DEEP.get(s)
    if deep:
        body.append(_fill(s, deep, "en"))
    else:
        body.append('<h2>What to do</h2><p>%s</p>' % e(DO[lvl]))
    src = SRC.get(cc)
    if src:
        body.append('<p>Official source for %s: <a href="%s" rel="nofollow noopener" target="_blank">%s</a></p>'
                    % (e(cname), e(src), e(src.split("/")[2])))
    body.append(_bridge(lvl, cc, "en"))
    body.append('<a class="cta" href="/next/en/r/%s">Check %s in 21 countries</a>' % (e(drug), e(drug)))
    if others or same_c:
        body.append('<div class="rel"><h2>Related</h2>')
        for dd, c in (others + same_c)[:8]:
            body.append('<a href="/can-i-bring/%s">%s → %s</a>' % (slug(dd, c), e(dd), e(_CC.get(c, c))))
        body.append('</div>')
    body.append('<p class="warn"><b>Not legal or medical advice.</b> Rules change and depend on dose, form and '
                'quantity. Always confirm with the %s embassy or health authority before you fly. '
                'We never tell you a medicine is "safe" to carry.</p>' % e(cname))
    ld = ('{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question",'
          '"name":"Can I bring %s to %s?","acceptedAnswer":{"@type":"Answer","text":"%s. %s"}}]}'
          % (drug, cname, LV[lvl], (why or DO[lvl]).replace('"', "'")))
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title><meta name="description" content="%s">'
            '<link rel="canonical" href="%s/can-i-bring/%s">%s'
            '<meta property="og:title" content="%s"><meta property="og:description" content="%s">'
            '<meta property="og:image" content="%s/next/og-en/%s.png">'
            '<meta name="twitter:card" content="summary_large_image">'
            '<script type="application/ld+json">%s</script>'
            '<style>%s</style></head><body><div class="w">%s</div></body></html>'
            % (e(title), e(desc), BASE, s, _alt_en(s), e(title), e(desc), BASE, e(drug), ld, CSS, "".join(body)))
    return Response(html, mimetype="text/html; charset=utf-8")


@cb_bp.route("/can-i-bring")
@cb_bp.route("/can-i-bring/")
def cb_index():
    e = _h.escape
    items = "".join('<p><a href="/can-i-bring/%s">Can I bring %s to %s?</a></p>'
                    % (slug(d, c), e(d), e(_CC.get(c, c))) for d, c in PAIRS)
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Can I bring my medicine abroad? Country-by-country guide</title>'
            '<meta name="description" content="Which medicines are banned or need a permit in Japan, UAE, Singapore, Saudi Arabia and more.">'
            '<link rel="canonical" href="%s/can-i-bring">'
            '<link rel="alternate" hreflang="en" href="%s/can-i-bring">'
            '<link rel="alternate" hreflang="ko" href="%s/ko">'
            '<link rel="alternate" hreflang="x-default" href="%s/can-i-bring">'
            '<style>%s</style></head><body><div class="w"><h1>Can I bring my medicine abroad?</h1>'
            '<p class="lede">Common medicines that are banned or restricted abroad.</p>%s'
            '<a class="cta" href="/next/en">Check any medicine in 21 countries</a>'
            '<p style="margin-top:18px;opacity:.7"><a href="/ko">한국어</a></p>'
            '</div></body></html>'
            % (BASE, BASE, BASE, BASE, CSS, items))
    return Response(html, mimetype="text/html; charset=utf-8")


@cb_bp.route("/sitemap-travel.xml")
def cb_sitemap():
    # ★gottago/eats 를 뺀다. 이 호스트에선 linklynk 로 301 되므로
    #   사이트맵이 튕기는 주소를 광고하는 꼴이었다. 저쪽 사이트맵으로 옮겼다.
    urls = ["%s/next/en" % BASE, "%s/can-i-bring" % BASE]
    urls += ["%s/can-i-bring/%s" % (BASE, slug(d, c)) for d, c in PAIRS]
    urls += ["%s/ko" % BASE]
    urls += ["%s/ko/%s" % (BASE, _q(ko_slug(l, c))) for l, q, c in KO_PAIRS]
    urls += ["%s/can-i-bring/%s" % (BASE, k) for k in KIT_EN]
    urls += ["%s/ko/%s" % (BASE, _q(k)) for k in KIT_KO]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join("<url><loc>%s</loc><changefreq>weekly</changefreq></url>" % u for u in urls)
           + "</urlset>")
    return Response(xml, mimetype="application/xml")


# ── IndexNow: Bing·Naver·Yandex 에 새 URL 을 즉시 알린다 (로그인 불필요, 키 파일로 소유 증명)
INDEXNOW_KEY = "8f3c1a7e5d2b4096a1c7e3f5b9d2a4c6"


@cb_bp.route("/8f3c1a7e5d2b4096a1c7e3f5b9d2a4c6.txt")
def cb_indexnow_key():
    return Response(INDEXNOW_KEY, mimetype="text/plain")


@cb_bp.route("/googleb66b58b492c65404.html")
def cb_google_verify():
    return Response("google-site-verification: googleb66b58b492c65404.html",
                    mimetype="text/html")


@cb_bp.route("/naver4bb0a34297d9200fa0c6f1417f6d6e3f.html")
def cb_naver_verify():
    return Response("naver-site-verification: naver4bb0a34297d9200fa0c6f1417f6d6e3f.html",
                    mimetype="text/html")


# ── 한국어 트랙 ──────────────────────────────────────────────────
# 닥터나우 질문 1건이 8개월간 1,839명을 모았다. 그 수요는 한국어 검색에 있는데
# 위 26개 페이지는 전부 영어였다. 같은 판정 엔진에 한국어 문안을 붙인다.
KO_CC = {"JP": "일본", "CN": "중국", "TW": "대만", "HK": "홍콩", "SG": "싱가포르",
         "TH": "태국", "VN": "베트남", "ID": "인도네시아", "PH": "필리핀",
         "AE": "UAE", "SA": "사우디", "QA": "카타르", "GB": "영국", "DE": "독일",
         "FR": "프랑스", "RU": "러시아", "US": "미국", "CA": "캐나다",
         "AU": "호주", "NZ": "뉴질랜드", "KR": "한국"}

# (표시명, 판정 질의, 국가코드)
KO_PAIRS = [
    ("감기약 슈도에페드린", "슈도에페드린", "JP"),
    ("감기약 슈도에페드린", "슈도에페드린", "TH"),
    ("코푸시럽", "코푸시럽", "JP"),
    ("애더럴", "애더럴", "JP"),
    ("애더럴", "애더럴", "SG"),
    ("애더럴", "애더럴", "TH"),
    ("콘서타", "콘서타", "JP"),
    ("콘서타", "콘서타", "SG"),
    ("코데인", "코데인", "JP"),
    ("코데인", "코데인", "AE"),
    ("트라마돌", "트라마돌", "JP"),
    ("졸피뎀", "졸피뎀", "JP"),
    ("졸피뎀", "졸피뎀", "SG"),
    ("자낙스", "자낙스", "AE"),
    ("멜라토닌", "멜라토닌", "GB"),
    ("멜라토닌", "멜라토닌", "DE"),
    ("CBD", "칸나비디올", "JP"),
    ("CBD", "칸나비디올", "SG"),
    ("타이레놀", "타이레놀", "JP"),
]

KO_LV = {"PROHIBITED": "반입이 막힙니다", "PERMIT": "사전 허가가 필요합니다",
         "DECLARE": "신고 대상입니다", "LIMIT": "수량·제형 제한이 있습니다",
         "OK": "특별한 제한은 확인되지 않았습니다"}

KO_DO = {
    "PROHIBITED": "두고 가세요. 현지에서 살 수 있는 대체약을 의사와 미리 상의하고, "
                  "질환을 설명하는 영문 소견서를 챙기면 도움이 됩니다.",
    "PERMIT": "출국 전에 도착국 보건당국의 승인을 받아야 합니다. 도착해서 신청할 수 "
              "없습니다. 처방전·영문 소견서·원래 포장을 함께 가져가세요.",
    "DECLARE": "세관에 신고하세요. 처방전을 지참하고 약은 원래 라벨이 붙은 포장 그대로 두세요.",
    "LIMIT": "허용 수량과 제형을 미리 확인하세요. 처방전과 원래 포장을 함께 가져갑니다.",
    "OK": "우리 데이터에서는 별도 제한이 확인되지 않았습니다. 다만 규정은 바뀝니다. "
          "처방전과 원래 포장은 그대로 두고 가세요.",
}

KO_WHY = {
    ("pseudoephedrine", "JP"): "일본은 슈도에페드린을 각성제 원료로 통제합니다. 일반 의약품용 약감증명이 아니라 마약단속부 사전 허가 대상이라, 출국 전에 허가를 받아야 합니다. 기준선은 10%입니다. 에페드린·슈도에페드린 10% 이하 함유 제제는 통제에서 제외됩니다. 한국 약국의 코감기약 상당수가 이 선을 넘기 때문에, 실무적으로는 두고 가고 현지에서 사는 편이 안전합니다.",
    ("pseudoephedrine", "TH"): "태국은 슈도에페드린을 향정신성 2종으로 분류합니다. 금지가 아니라 처방전이 있으면 30일분까지 허용이고 사전 허가도 필요 없습니다. 함정은 이 감기약을 보통 처방 없이 사기 때문에, 대부분의 여행자가 처방전 없이 들고 간다는 점입니다.",
    ("dihydrocodeine", "JP"): "코푸시럽에 든 디히드로코데인은 UN 국제통제물질 목록에 오른 마약류입니다. 한국에서 처방 없이 살 수 있다는 점 때문에 감각이 무뎌지기 쉽습니다.",
    ("dextroamphetamine", "JP"): "암페타민 계열 ADHD 약은 일본에서 반입이 금지됩니다. 본국 처방전이 있어도 예외가 아니며, 소지 자체가 형사 문제가 됩니다.",
    ("dextroamphetamine", "SG"): "싱가포르는 암페타민을 엄격히 통제합니다. 개인 반입은 원칙적으로 허용되지 않습니다.",
    ("dextroamphetamine", "TH"): "태국에서 암페타민은 1종 마약으로 분류됩니다. 개인 반입이 허용되지 않습니다.",
    ("methylphenidate", "JP"): "일본은 메틸페니데이트를 각성제가 아니라 향정신성 의약품으로 분류합니다. 마약단속부는 사전 허가가 필요 없는 성분으로 명시하고 있습니다. 적용되는 제한은 일반 처방약 기준인 1개월분까지이며, 그 범위 안이면 약감증명도 필요 없습니다. 애더럴은 정반대로 반입 자체가 금지돼 있어 둘을 혼동하기 쉽습니다.",
    ("methylphenidate", "SG"): "싱가포르는 메틸페니데이트를 통제 약물로 다룹니다. 반입 전 보건과학청(HSA) 승인이 필요합니다.",
    ("codeine", "JP"): "코데인은 일본에서 마약으로 분류되어, 일반 의약품용 약감증명이 아니라 마약단속부 사전 허가를 받아야 합니다. 기준선이 하나 있습니다. 코데인 1% 이하 함유 제제는 통제 대상에서 제외됩니다. 저용량 기침약이 통과하고 처방 강도 제제가 막히는 이유가 이것입니다.",
    ("codeine", "AE"): "UAE는 코데인을 금지하지 않습니다. 에미리트 의약품청은 코데인을 마약 스케줄 II로 분류하면서, 체류 기간 또는 3개월 중 짧은 쪽까지 여행자가 소지할 수 있다고 명시합니다. 조건은 서류이고 엄격합니다. 처방전 또는 의료기관이 공증한 소견서가 약과 함께 있어야 합니다. 보고된 구금 사례는 그 서류 없이 코데인 진통제나 기침약을 들고 간 경우입니다. 무료 온라인 사전승인도 있으며, 선택이지만 받아두는 편이 안전합니다.",
    ("tramadol", "JP"): "일본 마약단속부는 트라마돌이 마약이 아니라고 명시하고 있고, 통제물질 목록에도 없습니다. 일반 처방약으로 취급되어 1개월분까지는 약감증명 없이 가져갈 수 있습니다. 다만 UAE와 사우디는 정반대로 엄격히 통제하므로, 경유지가 있으면 그쪽 기준을 따로 확인해야 합니다.",
    ("zolpidem", "JP"): "졸피뎀은 일본에서 향정신성 의약품이며 사전 허가는 필요 없습니다. 적용되는 제한은 일반 처방약 기준인 1개월분까지입니다. 처방전과 원래 포장을 함께 지참하세요.",
    ("zolpidem", "SG"): "싱가포르는 졸피뎀을 통제 약물로 다룹니다. 처방전 지참이 필수이며 수량 제한이 있습니다.",
    ("alprazolam", "AE"): "UAE는 알프라졸람(자낙스)을 통제 물질로 다룹니다. 사전 승인 없이 반입하면 문제가 됩니다.",
    ("melatonin", "GB"): "영국에서 멜라토닌은 처방 의약품입니다. 미국·캐나다·호주에서는 마트 영양제 코너에 있어 같은 알약이라도 신분이 달라집니다.",
    ("melatonin", "DE"): "독일은 용량에 따라 멜라토닌을 처방 대상으로 봅니다. 영양제로 산 제품이라도 함량을 확인해야 합니다.",
    ("cannabidiol", "JP"): "일본은 THC가 포함된 CBD 제품의 반입을 금지합니다. THC 무함유 표기가 있어도 검사에서 검출되면 문제가 됩니다.",
    ("cannabidiol", "SG"): "싱가포르는 CBD를 통제 약물로 분류합니다. 반입이 허용되지 않습니다.",
    ("acetaminophen", "JP"): "아세트아미노펜은 일본에서도 일반 의약품입니다. 다만 개인 사용 수량 기준(의약품·의약부외품 2개월분)은 그대로 적용됩니다.",
}


def ko_slug(label, cc):
    b = re.sub(r"[^0-9A-Za-z가-힣]+", "-", label).strip("-")
    return "%s-%s" % (b, KO_CC.get(cc, cc))


_KO_BY_SLUG = {ko_slug(l, c): (l, q, c) for l, q, c in KO_PAIRS}


def _ko_why(ings, cc):
    for i in ings:
        for (k, c), txt in KO_WHY.items():
            if c == cc and (k in i or i in k):
                return txt
    return ""


@cb_bp.route("/ko/<path:s>")
def cb_ko_page(s):
    s = s.strip("/")
    _k = cb_kit(s, "ko")
    if _k is not None:
        return _k
    if s not in _KO_BY_SLUG:
        return Response("Not found", status=404)
    label, q, cc = _KO_BY_SLUG[s]
    kname = KO_CC.get(cc, cc)
    d = verdict(q)
    if not d.get("ok"):
        return Response("Not found", status=404)
    row = next((r for r in d.get("rows", []) if r["code"] == cc), None)
    lvl = row["level"] if row else "OK"
    why = _ko_why(d.get("ings", []), cc)
    ings = ", ".join(d.get("ings", [])[:3]) or "확인 필요"
    src = (row or {}).get("src") or SRC.get(cc) or ""
    ver = (row or {}).get("verified", False)
    title = "%s, %s에 가져가도 되나요?" % (label, kname)
    ansv = "%s에서 %s" % (kname, KO_LV[lvl])
    rel = [(l2, ko_slug(l2, c2)) for l2, q2, c2 in KO_PAIRS
           if (l2 == label or c2 == cc) and ko_slug(l2, c2) != s][:6]
    faq = ('{"@context":"https://schema.org","@type":"FAQPage","mainEntity":'
           '[{"@type":"Question","name":"%s","acceptedAnswer":{"@type":"Answer",'
           '"text":"%s %s"}}]}' % (_h.escape(title), _h.escape(ansv),
                                   _h.escape(why or KO_DO[lvl])))
    html = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>%s | BorderRx</title>'
        '<meta name="description" content="%s %s 성분 기준으로 확인한 결과입니다. 근거와 출처를 함께 표시합니다.">'
        '<link rel="canonical" href="%s/ko/%s">%s'
        '<script type="application/ld+json">%s</script>'
        '<style>%s</style></head><body><div class="w">'
        '<h1>%s</h1>'
        '<p class="lede">성분 기준 판정 · 출처 표기 · %s</p>'
        '<div class="ans"><div class="k">판정</div>'
        '<div class="v" style="color:%s">%s</div>'
        '<div class="ing">성분: %s</div></div>'
        % (_h.escape(title), _h.escape(label), _h.escape(kname),
           BASE, s, _alt_ko(s), faq, CSS, _h.escape(title),
           "규정 확인 권고" if not ver else "공식 출처 확인",
           COL.get(lvl, "#e9eef5"), _h.escape(ansv), _h.escape(ings)))
    if why:
        html += '<h2>왜 그런가</h2><p>%s</p>' % _h.escape(why)
    kdeep = KO_DEEP.get(s)
    if kdeep:
        html += _fill(s, kdeep, "ko")
    else:
        html += '<h2>어떻게 해야 하나</h2><p>%s</p>' % _h.escape(KO_DO[lvl])
    if src:
        html += ('<h2>출처</h2><p><a href="%s" rel="nofollow noopener" target="_blank">%s 공식 안내</a></p>'
                 % (_h.escape(src), _h.escape(kname)))
    html += _bridge(lvl, cc, "ko")
    html += ('<a class="cta" href="%s/next">약 이름 하나로 21개국 한 번에 보기</a>' % BASE)
    if rel:
        html += '<div class="rel"><h2>함께 보면 좋은 것</h2>' + "".join(
            '<a href="%s/ko/%s">%s</a>' % (BASE, sl, _h.escape(l2)) for l2, sl in rel) + '</div>'
    html += ('<div class="warn"><b>이 페이지는 참고용입니다.</b> UN 국제통제물질 등재는 '
             '단정할 수 있지만, 개별 국가 규정은 수시로 바뀌고 함량·제형에 따라 달라집니다. '
             '출국 전 해당국 공식 안내나 대사관으로 반드시 확인하세요. '
             '의학적 판단이 필요하면 의사·약사와 상의하세요.</div>'
             '</div></body></html>')
    return Response(html, mimetype="text/html; charset=utf-8")


@cb_bp.route("/ko")
@cb_bp.route("/ko/")
def cb_ko_index():
    items = "".join('<a href="%s/ko/%s">%s → %s</a>'
                    % (BASE, ko_slug(l, c), _h.escape(l), KO_CC.get(c, c))
                    for l, q, c in KO_PAIRS)
    html = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>약 해외 반입 가능 여부 | BorderRx</title>'
            '<meta name="description" content="감기약·ADHD약·수면제를 해외에 가져가도 되는지 '
            '성분 기준으로 확인합니다. 21개국, 출처 표기.">'
            '<link rel="canonical" href="%s/ko">'
            '<link rel="alternate" hreflang="ko" href="%s/ko">'
            '<link rel="alternate" hreflang="en" href="%s/can-i-bring">'
            '<link rel="alternate" hreflang="x-default" href="%s/can-i-bring">'
            '<style>%s</style></head><body><div class="w">'
            '<h1>이 약, 가져가도 되나요</h1>'
            '<p class="lede">브랜드가 아니라 성분으로 판정합니다. 21개국, 출처 함께 표기.</p>'
            '<div class="rel">%s</div>'
            '<a class="cta" href="%s/next">약 이름 직접 넣어보기</a>'
            '<p style="margin-top:18px;opacity:.7"><a href="%s/can-i-bring">English</a></p>'
            '</div></body></html>' % (BASE, BASE, BASE, BASE, CSS, items, BASE, BASE))
    return Response(html, mimetype="text/html; charset=utf-8")


# ── EN/KO 교차링크 ────────────────────────────────────────
# 구글이 /ko 를 고아로 본 이유: 들어오는 링크 0개, 번역 관계 신호 0개.
# 사이트맵에만 있고 링크가 없는 URL 은 후순위로 밀린다.
import urllib.parse as _up

def _q(p):
    """사이트맵 규격은 URL 이스케이프를 요구한다. 한글 경로를 인코딩한다."""
    return _up.quote(p, safe="")

_KO2EN_DRUG = {
    "감기약 슈도에페드린": "Sudafed", "애더럴": "Adderall",
    "코데인": "codeine", "트라마돌": "tramadol", "자낙스": "Xanax",
    "졸피뎀": "Ambien", "멜라토닌": "melatonin", "CBD": "CBD",
}
_EN_SET = set(PAIRS)

# KO 슬러그 -> EN 슬러그 (양쪽에 다 있는 조합만)
_KO2EN, _EN2KO = {}, {}
for _l, _qq, _c in KO_PAIRS:
    _d = _KO2EN_DRUG.get(_l)
    if _d and (_d, _c) in _EN_SET:
        _ks, _es = ko_slug(_l, _c), slug(_d, _c)
        _KO2EN[_ks] = _es
        _EN2KO[_es] = _ks


def _alt(ko_s, en_s):
    """★짝이 없으면 아무것도 내보내지 않는다.
       틀린 hreflang 쌍은 없는 것보다 나쁘다 — 구글이 두 페이지를 묶어버린다."""
    if not ko_s or not en_s:
        return ""
    return ('<link rel="alternate" hreflang="ko" href="%s/ko/%s">'
            '<link rel="alternate" hreflang="en" href="%s/can-i-bring/%s">'
            '<link rel="alternate" hreflang="x-default" href="%s/can-i-bring/%s">'
            % (BASE, _q(ko_s), BASE, en_s, BASE, en_s))


def _alt_ko(s):
    return _alt(s, _KO2EN.get(s))


def _alt_en(s):
    return _alt(_EN2KO.get(s), s)


# ══════════════════════════════════════════════════════════════
# canibringmeds.com 전용 홈 + 방법론 페이지
#
# ★이 사이트는 YMYL 이다. 약을 들고 국경을 넘어도 되는지 판정한다.
#   틀리면 사람이 공항에서 구금된다. 구글이 가장 늦게 신뢰하는 분류고,
#   익명 사이트는 아예 색인이 안 된다. 발행 주체·출처·방법·한계를
#   명시하는 건 장식이 아니라 입장권이다.
import os as _os

PUBLISHER = _os.environ.get("CB_PUBLISHER", "alaz ltd")
CONTACT   = _os.environ.get("CB_CONTACT", "")     # 비어 있으면 연락처 줄을 안 그린다

_ORG = ('{"@context":"https://schema.org","@type":"Organization",'
        '"name":"%s","url":"%s/","publisher":{"@type":"Organization","name":"%s"}}'
        % (PUBLISHER, BASE, PUBLISHER))


def _foot():
    c = ('<p><a href="%s/about">How we decide</a> · <a href="%s/ko">한국어</a></p>' % (BASE, BASE))
    return ('<div class="warn" style="margin-top:28px">'
            '<b>Reference only.</b> UN-scheduled substances we can state firmly, but '
            'national rules change and depend on dose and form. Confirm with the '
            "destination's official guidance or embassy before you fly. "
            'Talk to a doctor or pharmacist for medical decisions.</div>' + c)


def cb_home():
    """canibringmeds.com 의 루트. ★LinkLynk 앱 UI 가 아니다."""
    e = _h.escape
    top = "".join('<a href="%s/can-i-bring/%s">%s → %s</a>'
                  % (BASE, slug(d, c), e(d), e(_CC.get(c, c))) for d, c in PAIRS[:8])
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Can I bring my medicine abroad? — ingredient-based answers</title>'
        '<meta name="naver-site-verification" content="545a10d00ecef01274542750c9054dc4b9b4f8db">'
        '<meta name="description" content="Whether a medicine is allowed into a country '
        'depends on its active ingredient, not its brand. We check the ingredient against '
        'UN schedules and official national guidance, and show our sources.">'
        '<link rel="canonical" href="%s/">'
        '<link rel="alternate" hreflang="en" href="%s/">'
        '<link rel="alternate" hreflang="ko" href="%s/ko">'
        '<link rel="alternate" hreflang="x-default" href="%s/">'
        '<script type="application/ld+json">%s</script>'
        '<style>%s</style></head><body><div class="w">'
        '<h1>Can I bring my medicine abroad?</h1>'
        '<p class="lede">Brand names cross borders. Active ingredients decide whether '
        'you do. We check the ingredient, name the rule, and link the source.</p>'
        '<div class="rel">%s</div>'
        '<p><a href="%s/can-i-bring">All countries and medicines →</a></p>'
        '<a class="cta" href="%s/next/en">Check any medicine in 21 countries</a>'
        '%s</div></body></html>'
        % (BASE, BASE, BASE, BASE, _ORG, CSS, top, BASE, BASE, _foot()))
    return Response(html, mimetype="text/html; charset=utf-8")


@cb_bp.route("/about")
def cb_about():
    """어떻게 판정하는지, 무엇을 못 하는지. ★한계를 숨기면 신뢰를 잃는다."""
    contact = ('<h2>Contact</h2><p>%s</p>' % _h.escape(CONTACT)) if CONTACT else ""
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>How we decide — %s</title>'
        '<meta name="description" content="Our sources, our method, and what this site '
        'cannot tell you.">'
        '<link rel="canonical" href="%s/about">'
        '<script type="application/ld+json">%s</script>'
        '<style>%s</style></head><body><div class="w">'
        '<h1>How we decide</h1>'
        '<p class="lede">Published by %s.</p>'

        '<h2>Ingredient, not brand</h2>'
        '<p>Customs rules name substances, not products. Sudafed is pseudoephedrine in '
        'one country and a different formula in another; Adderall is amphetamine salts '
        'wherever it is sold. We resolve the product to its active ingredient first, then '
        'look the ingredient up. That is why a brand you consider harmless can still be '
        'refused entry.</p>'

        '<h2>Where the rules come from</h2>'
        '<p>Three layers, in this order:</p>'
        '<p>1. <b>UN scheduling.</b> The INCB Yellow, Green and Red Lists record which '
        'substances are under international control. This layer is stable and we state it '
        'plainly.</p>'
        '<p>2. <b>National guidance.</b> Japan MHLW, Singapore HSA, UAE MOHAP, Saudi SFDA, '
        'UK Home Office, and equivalent authorities elsewhere. Where a page exists we link '
        'it directly on the answer.</p>'
        '<p>3. <b>Nothing.</b> When neither layer covers a combination we say the '
        'restriction could not be confirmed, and we do not guess. A blank is not a yes.</p>'

        '<h2>What this site cannot tell you</h2>'
        '<p>It cannot tell you that you will be let through. Officers apply discretion, '
        'quantity limits and documentation rules that no public page fully captures. It '
        'cannot account for dose, formulation, or how much you carry — a quantity that is '
        'fine for personal use may be treated as import. It is not medical advice and not '
        'legal advice. It is a starting point for the question you then put to the '
        "destination's own authority.</p>"

        '<h2>When it is wrong</h2>'
        '<p>Rules change without notice and our pages lag. If you find an answer that no '
        'longer matches an official source, the official source wins. Treat anything here '
        'that contradicts an embassy or health ministry as out of date.</p>'
        '%s'
        '%s</div></body></html>'
        % (PUBLISHER, BASE, _ORG, CSS, _h.escape(PUBLISHER), contact, _foot()))
    return Response(html, mimetype="text/html; charset=utf-8")


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
and Welfare allows a {{qty_rx}} of prescription medicine and a {{qty_other}}
supply of other medicines with no certificate at all; above those amounts you
apply for one. The certificate raises the ceiling on medicines you are already
allowed to carry. It cannot authorise a substance whose import is prohibited
outright.</p>

<h2>The penalty</h2>
<p>Under the Stimulants Control Law, use, possession, transfer or receipt of
stimulants is punishable by {{stim_pen}}, as published by the Okinawa Institute of Science and
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
clinics describe {{visits}} even for a straightforward case.
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
<p><a href="https://jetprogramusa.org/wp-content/uploads/2025/03/2025-Yunyu-Kakuninsho-Import-of-Medication-Certification-Guide.pdf" rel="noopener" target="_blank">Yunyu Kakunin-sho import-of-medication guide, reproducing the MHLW quantity rules (PDF)</a><br>
<a href="https://www.oist.jp/resource-center/drugs" rel="noopener" target="_blank">Okinawa Institute of Science and Technology &mdash; drugs and the law in Japan</a><br>
<a href="https://www.us.emb-japan.go.jp/itpr_en/bringing-medications-to-japan.html" rel="noopener" target="_blank">Embassy of Japan in the United States &mdash; bringing medications to Japan</a><br>
<a href="https://www.associatedkyotoprogram.org/bringing-medications-japan/" rel="noopener" target="_blank">Associated Kyoto Program &mdash; bringing medications into Japan</a><br>
<a href="https://misti.mit.edu/japan-preparation-and-training/japan-logistics/japan-bringing-medication" rel="noopener" target="_blank">MIT MISTI &mdash; bringing medication to Japan</a><br>
<a href="https://imhclinic.jp/en/articles/adhd-in-japan" rel="noopener" target="_blank">IMH Clinic Tokyo &mdash; ADHD diagnosis and medication in Japan</a></p>
<p style="opacity:.7">Last checked 2 October 2026. Japanese rules change without
notice. Where the official pages above disagree with this one, they are right
and we are out of date.</p>
"""


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
permission where the preparation contains no more than {{pse_pct}} ephedrine or
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
<a href="https://jetprogramusa.org/wp-content/uploads/2025/03/2025-Yunyu-Kakuninsho-Import-of-Medication-Certification-Guide.pdf" rel="noopener" target="_blank">Yunyu Kakunin-sho import-of-medication guide, reproducing the MHLW quantity rules (PDF)</a><br>
<a href="https://www.accessible-japan.com/list-of-banned-and-restricted-medications-in-japan-late-2025-early-2026-guide/" rel="noopener" target="_blank">Accessible Japan &mdash; banned and restricted medications list</a><br>
<a href="https://www.associatedkyotoprogram.org/bringing-medications-japan/" rel="noopener" target="_blank">Associated Kyoto Program &mdash; bringing medications into Japan</a></p>
<p style="opacity:.7">Last checked 2 October 2026. Where the official pages above
disagree with this one, they are right and we are out of date. Where they
disagree with each other, ask the Regional Bureau.</p>
"""


DEEP["cbd-to-japan"] = """
<h2>The rule changed, and most guides you will find are describing the old one</h2>
<p>Japan used to decide this by plant part: products made from cannabis stems and
seeds were acceptable, products from leaves and flowers were not. That test is
gone. Since 12 December 2024 the revised Cannabis Control Act judges the finished
product by how much THC is left in it, whatever part of the plant it came from.
If a page tells you to check that your CBD is &ldquo;stem and seed derived,&rdquo;
it was written for a law that no longer applies.</p>

<h2>The thresholds</h2>
<p>Residual THC limits are set by product form, and they are low:</p>
<p><b>Oils and fats that are liquid at room temperature, and powders</b> &mdash;
{{thc_oil}}.</p>
<p><b>Water-soluble solutions</b> &mdash; {{thc_aq}}.</p>
<p><b>Everything else</b> &mdash; {{thc_other}}.</p>
<p>A second phase of the same law took effect on 1 March 2025, adding licensing
and testing requirements on the supply side.</p>

<h2>Why a product that is legal at home can be 300 times over the limit</h2>
<p>In the United States and much of Europe, hemp is defined as cannabis
containing no more than {{hemp_pct}} THC, and products are sold lawfully at that
ceiling. Convert the units: {{hemp_pct}} is {{hemp_ppm}}. Japan&rsquo;s limit for a CBD oil
is 10 ppm. A bottle that is entirely legal where you bought it, labelled as hemp
and marketed as non-intoxicating, can sit three hundred times above the Japanese
threshold and still be exactly what the label says. Nothing about the packaging
will tell you this. &ldquo;THC-free&rdquo; on a label is a marketing claim, not a
measurement against Japan&rsquo;s standard.</p>

<h2>Use is now an offence in itself</h2>
<p>The same revision created a cannabis use offence. Before it, the law reached
possession, transfer and cultivation; consumption as such was not separately
criminalised. It is now. This matters for travellers because it removes the
argument that you only used the product before arriving.</p>

<h2>What customs expects you to produce</h2>
<p>For a CBD product to clear, the documentation travellers are asked for is a
certificate of manufacture and a component analysis report from a laboratory
showing the THC content. That is a document you have to obtain from the maker
before you fly &mdash; it is not something you can assemble at the airport, and a
screenshot of a product page does not substitute for it.</p>

<h2>What we could not confirm</h2>
<p>We could not establish from an official Japanese source how the limits are
applied to a small quantity carried for personal use rather than to a commercial
import, or whether a traveller is in practice asked for the analysis report at
every border. We are not going to fill that gap with a guess. If the product
matters to you, ask a Regional Bureau Narcotics Control Department before you
book.</p>

<h2>Sources</h2>
<p><a href="https://www.mhlw.go.jp/stf/newpage_43079.html" rel="noopener" target="_blank">Ministry of Health, Labour and Welfare &mdash; phased enforcement of the revised Cannabis Control Act</a><br>
<a href="https://health-beauty-soleil.jp/news/%E3%80%90thc%E6%AE%8B%E7%95%99%E9%99%90%E5%BA%A6%E5%80%A4%E7%99%BA%E8%A1%A8%E3%80%91%E3%80%8C%E5%A4%A7%E9%BA%BB%E5%8F%96%E7%B7%A0%E6%B3%95%E5%8F%8A%E3%81%B3%E9%BA%BB%E8%96%AC%E5%8F%8A%E3%81%B3/" rel="noopener" target="_blank">Marunouchi Soleil Law Office &mdash; THC residual limit values, with the three thresholds and the 12 December 2024 date</a><br>
<a href="https://www.customs.go.jp/tokyo/english/yuubin/mayakuoyobikouseisinyaku.htm" rel="noopener" target="_blank">Tokyo Customs &mdash; narcotics, psychotropic drugs and raw materials for stimulants</a><br>
<a href="https://www.associatedkyotoprogram.org/bringing-medications-japan/" rel="noopener" target="_blank">Associated Kyoto Program &mdash; bringing medications into Japan</a></p>
<p style="opacity:.7">Last checked 2 October 2026. This area changed in December
2024 and again in March 2025. Treat anything older than that, here or elsewhere,
as describing a law that has been replaced.</p>
"""


# ══════════════════════════════════════════════════════════════
# 한글 깊은 본문. 영문판과 같은 1차 출처를 쓰되 한국 독자 기준으로 다시 썼다.
# ★hreflang 으로 "같은 글"이라고 선언해놨으니 한쪽만 두꺼우면 그 선언이 거짓이 된다.
KO_DEEP = {}

KO_DEEP["애더럴-일본"] = """
<h2>처방전과 영문 소견서가 통하지 않는 이유</h2>
<p>일본은 규제 약물을 서로 다른 법으로 나눠 관리하는데, 애더럴은 그중 반입 경로가
아예 없는 쪽에 들어갑니다. 마약과 향정신성의약품은 지방후생국장의 사전 허가를 받으면
개인이 가져갈 수 있습니다. 그런데 암페타민과 메스암페타민은 일본 법에서 마약이 아니라
<b>각성제</b>이고, 각성제단속법에는 개인 반입을 허가해주는 제도 자체가 없습니다.</p>
<p>그래서 평소 하던 준비가 전부 소용없습니다. 허가를 내주는 서류가 존재하지 않으니
처방전도, 번역한 소견서도, 약국 라벨이 붙은 원래 통도 도움이 되지 않습니다. 그것들은
그 암페타민이 본인 것이라는 증거일 뿐, 가져가도 된다는 허가가 아닙니다.</p>

<h2>수입확인증이 덮지 못하는 것</h2>
<p>輸入確認証(옛 약감증명)은 수량을 위한 제도이지 품목을 위한 제도가 아닙니다.
처방약 {{qty_rx}}, 그 외 의약품 {{qty_other}}까지는 증명 없이 가져갈 수 있고 그걸 넘으면
신청합니다. 이미 가져갈 수 있는 약의 한도를 올려주는 장치이지, 반입 자체가 금지된
물질을 허용해주지는 못합니다.</p>

<h2>형량</h2>
<p>각성제단속법상 각성제의 사용·소지·양도·수수는 {{stim_pen}}입니다.
오키나와과학기술대학원대학이 외국인 교직원·학생용으로 공개한 안내에 적힌 수치입니다.
교토 유학 프로그램은 더 실무적으로 씁니다 — ADHD 각성제를 &ldquo;어떤 이유로든&rdquo;
일본에 들여오면 체포·구금 위험이 있다고.</p>

<h2>체류 기간에 따라 답이 갈립니다</h2>
<p>애더럴은 일본에서 처방되지 않습니다. 그러니 진짜 질문은 현지에서 치료를 받을 수
있느냐이고, 그 답은 머무는 기간에 따라 완전히 달라집니다. 이 구분을 하는 페이지가
거의 없습니다.</p>
<p><b>짧은 여행 — 며칠에서 몇 주.</b> 현지에서 치료를 시작하는 건 현실적으로 어렵습니다.
콘서타와 바이반스는 2019년 말부터 시행된 유통관리 제도 아래 있고, 처방 의사·조제 약국·
환자 <b>세 주체가 전부 등록</b>돼 있어야 합니다. 해외에서 받은 진단은 일본 의사가 다시
확인해야 하며, 단순한 경우도 {{visits}}가 걸린다고 현지 클리닉은 설명합니다.
약 없이 다녀오는 일정으로 짜고, 그 얘기를 출국 전에 주치의와 하세요. 도착한 뒤가 아니라.</p>
<p><b>긴 체류 — 학기, 주재, 이주.</b> 치료는 가능하고 절차도 평범합니다. 콘서타
(메틸페니데이트 서방정)는 등록 경로로 전 연령 승인돼 있습니다. 스트라테라(아토목세틴)와
인튜니브(구안파신 서방정)는 전 연령 승인이고 별도 등록이 필요 없습니다. 바이반스는
6~18세만 승인이라 성인은 일본에서 새로 시작할 수 없습니다. 리탈린은 있지만 기면증용이지
ADHD용이 아닙니다. 진단서·검사 결과·복용 이력을 챙겨가면 재평가가 짧아집니다.</p>

<h2>같은 여행에서 저지르는 다른 실수</h2>
<p>애더럴을 두고 가는 판단은 제대로 해놓고 가방에 다른 금지 품목을 같이 넣는 경우가
많습니다. 슈도에페드린이 든 감기·비염약은 일본에서 따로 규제되고, 코데인이 든 진해·
진통제도 제한됩니다. 처방약만 보지 말고 상비약 칸을 열어보세요.</p>

<h2>출처</h2>
<p><a href="https://www.customs.go.jp/tokyo/english/yuubin/mayakuoyobikouseisinyaku.htm" rel="noopener" target="_blank">도쿄세관 — 마약·향정신성의약품·각성제원료</a><br>
<a href="https://kouseikyoku.mhlw.go.jp/kantoshinetsu/iji/documents/mayaku-keitaiyushutunyu28-eigo.pdf" rel="noopener" target="_blank">후생노동성 간토신에쓰 지방후생국 — 휴대에 의한 마약 수출입 (PDF)</a><br>
<a href="https://jetprogramusa.org/wp-content/uploads/2025/03/2025-Yunyu-Kakuninsho-Import-of-Medication-Certification-Guide.pdf" rel="noopener" target="_blank">수입확인증 안내서 — 후생노동성 수량 규정 수록 (PDF)</a><br>
<a href="https://www.oist.jp/resource-center/drugs" rel="noopener" target="_blank">오키나와과학기술대학원대학 — 일본의 약물 관련 법</a><br>
<a href="https://www.associatedkyotoprogram.org/bringing-medications-japan/" rel="noopener" target="_blank">Associated Kyoto Program — 일본 반입 의약품 안내</a><br>
<a href="https://imhclinic.jp/en/articles/adhd-in-japan" rel="noopener" target="_blank">IMH 클리닉 도쿄 — 일본의 ADHD 진단과 약물</a></p>
<p style="opacity:.7">최종 확인 2026년 10월 2일. 위 공식 안내와 이 페이지가 다르면
공식 안내가 맞고 이 페이지가 낡은 것입니다.</p>
"""

KO_DEEP["감기약-슈도에페드린-일본"] = """
<h2>이건 공식 출처끼리 말이 다른 몇 안 되는 경우입니다</h2>
<p>대부분의 여행 가이드는 슈도에페드린은 일본에 못 가져간다고 단정합니다. 일본 정부
문서는 그보다 좁게 쓰여 있고, 서로 완전히 일치하지도 않습니다. 틀렸을 때 대가가
공항 억류라서, 한쪽을 골라 단정하는 대신 각각이 뭐라고 쓰는지 그대로 보여드립니다.</p>
<p><b>일본 세관</b>은 각성제원료에 대해 &ldquo;의사의 처방에 따라 본인이 직접 휴대하여
반입하는 경우를 제외하고 일반 개인의 수입을 금지한다&rdquo;고 씁니다. 전면 금지가 아니라
조건부 금지입니다.</p>
<p><b>후생노동성 지방후생국</b>은 한 발 더 나가 기준을 제시합니다. 에페드린 또는
메틸에페드린을 {{pse_pct}} 이하로 함유한 제제는 개인의 약용 목적이면 사전 허가 없이 가능하고,
그 이상은 수입 허가가 필요합니다.</p>
<p><b>제3자 가이드</b>는, 외국인 거주자용으로 쓰인 것들을 포함해, 수도에페드린 제품은
처방이 있어도 개인 반입이 안 된다고 씁니다.</p>

<h2>어느 쪽으로 읽어도 예외가 없는 것</h2>
<p>세 가지는 모든 공식 출처에 공통으로 나오고 예외가 없습니다.</p>
<p><b>본인이 직접 들고 들어가야 합니다.</b> 다른 사람이 대신 가져다줄 수 없습니다.</p>
<p><b>우편으로는 안 됩니다.</b> 해외에서 국제우편으로 주문하는 것은 전면 금지이고,
세관은 필요한 허가 없이 들어온 우편물은 반입도 반송도 되지 않는다고 명시합니다.</p>
<p><b>처방이 있어야 합니다.</b> 약국 선반에서 산 일반의약품 상자는 세관이 말하는 조건을
충족하지 않습니다. 같은 성분이 다른 나라에서 전문의약품이더라도 마찬가지입니다.</p>

<h2>그래도 &ldquo;두고 가라&rdquo;가 합리적인 조언인 이유</h2>
<p>10% 기준은 성분이 아니라 <b>제품</b>의 속성입니다. 지금 들고 있는 상자의 함량을
본인이 알아야 하고, 그 면제 규정이 전제하는 처방을 갖고 있어야 하고, 창구에서 통역을
끼고 둘 다 설명할 수 있어야 합니다. 유학 담당 부서들이 그냥 가져가지 말라고 하는 건
위 세 가지 해석 중 어느 쪽이 맞아도 안전한 답이기 때문입니다. 여행 중에 꼭 필요한 약이
아니라면, 도착해서 일본 감기약을 사는 게 가장 싸고 확실합니다.</p>

<h2>브랜드가 아니라 성분표를 보세요</h2>
<p>브랜드 이름은 나라를 건너면 같은 성분을 뜻하지 않습니다. 그리고 복합 감기약에는
따로 규제되는 성분이 섞여 들어가는 일이 잦습니다 — 코데인이 대표적인데, 일본은 이걸
마약으로 분류해서 지방후생국장의 사전 허가를 요구하고 처리에 2주쯤 걸립니다.
실제로 가방에 넣을 그 상자의 성분표를 읽으세요.</p>

<h2>흡입기: 확인 못 했고, 못 했다고 씁니다</h2>
<p>코 흡입기는 각성제 계열 성분이 들어 있을 수 있다는 이유로 일본 여행 안내에서 반복해서
언급됩니다. 어떤 물질이 문제인지, 어떻게 분류되는지는 일본 공식 출처로 확인하지
못했습니다. 그래서 괜찮다고도 금지라고도 쓰지 않겠습니다. 흡입기는 알약과 별개의 질문으로
두고, 위 규정이 알아서 덮어주겠거니 하지 말고 출국 전에 지방후생국에 물어보세요.</p>

<h2>출처</h2>
<p><a href="https://www.customs.go.jp/tokyo/english/yuubin/mayakuoyobikouseisinyaku.htm" rel="noopener" target="_blank">도쿄세관 — 마약·향정신성의약품·각성제원료</a><br>
<a href="https://kouseikyoku.mhlw.go.jp/kantoshinetsu/iji/documents/mayaku-keitaiyushutunyu28-eigo.pdf" rel="noopener" target="_blank">후생노동성 간토신에쓰 지방후생국 — 휴대에 의한 마약 수출입 (PDF)</a><br>
<a href="https://jetprogramusa.org/wp-content/uploads/2025/03/2025-Yunyu-Kakuninsho-Import-of-Medication-Certification-Guide.pdf" rel="noopener" target="_blank">수입확인증 안내서 — 후생노동성 수량 규정 수록 (PDF)</a><br>
<a href="https://www.oist.jp/resource-center/drugs" rel="noopener" target="_blank">오키나와과학기술대학원대학 — 일본의 약물 관련 법</a><br>
<a href="https://www.associatedkyotoprogram.org/bringing-medications-japan/" rel="noopener" target="_blank">Associated Kyoto Program — 일본 반입 의약품 안내</a><br>
<a href="https://imhclinic.jp/en/articles/adhd-in-japan" rel="noopener" target="_blank">IMH 클리닉 도쿄 — 일본의 ADHD 진단과 약물</a></p>
<p style="opacity:.7">최종 확인 2026년 10월 2일. 위 공식 안내와 이 페이지가 다르면
공식 안내가 맞고 이 페이지가 낡은 것입니다.</p>
"""

KO_DEEP["CBD-일본"] = """
<h2>법이 바뀌었고, 검색해서 나오는 글 대부분은 옛 법 기준입니다</h2>
<p>일본은 예전에 이걸 식물 부위로 판단했습니다. 대마 줄기와 씨앗에서 뽑은 제품은 되고
잎·꽃에서 뽑은 건 안 되는 식이었습니다. 그 기준은 없어졌습니다. 2024년 12월 12일 시행된
개정 대마단속법은 어느 부위에서 왔든 <b>완성품에 THC가 얼마나 남아 있는지</b>로
판단합니다. &ldquo;줄기·씨앗 유래인지 확인하세요&rdquo;라고 적힌 글은 이미 없어진 법을
설명하고 있는 겁니다.</p>

<h2>기준치</h2>
<p>잔류 THC 한도는 제형별로 정해져 있고, 낮습니다.</p>
<p><b>상온에서 액체인 유지류와 분말</b> — {{thc_oil}}</p>
<p><b>수용액</b> — {{thc_aq}}</p>
<p><b>그 외 전부</b> — {{thc_other}}</p>
<p>같은 법의 2단계는 2025년 3월 1일 시행돼 공급 측에 허가·검사 의무를 추가했습니다.</p>

<h2>현지에서 합법인 제품이 일본 기준의 300배일 수 있는 이유</h2>
<p>미국과 유럽 상당수는 THC {{hemp_pct}} 이하를 헴프로 정의하고, 제품은 그 한도까지 합법적으로
팔립니다. 단위를 바꿔보면 {{hemp_pct}}는 <b>{{hemp_ppm}}</b>입니다. 일본의 CBD 오일 한도는 10 ppm
입니다. 산 곳에서 완벽히 합법이고 라벨에 적힌 그대로인 제품이 일본 기준의 삼백 배일 수
있습니다. 포장을 아무리 봐도 이건 알 수 없습니다. 라벨의 &ldquo;THC-free&rdquo;는 마케팅
문구이지 일본 기준으로 측정한 값이 아닙니다.</p>

<h2>이제 사용 자체가 범죄입니다</h2>
<p>같은 개정으로 대마 사용죄가 신설됐습니다. 그전까지 법은 소지·양도·재배를 다뤘고 사용
자체는 따로 처벌하지 않았습니다. 지금은 처벌합니다. 여행자에게 이게 중요한 이유는,
&ldquo;입국 전에 썼을 뿐&rdquo;이라는 설명이 더는 성립하지 않기 때문입니다.</p>

<h2>세관이 요구하는 서류</h2>
<p>CBD 제품이 통관되려면 여행자에게 요구되는 서류는 제조증명서와 시험기관의 성분분석서
입니다. THC 함량이 적힌 문서여야 합니다. 이건 출국 전에 제조사에서 받아둬야 하는
것이고, 공항에서 만들 수 없으며, 제품 판매 페이지 캡처는 대체가 되지 않습니다.</p>

<h2>확인하지 못한 것</h2>
<p>이 한도가 상업적 수입이 아니라 개인이 소량 휴대하는 경우에 어떻게 적용되는지,
여행자가 실제로 매번 분석서를 요구받는지는 일본 공식 출처로 확인하지 못했습니다.
그 빈칸을 추측으로 채우지 않겠습니다. 그 제품이 꼭 필요하다면 예약 전에 지방후생국
마약단속부에 문의하세요.</p>

<h2>출처</h2>
<p><a href="https://www.mhlw.go.jp/stf/newpage_43079.html" rel="noopener" target="_blank">후생노동성 — 개정 대마단속법 단계별 시행 안내</a><br>
<a href="https://health-beauty-soleil.jp/news/%E3%80%90thc%E6%AE%8B%E7%95%99%E9%99%90%E5%BA%A6%E5%80%A4%E7%99%BA%E8%A1%A8%E3%80%91%E3%80%8C%E5%A4%A7%E9%BA%BB%E5%8F%96%E7%B7%A0%E6%B3%95%E5%8F%8A%E3%81%B3%E9%BA%BB%E8%96%AC%E5%8F%8A%E3%81%B3/" rel="noopener" target="_blank">마루노우치 소레이유 법률사무소 — THC 잔류 한도치와 2024년 12월 12일 시행</a><br>
<a href="https://www.customs.go.jp/tokyo/english/yuubin/mayakuoyobikouseisinyaku.htm" rel="noopener" target="_blank">도쿄세관 — 마약·향정신성의약품·각성제원료</a><br>
<a href="https://www.associatedkyotoprogram.org/bringing-medications-japan/" rel="noopener" target="_blank">Associated Kyoto Program — 일본 반입 의약품 안내</a></p>
<p style="opacity:.7">최종 확인 2026년 10월 2일. 이 영역은 2024년 12월과 2025년 3월에
연달아 바뀌었습니다. 그보다 오래된 설명은 여기든 다른 곳이든 이미 교체된 법을
설명하는 것으로 보세요.</p>
"""


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
    "uae_qty":   {"en": "for the period of stay or a maximum of three months&rsquo; use, whichever is less",
                  "ko": "체류 기간분 또는 최대 3개월분 중 더 짧은 쪽"},
    "uae_rxage": {"en": "issued within the last three months and stamped by the issuing facility",
                  "ko": "3개월 이내 발급 + 의료기관 직인"},
    "cod_cls":   {"en": "Narcotic Schedule II", "ko": "마약 스케줄 II"},
    "tram_cls":  {"en": "a controlled drug (CD)", "ko": "통제 의약품(CD)"},
    "benz_cls":  {"en": "a controlled drug (CD), additionally listed under Psychotropic Schedule IV",
                  "ko": "통제 의약품(CD)이자 향정신성 스케줄 IV"},
    "uae_count": {"en": "more than two hundred", "ko": "200개가 넘는"},
    "uae_listd": {"en": "15 September 2022",    "ko": "2022년 9월 15일"},
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

_SRCFOR = {
 "adderall-to-japan": "jp", "sudafed-to-japan": "jp", "cbd-to-japan": "jp_cbd",
 "애더럴-일본": "jp", "감기약-슈도에페드린-일본": "jp", "CBD-일본": "jp_cbd",
 "codeine-to-united-arab-emirates": "uae", "코데인-UAE": "uae",
 "tramadol-to-united-arab-emirates": "uae",
 "xanax-to-united-arab-emirates": "uae", "자낙스-UAE": "uae",
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
    return _re.sub(r"\{\{([a-z_]+)\}\}", rep, tpl)



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
"""

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
"""


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
"""


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
"""

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
"""

# ── 배포 시점 검증. 키를 틀리면 여기서 죽는다.
for _s, _t in list(DEEP.items()):
    _fill(_s, _t, "en")
for _s, _t in list(KO_DEEP.items()):
    _fill(_s, _t, "ko")
# ══════════════════════════════════════════════════════════════════════
# 다리 — 판정에서 행동으로
#
# ★왜 필요한가: 영문 22페이지 중 PROHIBITED 14 · PERMIT 7 · LIMIT 1 이다.
#   즉 21명 중 21명이 "그냥 들고 타면 안 된다"는 답을 받는다. 그 사람에게
#   필요한 건 약이 아니라 서류다. 약은 우리가 팔 수 없고(약사법·각국 법),
#   서류 절차 안내는 팔 수 있다. 다리는 거기에 놓는다.
#
# ★절대 하지 않는 것: 금지 성분에 대해 "허가를 받으면 된다"고 말하는 것.
#   일본 각성제(애더럴)·슈도에페드린은 수입확인증이 발급되지 않는다.
#   PROHIBITED 와 PERMIT 의 안내문은 반드시 갈라야 한다.
# ══════════════════════════════════════════════════════════════════════

_FACT.update({
    # 싱가포르 HSA (hsa.gov.sg 2026-10-02 확인)
    "sg_portal": {"en": "go.gov.sg/hsa-ptm", "ko": "go.gov.sg/hsa-ptm"},
    "sg_lead":   {"en": "at least two weeks before you arrive",
                  "ko": "입국 최소 2주 전"},
    "sg_qty":    {"en": "three months&rsquo; supply", "ko": "3개월분"},
    "sg_label":  {"en": "the patient&rsquo;s name, the medication name and the quantity, "
                        "applied by the dispensing pharmacy",
                  "ko": "조제 약국이 붙인 환자 이름·약품명·수량"},
    # 일본 후생노동성 수입확인증 (impconf.mhlw.go.jp / JET 안내서 2026-10-02 확인)
    "jp_portal": {"en": "impconf.mhlw.go.jp", "ko": "impconf.mhlw.go.jp"},
    "jp_mail":   {"en": "yakkan@mhlw.go.jp", "ko": "yakkan@mhlw.go.jp"},
    "jp_lead":   {"en": "at least one month before departure &mdash; processing can take up to four weeks",
                  "ko": "출국 최소 한 달 전 — 심사에 최대 4주가 걸린다"},
    "jp_ext":    {"en": "24 items of any single product", "ko": "품목당 24개"},
})

_SRCSET.update({
 "sg_permit": [
  ("https://www.hsa.gov.sg/travelling-with-medication-and-medical-devices/personal-medications/",
   {"en": "Health Sciences Authority &mdash; travelling with medication to Singapore",
    "ko": "싱가포르 보건과학청(HSA) — 의약품 지참 입국 안내"}),
  ("https://go.gov.sg/hsa-ptm",
   {"en": "HSA &mdash; application form for bringing in personal medication",
    "ko": "HSA — 개인 의약품 반입 신청 양식"}),
 ],
 "jp_permit": [
  ("https://impconf.mhlw.go.jp/aicpte/page/login.jsp?lang=en",
   {"en": "Ministry of Health, Labour and Welfare &mdash; import confirmation online system",
    "ko": "후생노동성 — 의약품등 수입확인 온라인 시스템"}),
  ("https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iyakuhin/kojinyunyu/topics/tp010401-1.html",
   {"en": "MHLW &mdash; personal import of medicines",
    "ko": "후생노동성 — 의약품등의 개인 수입"}),
  ("https://jetprogramusa.org/wp-content/uploads/2025/03/2025-Yunyu-Kakuninsho-Import-of-Medication-Certification-Guide.pdf",
   {"en": "Yunyu Kakunin-sho guide, reproducing the MHLW quantity thresholds (PDF)",
    "ko": "수입확인증 안내서 — 후생노동성 수량 기준 수록 (PDF)"}),
  ("https://www.customs.go.jp/tokyo/english/yuubin/mayakuoyobikouseisinyaku.htm",
   {"en": "Tokyo Customs &mdash; narcotics, psychotropics and stimulant raw materials",
    "ko": "도쿄세관 — 마약·향정신성의약품·각성제원료"}),
 ],
 "ae_permit": [
  ("https://u.ae/en/information-and-services/health-and-fitness/Health-and-wellbeing/drugs-and-controlled-medicines",
   {"en": "UAE Government portal &mdash; drugs and controlled medicines",
    "ko": "UAE 정부 포털 — 약물과 통제 의약품"}),
  ("https://www.ede.gov.ae/documents/61005/0/Controlled+and+semi-controlled+medicines+list.pdf",
   {"en": "Emirates Drug Establishment &mdash; controlled and semi-controlled medicines list (PDF)",
    "ko": "에미리트 의약품청(EDE) — 통제·준통제 의약품 목록 (PDF)"}),
 ],
 "letter": [
  ("https://www.gov.uk/travelling-controlled-drugs",
   {"en": "UK Government &mdash; travelling with controlled medicine, and what the prescriber&rsquo;s letter must state",
    "ko": "영국 정부 — 통제 의약품 지참 여행과 처방자 소견서 필수 기재 사항"}),
  ("https://www.hsa.gov.sg/travelling-with-medication-and-medical-devices/personal-medications/",
   {"en": "Health Sciences Authority &mdash; prescription or doctor&rsquo;s letter and original labelled packaging",
    "ko": "싱가포르 보건과학청(HSA) — 처방전·소견서와 원포장 라벨 요건"}),
  ("https://www.incb.org/incb/en/narcotic-drugs/Yellowlist/yellow-list.html",
   {"en": "International Narcotics Control Board &mdash; Yellow List, narcotic drugs under international control",
    "ko": "UN 국제마약통제위원회 — 국제 통제 마약 옐로리스트"}),
  ("https://wwwnc.cdc.gov/travel/page/pack-smart",
   {"en": "US Centers for Disease Control and Prevention &mdash; packing medicines for travel",
    "ko": "미국 질병통제예방센터(CDC) — 여행용 의약품 포장 안내"}),
 ],
})

_SRCFOR.update({
 "permit-japan": "jp_permit",
 "permit-singapore": "sg_permit",
 "permit-united-arab-emirates": "ae_permit",
 "doctors-letter": "letter",
 "승인-일본": "jp_permit",
 "승인-싱가포르": "sg_permit",
 "승인-UAE": "ae_permit",
 "소견서": "letter",
})

# ── 승인 절차 허브. 판정 페이지 21개가 여기로 모인다.
KIT_EN, KIT_KO, KIT_ALT = {}, {}, {}

KIT_ALT["permit-japan"] = "승인-일본"
KIT_ALT["permit-singapore"] = "승인-싱가포르"
KIT_ALT["permit-united-arab-emirates"] = "승인-UAE"
KIT_ALT["doctors-letter"] = "소견서"

KIT_EN["permit-japan"] = (
 "How to get a Yunyu Kakunin-sho for Japan",
 "Japan's import confirmation certificate for medicine: when you need one, when no "
 "certificate can be issued at all, how to apply and how long it takes.",
 """
<h2>What the certificate is</h2>
<p>A Yunyu Kakunin-sho (&#36664;&#20837;&#30906;&#35469;&#35388;, also written <i>yakkan shoumei</i>) is
a confirmation from Japan's Ministry of Health, Labour and Welfare that the medicine you are
carrying is for your own treatment and not for sale. It is not a licence to import a banned
substance. It is a statement that your quantity is personal.</p>

<h2>When you need one</h2>
<p>Below certain quantities, confirmation at customs on arrival is normally enough. You need the
certificate when you exceed them:</p>
<p>&bull; more than a {{qty_rx}} of a prescription medicine<br>
&bull; more than a {{qty_other}} supply of a non-prescription medicine<br>
&bull; more than {{jp_ext}} of an external-use product</p>

<h2>When no certificate will be issued</h2>
<p>This is the part that gets travellers arrested. Japan does not issue an import confirmation for
substances it prohibits outright, and the prohibition covers medicines that are ordinary
prescriptions or even over-the-counter products elsewhere. Stimulants and stimulant raw materials
are the main trap: amphetamine-based ADHD medication and pseudoephedrine cold medicine both fall
in this group, and no application, letter or declaration opens that door. The penalty for
stimulants is {{stim_pen}}.</p>
<p>If your medicine is in that group, the certificate route is not a slower path to the same
destination &mdash; it is a closed door. Read the specific page instead:
<a href="/can-i-bring/adderall-to-japan">Adderall</a> &middot;
<a href="/can-i-bring/sudafed-to-japan">Sudafed and pseudoephedrine</a> &middot;
<a href="/can-i-bring/cbd-to-japan">CBD</a>.</p>

<h2>Narcotics and psychotropics are a separate route</h2>
<p>If you carry a narcotic or psychotropic medicine for your own treatment &mdash; not an excess
quantity of an ordinary drug, but a controlled one &mdash; permission to import by carrying is
handled by the narcotics control department of the regional health bureau, not by the ordinary
import confirmation. Ask about your specific medicine before you assume which form applies.</p>

<h2>How to apply</h2>
<p>Applications go through the ministry's online system at
<a href="https://impconf.mhlw.go.jp/aicpte/page/login.jsp?lang=en" rel="noopener" target="_blank">{{jp_portal}}</a>.
Questions go to {{jp_mail}}. Apply {{jp_lead}}, so a trip booked three weeks out is already
too late for anything that needs the certificate.</p>
<p>The application asks what the product is, what is in it, how much you are bringing and when you
are travelling. Have your prescription or a doctor's letter ready to attach, with the active
ingredient named in generic form &mdash; the officer reading your file works from the ingredient,
not the brand. Our <a href="/can-i-bring/doctors-letter">doctor's letter template</a> covers
the fields that get asked for.</p>

<h2>At the airport</h2>
<p>Carry the certificate with you on arrival. Not in checked baggage, not in an email you plan to
open on airport wi-fi. The guidance is blunt about this: if it is required, you must have it with
you when you arrive.</p>
""")

KIT_EN["permit-singapore"] = (
 "How to get HSA approval to bring medicine into Singapore",
 "Singapore's Health Sciences Authority approval for personal medication: who needs it, "
 "the application form, the two-week lead time and the three-month quantity limit.",
 """
<h2>Who needs approval</h2>
<p>Singapore's Health Sciences Authority requires prior approval for medicines containing
controlled substances. The authoritative list is Appendix A of HSA's document guide for bringing in
personal medications, which draws on the Second and Third Schedules to the Misuse of Drugs
Regulations and the First Schedule to the Health Products (Therapeutic Products) Regulations 2016.
Check your medicine against that appendix by active ingredient, not by brand name.</p>

<h2>If no approval is needed</h2>
<p>You may bring up to {{sg_qty}} of a medicine that is neither controlled nor prohibited. That
ceiling applies to the quantity you carry, not to the length of your trip.</p>

<h2>How to apply</h2>
<p>The application form is at
<a href="https://go.gov.sg/hsa-ptm" rel="noopener" target="_blank">{{sg_portal}}</a>.
Submit it {{sg_lead}}, which HSA asks for so there is time to process it. An application filed
from the departure lounge is not an application.</p>

<h2>What to carry regardless</h2>
<p>&bull; A copy of a valid prescription, or a doctor's letter from your country of residence.<br>
&bull; Each medicine in its original container or packaging, labelled with {{sg_label}}.</p>
<p>The labelling requirement is the one travellers break without noticing: decanting a month of
tablets into an unlabelled weekly organiser removes the only proof that the medicine is yours and
was dispensed to you. Carry the original box even if you also carry an organiser. Our
<a href="/can-i-bring/doctors-letter">doctor's letter template</a> covers the fields HSA and
other authorities ask for.</p>

<h2>Where the hard cases are</h2>
<p>Approval is a process for controlled medicines, not a workaround for prohibited ones. Cannabis
derivatives are the clearest example &mdash; Singapore's ban covers them regardless of THC content,
so no approval is available. The individual pages are more specific:
<a href="/can-i-bring/adderall-to-singapore">Adderall</a> &middot;
<a href="/can-i-bring/codeine-to-singapore">codeine</a> &middot;
<a href="/can-i-bring/ambien-to-singapore">Ambien</a> &middot;
<a href="/can-i-bring/cbd-to-singapore">CBD</a>.</p>
""")

KIT_EN["permit-united-arab-emirates"] = (
 "How to get UAE approval to bring medicine in",
 "The UAE controlled and semi-controlled medicines list, the prior-approval requirement, "
 "how recent your prescription must be and how much you may carry.",
 """
<h2>Three categories, not two</h2>
<p>The UAE sorts medicines into controlled, semi-controlled and uncontrolled. {{uae_count}}
substances sit on the controlled and semi-controlled list published by the Emirates Drug
Establishment, in the edition dated {{uae_listd}}. Opioid painkillers, benzodiazepines, sleep
medication and ADHD stimulants are spread across those categories, so a medicine being routine at
home says nothing about which category it lands in here.</p>

<h2>Prior approval</h2>
<p>For a controlled or semi-controlled medicine you need approval from the health authority
<i>before</i> you travel. There is no counter at the airport that issues it. Travellers have been
detained over quantities they considered obviously personal, which is the risk this step exists to
remove.</p>

<h2>Your prescription has an expiry for this purpose</h2>
<p>The prescription must be {{uae_rxage}}. A repeat prescription from last year, or a photo of a
label, does not meet that. Get a fresh one before you fly even if your medication has not
changed.</p>

<h2>How much you may carry</h2>
<p>{{uae_qty}}. Work out the figure for your own trip and carry that, not a round number. An
excess is the thing an officer can see at a glance.</p>

<h2>What to have on you</h2>
<p>The approval, the recent stamped prescription, and the medicine in its original labelled
packaging. A letter from your prescriber naming the active ingredient in generic form closes the
gap between the brand on your box and the substance on the UAE's list &mdash; our
<a href="/can-i-bring/doctors-letter">template</a> covers it.</p>
<p>Specific medicines: <a href="/can-i-bring/codeine-to-united-arab-emirates">codeine</a> &middot;
<a href="/can-i-bring/tramadol-to-united-arab-emirates">tramadol</a> &middot;
<a href="/can-i-bring/xanax-to-united-arab-emirates">Xanax</a> &middot;
<a href="/can-i-bring/valium-to-united-arab-emirates">Valium</a> &middot;
<a href="/can-i-bring/ambien-to-united-arab-emirates">Ambien</a> &middot;
<a href="/can-i-bring/adderall-to-united-arab-emirates">Adderall</a> &middot;
<a href="/can-i-bring/cbd-to-united-arab-emirates">CBD</a>.</p>
""")
KIT_EN["doctors-letter"] = (
 "Doctor's letter for travelling with medication &mdash; what it must say",
 "A customs officer works from the active ingredient, not your brand name. The fields a "
 "prescriber's letter must carry, and a template you can hand your doctor.",
 """
<h2>Why the brand name is the problem</h2>
<p>Control lists are written in generic names. The UN narcotics and psychotropics lists, the UAE's
controlled-substances list, Japan's stimulant schedules and Singapore's Misuse of Drugs Regulations
all name substances, not products. An officer holding a letter that says &ldquo;Adderall&rdquo; is
looking at a list that says &ldquo;amphetamine&rdquo;. A letter that names only the brand asks the
officer to do the translation, and the officer is not obliged to do it in your favour.</p>
<p>Name the active ingredient in generic form, with the strength and the daily dose. That single
habit resolves most of what goes wrong at a border with legitimate medicine.</p>

<h2>The minimum the letter must state</h2>
<p>The UK Home Office is the most explicit about this, and its four requirements are a good floor
anywhere:</p>
<p>&bull; your name<br>
&bull; the dates you are travelling<br>
&bull; a list of your medicine, including how much you have, the doses and the strength<br>
&bull; the signature of the person who prescribed it</p>

<h2>What to add beyond the floor</h2>
<p>&bull; the generic (INN) name of each active ingredient, alongside the brand<br>
&bull; your date of birth and passport number, so the letter ties to the document you present<br>
&bull; the condition being treated, in one line<br>
&bull; the prescriber's licence or registration number, facility name and a contact number<br>
&bull; the total quantity carried and the number of days of treatment it covers &mdash; stating the
arithmetic yourself stops the officer from doing it</p>
<p>Written on the prescriber's letterhead, dated, signed. An unsigned printout is a draft.</p>

<h2>Template</h2>
<p>Hand this to your doctor rather than asking them to compose one. Replace everything in square
brackets.</p>
<pre style="background:#111620;border:1px solid #27323f;border-radius:10px;padding:16px;
overflow-x:auto;font-size:13px;line-height:1.6;color:#c9d4e0;white-space:pre-wrap">[PRESCRIBER LETTERHEAD]

[Date]

TO WHOM IT MAY CONCERN &mdash; TRAVELLER CARRYING PRESCRIBED MEDICATION

Patient:        [Full name as printed in passport]
Date of birth:  [YYYY-MM-DD]
Passport no.:   [Number]
Travelling to:  [Country]   Dates: [YYYY-MM-DD] to [YYYY-MM-DD]

The above patient is under my care for [condition, one line]. The
medication listed below is prescribed for this patient's own
treatment and the quantity carried corresponds to the duration of
travel stated above.

  1. Brand name:        [Brand]
     Active ingredient: [Generic / INN name]
     Strength:          [e.g. 10 mg per tablet]
     Dose:              [e.g. 1 tablet twice daily]
     Quantity carried:  [e.g. 60 tablets = 30 days]

  2. [repeat per medicine]

This patient requires this medication for the duration of travel.
I can be contacted at the number below for verification.

[Prescriber name]
[Qualification]
[Licence / registration number]
[Facility name and address]
[Telephone]   [Email]

[Signature]</pre>

<h2>What the letter does not replace</h2>
<p>A letter is not an import permit. Where a country requires prior approval, the letter is an
attachment to that application, not an alternative to it &mdash;
<a href="/can-i-bring/permit-japan">Japan</a>,
<a href="/can-i-bring/permit-singapore">Singapore</a> and
<a href="/can-i-bring/permit-united-arab-emirates">the UAE</a> each run their own process. And no
letter makes a prohibited substance importable; for those the useful conversation is with your
prescriber about an alternative that is legal where you are going.</p>

<h2>Keep the original packaging</h2>
<p>Singapore states the requirement plainly &mdash; each medicine in its original container,
labelled with {{sg_label}} &mdash; and it is good practice everywhere. Decanting a trip's worth of
tablets into an unlabelled organiser destroys the link between the medicine and the prescription.
Carry the box as well as the organiser.</p>

<h2>Three months is the recurring ceiling</h2>
<p>The quantity limits are set independently by each country, but three of the strictest converge
near the same figure: the UK allows up to three months' supply, Singapore {{sg_qty}}, and the UAE
{{uae_qty}}. It is not a universal rule and it is not a defence anywhere, but if you are packing
more than three months of a controlled medicine you are outside what the strict jurisdictions
contemplate, and that is worth knowing before you pack rather than after.</p>
""")

KIT_KO["승인-일본"] = (
 "일본 수입확인증(輸入確認証) 받는 방법",
 "일본에 약을 가져갈 때 필요한 수입확인증 — 언제 필요하고, 언제 아예 발급되지 않으며, "
 "어디에 어떻게 신청하고 얼마나 걸리는지.",
 """
<h2>수입확인증이 무엇인가</h2>
<p>수입확인증(輸入確認証, 야칸쇼메이)은 지참한 약이 본인 치료용이고 판매용이 아니라는 것을
일본 후생노동성이 확인해 주는 서류입니다. <b>금지 성분을 들여올 수 있게 해 주는 허가가
아닙니다.</b> 수량이 개인용 범위라는 확인일 뿐입니다.</p>

<h2>언제 필요한가</h2>
<p>아래 수량을 넘지 않으면 보통 공항 세관 확인으로 끝납니다. 넘으면 수입확인증이 필요합니다.</p>
<p>&bull; 처방약 {{qty_rx}}을 넘는 경우<br>
&bull; 비처방약 {{qty_other}}을 넘는 경우<br>
&bull; 외용제 {{jp_ext}}을 넘는 경우</p>

<h2>아예 발급되지 않는 경우</h2>
<p>여기서 사람이 잡힙니다. 일본이 전면 금지하는 성분에는 수입확인증이 발급되지 않습니다.
그리고 그 금지 목록에는 다른 나라에서는 평범한 처방약이거나 심지어 약국에서 그냥 사는 약이
들어 있습니다. 각성제와 각성제원료가 대표적입니다 — 암페타민계 ADHD 약과 슈도에페드린
감기약이 둘 다 여기 해당하고, 신청서·소견서·신고 그 무엇으로도 열리지 않습니다. 각성제
위반 처벌은 {{stim_pen}}입니다.</p>
<p>내 약이 이 그룹이면 수입확인증은 "느린 우회로"가 아니라 닫힌 문입니다. 해당 페이지를
보세요: <a href="/ko/애더럴-일본">애더럴</a> &middot;
<a href="/ko/감기약-슈도에페드린-일본">감기약·슈도에페드린</a> &middot;
<a href="/ko/CBD-일본">CBD</a>.<br>
마약·향정신성 쪽은 <a href="/ko/코데인-일본">코데인</a> &middot;
<a href="/ko/트라마돌-일본">트라마돌</a> &middot;
<a href="/ko/졸피뎀-일본">졸피뎀</a>.</p>

<h2>마약·향정신성은 별도 절차다</h2>
<p>치료용으로 마약이나 향정신성의약품을 직접 지참하는 경우는 — 일반 약을 수량 초과로
가져가는 것과 다릅니다 — 지방후생국 마약단속부의 휴대 수입 허가를 받습니다. 일반
수입확인증과 창구가 다릅니다. 내 약이 어느 쪽인지 먼저 확인하세요.</p>

<h2>신청 방법</h2>
<p>후생노동성 온라인 시스템
<a href="https://impconf.mhlw.go.jp/aicpte/page/login.jsp?lang=en" rel="noopener" target="_blank">{{jp_portal}}</a>
에서 신청합니다. 문의는 {{jp_mail}}. 신청 시점은 {{jp_lead}} — 3주 뒤 출발하는 일정이면
수입확인증이 필요한 약은 이미 늦었습니다.</p>
<p>신청서는 제품이 무엇이고 무엇이 들었고 얼마나 가져가고 언제 여행하는지를 묻습니다.
처방전이나 영문 소견서를 첨부할 수 있게 준비하고, <b>성분명을 일반명(제네릭)으로</b>
적으세요. 서류를 읽는 담당자는 상품명이 아니라 성분으로 판단합니다.
<a href="/ko/소견서">소견서 양식</a>에 필요한 항목을 정리해 두었습니다.</p>

<h2>공항에서</h2>
<p>확인증은 몸에 들고 입국합니다. 수탁 수하물에 넣지 말고, 공항 와이파이로 열어 보겠다는
생각으로 메일에만 두지 마세요. 안내문 표현이 단호합니다 — 필요한 경우 반드시 소지해야 합니다.</p>
""")

KIT_KO["승인-싱가포르"] = (
 "싱가포르 HSA 의약품 반입 승인받는 방법",
 "싱가포르 보건과학청 사전 승인 — 누가 받아야 하고, 신청 양식은 어디 있고, "
 "2주 전 제출과 3개월분 수량 제한.",
 """
<h2>누가 승인을 받아야 하나</h2>
<p>싱가포르 보건과학청(HSA)은 통제물질이 든 의약품에 사전 승인을 요구합니다. 기준 목록은
HSA 개인 의약품 반입 안내서의 부록 A이고, 이는 오용약물규정 제2·3표와 2016년
건강제품(치료제)규정 제1표에서 가져온 것입니다. <b>상품명이 아니라 성분으로</b> 대조하세요.</p>

<h2>승인이 필요 없는 경우</h2>
<p>통제물질도 금지물질도 아닌 약은 {{sg_qty}}까지 가져갈 수 있습니다. 이 상한은 여행 기간이
아니라 지참 수량에 걸립니다.</p>

<h2>신청 방법</h2>
<p>신청 양식은 <a href="https://go.gov.sg/hsa-ptm" rel="noopener" target="_blank">{{sg_portal}}</a>
에 있습니다. {{sg_lead}}에 제출하라고 HSA가 명시합니다. 심사 시간을 두라는 뜻입니다.
출국 게이트에서 넣는 신청은 신청이 아닙니다.</p>

<h2>승인과 무관하게 챙길 것</h2>
<p>&bull; 거주국에서 발급한 유효한 처방전 사본 또는 의사 소견서<br>
&bull; 약은 원래 용기·포장 그대로, {{sg_label}}이 붙은 상태</p>
<p>여행자가 모르고 어기는 쪽은 라벨 요건입니다. 한 달치 알약을 라벨 없는 요일별 약통에
옮겨 담으면, 그 약이 내 것이고 내게 조제되었다는 유일한 증거가 사라집니다. 약통을 쓰더라도
원래 상자를 같이 가져가세요. <a href="/ko/소견서">소견서 양식</a>에 요구 항목을
정리했습니다.</p>

<h2>어려운 경우</h2>
<p>승인은 통제 의약품을 위한 절차이고, 금지 의약품의 우회로가 아닙니다. 대마 유래 성분이
가장 분명한 예입니다 — 싱가포르 금지는 THC 함량과 무관하게 적용되어 승인 자체가 없습니다.
개별 페이지가 더 구체적입니다:
<a href="/ko/애더럴-싱가포르">애더럴</a> &middot;
<a href="/ko/콘서타-싱가포르">콘서타</a> &middot;
<a href="/ko/졸피뎀-싱가포르">졸피뎀</a> &middot;
<a href="/ko/CBD-싱가포르">CBD</a>.</p>
""")

KIT_KO["승인-UAE"] = (
 "UAE 의약품 반입 승인받는 방법",
 "UAE 통제·준통제 의약품 목록, 사전 승인 요건, 처방전 발급 시점 요건과 허용 수량.",
 """
<h2>분류가 둘이 아니라 셋이다</h2>
<p>UAE는 의약품을 통제·준통제·비통제로 나눕니다. 에미리트 의약품청(EDE)이 공표한
통제·준통제 목록에 {{uae_count}} 물질이 올라 있고, 판본 날짜는 {{uae_listd}}입니다.
오피오이드 진통제·벤조디아제핀·수면제·ADHD 각성제가 이 분류들에 흩어져 있어서, 집에서
평범한 약이라는 사실은 여기서 어느 칸에 떨어지는지에 대해 아무것도 알려주지 않습니다.</p>

<h2>사전 승인</h2>
<p>통제·준통제 의약품은 <b>출국 전에</b> 보건당국 승인을 받아야 합니다. 공항에 발급 창구가
없습니다. 본인은 당연히 개인용이라고 생각한 수량 때문에 구금된 사례가 보고되어 있고, 이
절차는 바로 그 위험을 없애기 위해 있습니다.</p>

<h2>처방전에도 유효기간이 있다</h2>
<p>처방전은 {{uae_rxage}} 조건을 만족해야 합니다. 작년에 받은 반복 처방이나 약 라벨 사진은
해당하지 않습니다. 약이 그대로라도 출국 전에 새로 받으세요.</p>

<h2>허용 수량</h2>
<p>{{uae_qty}}입니다. 내 일정으로 직접 계산해서 그 수량만 가져가세요. 어림수로 넉넉히
담은 초과분은 담당자 눈에 한 번에 보이는 바로 그것입니다.</p>

<h2>몸에 지닐 것</h2>
<p>승인서, 직인이 있는 최근 처방전, 원래 라벨이 붙은 포장. 성분을 일반명으로 적은 소견서가
내 상자의 상품명과 UAE 목록의 물질명 사이 간극을 메웁니다 —
<a href="/ko/소견서">양식</a>에 정리해 두었습니다.</p>
<p>개별 약: <a href="/ko/코데인-UAE">코데인</a> &middot;
<a href="/ko/자낙스-UAE">자낙스</a>.</p>
""")

KIT_KO["소견서"] = (
 "약 가지고 출국할 때 쓰는 영문 소견서 — 무엇을 적어야 하나",
 "세관 담당자는 상품명이 아니라 성분으로 판단합니다. 소견서에 반드시 들어가야 하는 항목과 "
 "의사에게 그대로 건넬 수 있는 영문 양식.",
 """
<h2>상품명이 문제인 이유</h2>
<p>통제 목록은 일반명으로 쓰여 있습니다. UN 마약·향정신성 목록, UAE 통제물질 목록, 일본
각성제 분류, 싱가포르 오용약물규정 모두 제품이 아니라 성분을 적습니다.
"Adderall"이라고 쓰인 소견서를 든 담당자는 "amphetamine"이라고 쓰인 목록을 보고 있습니다.
상품명만 적은 소견서는 그 번역을 담당자에게 맡기는 것이고, 담당자가 내게 유리한 쪽으로
해 줄 의무는 없습니다.</p>
<p>성분을 일반명으로, 함량과 1일 용량까지 적으세요. 정당한 약이 국경에서 꼬이는 일의
대부분이 이 습관 하나로 정리됩니다.</p>

<h2>최소한 들어가야 하는 것</h2>
<p>영국 내무부가 이 부분을 가장 명확하게 규정하고 있고, 그 네 항목은 어디서든 통하는
하한선입니다.</p>
<p>&bull; 본인 이름<br>
&bull; 여행 날짜<br>
&bull; 약 목록 — 수량·용량·함량 포함<br>
&bull; 처방한 사람의 서명</p>

<h2>하한선 위에 더할 것</h2>
<p>&bull; 성분별 일반명(INN) — 상품명과 나란히<br>
&bull; 생년월일과 여권번호 — 제시하는 신분증과 소견서가 서로 연결되도록<br>
&bull; 치료 중인 질환, 한 줄<br>
&bull; 처방자의 면허·등록번호, 의료기관명, 연락 가능한 전화번호<br>
&bull; 지참 총수량과 그것이 며칠분인지 — 계산을 내가 적어두면 담당자가 계산하지 않습니다</p>
<p>의료기관 레터헤드에, 날짜를 적고, 서명까지. 서명 없는 출력물은 초안입니다.</p>

<h2>양식</h2>
<p>의사에게 "써 주세요"라고 부탁하지 말고 이것을 그대로 건네세요. 대괄호만 채우면 됩니다.</p>
<pre style="background:#111620;border:1px solid #27323f;border-radius:10px;padding:16px;
overflow-x:auto;font-size:13px;line-height:1.6;color:#c9d4e0;white-space:pre-wrap">[PRESCRIBER LETTERHEAD]

[Date]

TO WHOM IT MAY CONCERN &mdash; TRAVELLER CARRYING PRESCRIBED MEDICATION

Patient:        [여권 영문 이름]
Date of birth:  [YYYY-MM-DD]
Passport no.:   [여권번호]
Travelling to:  [국가]   Dates: [YYYY-MM-DD] to [YYYY-MM-DD]

The above patient is under my care for [질환, 한 줄]. The
medication listed below is prescribed for this patient's own
treatment and the quantity carried corresponds to the duration of
travel stated above.

  1. Brand name:        [상품명]
     Active ingredient: [성분 일반명 / INN]
     Strength:          [예: 10 mg per tablet]
     Dose:              [예: 1 tablet twice daily]
     Quantity carried:  [예: 60 tablets = 30 days]

  2. [약마다 반복]

This patient requires this medication for the duration of travel.
I can be contacted at the number below for verification.

[의사 이름]
[전문 과목]
[면허 / 등록번호]
[의료기관명 및 주소]
[전화]   [이메일]

[서명]</pre>

<h2>소견서가 대신하지 못하는 것</h2>
<p>소견서는 수입 허가가 아닙니다. 사전 승인을 요구하는 나라에서 소견서는 그 신청서에
<b>첨부하는 서류</b>이고, 신청 대신 쓰는 서류가 아닙니다 —
<a href="/ko/승인-일본">일본</a>,
<a href="/ko/승인-싱가포르">싱가포르</a>,
<a href="/ko/승인-UAE">UAE</a>가 각자 다른 절차를 돌립니다. 그리고 어떤 소견서도 금지
성분을 반입 가능하게 만들지 못합니다. 그 경우 정말 도움이 되는 상대는 세관이 아니라,
목적지에서 합법인 대체약을 아는 처방 의사입니다.</p>

<h2>원래 포장을 버리지 마라</h2>
<p>싱가포르는 요건을 명문으로 적어 두었습니다 — 약은 원래 용기에, {{sg_label}}이 붙은
상태로. 어디서든 좋은 습관입니다. 여행 분량을 라벨 없는 약통에 옮겨 담으면 약과 처방을
잇는 연결이 끊어집니다. 약통과 함께 상자도 가져가세요.</p>

<h2>3개월이 반복해서 나오는 상한이다</h2>
<p>수량 제한은 나라마다 따로 정하지만, 엄격한 쪽 세 곳이 비슷한 숫자로 모입니다. 영국은
3개월분까지, 싱가포르는 {{sg_qty}}, UAE는 {{uae_qty}}입니다. 보편 규칙이 아니고 어디서도
면책 사유가 아니지만, 통제 의약품을 3개월분 넘게 담고 있다면 엄격한 관할들이 상정하는
범위 밖이라는 뜻입니다. 짐을 싼 뒤가 아니라 싸기 전에 알아야 하는 사실입니다.</p>
""")
# ── 판정 → 행동. 레벨마다 다른 말을 한다.
_KITCC = {"JP": ("permit-japan", "승인-일본"),
          "SG": ("permit-singapore", "승인-싱가포르"),
          "AE": ("permit-united-arab-emirates", "승인-UAE")}

_BOX = ('<div style="border-radius:14px;padding:18px 20px;background:#111620;'
        'border:1px solid %s;margin:24px 0"><div style="font-weight:700;color:%s;'
        'margin-bottom:6px">%s</div>%s</div>')


def _bridge(lvl, cc, lang):
    """★PROHIBITED 와 PERMIT 은 절대 같은 말을 하지 않는다.
       금지 성분에 "허가받으면 된다"고 하면 사람이 공항에서 잡힌다."""
    kit = _KITCC.get(cc)
    ks = (kit[0] if lang == "en" else kit[1]) if kit else None
    kurl = ("/can-i-bring/%s" % ks) if (ks and lang == "en") else (("/ko/%s" % ks) if ks else None)
    lurl = "/can-i-bring/doctors-letter" if lang == "en" else "/ko/소견서"

    if lvl == "PERMIT" and kurl:
        if lang == "en":
            return _BOX % ("#6b5a2a", "#f0b04c", "Approval has to be in hand before you board",
                           '<p style="margin:0">There is no counter at the airport that issues it. '
                           '<a href="%s">The application process, the lead time and what to attach</a> '
                           '&mdash; and a <a href="%s">letter template</a> for your prescriber.</p>'
                           % (kurl, lurl))
        return _BOX % ("#6b5a2a", "#f0b04c", "승인은 출국 전에 손에 들고 있어야 한다",
                       '<p style="margin:0">공항에 발급 창구가 없습니다. '
                       '<a href="%s">신청 절차·소요 기간·첨부 서류</a>와 '
                       '<a href="%s">의사에게 건넬 영문 소견서 양식</a>.</p>' % (kurl, lurl))

    if lvl == "PERMIT":
        # ★허가 절차를 우리가 확인하지 않은 나라다. 없는 절차를 지어내지 않는다.
        if lang == "en":
            return _BOX % ("#6b5a2a", "#f0b04c", "Clear it before you fly, not at the border",
                           '<p style="margin:0">This one needs authorisation, a local prescription, '
                           'or both &mdash; which of those depends on the country, so ask the '
                           'authority named in the sources below before you book. Carry the original '
                           'labelled packaging, the prescription, and a prescriber&rsquo;s letter '
                           'naming the generic ingredient. '
                           '<a href="%s">Letter template</a>.</p>' % lurl)
        return _BOX % ("#6b5a2a", "#f0b04c", "국경이 아니라 출국 전에 정리할 일이다",
                       '<p style="margin:0">허가가 필요한지, 현지 처방이 필요한지, 둘 다인지는 '
                       '나라마다 다릅니다. 예약 전에 아래 출처의 담당 기관에 확인하세요. 원래 '
                       '라벨이 붙은 포장, 처방전, 성분 일반명을 적은 소견서를 함께 가져갑니다. '
                       '<a href="%s">소견서 양식</a>.</p>' % lurl)

    if lvl == "PROHIBITED":
        if lang == "en":
            extra = (' A permit does not exist for this one &mdash; '
                     '<a href="%s">why no certificate is issued</a>.' % kurl) if kurl else ""
            return _BOX % ("#6e3a35", "#ff5c50", "Paperwork will not fix this one",
                           '<p style="margin:0">Applying for approval is not a slower route to the '
                           'same destination.%s What does help: a prescriber&rsquo;s letter naming '
                           'your condition and the generic ingredient, and a conversation with that '
                           'prescriber about what is legal where you are going. '
                           '<a href="%s">Letter template</a>.</p>' % (extra, lurl))
        extra = (' 이 성분에는 허가가 존재하지 않습니다 — '
                 '<a href="%s">왜 발급되지 않는가</a>.' % kurl) if kurl else ""
        return _BOX % ("#6e3a35", "#ff5c50", "서류로 해결되는 문제가 아니다",
                       '<p style="margin:0">승인 신청은 같은 목적지로 가는 느린 길이 아닙니다.%s '
                       '도움이 되는 것은 질환과 성분 일반명을 적은 의사 소견서, 그리고 '
                       '목적지에서 합법인 대체약에 대해 그 의사와 나누는 상담입니다. '
                       '<a href="%s">소견서 양식</a>.</p>' % (extra, lurl))

    # DECLARE · LIMIT · OK — 들고 타는 사람들. 포장과 서류에서 걸린다.
    # ★허가가 필요 없는 경우에도 그 나라의 절차 페이지는 읽을 값이 있다.
    #   "허가 불필요"라는 사실 자체가 거기 적혀 있기 때문이다(태국 향정 2~4종).
    if lang == "en":
        more = (' <a href="%s">And the destination&rsquo;s own procedure</a>.' % kurl) if kurl else ""
        return _BOX % ("#27323f", "#8b98a8", "If you are carrying it, carry the paperwork too",
                       '<p style="margin:0">Original labelled packaging, the prescription, and a '
                       'letter naming the active ingredient in generic form &mdash; control lists '
                       'are written in generic names, not brands. '
                       '<a href="%s">What the letter must say</a>.%s</p>' % (lurl, more))
    more = (' <a href="%s">그리고 이 나라의 절차</a>.' % kurl) if kurl else ""
    return _BOX % ("#27323f", "#8b98a8", "들고 탈 거라면 서류도 같이",
                   '<p style="margin:0">원래 라벨이 붙은 포장, 처방전, 그리고 성분을 '
                   '일반명으로 적은 소견서. 통제 목록은 상품명이 아니라 일반명으로 쓰여 '
                   '있습니다. <a href="%s">소견서에 무엇을 적어야 하나</a>.%s</p>' % (lurl, more))


def cb_kit(s, lang):
    """승인 절차 허브 페이지를 그린다. 본문은 _fill 을 거쳐 출처가 정본으로 붙는다."""
    tbl = KIT_EN if lang == "en" else KIT_KO
    if s not in tbl:
        return None
    title, desc, tpl = tbl[s]
    e = _h.escape
    if lang == "en":
        can, alt, lede = ("%s/can-i-bring/%s" % (BASE, s), _alt(KIT_ALT.get(s), s),
                          "Primary sources only. Where the official page disagrees with this one, it is right.")
        back = '<p style="margin-top:30px"><a href="/can-i-bring">&larr; All medicines and countries</a></p>'
        warn = ('<div class="warn"><b>Not legal or medical advice.</b> Procedures and quantities '
                'change, and an authority can decide differently on your particular case. Confirm '
                'with the authority named above before you rely on any of this.</div>')
        lng = "en"
    else:
        _en = next((k for k, v in KIT_ALT.items() if v == s), None)
        can, alt, lede = ("%s/ko/%s" % (BASE, _q(s)), _alt(s, _en),
                          "1차 출처만 씁니다. 공식 안내와 이 페이지가 다르면 공식 안내가 맞습니다.")
        back = '<p style="margin-top:30px"><a href="/ko">&larr; 약·국가 전체 보기</a></p>'
        warn = ('<div class="warn"><b>이 페이지는 법률·의학 조언이 아닙니다.</b> 절차와 수량은 '
                '바뀌고, 당국은 개별 사안을 다르게 판단할 수 있습니다. 여기에 의존하기 전에 '
                '위에 적힌 당국에 직접 확인하세요.</div>')
        lng = "ko"
    body = _fill(s, tpl, lang)
    html = ('<!doctype html><html lang="%s"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title><meta name="description" content="%s">'
            '<link rel="canonical" href="%s">%s'
            '<meta property="og:title" content="%s"><meta property="og:description" content="%s">'
            '<style>%s</style></head><body><div class="w"><h1>%s</h1>'
            '<p class="lede">%s</p>%s%s%s</div></body></html>'
            % (lng, e(title), e(desc), can, alt, e(title), e(desc), CSS,
               title, e(lede), body, back, warn))
    return Response(html, mimetype="text/html; charset=utf-8")


# ── 배포 시점 검증. 사실 키를 틀리면 임포트에서 죽는다.
for _s, _v in list(KIT_EN.items()):
    _fill(_s, _v[2], "en")
    assert _SRCFOR.get(_s), "출처 미등록: %s" % _s
for _s, _v in list(KIT_KO.items()):
    _fill(_s, _v[2], "ko")
    assert _SRCFOR.get(_s), "출처 미등록: %s" % _s
assert set(KIT_ALT) == set(KIT_EN) and set(KIT_ALT.values()) == set(KIT_KO), "EN/KO 짝이 안 맞는다"
# ══ 태국 — 창구가 둘로 갈린다. 거기서 사람들이 틀린다 ══
_FACT.update({
    "th_qty":    {"en": "30 days of prescribed usage", "ko": "처방된 용법으로 30일분"},
    "th_lead":   {"en": "around two weeks before you travel, and not more than one month ahead",
                  "ko": "출국 2주 전쯤 — 1개월보다 더 일찍은 안 된다"},
    "th_mail":   {"en": "tnarcotics@fda.moph.go.th", "ko": "tnarcotics@fda.moph.go.th"},
    "th_tel":    {"en": "+66 2590 7346", "ko": "+66 2590 7346"},
    "th_portal": {"en": "permitfortraveler.fda.moph.go.th", "ko": "permitfortraveler.fda.moph.go.th"},
    "th_banned": {"en": "prohibited, and determined to have no medical use in Thailand",
                  "ko": "금지 — 태국에서 의학적 용도가 없다고 판정된 것들"},
    "th_disc":   {"en": "The Thai FDA guidance puts the ceiling at 30 days for both routes. "
                        "A Royal Thai Embassy page states 90 days for narcotics and 30 for "
                        "psychotropics. We use the stricter figure and we are telling you the two "
                        "official pages disagree, because you are the one standing at the counter",
                  "ko": "태국 FDA 지침은 두 경로 모두 30일분으로 적고, 주스웨덴 태국대사관 "
                        "페이지는 마약 90일분·향정신성 30일분으로 적는다. 우리는 더 엄격한 쪽을 "
                        "쓰고, 공식 출처 둘이 어긋난다는 사실을 그대로 알린다. 창구에 서는 건 "
                        "당신이기 때문이다"},
})

_SRCSET.update({
 "th_permit": [
  ("https://permitfortraveler.fda.moph.go.th/permit_new/home/Main",
   {"en": "Thai FDA Narcotics Control Division &mdash; permit portal for travellers, with the drug-category lookup",
    "ko": "태국 FDA 마약단속부 — 여행자 허가 포털 및 약물 분류 조회"}),
  ("https://image.mfa.go.th/mfa/0/kjBTSaxCcf/Consular/Custom/medication.pdf",
   {"en": "Thai FDA &mdash; guidance for travellers under treatment carrying personal medications (PDF)",
    "ko": "태국 FDA — 치료 중 여행자의 개인 의약품 지참 지침 (PDF)"}),
  ("https://image.mfa.go.th/mfa/0/SRBviAC5gs/Medications/One-page-THAI-FDA.pdf",
   {"en": "Thai FDA &mdash; one-page traveller procedure, four steps (PDF)",
    "ko": "태국 FDA — 여행자 절차 1페이지 요약, 4단계 (PDF)"}),
  ("https://en.fda.moph.go.th/entrepreneurs-narcotic-drugs-and-psychotropic-substances/psychotropic-substances-01",
   {"en": "Thai FDA &mdash; the four psychotropic categories and what is in each",
    "ko": "태국 FDA — 향정신성 4개 분류와 각 분류의 수록 물질"}),
  ("https://thaiembassy.se/en/tourism/restricted-medicine/",
   {"en": "Royal Thai Embassy &mdash; restricted medicine, traveller summary",
    "ko": "주스웨덴 태국대사관 — 제한 의약품 여행자 안내"}),
 ],
})

_SRCFOR.update({"permit-thailand": "th_permit", "승인-태국": "th_permit"})
KIT_ALT["permit-thailand"] = "승인-태국"
_KITCC["TH"] = ("permit-thailand", "승인-태국")

KIT_EN["permit-thailand"] = (
 "Bringing medicine into Thailand &mdash; which route applies to you",
 "Thailand runs two separate routes under two separate acts. One needs a permit before you "
 "fly; the other needs only a prescription. Most travellers guess wrong about which one they are on.",
 """
<h2>Two acts, two routes, and most people pick the wrong one</h2>
<p>Thailand does not have a single medication rule. It has two, written under two different laws,
and which one applies to you depends on how your medicine is scheduled &mdash; not on how serious
it feels. Getting this wrong in either direction costs you: one way you skip a permit you needed,
the other way you spend three weeks applying for a permit that does not exist for your drug.</p>

<h2>Route A &mdash; narcotic drugs of Category 2: permit required</h2>
<p>Under the Narcotics Act B.E. 2522, a traveller carrying a Category 2 narcotic must hold a
permit issued by the Thai FDA <i>before</i> travelling. Category 2 is where the opioids sit:
codeine, dihydrocodeine, dextropropoxyphene, fentanyl, hydrocodone, hydromorphone, methadone,
morphine, oxycodone and pethidine are the examples the FDA itself gives.</p>
<p>&bull; Apply {{th_lead}}. Both ends of that window matter &mdash; too early is also refused.<br>
&bull; Form IC-1 is the application to carry in; OC-1 is to carry out.<br>
&bull; Limit: {{th_qty}}.<br>
&bull; On arrival you must present the medicine, the documents and the permit at the Customs
Department <b>Red Channel</b>. Not the green one. Walking through the nothing-to-declare lane with
a Category 2 narcotic is the mistake that turns paperwork into an incident.</p>

<h2>Route B &mdash; psychotropic substances of Categories 2, 3 and 4: no permit</h2>
<p>Under the Psychotropic Substances Act B.E. 2518, these need <b>no permit at all</b>. A
certificate or prescription from the prescribing physician is enough, up to {{th_qty}}. The FDA
goes further: carried that way, they are <i>considered personal belongings</i>, and you do not
have to declare them at the Red Channel.</p>
<p>This is the half nobody gets right. The substances here include zolpidem, methylphenidate,
midazolam, nitrazepam, phentermine, temazepam, triazolam, buprenorphine and ketamine (Category 2);
pentazocine and the barbiturates pentobarbital and amobarbital (Category 3); and alprazolam,
bromazepam, chlordiazepoxide, clonazepam, clorazepate, diazepam, lorazepam, oxazepam and
phenobarbital (Category 4). <b>Pseudoephedrine is in Category 2</b> &mdash; which means the cold
medicine everyone assumes is banned is in fact allowed with a prescription, and the real problem is
that almost nobody has a prescription for a cold medicine they bought off a shelf.</p>

<h2>What is not a route</h2>
<p>Narcotics of Category 1 and psychotropics of Category 1 are {{th_banned}}. The FDA's own examples
are amphetamine, dexamphetamine, cathinone and THC. No permit is issued, no letter helps, and no
amount of lead time changes it. If your medicine is here, the only useful conversation is with your
prescriber about an alternative &mdash; which is the FDA's own advice too.</p>
<p>The specific pages: <a href="/can-i-bring/adderall-to-thailand">Adderall and amphetamine</a>
&middot; <a href="/can-i-bring/sudafed-to-thailand">Sudafed and pseudoephedrine</a>.</p>

<h2>The quantity figure, and why we are showing you the disagreement</h2>
<p>{{th_disc}}.</p>

<h2>The document people do not know about</h2>
<p>For the Route A permit, the Thai FDA asks for three things: the application form, a medical
prescription, and &mdash; this is the one &mdash; a <b>certificate issued by a competent authority
of the country of departure</b> confirming that you are legally authorised to carry the medication
for personal use. That is a government document, not a note from your doctor, and the FDA publishes
a model form for it. Start on that first; it is the step with the longest tail.</p>

<h2>What the prescription itself must state</h2>
<p>Both routes require the same content in the prescription or physician's certificate:</p>
<p>&bull; your name and address<br>
&bull; the identified medical condition<br>
&bull; the name of each medication and why it was prescribed<br>
&bull; the posology and the total amount prescribed<br>
&bull; the prescribing physician's name, address and licence number</p>
<p>Our <a href="/can-i-bring/doctors-letter">letter template</a> carries these fields. Keep the
prescription or certificate with you for the whole stay, not just at the airport.</p>

<h2>Three small rules that catch people</h2>
<p>&bull; Keep the medicine in its original prescription container with the contents clearly
marked.<br>
&bull; You may not sell or supply your medication to anyone else in Thailand.<br>
&bull; Check the category before each trip rather than relying on last time &mdash; the FDA's
lookup tool at {{th_portal}} exists for exactly this.</p>

<h2>Where to ask, and a warning about the links</h2>
<p>Questions go to {{th_mail}} or {{th_tel}}. One caution on sources: the FDA reorganised this part
of its website, and the form-download link printed inside its own guidance document now returns a
404. Start from the portal rather than from any direct form link you find, including an older one
of ours if we ever let one rot.</p>
""")

KIT_KO["승인-태국"] = (
 "태국에 약 가져가기 — 내 약은 어느 창구인가",
 "태국은 법이 둘이고 창구가 둘이다. 한쪽은 출국 전 허가가 필요하고 다른 쪽은 처방전만 "
 "있으면 된다. 대부분의 여행자가 자기가 어느 쪽인지 틀리게 안다.",
 """
<h2>법이 둘, 창구가 둘, 그리고 사람들은 틀린 쪽을 고른다</h2>
<p>태국에는 의약품 규정이 하나가 아닙니다. 서로 다른 두 법 아래 두 개가 있고, 어느 쪽이
적용되는지는 내 약이 어떻게 분류돼 있느냐로 갈립니다 — 약이 얼마나 센 느낌인지와는 상관이
없습니다. 어느 방향으로 틀려도 대가가 있습니다. 한쪽으로 틀리면 필요한 허가를 빼먹고,
반대로 틀리면 내 약에는 존재하지도 않는 허가를 3주 동안 신청하고 있습니다.</p>

<h2>A 경로 — 마약 2종: 사전 허가 필수</h2>
<p>마약법(B.E. 2522)상 마약 2종을 지참하는 여행자는 <b>출국 전에</b> 태국 FDA가 발급한 허가를
손에 들고 있어야 합니다. 2종에는 오피오이드가 모여 있습니다 — FDA가 직접 든 예가 코데인,
디하이드로코데인, 덱스트로프로폭시펜, 펜타닐, 하이드로코돈, 하이드로모르폰, 메타돈, 모르핀,
옥시코돈, 페티딘입니다.</p>
<p>&bull; 신청 시점은 {{th_lead}}. 양쪽 끝이 다 중요합니다 — 너무 일찍도 반려됩니다.<br>
&bull; 반입 신청은 Form IC-1, 반출은 OC-1.<br>
&bull; 수량 한도: {{th_qty}}.<br>
&bull; 입국 시 약·서류·허가서를 세관 <b>레드채널</b>에 제시해야 합니다. 그린채널이 아닙니다.
마약 2종을 들고 신고 없음 통로로 걸어 들어가는 것이, 서류 문제를 사건으로 바꾸는 바로 그
실수입니다.</p>

<h2>B 경로 — 향정신성 2·3·4종: 허가 불필요</h2>
<p>향정신성의약품법(B.E. 2518)상 이쪽은 <b>허가가 아예 필요 없습니다.</b> 처방 의사의
소견서나 처방전만 있으면 {{th_qty}}까지 됩니다. FDA 문서는 한 걸음 더 나갑니다 — 그렇게
지참하면 <i>개인 소지품으로 본다</i>고, 레드채널 신고 의무도 없다고 적습니다.</p>
<p>아무도 제대로 모르는 쪽이 이 절반입니다. 여기 들어가는 성분은 졸피뎀, 메틸페니데이트,
미다졸람, 니트라제팜, 펜터민, 테마제팜, 트리아졸람, 부프레노르핀, 케타민(2종) · 펜타조신과
바르비투르계 펜토바르비탈·아모바르비탈(3종) · 알프라졸람, 브로마제팜, 클로르디아제폭사이드,
클로나제팜, 클로라제페이트, 디아제팜, 로라제팜, 옥사제팜, 페노바르비탈(4종)입니다.
<b>슈도에페드린이 2종에 있습니다</b> — 모두가 금지라고 믿는 그 감기약이 실제로는 처방전만
있으면 허용이고, 진짜 문제는 선반에서 그냥 사 온 감기약에 처방전을 가진 사람이 거의 없다는
점입니다.</p>

<h2>경로가 아닌 것</h2>
<p>마약 1종과 향정신성 1종은 {{th_banned}}. FDA가 든 예가 암페타민, 덱스암페타민, 카티논,
THC입니다. 허가가 발급되지 않고, 소견서로도 안 되고, 아무리 일찍 신청해도 달라지지
않습니다. 내 약이 여기 있으면 쓸 만한 대화 상대는 하나뿐입니다 — 대체약을 아는 처방 의사.
그게 FDA 문서 자체의 권고이기도 합니다.</p>
<p>해당 페이지: <a href="/ko/애더럴-태국">애더럴·암페타민</a> &middot;
<a href="/ko/감기약-슈도에페드린-태국">감기약·슈도에페드린</a>.</p>

<h2>수량 숫자, 그리고 불일치를 왜 그대로 보여주는가</h2>
<p>{{th_disc}}.</p>

<h2>사람들이 모르는 서류 하나</h2>
<p>A 경로 허가에 태국 FDA가 요구하는 건 셋입니다. 신청서, 처방전, 그리고 — 이게 그 하나인데
— <b>출발국 관할 당국이 발급한 증명서</b>로, 본인이 그 약을 개인용으로 지참할 법적 권한이
있음을 확인하는 문서입니다. 의사 메모가 아니라 <b>정부 문서</b>이고, FDA가 양식 견본을
배포합니다. 여기부터 시작하세요. 가장 오래 끌리는 단계입니다.</p>

<h2>처방전에 들어가야 하는 내용</h2>
<p>두 경로 모두 처방전·소견서에 같은 내용을 요구합니다.</p>
<p>&bull; 본인 이름과 주소<br>
&bull; 확인된 질환<br>
&bull; 각 약의 이름과 처방 이유<br>
&bull; 용법·용량과 처방 총량<br>
&bull; 처방 의사의 이름·주소·면허번호</p>
<p><a href="/ko/소견서">소견서 양식</a>에 이 항목들이 들어 있습니다. 처방전이나 증명서는
공항에서만이 아니라 <b>체류 기간 전체</b> 동안 소지하세요.</p>

<h2>사람 잡는 작은 규정 셋</h2>
<p>&bull; 약은 원래 조제 용기에, 내용물이 명확히 표시된 상태로 둡니다.<br>
&bull; 태국에서 내 약을 다른 사람에게 판매·제공할 수 없습니다.<br>
&bull; 지난번을 믿지 말고 매 여행마다 분류를 다시 확인하세요 — {{th_portal}} 의 조회 도구가
정확히 이 용도로 있습니다.</p>

<h2>문의처, 그리고 링크에 대한 경고</h2>
<p>문의는 {{th_mail}} 또는 {{th_tel}}. 출처에 관한 주의 하나 — FDA가 이 부분 웹사이트를
개편해서, <b>자기 지침 문서 안에 인쇄된 양식 다운로드 링크가 지금 404</b>입니다. 어디서 찾은
양식 직링크든 믿지 말고 포털에서 시작하세요. 나중에 우리 링크가 썩으면 그것도
포함해서입니다.</p>
""")

# ── 태국 허브 배포 시점 검증 + 이 버그 종류를 구조적으로 죽인다.
#
# ★왜: _fill 의 치환 정규식은 [a-z_]+ 다. 숫자가 든 키({{th_cat1}})는
#   "없는 키"로 터지지도 않고 그냥 본문에 날것으로 찍혀 나간다. 기존
#   검증기는 못 잡는 구멍이었다. 아래 두 검사가 그걸 닫는다.
import re as _re_v

for _k in _FACT:
    assert _re_v.fullmatch(r"[a-z_]+", _k), \
        "사실 키에 _fill 이 못 받는 문자가 있다(숫자 금지): %s" % _k

for _s, _v in list(KIT_EN.items()):
    _o = _fill(_s, _v[2], "en")
    assert "{{" not in _o, "치환 안 된 자리표시자가 남았다: %s/en" % _s
    assert _SRCFOR.get(_s), "출처 미등록: %s" % _s
for _s, _v in list(KIT_KO.items()):
    _o = _fill(_s, _v[2], "ko")
    assert "{{" not in _o, "치환 안 된 자리표시자가 남았다: %s/ko" % _s
    assert _SRCFOR.get(_s), "출처 미등록: %s" % _s
for _s, _t in list(DEEP.items()):
    assert "{{" not in _fill(_s, _t, "en"), "치환 안 된 자리표시자: %s/en" % _s
for _s, _t in list(KO_DEEP.items()):
    assert "{{" not in _fill(_s, _t, "ko"), "치환 안 된 자리표시자: %s/ko" % _s
assert set(KIT_ALT) == set(KIT_EN) and set(KIT_ALT.values()) == set(KIT_KO), "EN/KO 짝이 안 맞는다"
assert "TH" in _KITCC and _KITCC["TH"][0] in KIT_EN, "태국 허브가 다리에 연결되지 않았다"
# ══ 태국 개별 페이지 심화. 허브는 절차, 여기는 성분별 판정 근거 ══
_SRCFOR.update({
    "adderall-to-thailand": "th_permit",
    "sudafed-to-thailand":  "th_permit",
    "애더럴-태국":              "th_permit",
    "감기약-슈도에페드린-태국":       "th_permit",
})

DEEP["adderall-to-thailand"] = """
<h2>What Thailand calls it</h2>
<p>Amphetamine and dexamphetamine are <b>Narcotic Category 1</b> under the Narcotics Act
B.E. 2522. The Thai FDA lists them by name as examples of what travellers are forbidden to
transport into or out of Thailand, and gives the reason in a single phrase: these substances are
{{th_banned}}.</p>
<p>That phrase is the whole page. &ldquo;No medical use&rdquo; is not a comment on your diagnosis
&mdash; it is the legal finding that closes the door, because Thailand's permit system exists only
for substances it accepts as medicine.</p>

<h2>Why no amount of paperwork opens it</h2>
<p>Thailand's traveller permit covers exactly two groups: narcotic Category 2, and psychotropic
Categories 2, 3 and 4. Category 1 is in neither. There is no application form for it, no lead
time that helps, and no doctor's letter that converts it. Travellers sometimes assume the
permit route is simply slower for stricter drugs; here it does not exist at all.
<a href="/can-i-bring/permit-thailand">The two routes, and which one your medicine is on</a>.</p>

<h2>The useful fact: methylphenidate is on the other side of the line</h2>
<p>Methylphenidate &mdash; Concerta, Ritalin &mdash; is <b>psychotropic Category 2</b> in Thailand,
which is the group that needs <i>no permit at all</i>: a certificate or prescription from the
prescribing physician, and up to {{th_qty}}. Same condition, same treatment goal, completely
different legal position at the border.</p>
<p>So an ADHD traveller to Thailand is not out of options. The option is a conversation with the
prescriber about a different molecule for the trip, held well before departure rather than at the
airport. Lisdexamfetamine (Vyvanse) is not a way around this &mdash; it is a prodrug that the body
converts to dexamfetamine, so treat it as sitting with the amphetamines and confirm it against the
FDA's own lookup at {{th_portal}} before you rely on anything here.</p>

<h2>What to do before you fly</h2>
<p>&bull; Leave it at home. Do not pack it in checked baggage &ldquo;to be safe&rdquo; &mdash;
there is no safe side of this one.<br>
&bull; Do not have it posted to you in Thailand. Mail is an import in its own right and gets the
same answer, without you there to explain.<br>
&bull; Carry a letter from your prescriber describing the condition and the treatment you are
<i>not</i> carrying. It explains a gap in your medication history to a doctor in Thailand if you
need care. <a href="/can-i-bring/doctors-letter">What that letter should say</a>.<br>
&bull; Ask the prescriber in the same appointment whether a Category 2&ndash;4 alternative or a
non-stimulant is reasonable for the length of your trip.</p>
<p>Questions about a specific product go to the Thai FDA Narcotics Control Division at
{{th_mail}} or {{th_tel}}. They answer about substances; they do not pre-clear a traveller
over email.</p>
"""

KO_DEEP["애더럴-태국"] = """
<h2>태국은 이걸 뭐라고 분류하나</h2>
<p>암페타민과 덱스암페타민은 마약법(B.E. 2522)상 <b>마약 1종</b>입니다. 태국 FDA는 여행자가
태국으로 반입·반출할 수 없는 물질의 예로 이 둘을 이름까지 적어 두고, 이유를 한 문장으로
답니다 — {{th_banned}}.</p>
<p>그 한 문장이 이 페이지의 전부입니다. "의학적 용도가 없다"는 건 내 진단에 대한 평가가
아니라, <b>허가 제도 자체를 닫는 법적 판단</b>입니다. 태국의 허가 제도는 태국이 의약품으로
인정한 물질에만 존재하기 때문입니다.</p>

<h2>어떤 서류로도 열리지 않는 이유</h2>
<p>태국 여행자 허가가 덮는 건 딱 두 그룹입니다 — 마약 2종, 그리고 향정신성 2·3·4종. 1종은
둘 중 어디에도 없습니다. 신청 양식이 없고, 일찍 신청해도 소용없고, 소견서로 바뀌지도
않습니다. 더 센 약은 허가 절차가 더 까다로울 뿐이라고 생각하는 분이 많지만, 여기서는 절차가
아예 없습니다. <a href="/ko/승인-태국">두 경로와 내 약이 어느 쪽인지</a>.</p>

<h2>쓸 수 있는 사실: 메틸페니데이트는 선 반대편에 있다</h2>
<p>메틸페니데이트 — 콘서타, 리탈린 — 는 태국에서 <b>향정신성 2종</b>이고, 이 그룹은
<i>허가가 전혀 필요 없습니다</i>. 처방 의사의 소견서나 처방전, 그리고 {{th_qty}}까지면
됩니다. 같은 질환, 같은 치료 목적인데 국경에서의 법적 위치가 완전히 다릅니다.</p>
<p>그래서 태국에 가는 ADHD 환자에게 선택지가 없는 게 아닙니다. 선택지는 <b>여행 기간용으로
다른 성분을 쓸지 처방 의사와 상의하는 것</b>이고, 그 대화는 공항이 아니라 출국 한참 전에
해야 합니다. 리스덱스암페타민(비반스)은 우회로가 아닙니다 — 체내에서 덱스암페타민으로
전환되는 전구약물이라 암페타민 쪽으로 보고, 이 페이지를 믿기 전에 {{th_portal}} 의 FDA
조회로 직접 확인하세요.</p>

<h2>출국 전에 할 것</h2>
<p>&bull; 두고 갑니다. "혹시 모르니" 수탁 수하물에 넣는 것도 안 됩니다 — 이 건에는 안전한
쪽이 없습니다.<br>
&bull; 태국으로 우편 발송하지 마세요. 우편도 그 자체로 수입이고 같은 답이 나오는데, 설명할
사람이 그 자리에 없습니다.<br>
&bull; 질환과 <i>지금 안 가져가는</i> 치료 내용을 적은 처방 의사 소견서를 챙기세요. 현지에서
진료를 받아야 할 때 복약 공백을 설명해 줍니다.
<a href="/ko/소견서">소견서에 무엇을 적어야 하나</a>.<br>
&bull; 같은 진료에서 2~4종 대체약이나 비자극성 약이 여행 기간에 적절한지 함께 물어보세요.</p>
<p>특정 제품 문의는 태국 FDA 마약단속부 {{th_mail}} 또는 {{th_tel}}. 물질에 대해서는
답해 주지만, 메일로 여행자를 사전 승인해 주지는 않습니다.</p>
"""

DEEP["sudafed-to-thailand"] = """
<h2>The short version, and we had this wrong until yesterday</h2>
<p>Pseudoephedrine is not banned in Thailand. The Thai FDA lists it as a <b>Category 2 psychotropic
substance</b>, by name, alongside zolpidem, methylphenidate and ketamine. Category 2 is in the group
travellers may carry: a certificate or prescription from the prescribing physician, up to
{{th_qty}}, <b>no permit required</b>, and the FDA's own guidance says medicines carried that way
are considered personal belongings with nothing to declare at the Customs Red Channel.</p>
<p>This page said &ldquo;banned&rdquo; until we read the Thai FDA's classification page directly.
Most guides still say it. If you are reading a page that tells you pseudoephedrine is prohibited in
Thailand, including an older version of this one, it is working from the wrong category.</p>

<h2>So where is the actual risk</h2>
<p>In the prescription you probably do not have. Being a Category 2 psychotropic makes
pseudoephedrine a <i>controlled medicine</i> in Thailand &mdash; and in most of the world it is a
box off a pharmacy shelf. That mismatch is the whole problem. The traveller carrying Sudafed from
home is carrying a Thai controlled substance with no document tying it to a prescriber, which is
exactly the case the 30-day rule does not cover.</p>
<p>The molecule is fine. The paperwork is what is missing.</p>

<h2>What to do, in order</h2>
<p>&bull; Ask your doctor for a prescription or certificate that names <b>pseudoephedrine</b> as the
active ingredient, with the strength, the dose, the total quantity and the number of days it
covers. Brand name alone does not do the job &mdash; the Thai list is written in substances.
<a href="/can-i-bring/doctors-letter">Template</a>.<br>
&bull; Keep it in the original labelled box. The Thai FDA requires the original container with
contents clearly marked, and the box is what connects the prescription to the pills.<br>
&bull; Stay inside {{th_qty}}, counted for your own trip rather than rounded up.<br>
&bull; If getting a prescription for a cold medicine is more trouble than it is worth &mdash; which
is a reasonable conclusion &mdash; leave it and pick a decongestant without pseudoephedrine in it,
with a pharmacist, before you fly.</p>

<h2>Read the ingredient panel, not the front of the box</h2>
<p>This is where people get caught without meaning to. Pseudoephedrine hides inside combination
cold and flu products whose front label advertises something else entirely, and the traveller who
carefully left the Sudafed at home brings three days of a multi-symptom product that contains it.
Check the active-ingredients panel of everything in the washbag, not just the thing you think of as
the decongestant.</p>

<h2>The quantity figure</h2>
<p>{{th_disc}}.</p>
<p>Procedure and the two routes: <a href="/can-i-bring/permit-thailand">bringing medicine into
Thailand</a>. For a specific product, the FDA's lookup is at {{th_portal}} and the Narcotics
Control Division answers at {{th_mail}}.</p>
"""

KO_DEEP["감기약-슈도에페드린-태국"] = """
<h2>결론부터, 그리고 우리도 어제까지 틀렸다</h2>
<p>슈도에페드린은 태국에서 금지가 아닙니다. 태국 FDA는 이 성분을 <b>향정신성 2종</b>에
졸피뎀·메틸페니데이트·케타민과 나란히 <b>이름까지 적어</b> 올려놨습니다. 2종은 여행자가
지참할 수 있는 그룹입니다 — 처방 의사의 소견서나 처방전, {{th_qty}}까지,
<b>사전 허가 불필요</b>. 그렇게 지참한 약은 개인 소지품으로 보고 세관 레드채널 신고 의무도
없다고 FDA 지침이 직접 적습니다.</p>
<p>이 페이지는 어제까지 "반입이 막힙니다"라고 띄우고 있었습니다. 태국 FDA 분류 페이지를
직접 읽고 고쳤습니다. 대부분의 안내 글이 아직 금지라고 씁니다. 슈도에페드린이 태국에서
금지라고 적힌 페이지를 보고 있다면 — 이 페이지의 옛 버전을 포함해서 — 틀린 분류를 보고
쓴 글입니다.</p>

<h2>그럼 실제 위험은 어디에 있나</h2>
<p>아마 당신에게 없을 그 처방전에 있습니다. 향정신성 2종이라는 건 태국에서 이 성분이
<i>통제 의약품</i>이라는 뜻이고, 세계 대부분에서 이건 약국 선반에서 그냥 집어오는 상자입니다.
그 불일치가 문제의 전부입니다. 집에서 사 온 감기약을 들고 가는 여행자는, 처방자와 연결되는
서류가 전혀 없는 태국 통제물질을 들고 가는 것이고, 그게 바로 30일 규정이 덮어주지 않는
경우입니다.</p>
<p>성분은 문제가 없습니다. 없는 건 서류입니다.</p>

<h2>순서대로 할 것</h2>
<p>&bull; 의사에게 <b>슈도에페드린</b>을 성분명으로 적은 처방전이나 소견서를 받으세요. 함량,
1회 용량, 총 지참 수량, 며칠분인지까지. 상품명만으로는 안 됩니다 — 태국 목록은 성분으로
쓰여 있습니다. <a href="/ko/소견서">양식</a>.<br>
&bull; 원래 라벨 상자에 그대로 둡니다. 태국 FDA는 내용물이 명확히 표시된 원래 용기를
요구하고, 처방전과 알약을 잇는 게 바로 그 상자입니다.<br>
&bull; {{th_qty}} 안에서, 내 일정으로 계산한 수량만 가져갑니다.<br>
&bull; 감기약 하나 때문에 처방전을 받는 게 번거롭다고 판단되면 — 합리적인 결론입니다 —
두고 가고, 출국 전에 약사와 상의해 슈도에페드린이 안 든 코막힘약을 고르세요.</p>

<h2>상자 앞면이 아니라 성분표를 봐라</h2>
<p>모르고 걸리는 지점이 여기입니다. 슈도에페드린은 앞면에 전혀 다른 걸 광고하는 종합
감기약 안에 숨어 있습니다. 슈다페드는 꼼꼼히 두고 온 사람이, 그 성분이 든 종합감기약
3일분을 들고 갑니다. 세면백에 든 모든 약의 <b>주성분표</b>를 확인하세요. 내가 "코막힘약"
이라고 생각하는 그것만이 아니라.</p>

<h2>수량 숫자</h2>
<p>{{th_disc}}.</p>
<p>절차와 두 경로: <a href="/ko/승인-태국">태국에 약 가져가기</a>. 특정 제품은
{{th_portal}} 의 FDA 조회, 문의는 마약단속부 {{th_mail}}.</p>
"""

# ── 태국 심화 4페이지 배포 시점 재검증 (위 검증기 이후에 추가됐으므로 다시 돈다)
for _s in ("adderall-to-thailand", "sudafed-to-thailand"):
    assert _s in DEEP and _SRCFOR.get(_s), "영문 태국 심화 누락: %s" % _s
    assert "{{" not in _fill(_s, DEEP[_s], "en"), "치환 안 된 자리표시자: %s/en" % _s
for _s in ("애더럴-태국", "감기약-슈도에페드린-태국"):
    assert _s in KO_DEEP and _SRCFOR.get(_s), "한글 태국 심화 누락: %s" % _s
    assert "{{" not in _fill(_s, KO_DEEP[_s], "ko"), "치환 안 된 자리표시자: %s/ko" % _s


# ══════════════════════════════════════════════════════════════
# ★RX 등급 표시 (2026-10-09). borderrx_v1 의 RANK["RX"] 와 짝이다.
#   ★딕셔너리를 순회하는 코드가 한 곳도 없는 걸 확인하고 키만 더한다.
#   색은 마젠타다. 빨강·호박·파랑·보라·초록이 이미 쓰였고, 심각도 축의
#   중간색을 쓰면 호박(PERMIT)과 헷갈린다. RX 는 '더 약한 허가'가 아니라
#   종류가 다른 장애물이라 계열을 달리하는 게 맞다.
LV["RX"] = "Prescription required there"
COL["RX"] = "#e79ac9"
DO["RX"] = ("There is no import permit to apply for. Bring your own supply with the "
            "prescription and the original labelled packaging. The catch is at the other "
            "end: a pharmacy there will not sell you more without a prescription written "
            "in that country, so take enough for the whole trip.")
KO_LV["RX"] = "현지에서 처방 대상입니다"
KO_DO["RX"] = ("신청할 수입 허가 제도가 없습니다. 본인 처방분을 처방전과 원래 라벨이 "
               "붙은 포장 그대로 가져가면 됩니다. 문제는 도착한 다음입니다 — 현지 "
               "약국은 그 나라 의사의 처방 없이는 더 팔지 않으므로, 여행 기간 전체에 "
               "쓸 만큼을 챙겨 가세요.")

# ★_bridge 를 감싼다. 모듈 전역 이름을 다시 묶으므로 이후 호출은 이쪽을 탄다.
#   원본은 PERMIT/PROHIBITED 세 갈래뿐이라 RX 는 아무 박스도 못 받는다.
_bridge_before_rx = _bridge


def _bridge(lvl, cc, lang):
    if lvl == "RX":
        lurl = "/can-i-bring/doctors-letter" if lang == "en" else "/ko/소견서"
        if lang == "en":
            return _BOX % ("#6b3a55", "#e79ac9",
                           "Nothing to apply for &mdash; but you cannot buy it there either",
                           '<p style="margin:0">No permit exists for this one, so there is no '
                           'paperwork to file before you fly. It is prescription-only at your '
                           'destination, which means a pharmacy there will turn you away without '
                           'a local prescription. Carry enough for the whole trip in the original '
                           'labelled packaging, with your prescription and a prescriber&rsquo;s '
                           'letter naming the generic ingredient. '
                           '<a href="%s">Letter template</a>.</p>' % lurl)
        return _BOX % ("#6b3a55", "#e79ac9",
                       "신청할 것은 없지만, 현지에서 살 수도 없다",
                       '<p style="margin:0">이 성분에는 허가 제도가 없어서 출국 전에 낼 서류가 '
                       '없습니다. 대신 도착지에서 처방 대상이라 현지 약국은 그 나라 처방전 없이 '
                       '팔지 않습니다. 여행 기간 전체에 쓸 분량을 원래 라벨이 붙은 포장 그대로, '
                       '처방전과 성분 일반명을 적은 소견서와 함께 가져가세요. '
                       '<a href="%s">소견서 양식</a>.</p>' % lurl)
    return _bridge_before_rx(lvl, cc, lang)
