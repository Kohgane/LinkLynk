# -*- coding: utf-8 -*-
"""BorderRx 도메인 분리. ★앵커 1회 매치 아니면 전부 취소."""
import io, sys

src_cb = io.open("canibring_v1.py", encoding="utf-8").read()
OLD = 'BASE = "https://linklynk.onrender.com"'
NEW = 'BASE = "https://canibringmeds.com"'
if src_cb.count(OLD) != 1:
    print("실패: canibring_v1.py BASE %d회 매치" % src_cb.count(OLD)); sys.exit(1)
src_cb = src_cb.replace(OLD, NEW, 1)
print("  OK canibring_v1.py / BASE")

src_app = io.open("app.py", encoding="utf-8").read()
if "_split_hosts" in src_app:
    print("실패: app.py 에 이미 붙어 있다"); sys.exit(1)

src_app += u'''

# ══════════════════════════════════════════════════════════════
# BorderRx 도메인 분리 (canibringmeds.com)
#
# 한 서비스가 사이트 둘을 돌린다.
#   canibringmeds.com      약 반입 판정. YMYL — 주소창이 곧 신뢰다
#   linklynk.onrender.com  LinkLynk 앱·보임·나머지 도구
#
# ★기본값은 '안 옮김'이다. 아는 경로만 옮긴다.
#   before_request 를 잘못 걸면 앱도 보임도 같이 죽는다.
from flask import redirect as _rd
from canibring_v1 import cb_home as _cb_home

CB_HOST, APP_HOST = "canibringmeds.com", "linklynk.onrender.com"

_CB_EXACT = {"/", "/can-i-bring", "/can-i-bring/", "/ko", "/ko/",
             "/next", "/next/", "/next/en", "/next/en/",
             "/about", "/sitemap-travel.xml"}
_CB_PREFIX = ("/can-i-bring/", "/ko/", "/next/")
_BOTH = {"/robots.txt"}       # 호스트마다 제 내용을 낸다. 절대 안 넘긴다

# ★카드 이미지는 옛 주소에 그대로 둔다.
#   쓰레드 게시가 이 URL 을 200 으로 사전 확인한다. 301 로 바꾸면 게시가 막힌다.
_STAY = ("/next/card", "/next/og")

_CB_ROBOTS = ("User-agent: *\\n"
              "Disallow: /api/\\n"
              "Disallow: /t/\\n\\n"
              "Sitemap: https://canibringmeds.com/sitemap-travel.xml\\n")


def _is_cb(p):
    return p in _CB_EXACT or p.startswith(_CB_PREFIX)


def _to(host, p):
    q = request.query_string.decode("utf-8", "replace")
    return "https://%s%s%s" % (host, p, ("?" + q) if q else "")


@app.before_request
def _split_hosts():
    h = (request.host or "").split(":")[0].lower()
    p = request.path

    if h == "www." + CB_HOST:
        return _rd(_to(CB_HOST, p), 301)

    if h == CB_HOST:
        if p in _BOTH:
            return Response(_CB_ROBOTS, mimetype="text/plain; charset=utf-8")
        if p == "/":
            return _cb_home()         # ★앱 UI 가 아니라 BorderRx 홈
        if not _is_cb(p):
            return _rd(_to(APP_HOST, p), 301)
        return None

    if h == APP_HOST:
        if p in _BOTH or p == "/" or p.startswith(_STAY):
            return None
        if _is_cb(p):                 # 구글이 이미 아는 26개를 새 주소로 넘긴다
            return _rd(_to(CB_HOST, p), 301)
    return None
'''

io.open("canibring_v1.py", "w", encoding="utf-8").write(src_cb)
io.open("app.py", "w", encoding="utf-8").write(src_app)
print("  OK app.py / 호스트 분기")
print("기록 완료")
