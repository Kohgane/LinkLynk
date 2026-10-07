# -*- coding: utf-8 -*-
"""
parking_v1.py — 2주 검증용 단일 페이지. 주차 수직 테스트.

★왜 이 파일이 따로 있나: 버리기 쉬우라고. 실패하면 이 파일 지우고
  app.py 의 앵커 3개만 되돌리면 끝난다. canibring 쪽을 import 하지 않는다
  (CSS 를 복사해 쓴다). 결합을 만들면 버릴 때 비용이 생긴다.

★왜 canibringmeds.com 에 올리나: linklynk.onrender.com 은 무료 Render
  서브도메인이라 유휴 시 잠든다. 2주 안에 색인될 가능성이 거의 없고,
  그러면 "신호 없음"이 수요 때문인지 호스팅 때문인지 구분이 안 된다.
  측정 불가능한 테스트는 테스트가 아니다. canibringmeds.com 은 GSC/Bing/
  네이버 3곳에 소유 증명이 끝났고 실제로 크롤링되고 있는 유일한 호스트다.

★왜 사이트맵을 따로 내나: /sitemap-parking.xml 하나에 이 페이지만 넣으면
  Search Console 이 사이트맵별 커버리지를 따로 보여준다. 즉 사이트맵 자체가
  이 테스트의 측정 단위가 된다. 의약품 62페이지와 섞이지 않는다.

★출처: 전부 레이캬비크시(Bílastæðasjóður) 자체 페이지. 2026-10-07 확인.
  요금/시간은 2026-04-14, 2026-06-16 시의회 결정으로 재검토 중이다.
  그래서 페이지에 확인 날짜와 재검토 사실을 같이 적는다.
"""
import html as _h
from flask import Blueprint, Response

pk_bp = Blueprint("parking_v1", __name__)

BASE = "https://canibringmeds.com"
VERIFIED = "7 October 2026"

CSS = """*{box-sizing:border-box}body{margin:0;background:#0b0d12;color:#e9eef5;
font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.w{max-width:680px;margin:0 auto;padding:30px 18px 70px}
h1{font-size:30px;line-height:1.25;margin:0 0 8px;letter-spacing:-.5px}
.lede{color:#8b98a8;font-size:14px;margin:0 0 22px}
.ans{border-radius:14px;padding:20px;background:#111620;border:1px solid #27323f;margin:0 0 22px}
.ans .k{font-size:13px;color:#8b98a8}.ans .v{font-size:26px;font-weight:800;margin:4px 0}
h2{font-size:19px;margin:28px 0 8px}
p{margin:0 0 14px;color:#c9d4e0}
a{color:#5ec8bb}
table{width:100%;border-collapse:collapse;margin:0 0 16px;font-size:15px}
th,td{text-align:left;padding:9px 8px;border-bottom:1px solid #1a212c;color:#c9d4e0}
th{color:#8b98a8;font-size:13px;font-weight:600}
td b{color:#e9eef5}
ul{margin:0 0 14px;padding-left:20px;color:#c9d4e0}li{margin:0 0 6px}
.box{border-radius:12px;padding:16px 18px;background:#141a24;border:1px solid #27323f;margin:0 0 18px}
.warn{margin-top:30px;font-size:13px;color:#7d8a99;border-top:1px solid #1a212c;padding-top:18px}
.warn b{color:#cfdae6}
.src{font-size:13px;color:#7d8a99}.src a{color:#5ec8bb}"""

_FAQ = [
    ("How do you pay for parking in Reykjavik?",
     "Three ways. A mobile app (EasyPark, Parka or SiminnPay), a street meter "
     "that takes coins, cards or a phone, or the city's own web payment page. "
     "With an app you register the plate, pick the right zone (P1 to P4) and "
     "check out when you leave."),
    ("Which parking app works in Iceland?",
     "EasyPark, Parka and SiminnPay all cover every paid zone run by the City "
     "of Reykjavik. EasyPark and Parka also work inside the city's car parks. "
     "All three are free to download."),
    ("What happens if you do not pay for parking in a rental car in Iceland?",
     "The charge is 4,500 ISK, and no ticket is placed on the windscreen. "
     "Reykjavik sends it to the vehicle's registered keeper through island.is "
     "and their online bank, and the city is not permitted to move the claim "
     "to anyone else. In a rental car that keeper is the rental company, so it "
     "reaches you later as a card charge from them."),
]

_ZONES = [
    ("P1", "660 ISK", "09:00-20:00 Mon-Fri, 10:00-20:00 Sat &amp; Sun",
     "Max 3 hours. The central core."),
    ("P2", "240 ISK", "09:00-20:00 Mon-Fri, 10:00-20:00 Sat &amp; Sun", "No stated time cap."),
    ("P3", "240 ISK", "09:00-18:00 Mon-Fri only",
     "240 ISK for the first two hours, then 70 ISK/hour. Nothing to pay evenings or weekends."),
    ("P4", "240 ISK", "08:00-16:00 Mon-Fri only", "Nothing to pay evenings or weekends."),
]

