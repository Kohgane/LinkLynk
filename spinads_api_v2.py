# spinads_api_v1.py — Claude Code 스피너 광고 서버 (Flask Blueprint)
# 클릭 라우트는 /s/<short_code> (LinkLynk 기존 /r/<link_id>와 분리)
import os, random, hashlib
from flask import Blueprint, request, jsonify, redirect
import psycopg2, psycopg2.extras
psycopg2.extras.register_uuid()  # uuid.UUID insert 어댑터 (없으면 can't adapt type 'UUID')

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
    import html as _html
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("select id, kind, landing_url from spinads.campaigns where short_code=%s", (short_code,))
            c = cur.fetchone()
            if not c or not c["landing_url"]:
                return "not found", 404
            cur.execute("insert into spinads.clicks (campaign_id, ip_hash, ua) values (%s,%s,%s)",
                        (c["id"], _ip_hash(), (request.user_agent.string or "")[:200]))
    dest = _html.escape(c["landing_url"], quote=True)
    disclosure = ("이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
                  if c["kind"] == "affiliate" else "SpinAds 광고 링크로 이동합니다.")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>이동 중… — SpinAds</title>
<style>body{{font-family:system-ui,-apple-system,'Noto Sans KR',sans-serif;display:flex;min-height:100vh;
align-items:center;justify-content:center;margin:0;background:#111;color:#eee}}
.card{{max-width:420px;padding:32px;text-align:center}}
.ad{{font-size:12px;color:#888;letter-spacing:2px}}h1{{font-size:18px;font-weight:600;margin:12px 0}}
p{{font-size:13px;color:#aaa;line-height:1.6}}a{{color:#7aa2ff}}</style>
<meta http-equiv="refresh" content="1.4;url={dest}"></head><body><div class="card">
<div class="ad">(광고)</div><h1>잠시 후 이동합니다</h1>
<p>{disclosure}</p>
<p><a href="{dest}">바로 이동</a> · <a href="/spinads">이 자리에 광고하기</a></p>
</div><script>setTimeout(function(){{location.href="{dest}"}},1400)</script></body></html>"""

@spinads_bp.get("/spinads")
def spinads_landing():
    return """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SpinAds — 개발자의 터미널에 광고를</title>
<style>body{font-family:system-ui,-apple-system,'Noto Sans KR',sans-serif;background:#111;color:#eee;
max-width:560px;margin:0 auto;padding:48px 20px;line-height:1.7}
h1{font-size:26px}h2{font-size:16px;margin-top:36px}p{color:#bbb;font-size:14px}
input,textarea{width:100%;box-sizing:border-box;background:#1c1c1c;border:1px solid #333;color:#eee;
border-radius:8px;padding:10px;margin:6px 0;font-size:14px}
button{background:#7aa2ff;color:#111;border:0;border-radius:8px;padding:12px 20px;font-weight:700;
font-size:14px;cursor:pointer;margin-top:10px}
.mono{font-family:ui-monospace,monospace;background:#1c1c1c;padding:2px 6px;border-radius:4px}
#done{display:none;color:#9f9;font-size:14px}</style></head><body>
<h1>SpinAds</h1>
<p>Claude Code가 생각하는 동안 도는 스피너 — 하루에도 수백 번 개발자의 시선이 머무는 그 한 줄에
광고를 싣습니다. <span class="mono">폭염 속 목에 걸 선풍기 찾는 중… 링크</span> 처럼요.</p>
<h2>왜 이 지면인가</h2>
<p>개발자가 가장 오래, 가장 자주 보는 화면은 터미널입니다. 배너 블라인드가 없는 자리, 세션당 과금,
클릭 트래킹 제공.</p>
<h2>광고 신청</h2>
<form id="f">
<input name="advertiser" placeholder="광고주명 (필수)" required maxlength="60">
<input name="contact" placeholder="연락처 이메일/텔레그램 (필수)" required maxlength="120">
<input name="verb" placeholder="스피너 문구 — 예: OO 개발자 키보드 세일 중… (필수, 40자 이내)" required maxlength="40">
<input name="landing" placeholder="랜딩 URL (선택)" maxlength="300">
<input name="bid" type="number" placeholder="세션당 입찰가 (원, 기본 10)" min="1" value="10">
<input name="budget" type="number" placeholder="총 예산 (원)" min="1000" value="50000">
<button>신청하기</button>
</form>
<p id="done">접수됐습니다. 검토 후 연락처로 게재 안내를 드립니다.</p>
<p style="font-size:12px;color:#666">신청 → 검토·입금 확인 후 게재됩니다. 쿠팡 파트너스 등 제휴 링크
경유 시 관련 고지가 자동 표기됩니다. 문의: ikymximy@kohganemultishop.org</p>
<script>
document.getElementById('f').onsubmit=async function(e){e.preventDefault();
const d=Object.fromEntries(new FormData(this));
const r=await fetch('/api/spinads/apply',{method:'POST',
headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
if(r.ok){this.style.display='none';document.getElementById('done').style.display='block'}
else{alert('접수 실패 — 입력값을 확인해주세요')}};
</script></body></html>"""

@spinads_bp.post("/api/spinads/apply")
def spinads_apply():
    import secrets
    d = request.get_json(silent=True) or {}
    adv = (d.get("advertiser") or "").strip()[:60]
    contact = (d.get("contact") or "").strip()[:120]
    verb = (d.get("verb") or "").strip()[:40]
    landing = (d.get("landing") or "").strip()[:300]
    try:
        bid = max(1, int(d.get("bid") or 10))
        budget = max(1000, int(d.get("budget") or 50000))
    except (TypeError, ValueError):
        return jsonify(error="bad numbers"), 400
    if not adv or not contact or not verb:
        return jsonify(error="missing fields"), 400
    if landing and not landing.startswith(("http://", "https://")):
        return jsonify(error="bad landing url"), 400
    if landing and "{URL}" not in verb:
        verb = verb + " {URL}"
    code = secrets.token_urlsafe(4).lower().replace("_", "a").replace("-", "b")
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("""insert into spinads.campaigns
                (kind, advertiser, advertiser_contact, verb, landing_url, short_code, bid_krw, budget_krw, active)
                values ('direct', %s, %s, %s, %s, %s, %s, %s, false)""",
                (adv, contact, verb, landing or None, code, bid, budget))
    return jsonify(ok=True), 201

@spinads_bp.get("/api/spinads/health")
def spinads_health():
    return jsonify(ok=True, service="spinads", version="v2.1")

# ---- 퍼블리셔 온보딩 (v2.1) ----
from flask import Response
import spinads_assets_v1 as _assets

@spinads_bp.get("/spinads/publish")
def spinads_publish_page():
    return _assets.PUBLISH_HTML

@spinads_bp.post("/api/spinads/publishers/register")
def spinads_publisher_register():
    d = request.get_json(silent=True) or {}
    name = (d.get("name") or "").strip()[:40]
    email = (d.get("email") or "").strip()[:120]
    method = d.get("payout_method") or "toss"
    if not name or not email or "@" not in email:
        return jsonify(error="missing fields"), 400
    if method not in ("toss", "bank_krw", "paypal", "payoneer"):
        method = "toss"
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""insert into spinads.publishers (name, email, payout_method)
                           values (%s,%s,%s) returning id, api_key""", (name, email, method))
            row = cur.fetchone()
    return jsonify(ok=True, publisher_id=str(row["id"]), api_key=row["api_key"]), 201

def _script(text):
    return Response(text, mimetype="text/plain; charset=utf-8")

@spinads_bp.get("/spinads/install.ps1")
def spinads_install_ps1():
    return _script(_assets.INSTALL_PS1)

@spinads_bp.get("/spinads/install.sh")
def spinads_install_sh():
    return _script(_assets.INSTALL_SH)

@spinads_bp.get("/spinads/client.ps1")
def spinads_client_ps1():
    return _script(_assets.CLIENT_PS1)

@spinads_bp.get("/spinads/client.py")
def spinads_client_py():
    return _script(_assets.CLIENT_PY)
