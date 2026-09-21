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
BASE = "https://linklynk.onrender.com"
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
            '<link rel="canonical" href="%s/can-i-bring/%s">'
            '<meta property="og:title" content="%s"><meta property="og:description" content="%s">'
            '<meta property="og:image" content="%s/next/og-en/%s.png">'
            '<meta name="twitter:card" content="summary_large_image">'
            '<script type="application/ld+json">%s</script>'
            '<style>%s</style></head><body><div class="w">%s</div></body></html>'
            % (e(title), e(desc), BASE, s, e(title), e(desc), BASE, e(drug), ld, CSS, "".join(body)))
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
            '<style>%s</style></head><body><div class="w"><h1>Can I bring my medicine abroad?</h1>'
            '<p class="lede">Common medicines that are banned or restricted abroad.</p>%s'
            '<a class="cta" href="/next/en">Check any medicine in 21 countries</a></div></body></html>'
            % (CSS, items))
    return Response(html, mimetype="text/html; charset=utf-8")


@cb_bp.route("/sitemap-travel.xml")
def cb_sitemap():
    urls = ["%s/next/en" % BASE, "%s/can-i-bring" % BASE,
            "%s/gottago/" % BASE, "%s/eats/" % BASE]
    urls += ["%s/can-i-bring/%s" % (BASE, slug(d, c)) for d, c in PAIRS]
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