_HOLIDAYS = ("New Year's Day, Maundy Thursday, Good Friday, Easter Sunday, "
             "Easter Monday, First Day of Summer, 1 May, Ascension Day, "
             "Whit Sunday, Whit Monday, 17 June, Commerce Day, "
             "Christmas Day and 26 December")


def _body():
    rows = "".join(
        "<tr><td><b>%s</b></td><td>%s</td><td>%s</td></tr>"
        "<tr><td></td><td colspan=\"2\" style=\"color:#8b98a8;font-size:14px;"
        "border-bottom:1px solid #1a212c\">%s</td></tr>" % z
        for z in _ZONES)

    faq = "".join("<h2>%s</h2><p>%s</p>" % (q, a) for q, a in _FAQ)

    return (
        '<h1>Parking in Reykjavik: what you pay, and the fine that finds you '
        'weeks later</h1>'
        '<p class="lede">Rates, hours and penalties straight from the City of '
        'Reykjavik\'s own pages. Verified %s.</p>'

        '<div class="ans"><div class="k">Kerbside, city centre</div>'
        '<div class="v">660 ISK / hour</div>'
        '<div class="k">Zone P1. Everywhere else the city charges 240 ISK/hour. '
        'A city car park starts at 190 ISK for the first hour. '
        'Not paying costs 4,500 ISK.</div></div>'

        '<h2>The four zones</h2>'
        '<p>Reykjavik has four paid zones. The sign at the kerb tells you which '
        'one you are in, and the zone decides both the price and the hours. '
        'Outside the hours listed below, that zone is free.</p>'
        '<table><tr><th>Zone</th><th>Per hour</th><th>Charged</th></tr>%s</table>'
        '<p>Blue disabled-badge (P-kort) holders pay nothing in paid spaces. In a '
        'marked EV charging bay you pay for the charge, not the space — but '
        'you may only park there while actually charging, and a broken charger '
        'is not permission to stay.</p>'

        '<h2>How to pay</h2>'
        '<ul>'
        '<li><b>An app.</b> EasyPark, Parka and SiminnPay all cover every paid '
        'city zone. EasyPark and Parka also work inside the city car parks. '
        'Register the plate, select the zone, check out when you leave.</li>'
        '<li><b>A meter.</b> Coins, card, or phone.</li>'
        '<li><b>The city website.</b> Bilastaedasjodur takes card payments for '
        'on-street spaces — but not for the city car parks, and not for '
        'private operators\' charges.</li>'
        '</ul>'

        '<div class="box"><h2 style="margin-top:0">If you are driving a rental '
        'car, read this part</h2>'
        '<p>Reykjavik no longer puts a ticket under your wiper. The city says so '
        'plainly: <i>"Ekki er lengur settur midi undir ruduthurrku."</i> The '
        'charge is raised against whoever the vehicle register lists as owner or '
        'keeper, and it appears in <b>their</b> island.is account and <b>their</b> '
        'online bank.</p>'
        '<p>Two consequences that catch visitors:</p>'
        '<ul>'
        '<li>You get no notice at all while you are in Iceland. No paper, no '
        'email, nothing on the windscreen. You can drive home not knowing.</li>'
        '<li>The city states it is <b>not permitted</b> to transfer the claim '
        'between parties — it stays with the registered keeper. For a rental '
        'car that is the rental company, which then recovers it from the card you '
        'left on file, usually with its own handling fee on top. You cannot have '
        'the charge reassigned to your own name.</li>'
        '</ul>'
        '<p>So the three-business-day discount below is, in practice, unreachable '
        'in a rental car: by the time anyone tells you, the discount window has '
        'closed.</p></div>'

        '<h2>What it costs if you get it wrong</h2>'
        '<p>Iceland splits these into two kinds. An <i>aukastodugjald</i> is for '
        'not paying, or paying for too little time. A <i>stodubrotsgjald</i> is '
        'for parking somewhere you may not — on the pavement, in a pedestrian '
        'street, under a no-parking sign, too close to a crossing or a junction. '
        'Since 1 January 2020 both are charges, not police fines.</p>'
        '<table>'
        '<tr><th>What happened</th><th>Charge</th><th>After 14 days</th>'
        '<th>After 28 days</th></tr>'
        '<tr><td>Did not pay, or underpaid</td><td><b>4,500</b></td>'
        '<td>6,750</td><td>9,000</td></tr>'
        '<tr><td>Parked illegally</td><td><b>10,000</b></td>'
        '<td>15,000</td><td>20,000</td></tr>'
        '<tr><td>Disabled bay, no badge</td><td><b>20,000</b></td>'
        '<td>30,000</td><td>40,000</td></tr>'
        '</table>'
        '<p>All in ISK. Pay within three working days and 1,100 ISK comes off any '
        'of them. You can ask for the charge to be reconsidered '
        '(<i>endurupptaka</i>) within 28 days, or ask for the reasoning behind it '
        'within 14 days.</p>'
        '<p>Two rules that surprise people: you may not park across your own '
        'driveway — the traffic act makes no exception for the owner — '
        'and loading or unloading does not exempt a van from paying, nor from the '
        'no-stopping rules.</p>'

        '<h2>The cheapest legal move downtown</h2>'
        '<p>The city runs seven car parks (<i>bilahus</i>) in the centre, open '
        '07:00-24:00 daily, except Bergstadir which is open around the clock. '
        'Short-stay rates are 190 ISK for the first hour then 140 ISK/hour at '
        'Stjornuport and Vitatorg, and 280 ISK then 150 ISK/hour at Kolaport, '
        'Radhus, Tradarkot and Vesturgata.</p>'
        '<p>Compare three hours in the centre. Kerbside in P1: 660 × 3 = '
        '<b>1,980 ISK</b>, and P1 caps you at three hours anyway. Vitatorg car '
        'park: 190 + 140 + 140 = <b>470 ISK</b>, with no cap. The garage is '
        'roughly a quarter of the price and it is indoors, which in an Icelandic '
        'winter is its own argument.</p>'

        '<h2>Days you pay nothing</h2>'
        '<p>The city suspends charging on %s.</p>'

        '%s'

        '<h2>What this page does not cover</h2>'
        '<p>Only spaces run by the City of Reykjavik. Private car parks, '
        'shopping-centre barriers, Keflavik airport and the car parks at rural '
        'attractions are separate operators with their own prices and their own '
        'enforcement, and the city cannot take payment for any of them.</p>'

        '<p class="warn"><b>Under review.</b> On 14 April 2026 the city council '
        'agreed to reopen the P1 price, to move part of P2 into P3, and to '
        'reconsider Sunday charging. On 16 June 2026 it agreed to look again at '
        'how long the centre is charged for and to simplify electronic payment. '
        'Figures on this page were taken from the city\'s own pages on %s and may '
        'move. Check before you travel.</p>'

        '<p class="src"><b>Sources</b> — all City of Reykjavik:<br>'
        '<a href="https://reykjavik.is/bilastaedi/leggja" rel="nofollow">Leggja '
        'bil i gjaldskyld staedi</a> (zones, rates, hours, apps, car parks)<br>'
        '<a href="https://reykjavik.is/stodvunarbrotagjold" rel="nofollow">'
        'Stodvunarbrotagjold</a> (charges and escalation)<br>'
        '<a href="https://reykjavik.is/bilastaedi/spurt-og-svarad" rel="nofollow">'
        'Spurt og svarad hja Bilastaedasjodi</a> (who the charge lands on)<br>'
        '<a href="https://reykjavik.is/frettir/2026/gjaldsvaedi-bilastaeda-og-'
        'utfaersla-gjaldskyldu-endurskodud" rel="nofollow">Council decision, '
        '14 April 2026</a> and <a href="https://reykjavik.is/frettir/2026/'
        'endurskodun-bilastaedamala-i-borginni" rel="nofollow">16 June 2026</a>'
        '</p>'
        % (VERIFIED, rows, _HOLIDAYS, faq, VERIFIED))


