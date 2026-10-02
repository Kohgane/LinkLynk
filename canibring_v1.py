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
        body.append(deep)      # ★1차 출처 읽고 직접 쓴 본문
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
