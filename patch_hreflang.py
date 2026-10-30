# -*- coding: utf-8 -*-
"""EN/KO 교차링크 + hreflang + 사이트맵 URL 인코딩.
   ★앵커가 정확히 1회 매치될 때만 바꾼다. 하나라도 어긋나면 전부 취소."""
import io, sys

F = "canibring_v1.py"
src = io.open(F, encoding="utf-8").read()
orig = src
fail = []

def sub(tag, old, new):
    global src
    n = src.count(old)
    if n != 1:
        fail.append("%s — %d회 매치" % (tag, n)); return
    src = src.replace(old, new, 1)
    print("  OK %s" % tag)

# 1. 영문 상세 head
sub("EN page head",
    '\'<link rel="canonical" href="%s/can-i-bring/%s">\'',
    '\'<link rel="canonical" href="%s/can-i-bring/%s">%s\'')
sub("EN page args",
    '% (e(title), e(desc), BASE, s, e(title), e(desc), BASE, e(drug), ld, CSS, "".join(body)))',
    '% (e(title), e(desc), BASE, s, _alt_en(s), e(title), e(desc), BASE, e(drug), ld, CSS, "".join(body)))')

# 2. 한글 상세 head
sub("KO page head",
    '\'<link rel="canonical" href="%s/ko/%s">\'',
    '\'<link rel="canonical" href="%s/ko/%s">%s\'')
sub("KO page args",
    'BASE, s, faq, CSS, _h.escape(title),',
    'BASE, s, _alt_ko(s), faq, CSS, _h.escape(title),')

# 3. 한글 인덱스 — hreflang + 영문판 링크
sub("KO index head",
    '\'<link rel="canonical" href="%s/ko"><style>%s</style></head><body><div class="w">\'',
    '\'<link rel="canonical" href="%s/ko">\'\n'
    '            \'<link rel="alternate" hreflang="ko" href="%s/ko">\'\n'
    '            \'<link rel="alternate" hreflang="en" href="%s/can-i-bring">\'\n'
    '            \'<link rel="alternate" hreflang="x-default" href="%s/can-i-bring">\'\n'
    '            \'<style>%s</style></head><body><div class="w">\'')
sub("KO index cta",
    '\'<a class="cta" href="%s/next">약 이름 직접 넣어보기</a>\'',
    '\'<a class="cta" href="%s/next">약 이름 직접 넣어보기</a>\'\n'
    '            \'<p style="margin-top:18px;opacity:.7"><a href="%s/can-i-bring">English</a></p>\'')
sub("KO index args",
    '% (BASE, CSS, items, BASE))',
    '% (BASE, BASE, BASE, BASE, CSS, items, BASE, BASE))')

# 4. 영문 인덱스 — canonical 없었다 + hreflang + 한국어 링크
sub("EN index head",
    '\'<meta name="description" content="Which medicines are banned or need a permit in Japan, UAE, Singapore, Saudi Arabia and more.">\'',
    '\'<meta name="description" content="Which medicines are banned or need a permit in Japan, UAE, Singapore, Saudi Arabia and more.">\'\n'
    '            \'<link rel="canonical" href="%s/can-i-bring">\'\n'
    '            \'<link rel="alternate" hreflang="en" href="%s/can-i-bring">\'\n'
    '            \'<link rel="alternate" hreflang="ko" href="%s/ko">\'\n'
    '            \'<link rel="alternate" hreflang="x-default" href="%s/can-i-bring">\'')
sub("EN index body+args",
    '\'<a class="cta" href="/next/en">Check any medicine in 21 countries</a></div></body></html>\'\n'
    '            % (CSS, items))',
    '\'<a class="cta" href="/next/en">Check any medicine in 21 countries</a>\'\n'
    '            \'<p style="margin-top:18px;opacity:.7"><a href="/ko">한국어</a></p>\'\n'
    '            \'</div></body></html>\'\n'
    '            % (BASE, BASE, BASE, BASE, CSS, items))')

# 5. 사이트맵 — 한글 경로 퍼센트 인코딩
sub("sitemap encode",
    'urls += ["%s/ko/%s" % (BASE, ko_slug(l, c)) for l, q, c in KO_PAIRS]',
    'urls += ["%s/ko/%s" % (BASE, _q(ko_slug(l, c))) for l, q, c in KO_PAIRS]')

if fail:
    print("\n실패 — 아무것도 안 바꿨다:")
    for f in fail: print("   ", f)
    sys.exit(1)

src += u'''

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
'''

io.open(F, "w", encoding="utf-8").write(src)
print("\n패치 완료. %d -> %d 바이트" % (len(orig), len(src)))