@pk_bp.route("/parking/iceland")
def pk_iceland():
    title = "Parking in Reykjavik, Iceland: rates, apps and fines (2026)"
    desc = ("What parking costs in Reykjavik by zone, which apps work, and why a "
            "rental-car parking charge reaches you weeks later. From the city's "
            "own pages.")
    ld = (
        '{"@context":"https://schema.org","@type":"FAQPage","mainEntity":['
        + ",".join(
            '{"@type":"Question","name":%s,"acceptedAnswer":'
            '{"@type":"Answer","text":%s}}' % (_j(q), _j(a)) for q, a in _FAQ)
        + ']}')
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title><meta name="description" content="%s">'
            '<link rel="canonical" href="%s/parking/iceland">'
            '<meta property="og:title" content="%s">'
            '<meta property="og:description" content="%s">'
            '<script type="application/ld+json">%s</script>'
            '<style>%s</style></head><body><div class="w">%s</div></body></html>'
            % (_h.escape(title), _h.escape(desc), BASE,
               _h.escape(title), _h.escape(desc), ld, CSS, _body()))
    return Response(html, mimetype="text/html; charset=utf-8")


def _j(s):
    """JSON 문자열 하나. json.dumps 와 같되 </script> 를 못 닫게 막는다."""
    out = s.replace("\\", "\\\\").replace('"', '\\"')
    out = out.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return '"%s"' % out


@pk_bp.route("/sitemap-parking.xml")
def pk_sitemap():
    # ★이 테스트의 측정 단위. 페이지가 늘면 여기만 늘린다.
    urls = ["%s/parking/iceland" % BASE]
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + "".join("<url><loc>%s</loc><changefreq>monthly</changefreq></url>" % u
                     for u in urls)
           + "</urlset>")
    return Response(xml, mimetype="application/xml")

@pk_bp.route("/parking")
@pk_bp.route("/parking/")
def pk_index():
    # ★왜 있나: /parking 을 그냥 두면 APP_HOST 로 301 된 뒤 404 다.
    #   크롤 예산을 버리는 죽은 끝이 된다. 한 장뿐이니 바로 넘긴다.
    return Response(status=301, headers={"Location": "/parking/iceland"})
