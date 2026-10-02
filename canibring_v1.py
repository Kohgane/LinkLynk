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
]

# 조합별 고유 설명 — 얇은 페이지 방지의 핵심. 보수적으로 쓴다.
WHY = {
    ("pseudoephedrine", "JP"): "Japan treats pseudoephedrine as a stimulant precursor. Cold medicines containing it, including Sudafed and some Vicks products, cannot be brought in even with a prescription.",
    ("pseudoephedrine", "TH"): "Thailand controls pseudoephedrine as a precursor chemical. Carrying pseudoephedrine cold medicine is not advised.",
    ("dextroamphetamine", "JP"): "Amphetamine-based ADHD medication is prohibited in Japan and cannot be imported even with a doctor's prescription. Possession is a criminal offence.",
    ("dextroamphetamine", "SG"): "Amphetamine is strictly controlled in Singapore. Personal import is generally not permitted.",
    ("dextroamphetamine", "AE"): "The UAE prohibits amphetamine-based medication. Travellers have faced detention over ADHD medication.",
    ("dextroamphetamine", "TH"): "Amphetamine is a Category 1 narcotic in Thailand. Personal import is not permitted.",
    ("dextroamphetamine", "SA"): "Amphetamine is prohibited in Saudi Arabia.",
    ("codeine", "AE"): "The UAE strictly controls codeine. Travellers have been detained for carrying codeine painkillers or cough medicine without prior approval.",
    ("codeine", "SA"): "Codeine is treated as a narcotic in Saudi Arabia. Carrying it without authorisation risks detention.",
    ("codeine", "SG"): "Singapore requires prior approval from the Health Sciences Authority to bring in codeine-containing medicine.",
    ("tramadol", "AE"): "Tramadol is tightly controlled in the UAE and arrests of travellers have been reported.",
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
    urls = ["%s/next/en" % BASE, "%s/can-i-bring" % BASE,
            "%s/gottago/" % BASE, "%s/eats/" % BASE]
    urls += ["%s/can-i-bring/%s" % (BASE, slug(d, c)) for d, c in PAIRS]
    urls += ["%s/ko" % BASE]
    urls += ["%s/ko/%s" % (BASE, _q(ko_slug(l, c))) for l, q, c in KO_PAIRS]
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
    ("pseudoephedrine", "JP"): "일본은 슈도에페드린을 각성제 원료로 취급합니다. 이 성분이 든 감기약은 처방전이 있어도 반입할 수 없습니다. 한국 약국에서 흔히 파는 코감기약에 들어 있어 가장 많이 걸리는 성분입니다.",
    ("pseudoephedrine", "TH"): "태국은 슈도에페드린을 전구물질로 통제합니다. 이 성분이 든 감기약은 가져가지 않는 편이 안전합니다.",
    ("dihydrocodeine", "JP"): "코푸시럽에 든 디히드로코데인은 UN 국제통제물질 목록에 오른 마약류입니다. 한국에서 처방 없이 살 수 있다는 점 때문에 감각이 무뎌지기 쉽습니다.",
    ("dextroamphetamine", "JP"): "암페타민 계열 ADHD 약은 일본에서 반입이 금지됩니다. 본국 처방전이 있어도 예외가 아니며, 소지 자체가 형사 문제가 됩니다.",
    ("dextroamphetamine", "SG"): "싱가포르는 암페타민을 엄격히 통제합니다. 개인 반입은 원칙적으로 허용되지 않습니다.",
    ("dextroamphetamine", "TH"): "태국에서 암페타민은 1종 마약으로 분류됩니다. 개인 반입이 허용되지 않습니다.",
    ("methylphenidate", "JP"): "메틸페니데이트는 일본에서 각성제로 통제됩니다. 등록 의사 제도를 통해 일본 내 처방은 가능하지만, 개인이 들고 들어가는 것은 원칙적으로 안 됩니다.",
    ("methylphenidate", "SG"): "싱가포르는 메틸페니데이트를 통제 약물로 다룹니다. 반입 전 보건과학청(HSA) 승인이 필요합니다.",
    ("codeine", "JP"): "코데인은 마약류로 분류됩니다. 함량과 제형에 따라 취급이 달라지므로, 코데인이 든 진통제·기침약은 성분표를 먼저 확인해야 합니다.",
    ("codeine", "AE"): "UAE는 코데인을 엄격히 통제합니다. 사전 승인 없이 코데인이 든 진통제나 기침약을 가져갔다가 구금된 사례가 보고돼 있습니다.",
    ("tramadol", "JP"): "트라마돌은 마약성 진통제로 통제 대상입니다. 처방전과 영문 소견서 없이 가져가지 마세요.",
    ("zolpidem", "JP"): "졸피뎀은 향정신성 의약품으로 통제됩니다. 처방전과 함께, 개인 사용 분량으로만 반입할 수 있습니다.",
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
    return _re.sub(r"\{\{([a-z_]+)\}\}", rep, tpl)


# ── 배포 시점 검증. 키를 틀리면 여기서 죽는다.
for _s, _t in list(DEEP.items()):
    _fill(_s, _t, "en")
for _s, _t in list(KO_DEEP.items()):
    _fill(_s, _t, "ko")
