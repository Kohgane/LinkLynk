# -*- coding: utf-8 -*-
"""콘텐츠 사이트 방문 로그. ★측정이 페이지를 죽이면 안 된다 — 전부 삼킨다."""
import io, sys
src = io.open("app.py", encoding="utf-8").read()
if "_log_hit" in src:
    print("이미 있다"); sys.exit(1)
A = "@app.before_request\ndef _split_hosts():"
if src.count(A) != 1:
    print("실패: 앵커 %d회" % src.count(A)); sys.exit(1)

src += u'''

# ══════════════════════════════════════════════════════════════
# 방문 기록 (canibringmeds.com 전용)
#
# ★왜 자체 로그인가: 이 사이트는 /ko, 멜라토닌-영국·독일 때문에 EU 독자가 온다.
#   3자 분석도구는 동의 배너를 끌고 온다. 1차 로그는 쿠키를 안 쓰고
#   IP 는 해시만 남기므로 그 문제가 없다.
# ★원칙: 로그가 실패해도 페이지는 떠야 한다. 예외는 전부 삼킨다.
import hashlib as _hl, re as _re_h, threading as _th

_BOT = _re_h.compile(r"bot|crawl|spider|slurp|bing|yandex|baidu|duckduck|"
                     r"facebookexternalhit|headless|preview|monitor|"
                     r"curl|wget|python-requests|go-http|java/", _re_h.I)
_HITS_READY = [False]
_SKIP = ("/robots.txt", "/sitemap", "/favicon", "/apple-touch", "/manifest")


def _log_hit(path, ua, ref, iph):
    try:
        import os as _os, psycopg2 as _pg
        cn = _pg.connect(_os.environ["DATABASE_URL"])
        try:
            with cn:
                with cn.cursor() as cur:
                    if not _HITS_READY[0]:
                        cur.execute("""CREATE TABLE IF NOT EXISTS cb_hits(
                            id bigserial primary key,
                            at timestamptz default now(),
                            path text, lang text, ref text,
                            ua text, bot boolean, iph text)""")
                        cur.execute("CREATE INDEX IF NOT EXISTS cb_hits_at ON cb_hits(at)")
                        _HITS_READY[0] = True
                    cur.execute(
                        "INSERT INTO cb_hits(path,lang,ref,ua,bot,iph) VALUES(%s,%s,%s,%s,%s,%s)",
                        (path[:200], "ko" if path.startswith("/ko") else "en",
                         (ref or "")[:120], (ua or "")[:200],
                         bool(_BOT.search(ua or "")), iph))
        finally:
            cn.close()
    except Exception:
        pass


@app.after_request
def _count_hit(resp):
    try:
        h = (request.host or "").split(":")[0].lower()
        p = request.path
        if h == CB_HOST and resp.status_code == 200 and not p.startswith(_SKIP):
            ua = request.headers.get("User-Agent", "")
            # 참조는 호스트만 남긴다. 전체 URL 은 남의 사생활이 섞인다.
            ref = (request.headers.get("Referer", "") or "").split("/")[2:3]
            ref = ref[0] if ref else ""
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
            iph = _hl.sha256(ip.encode()).hexdigest()[:16]
            # ★응답을 막지 않는다
            _th.Thread(target=_log_hit, args=(p, ua, ref, iph), daemon=True).start()
    except Exception:
        pass
    return resp


@app.route("/api/cb/stats")
def _cb_stats():
    """관리자용 집계. 키는 환경변수에서만 읽는다."""
    import os as _os
    want = _os.environ.get("TH_ADMIN_KEY", "")
    got = request.headers.get("X-Admin-Key") or request.args.get("key") or ""
    if not want or got != want:
        return jsonify(error="nope"), 403
    days = min(90, max(1, request.args.get("days", 14, type=int)))
    try:
        import psycopg2, psycopg2.extras
        with psycopg2.connect(_os.environ["DATABASE_URL"]) as cn:
            with cn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""select date_trunc('day',at)::date::text d, lang,
                                      count(*) filter (where not bot) humans,
                                      count(*) filter (where bot) bots,
                                      count(distinct iph) filter (where not bot) uniq
                               from cb_hits where at > now() - (%s || ' days')::interval
                               group by 1,2 order by 1 desc, 2""", (days,))
                days_rows = [dict(r) for r in cur.fetchall()]
                cur.execute("""select path, count(*) n from cb_hits
                               where not bot and at > now() - (%s || ' days')::interval
                               group by 1 order by n desc limit 20""", (days,))
                top = [dict(r) for r in cur.fetchall()]
                cur.execute("""select coalesce(nullif(ref,''),'(직접)') ref, count(*) n
                               from cb_hits where not bot and at > now() - (%s || ' days')::interval
                               group by 1 order by n desc limit 15""", (days,))
                refs = [dict(r) for r in cur.fetchall()]
        return jsonify(days=days_rows, top_paths=top, referrers=refs)
    except Exception as e:
        return jsonify(error=str(e)[:160]), 500
'''

io.open("app.py", "w", encoding="utf-8").write(src)
print("기록 완료 (%d바이트)" % len(src))
