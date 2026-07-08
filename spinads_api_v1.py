# spinads_api_v1.py — Claude Code 스피너 광고 서버 (Flask Blueprint)
# 클릭 라우트는 /s/<short_code> (LinkLynk 기존 /r/<link_id>와 분리)
import os, random, hashlib
from flask import Blueprint, request, jsonify, redirect
import psycopg2, psycopg2.extras

DB_URL = os.environ["DATABASE_URL"]  # LinkLynk 기존 pooler URL 재사용
MAX_ADS_PER_SESSION = 3

spinads_bp = Blueprint("spinads", __name__)

def _db():
    return psycopg2.connect(DB_URL)

def _ip_hash():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    return hashlib.sha256(ip.encode()).hexdigest()[:16]

@spinads_bp.get("/api/spinads/verbs")
def spinads_verbs():
    key = request.headers.get("X-API-Key", "")
    if not key:
        return jsonify(error="missing api key"), 401
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("select id, share_pct from spinads.publishers where api_key=%s and active", (key,))
            pub = cur.fetchone()
            if not pub:
                return jsonify(error="invalid api key"), 403
            cur.execute("""
                select id, verb, short_code, bid_krw, weight from spinads.campaigns
                where active and starts_at <= now()
                  and (ends_at is null or ends_at > now())
                  and (budget_krw is null or spent_krw < budget_krw)
            """)
            camps = cur.fetchall()
            if not camps:
                return jsonify(verbs=[], session_id=None)
            picked, pool = [], list(camps)
            for _ in range(min(MAX_ADS_PER_SESSION, len(pool))):
                c = random.choices(pool, weights=[x["weight"] for x in pool], k=1)[0]
                picked.append(c); pool.remove(c)
            base = request.url_root.rstrip("/")
            verbs = [c["verb"].replace("{URL}", f"{base}/s/{c['short_code']}") for c in picked]
            cur.execute(
                "insert into spinads.sessions (publisher_id, campaign_ids, ip_hash, ua) values (%s,%s,%s,%s) returning id",
                (pub["id"], [c["id"] for c in picked], _ip_hash(), (request.user_agent.string or "")[:200]))
            sid = cur.fetchone()["id"]
            for c in picked:
                if c["bid_krw"] > 0:
                    cur.execute("update spinads.campaigns set spent_krw = spent_krw + %s where id=%s",
                                (c["bid_krw"], c["id"]))
                    cur.execute("""insert into spinads.ledger (publisher_id, amount_krw, reason, ref_session)
                                   values (%s, %s, 'session_share', %s)""",
                                (pub["id"], c["bid_krw"] * pub["share_pct"] // 100, sid))
    return jsonify(verbs=verbs, session_id=sid, mode="append")

@spinads_bp.get("/s/<short_code>")
def spinads_click(short_code):
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("select id, landing_url from spinads.campaigns where short_code=%s", (short_code,))
            c = cur.fetchone()
            if not c or not c["landing_url"]:
                return "not found", 404
            cur.execute("insert into spinads.clicks (campaign_id, ip_hash, ua) values (%s,%s,%s)",
                        (c["id"], _ip_hash(), (request.user_agent.string or "")[:200]))
    return redirect(c["landing_url"], code=302)

@spinads_bp.get("/api/spinads/health")
def spinads_health():
    return jsonify(ok=True, service="spinads", version="v1")
