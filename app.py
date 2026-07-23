"""
LinkLynk — 백엔드 API 서버 (멀티테넌트)
- 회원가입/로그인 (세션)
- 유저별 쿠팡 파트너스 키 등록 (암호화 저장)
- 유저 자기 키로 딥링크 생성
- 무료/Pro 사용량 제한
- 링크 히스토리 + 링크인바이오 프로필
"""
import os
import threading
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, session, make_response

from core import CoupangPartners, is_valid_coupang_url, make_blog_draft, COUPANG_DISCLOSURE, unshorten_coupang, is_short_coupang_link, extract_coupang_url, build_naver_html, zernio_publish
import store
from spinads_api_v2 import spinads_bp

app = Flask(__name__, static_folder=".")

# 부팅 직후 트렌드 레이더 미리 채움 → 첫 요청도 대기 0
try:
    from core import warm_radar
    warm_radar()
except Exception:
    pass
app.register_blueprint(spinads_bp)
app.secret_key = os.environ.get("LINKLYNK_SESSION_SECRET", "dev-secret-change-me")
from datetime import timedelta
app.permanent_session_lifetime = timedelta(days=365)  # 로그인 1년 유지 (자동로그인)
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,     # HTTPS(onrender)에서 쿠키 유지
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_REFRESH_EACH_REQUEST=True,  # 매 요청마다 만료 갱신
)

# 폴백 키 비활성화: 개인 파트너스 키로만 API 호출 (공용 키 과다호출 방지)
FALLBACK_ACCESS = os.environ.get("COUPANG_PT_ACCESS", "")
FALLBACK_SECRET = os.environ.get("COUPANG_PT_SECRET", "")

store.init_db()
try:
    store.boim_init()
    store.boim_kit_init()
except Exception:
    pass


def _auto_image(product_name, info=None):
    """상품 이미지 자동 확보 (사람 손 안 가게).
    1) 파트너스 API가 준 이미지 (서버 접근 가능) → 2) 없으면 이미지 검색."""
    img = (info or {}).get("image")
    if img:
        return img
    if not product_name:
        return None
    try:
        from core import search_images
        r = search_images(product_name, limit=1)
        if r.get("ok") and r.get("images"):
            return r["images"][0]["image"]
    except Exception:
        pass
    return None


def _gen_draft(uid, product_name, deeplink, tone, channel, info, provider=None, extra="", quality=False):
    """초안 생성. AI 키 있으면 AI가 직접 작성(사람다움), 없으면 템플릿."""
    if channel == "threads":
        try:
            keys = store.get_llm_keys(uid)
        except Exception:
            keys = {}
        akey = None
        if provider and provider in keys:
            akey = keys[provider]
        elif keys:
            # 선호: gemini > openrouter > anthropic (무료 우선)
            for p in ("gemini", "groq", "openrouter"):   # 유료(anthropic)는 자동 선택 안 함
                if p in keys:
                    akey = keys[p]; break
            if not akey and "anthropic" in keys and provider == "anthropic":
                akey = keys["anthropic"]
        if akey:
            from core import claude_write_thread
            price = (info or {}).get("price")
            # 선택 모델로 시도. 플레이스홀더/실패면 다른 무료 모델로 자동 폴백.
            tried = []
            chain = [akey]
            # 폴백 체인: 선택 모델 → 다른 보유 모델(빠른 순) → llm7(키 없이)
            for fp in ("cerebras", "groq", "gemini", "github", "openrouter"):
                if fp in keys and keys[fp] not in chain:
                    chain.append(keys[fp])
            chain.append("__free__")   # 최후: 키 없이 되는 무료 AI
            for k in chain:
                r = claude_write_thread(k, product_name, deeplink, tone, price, extra=extra, fast=(not quality))
                tried.append(r.get("provider") or "?")
                if r.get("ok") and r.get("content"):
                    # ★플레이스홀더가 최종 결과에 남아있으면 폴백 계속
                    body = r["content"].split("\n===THREAD===\n")[0].strip()
                    if body in ("본문 텍스트", "본글") or "{" in body[:3] or len(body) < 6:
                        continue
                    return r["content"]
    return make_blog_draft(product_name, deeplink, tone, channel, info)


def login_required(f):
    @wraps(f)
    def wrap(*a, **k):
        if not session.get("uid"):
            return jsonify({"ok": False, "error": "로그인이 필요합니다", "need_login": True}), 401
        return f(*a, **k)
    return wrap


def _partners_for(user):
    """유저 본인 파트너스 키로만 딥링크 생성. 키 없으면 None (자동생성 불가)."""
    key = store.get_partners_key(user["id"])
    if key:
        return CoupangPartners(key["access"], key["secret"]), True
    return None, False


@app.route("/")
def home():
    resp = make_response(send_from_directory(".", "index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    resp.headers["CDN-Cache-Control"] = "no-store"
    resp.headers["Surrogate-Control"] = "no-store"
    return resp

@app.route("/app.js")
def appjs():
    resp = make_response(send_from_directory(".", "app.js", mimetype="application/javascript"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

@app.route("/manifest.json")
def manifest():
    return send_from_directory(".", "manifest.json", mimetype="application/json")

@app.route("/sw.js")
def sw():
    return send_from_directory(".", "sw.js", mimetype="application/javascript")

@app.route("/icon-<path:name>")
def icon(name):
    return send_from_directory(".", f"icon-{name}", mimetype="image/png")

@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
def apple_icon():
    return send_from_directory(".", "apple-touch-icon.png", mimetype="image/png")

@app.route("/favicon.ico")
@app.route("/favicon-32.png")
def favicon():
    return send_from_directory(".", "favicon-32.png", mimetype="image/png")

@app.route("/api/health")
def health():
    return jsonify({"ok": True, "service": "LinkLynk"})


@app.route("/api/signup", methods=["POST"])
def signup():
    d = request.get_json(force=True, silent=True) or {}
    email = (d.get("email") or "").strip().lower()
    pw = d.get("password") or ""
    handle = (d.get("handle") or "").strip() or None
    if not email or "@" not in email or len(pw) < 6:
        return jsonify({"ok": False, "error": "이메일과 6자 이상 비밀번호를 입력하세요"}), 400
    r = store.create_user(email, pw, handle=handle)
    if not r["ok"]:
        return jsonify(r), 409
    session.permanent = True
    session["uid"] = r["user_id"]
    return jsonify({"ok": True, "user_id": r["user_id"]})

@app.route("/api/login", methods=["POST"])
def login():
    d = request.get_json(force=True, silent=True) or {}
    u = store.auth_user((d.get("email") or "").strip().lower(), d.get("password") or "")
    if not u:
        return jsonify({"ok": False, "error": "이메일 또는 비밀번호가 올바르지 않습니다"}), 401
    session.permanent = True
    session["uid"] = u["id"]
    return jsonify({"ok": True, "user": {"email": u["email"], "handle": u["handle"], "plan": u["plan"]}})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


# ── 소셜 로그인 (구글/카카오/네이버 OAuth) ──
import urllib.parse as _up, urllib.request as _ur, secrets as _secrets, json, ssl as _ssl_mod

def _oauth_cfg():
    """환경변수에서 OAuth 설정 읽기."""
    base = os.environ.get("OAUTH_REDIRECT_BASE", "https://linklynk.onrender.com")
    return {
        "google": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "auth": "https://accounts.google.com/o/oauth2/v2/auth",
            "token": "https://oauth2.googleapis.com/token",
            "userinfo": "https://www.googleapis.com/oauth2/v2/userinfo",
            "scope": "openid email profile",
            "redirect": f"{base}/auth/google/callback",
        },
        "kakao": {
            "client_id": os.environ.get("KAKAO_CLIENT_ID", ""),
            "client_secret": os.environ.get("KAKAO_CLIENT_SECRET", ""),
            "auth": "https://kauth.kakao.com/oauth/authorize",
            "token": "https://kauth.kakao.com/oauth/token",
            "userinfo": "https://kapi.kakao.com/v2/user/me",
            "scope": "account_email",
            "redirect": f"{base}/auth/kakao/callback",
        },
        "naver": {
            "client_id": os.environ.get("NAVER_CLIENT_ID", ""),
            "client_secret": os.environ.get("NAVER_CLIENT_SECRET", ""),
            "auth": "https://nid.naver.com/oauth2.0/authorize",
            "token": "https://nid.naver.com/oauth2.0/token",
            "userinfo": "https://openapi.naver.com/v1/nid/me",
            "scope": "",
            "redirect": f"{base}/auth/naver/callback",
        },
    }


@app.route("/auth/<provider>/login")
def oauth_login(provider):
    cfg = _oauth_cfg().get(provider)
    if not cfg or not cfg["client_id"]:
        return f"{provider} 로그인이 아직 설정되지 않았어요 (관리자: 환경변수 확인)", 503
    state = _secrets.token_urlsafe(16)
    session["oauth_state"] = state
    session["oauth_provider"] = provider
    params = {
        "client_id": cfg["client_id"], "redirect_uri": cfg["redirect"],
        "response_type": "code", "state": state,
    }
    if cfg["scope"]:
        params["scope"] = cfg["scope"]
    from flask import redirect
    return redirect(cfg["auth"] + "?" + _up.urlencode(params))


@app.route("/auth/<provider>/callback")
def oauth_callback(provider):
    from flask import redirect
    cfg = _oauth_cfg().get(provider)
    if not cfg:
        return "알 수 없는 로그인 제공자", 400
    if request.args.get("state") != session.get("oauth_state"):
        return redirect("/?login_error=state")
    code = request.args.get("code")
    if not code:
        return redirect("/?login_error=nocode")
    try:
        _ctx = _ssl_mod.create_default_context()
        # 1) code → access_token
        tok_data = _up.urlencode({
            "grant_type": "authorization_code",
            "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
            "redirect_uri": cfg["redirect"], "code": code,
            "state": request.args.get("state", ""),
        }).encode()
        treq = _ur.Request(cfg["token"], data=tok_data,
                           headers={"Content-Type": "application/x-www-form-urlencoded",
                                    "Accept": "application/json"}, method="POST")
        tok = json.loads(_ur.urlopen(treq, timeout=15, context=_ctx).read())
        access = tok.get("access_token")
        if not access:
            return redirect("/?login_error=token")
        # 2) access_token → 유저 이메일
        ureq = _ur.Request(cfg["userinfo"], headers={"Authorization": f"Bearer {access}"})
        uinfo = json.loads(_ur.urlopen(ureq, timeout=15, context=_ctx).read())
        email, name = _extract_oauth_email(provider, uinfo)
        if not email:
            return redirect("/?login_error=noemail")
        # ★이미 로그인 중이면 → 현재 계정에 이 소셜 이메일을 연결 (계정 통합)
        if session.get("uid"):
            store.link_email(session["uid"], email)
            return redirect("/?linked=1")
        # 3) 유저 생성/로그인 (연결된 이메일도 확인)
        u = store.get_or_create_oauth_user(email, provider, display_name=name)
        if not u:
            return redirect("/?login_error=create")
        session.permanent = True
        session["uid"] = u["id"]
        return redirect("/")
    except Exception as e:
        import traceback; traceback.print_exc()
        return redirect("/?login_error=" + _up.quote(str(e)[:80]))


def _extract_oauth_email(provider, uinfo):
    """제공자별 응답에서 이메일·이름 추출."""
    if provider == "google":
        return uinfo.get("email"), uinfo.get("name")
    if provider == "kakao":
        acc = uinfo.get("kakao_account", {})
        prof = acc.get("profile", {})
        return acc.get("email"), prof.get("nickname")
    if provider == "naver":
        r = uinfo.get("response", {})
        return r.get("email"), r.get("name") or r.get("nickname")
    return None, None


@app.route("/api/oauth-status")
def oauth_status():
    """어떤 소셜 로그인이 설정됐는지 (버튼 표시용)."""
    cfg = _oauth_cfg()
    return jsonify({p: bool(c["client_id"]) for p, c in cfg.items()})

@app.route("/api/me")
@login_required
def me():
    u = store.get_user(session["uid"])
    key = store.get_partners_key(u["id"])
    usage = store.get_usage(u["id"])
    sns = store.get_zernio_key(u["id"])
    llm_keys = store.get_llm_keys(u["id"])
    return jsonify({"ok": True, "email": u["email"], "handle": u["handle"],
                    "plan": u["plan"], "has_key": bool(key), "has_sns": bool(sns),
                    "has_claude": bool(llm_keys), "llm_providers": list(llm_keys.keys()),
                    "usage": usage, "limits": store.FREE_LIMITS})


@app.route("/api/sns-key", methods=["POST"])
@login_required
def save_sns_key():
    d = request.get_json(force=True, silent=True) or {}
    key = (d.get("key") or "").strip()
    if not key:
        return jsonify({"ok": False, "error": "키를 입력하세요"}), 400
    store.save_zernio_key(session["uid"], key)
    return jsonify({"ok": True, "message": "SNS 자동 게시가 연결됐어요"})


@app.route("/api/search-images", methods=["POST"])
@login_required
def search_images_api():
    """키워드로 상품 이미지 검색 (쿠팡 크롤 없이 무료)."""
    d = request.get_json(force=True, silent=True) or {}
    keyword = (d.get("keyword") or "").strip()
    if not keyword:
        return jsonify({"ok": False, "error": "검색어를 입력하세요"}), 400
    from core import search_images
    r = search_images(keyword, limit=12)
    if r.get("ok"):
        return jsonify({"ok": True, "images": r["images"]})
    return jsonify({"ok": False, "error": "이미지를 찾지 못했어요", "detail": r.get("error", "")}), 200


@app.route("/img-proxy")
@login_required
def img_proxy():
    """쿠팡 이미지 프록시. 이미지 CDN은 서버 접근 가능하므로 우리 서버가 받아서 전달.
    유저 브라우저에서 CORS 없이 쿠팡 이미지 사용 가능."""
    import urllib.request as _u, ssl as _s
    url = request.args.get("u", "")
    if not url.startswith("http"):
        return "", 400
    try:
        ctx = _s.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=_s.CERT_NONE
        req = _u.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.coupang.com/"})
        with _u.urlopen(req, timeout=15, context=ctx) as r:
            data = r.read()
            ct = r.headers.get("Content-Type", "image/jpeg")
        from flask import Response
        resp = Response(data, content_type=ct)
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp
    except Exception:
        return "", 502


@app.route("/api/coupang-images", methods=["POST"])
@login_required
def coupang_images_api():
    """유저 브라우저(북마클릿)가 쿠팡 상품페이지에서 긁은 상세 이미지 URL들 수신.
    ★서버가 쿠팡에 접근하는 게 아니라 유저 브라우저가 긁으므로 Akamai 차단 없음."""
    d = request.get_json(force=True, silent=True) or {}
    images = d.get("images") or []
    product_name = (d.get("productName") or "").strip()
    # 이미지 URL만 필터 (쿠팡 이미지 도메인)
    valid = [u for u in images if isinstance(u, str) and u.startswith("http")
             and any(dom in u for dom in ["coupangcdn.com", "coupang.com", "pstatic", "image"])]
    if not valid:
        return jsonify({"ok": False, "error": "이미지를 찾지 못했어요"}), 400
    # 최근 검색결과에 이미지 붙여서 세션에 임시 저장 (초안 생성 시 사용)
    return jsonify({"ok": True, "count": len(valid), "images": valid[:20],
                    "product_name": product_name})


@app.route("/api/anthropic-key", methods=["POST"])
@login_required
def save_anthropic_key_api():
    d = request.get_json(force=True, silent=True) or {}
    key = (d.get("key") or "").strip()
    if not key:
        return jsonify({"ok": False, "error": "키를 입력하세요"}), 400
    from core import detect_llm_provider
    p = detect_llm_provider(key)
    if p in ("unknown", "llm7"):
        return jsonify({"ok": False, "error": "키 형식을 인식할 수 없어요. "
                        "AIza…(Gemini) / gsk_…(Groq) / csk-…(Cerebras) / nvapi-…(NVIDIA) / "
                        "ghp_…(GitHub) / sk-or-…(OpenRouter) / sk-ant-…(Claude)"}), 400
    store.save_llm_key(session["uid"], p, key)
    if p == "anthropic":
        store.save_anthropic_key(session["uid"], key)   # 하위호환
    names = {"gemini": "Google Gemini (무료)", "openrouter": "OpenRouter (무료)",
             "groq": "Groq (무료)", "cerebras": "Cerebras (무료·최고속)",
             "nvidia": "NVIDIA NIM (무료)", "github": "GitHub Models (무료)",
             "zai": "Z.AI GLM (무료)", "anthropic": "Claude"}
    return jsonify({"ok": True, "provider": p,
                    "message": f"{names.get(p, p)} 연결됐어요"})


@app.route("/api/research", methods=["POST"])
@login_required
def research_api():
    """상품 특징 후보 (검색 결과 스니펫)."""
    d = request.get_json(force=True, silent=True) or {}
    name = (d.get("productName") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "상품명이 없어요"}), 400
    from core import naver_research
    items = naver_research(name, limit=6)
    return jsonify({"ok": True, "items": items})


# ══════════ 보임(BOIM) — AI 검색 노출 진단 (공개) ══════════
import uuid as _uuid

@app.route("/boim")
def boim_landing():
    return app.send_static_file("boim.html")


@app.route("/boim/r/<scan_id>")
def boim_report_page(scan_id):
    return app.send_static_file("boim.html")


@app.route("/api/boim/scan", methods=["POST"])
def boim_scan_start():
    """공개 진단 시작 — 로그인 불필요. IP당 하루 3회."""
    d = request.get_json(force=True, silent=True) or {}
    store_name = (d.get("store") or "").strip()[:40]
    kws = [k.strip()[:20] for k in (d.get("keywords") or []) if k and k.strip()][:3]
    if not store_name or not kws:
        return jsonify({"ok": False, "error": "스토어 이름과 업종 키워드(1개 이상)가 필요해요"}), 400
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "?").split(",")[0].strip()
    if store.boim_recent_by_ip(ip, 24) >= 3:
        return jsonify({"ok": False,
                        "error": "무료 진단은 하루 3회까지예요. 내일 다시 시도해주세요."}), 429

    scan_id = _uuid.uuid4().hex[:12]
    store.boim_create(scan_id, store_name, kws, ip)

    def _run():
        try:
            import boim as _boim
            r = _boim.run_scan("__free__", store_name, kws,
                               aliases=[a.strip() for a in (d.get("aliases") or []) if a.strip()][:3])
            store.boim_finish(scan_id, result=r)
        except Exception as e:
            store.boim_finish(scan_id, error=str(e))

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "scan_id": scan_id})


@app.route("/boim/pay/success")
@app.route("/boim/pay/fail")
def boim_pay_pages():
    return app.send_static_file("boim.html")


@app.route("/boim-manifest.json")
def boim_manifest():
    return send_from_directory(".", "boim-manifest.json", mimetype="application/manifest+json")


@app.route("/boim-icon-<size>.png")
def boim_icon(size):
    return send_from_directory(".", f"boim-icon-{size}.png", mimetype="image/png")


@app.route("/api/boim/pay/config")
def boim_pay_config():
    """토스 클라이언트 키 — Render 환경변수 TOSS_CLIENT_KEY."""
    ck = os.environ.get("TOSS_CLIENT_KEY", "").strip()
    if not ck:
        return jsonify({"ok": False,
                        "error": "결제 설정이 아직 안 됐어요 (TOSS_CLIENT_KEY 미설정)"}), 200
    return jsonify({"ok": True, "client_key": ck})


@app.route("/api/boim/pay/confirm", methods=["POST"])
def boim_pay_confirm():
    """토스 결제 승인 — 시크릿 키로 서버에서 확정. 금액 검증 필수."""
    import base64
    import urllib.request as _ur
    sk = os.environ.get("TOSS_SECRET_KEY", "").strip()
    if not sk:
        return jsonify({"ok": False, "error": "TOSS_SECRET_KEY 미설정"}), 500
    d = request.get_json(force=True, silent=True) or {}
    payment_key = (d.get("paymentKey") or "").strip()
    order_id = (d.get("orderId") or "").strip()
    amount = int(d.get("amount") or 0)
    if not payment_key or not order_id or amount <= 0:
        return jsonify({"ok": False, "error": "결제 정보가 불완전해요"}), 400
    # ★금액 위조 방지: 우리 가격표와 대조
    plan = "boost" if order_id.startswith("boim_boost") else            "watch" if order_id.startswith("boim_watch") else None
    PRICES = {"watch": 9900, "boost": 29900}
    if not plan or PRICES[plan] != amount:
        return jsonify({"ok": False, "error": "금액이 상품 가격과 달라요"}), 400
    # 토스 승인 API
    auth = base64.b64encode((sk + ":").encode()).decode()
    body = json.dumps({"paymentKey": payment_key, "orderId": order_id,
                       "amount": amount}).encode()
    req = _ur.Request("https://api.tosspayments.com/v1/payments/confirm",
                      data=body, method="POST",
                      headers={"Authorization": "Basic " + auth,
                               "Content-Type": "application/json"})
    try:
        raw = _ur.urlopen(req, timeout=15).read().decode()
        pr = json.loads(raw)
    except Exception as e:
        detail = ""
        try:
            detail = e.read().decode()[:300]      # HTTPError body
        except Exception:
            detail = str(e)[:200]
        return jsonify({"ok": False, "error": "토스 승인 실패", "detail": detail}), 400
    if pr.get("status") != "DONE":
        return jsonify({"ok": False, "error": f"승인 상태: {pr.get('status')}"}), 400
    # 주문 저장
    try:
        store._q("""CREATE TABLE IF NOT EXISTS linklynk_boim_orders (
            order_id TEXT PRIMARY KEY, payment_key TEXT, plan TEXT,
            amount INTEGER, status TEXT, scan_id TEXT, created_at BIGINT)""")
        scan_ref = order_id.split("_")[2] if order_id.count("_") >= 3 else ""
        store._q("""INSERT INTO linklynk_boim_orders
                    (order_id, payment_key, plan, amount, status, scan_id, created_at)
                    VALUES (%s,%s,%s,%s,'paid',%s,%s)
                    ON CONFLICT (order_id) DO NOTHING""",
                 (order_id, payment_key, plan, amount, scan_ref,
                  int(__import__("time").time())))
    except Exception:
        pass
    return jsonify({"ok": True, "plan": plan})


@app.route("/boim/kit/<order_id>")
def boim_kit_page(order_id):
    return app.send_static_file("boim.html")


@app.route("/api/boim/order/<order_id>")
def boim_order_api(order_id):
    """주문 확인 — 키트 접근 권한."""
    o = store.boim_order_get(order_id)
    if not o or o.get("status") != "paid":
        return jsonify({"ok": False, "error": "결제 내역을 찾을 수 없어요"}), 404
    kit = store.boim_kit_get(order_id)
    return jsonify({"ok": True, "plan": o.get("plan"),
                    "kit_status": (kit or {}).get("status"),
                    "kit_request": (kit or {}).get("request")})


@app.route("/api/boim/kit/<order_id>", methods=["POST"])
def boim_kit_start_api(order_id):
    o = store.boim_order_get(order_id)
    if not o or o.get("status") != "paid":
        return jsonify({"ok": False, "error": "결제 내역을 찾을 수 없어요"}), 404
    if o.get("plan") != "boost":
        return jsonify({"ok": False, "error": "실행 키트는 부스트 플랜 전용이에요"}), 403
    d = request.get_json(force=True, silent=True) or {}
    store_name = (d.get("store") or "").strip()[:40]
    kws = [k.strip()[:20] for k in (d.get("keywords") or []) if k.strip()][:3]
    products = [x.strip()[:60] for x in (d.get("products") or []) if x.strip()][:3]
    if not store_name or not products:
        return jsonify({"ok": False, "error": "스토어 이름과 상품 1개 이상이 필요해요"}), 400
    store.boim_kit_start(order_id, {"store": store_name, "keywords": kws,
                                    "products": products})

    def _run():
        try:
            import boim as _boim
            key = os.environ.get("BOIM_LLM_KEY", "").strip() or "__free__"
            r = _boim.run_kit(key, store_name, kws or ["쇼핑"], products)
            if not r.get("ok") and key != "__free__":
                r = _boim.run_kit("__free__", store_name, kws or ["쇼핑"], products)
            if r.get("ok"):
                store.boim_kit_finish(order_id, result=r)
            else:
                store.boim_kit_finish(order_id, error=r.get("error"))
        except Exception as e:
            store.boim_kit_finish(order_id, error=str(e))

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/boim/kit/<order_id>/result")
def boim_kit_result_api(order_id):
    kit = store.boim_kit_get(order_id)
    if not kit:
        return jsonify({"ok": False, "error": "아직 생성 요청이 없어요"}), 404
    return jsonify({"ok": True, **kit})


@app.route("/api/boim/teaser", methods=["POST"])
def boim_teaser_api():
    """★무료 맛보기 — 진단당 1회. FAQ 3문답 공개 + 7개 잠금."""
    d = request.get_json(force=True, silent=True) or {}
    scan_id = (d.get("scan_id") or "").strip()[:20]
    product = (d.get("product") or "").strip()[:60]
    if not scan_id or not product:
        return jsonify({"ok": False, "error": "상품 이름을 넣어주세요"}), 400
    scan = store.boim_get(scan_id)
    if not scan or scan.get("status") != "done":
        return jsonify({"ok": False, "error": "진단을 먼저 완료해주세요"}), 404
    tid = "teaser_" + scan_id
    exist = store.boim_kit_get(tid)
    if exist and exist.get("status") == "done":
        return jsonify({"ok": True, "teaser": exist.get("result"), "cached": True})
    if exist and exist.get("status") == "running":
        return jsonify({"ok": True, "running": True})
    store.boim_kit_start(tid, {"product": product})

    def _run():
        try:
            import boim as _boim
            key = os.environ.get("BOIM_LLM_KEY", "").strip() or "__free__"
            t = _boim.build_teaser(key, scan.get("store") or "", product,
                                   scan.get("keywords") or [])
            if not t and key != "__free__":
                t = _boim.build_teaser("__free__", scan.get("store") or "", product,
                                       scan.get("keywords") or [])
            if t:
                store.boim_kit_finish(tid, result=t)
            else:
                store.boim_kit_finish(tid, error="생성 실패")
        except Exception as e:
            store.boim_kit_finish(tid, error=str(e))

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True, "running": True})


@app.route("/api/boim/teaser/<scan_id>")
def boim_teaser_get(scan_id):
    k = store.boim_kit_get("teaser_" + scan_id)
    if not k:
        return jsonify({"ok": False}), 404
    return jsonify({"ok": True, "status": k.get("status"),
                    "teaser": k.get("result"), "error": k.get("error")})


@app.route("/api/boim/history")
def boim_history_api():
    st = (request.args.get("store") or "").strip()[:40]
    if not st:
        return jsonify({"ok": False}), 400
    return jsonify({"ok": True, "items": store.boim_history(st)})


@app.route("/api/boim/llmdiag")
def boim_llmdiag():
    """서버 BOIM_LLM_KEY 검진 — 구글 모델 리스트 API로 키 유효성 직접 확인.
    보안: 크론 키 필요. 키 값은 절대 노출하지 않고 형태 정보만."""
    ck = os.environ.get("BOIM_CRON_KEY", "").strip()
    if not ck or request.args.get("key") != ck:
        return jsonify({"ok": False}), 403
    import urllib.request as _ur
    import re as _re
    raw = os.environ.get("BOIM_LLM_KEY", "")
    clean = _re.sub(r"[^\x21-\x7E]", "", raw)
    info = {
        "len_raw": len(raw), "len_clean": len(clean),
        "prefix": clean[:6], "suffix_len4": clean[-4:] if len(clean) >= 4 else "",
        "had_invisible": len(raw) != len(clean),
    }
    try:
        u = f"https://generativelanguage.googleapis.com/v1beta/models?key={clean}&pageSize=3"
        with _ur.urlopen(u, timeout=12) as r:
            data = json.loads(r.read().decode())
        info["google"] = "OK"
        info["models"] = [m.get("name") for m in data.get("models", [])][:3]
        # generateContent 페이로드 이등분 탐색 — 어느 필드가 400을 내는가
        tests = {
            "bare": {"contents": [{"parts": [{"text": "안녕"}]}]},
            "sys": {"systemInstruction": {"parts": [{"text": "한 단어로 답해"}]},
                    "contents": [{"parts": [{"text": "안녕"}]}]},
            "cfg": {"contents": [{"parts": [{"text": "안녕"}]}],
                    "generationConfig": {"temperature": 1.0, "maxOutputTokens": 1500}},
            "think": {"contents": [{"parts": [{"text": "안녕"}]}],
                      "generationConfig": {"maxOutputTokens": 1500,
                                           "thinkingConfig": {"thinkingBudget": 0}}},
        }
        gen = {}
        for name, pl in tests.items():
            try:
                gu = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={clean}"
                gr = _ur.Request(gu, data=json.dumps(pl).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
                with _ur.urlopen(gr, timeout=15) as rr:
                    json.loads(rr.read().decode())
                gen[name] = "OK"
            except Exception as ee:
                b = ""
                try:
                    b = ee.read().decode()[:150]
                except Exception:
                    b = str(ee)[:100]
                gen[name] = b
        info["generate"] = gen
    except Exception as e:
        body = ""
        try:
            body = e.read().decode()[:400]
        except Exception:
            body = str(e)[:200]
        info["google"] = "FAIL"
        info["error"] = body
    return jsonify(info)


@app.route("/api/boim/cron/weekly", methods=["POST", "GET"])
def boim_cron_weekly():
    """주간 재측정 — 유효 이용권(30일) 스토어 재스캔. Bluehost 크론이 호출.
    보안: BOIM_CRON_KEY 환경변수와 일치해야 실행."""
    ck = os.environ.get("BOIM_CRON_KEY", "").strip()
    if not ck or request.args.get("key") != ck:
        return jsonify({"ok": False}), 403
    orders = store.boim_paid_orders_active(30)
    started = []
    for o in orders:
        ref = (o.get("scan_id") or "").strip()
        # scan_id 앞 8자만 저장돼 있으므로 원본 스캔을 prefix로 찾는다
        row = store._q("""SELECT * FROM linklynk_boim_scans
                          WHERE id LIKE %s AND status='done'
                          ORDER BY created_at ASC LIMIT 1""",
                       (ref + "%",), fetch="one")
        if not row:
            continue
        try:
            kws = json.loads(row.get("keywords") or "[]")
        except Exception:
            kws = []
        if not kws:
            continue
        import uuid as _u
        new_id = _u.uuid4().hex[:12]
        store.boim_create(new_id, row["store"], kws, "cron")

        def _run(nid=new_id, st=row["store"], kk=kws):
            try:
                import boim as _boim
                key = os.environ.get("BOIM_LLM_KEY", "").strip() or "__free__"
                r = _boim.run_scan(key, st, kk)
                store.boim_finish(nid, result=r)
            except Exception as e:
                store.boim_finish(nid, error=str(e))

        threading.Thread(target=_run, daemon=True).start()
        started.append({"store": row["store"], "scan_id": new_id})
    return jsonify({"ok": True, "started": started})


# ══════════ 선물레이더 — 앱인토스 미니앱 (공개) ══════════
_GIFT_IP = {}

@app.route("/gift")
def gift_page():
    return app.send_static_file("gift.html")


@app.route("/api/gift/reco", methods=["POST", "OPTIONS"])
def gift_reco_api():
    if request.method == "OPTIONS":
        resp = make_response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp
    """선물 추천 — IP당 하루 10회."""
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "?").split(",")[0].strip()
    import time as _t
    now = int(_t.time())
    hist = [t for t in _GIFT_IP.get(ip, []) if now - t < 86400]
    if len(hist) >= 10:
        return jsonify({"ok": False, "error": "오늘 추천 횟수를 다 썼어요. 내일 다시 만나요!"}), 429
    d = request.get_json(force=True, silent=True) or {}
    who = (d.get("who") or "").strip()[:30]
    budget = (d.get("budget") or "").strip()[:20]
    taste = (d.get("taste") or "").strip()[:80]
    if not who or not budget:
        return jsonify({"ok": False, "error": "받는 사람과 예산을 알려주세요"}), 400
    import gift as _gift
    key = os.environ.get("BOIM_LLM_KEY", "").strip() or "__free__"
    r = _gift.recommend(key, who, budget, taste)
    key_err = None
    if not r.get("ok") and key != "__free__":
        key_err = (r.get("detail") or r.get("error") or "")[:500]
        r = _gift.recommend("__free__", who, budget, taste)   # 키 죽어도 서비스는 산다
    if key_err:
        r["key_err"] = key_err
    if r.get("ok"):
        hist.append(now)
        _GIFT_IP[ip] = hist
    resp = jsonify(r)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/boim/waitlist", methods=["POST"])
def boim_waitlist():
    d = request.get_json(force=True, silent=True) or {}
    em = (d.get("email") or "").strip()[:120]
    if "@" not in em:
        return jsonify({"ok": False}), 400
    try:
        store._q("""CREATE TABLE IF NOT EXISTS linklynk_boim_waitlist
                    (email TEXT PRIMARY KEY, created_at BIGINT)""")
        store._q("""INSERT INTO linklynk_boim_waitlist (email, created_at)
                    VALUES (%s,%s) ON CONFLICT (email) DO NOTHING""",
                 (em, int(__import__("time").time())))
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/api/boim/scan/<scan_id>")
def boim_scan_get(scan_id):
    r = store.boim_get(scan_id)
    if not r:
        return jsonify({"ok": False, "error": "없는 진단이에요"}), 404
    return jsonify({"ok": True, **r})


@app.route("/api/naver-keys", methods=["GET", "POST", "DELETE"])
@login_required
def naver_keys_api():
    """네이버 데이터랩 자격증명 (무료). 쇼핑인사이트=구매의도 축."""
    uid = session["uid"]
    if request.method == "GET":
        k = store.get_naver_keys(uid)
        if not k:
            return jsonify({"ok": True, "connected": False})
        cid = k["client_id"]
        return jsonify({"ok": True, "connected": True,
                        "masked": (cid[:4] + "•" * 6 + cid[-3:]) if len(cid) > 8 else "•" * len(cid)})
    if request.method == "DELETE":
        store.delete_naver_keys(uid)
        return jsonify({"ok": True, "message": "네이버 연결을 끊었어요"})
    d = request.get_json(force=True, silent=True) or {}
    cid = (d.get("client_id") or "").strip()
    csec = (d.get("client_secret") or "").strip()
    if not cid or not csec:
        return jsonify({"ok": False, "error": "Client ID와 Secret 둘 다 필요해요"}), 400
    # 실제로 되는 키인지 검증
    from core import naver_keyword_trend
    t = naver_keyword_trend(cid, csec, ["선풍기"], days=14)
    if not t.get("ok"):
        raw = str(t.get("detail") or t.get("error") or "")
        # 네이버가 준 실제 사유를 사람 말로 번역
        if "024" in raw or "Authentication failed" in raw or "401" in raw:
            msg = "Client ID 또는 Secret이 틀렸어요. 개발자센터에서 다시 복사해주세요(앞뒤 공백 주의)."
        elif "028" in raw or "no_permission" in raw or "403" in raw:
            msg = ("이 앱에 '데이터랩' 권한이 없어요. 개발자센터 > 내 애플리케이션 > API 설정에서 "
                   "'데이터랩(검색어트렌드)'을 추가하고 저장한 뒤 다시 시도해주세요.")
        elif "012" in raw or "Not Exist" in raw:
            msg = "등록되지 않은 애플리케이션이에요. Client ID를 확인해주세요."
        else:
            msg = "네이버 연결에 실패했어요."
        return jsonify({"ok": False, "error": msg, "detail": raw[:300]}), 400
    store.save_naver_keys(uid, cid, csec)
    return jsonify({"ok": True, "message": "네이버 데이터랩 연결됐어요 ✅"})


@app.route("/api/shopping-rising")
@login_required
def shopping_rising_api():
    """★구매의도 축 — 네이버 쇼핑에서 지금 급등한 검색어."""
    k = store.get_naver_keys(session["uid"])
    if not k:
        return jsonify({"ok": False, "need_naver": True,
                        "error": "네이버 데이터랩을 연결하면 '실제로 사는 사람들'의 급등 키워드를 봐요"}), 200
    from core import naver_shopping_rising
    force = request.args.get("refresh") == "1"
    if force:
        from core import _NAVER_CACHE
        _NAVER_CACHE["items"] = []; _NAVER_CACHE["at"] = 0
    r = naver_shopping_rising(k["client_id"], k["client_secret"],
                              days=int(request.args.get("days", 21)))
    return jsonify(r)


@app.route("/api/keyword-verdict", methods=["POST"])
@login_required
def keyword_verdict_api():
    """이 키워드가 지금 뜨는지 지는지 — 상품 고르기 전 확인."""
    k = store.get_naver_keys(session["uid"])
    if not k:
        return jsonify({"ok": False, "need_naver": True}), 200
    d = request.get_json(force=True, silent=True) or {}
    kws = [x for x in (d.get("keywords") or []) if x][:5]
    if not kws:
        return jsonify({"ok": False, "error": "키워드가 필요해요"}), 400
    from core import naver_keyword_trend
    return jsonify(naver_keyword_trend(k["client_id"], k["client_secret"], kws))


@app.route("/api/trend-radar")
@login_required
def trend_radar():
    """지금 뜨는 주제 레이더 (Google Trends + 계절 신호). 무료·키 불필요."""
    from core import fetch_trend_radar
    force = request.args.get("refresh") == "1"
    items = fetch_trend_radar(force=force)
    rng = request.args.get("range", "24시간")   # 표시용(트렌드 RSS는 실시간 기준)
    cat = request.args.get("cat")
    if cat and cat not in ("추천", "전체"):
        items = [i for i in items if i.get("cat") == cat]
    elif cat == "추천":
        items = [i for i in items if i.get("kind") == "season" or i.get("related")]
    return jsonify({"ok": True, "items": items[:12]})


@app.route("/api/llm-list")
@login_required
def llm_list():
    """등록된 AI 목록 (글쓰기 툴 선택·비교용)."""
    keys = store.get_llm_keys(session["uid"])
    keys["llm7"] = "__free__"          # 키 없이 쓰는 무료 AI (항상 사용 가능)
    names = {
        "llm7":       "무료 AI (키 없이) ✨",
        "cerebras":   "Cerebras (무료) ⚡⚡",
        "groq":       "Groq (무료) ⚡",
        "gemini":     "Gemini (무료)",
        "github":     "GitHub Models (무료)",
        "nvidia":     "NVIDIA (무료)",
        "zai":        "Z.AI GLM (무료)",
        "openrouter": "OpenRouter (무료·느림)",
        "anthropic":  "Claude",
    }
    # 빠른 순 → 느린 순. 키 없이 쓰는 무료 AI는 항상 제공한다.
    order = ["llm7", "cerebras", "groq", "gemini", "github", "nvidia", "zai", "openrouter", "anthropic"]
    have = set(keys) | {"llm7"}
    usable = [p for p in order if p in have]

    vis = store.get_llm_visible(session["uid"])          # None = 전부 보임
    shown = [p for p in usable if (vis is None or p in vis)] or usable[:1]

    return jsonify({
        "ok": True,
        "providers": [{"id": p, "name": names[p]} for p in shown],
        # 설정 화면용: 쓸 수 있는 전부 + 지금 켜져 있는 것
        "all": [{"id": p, "name": names[p], "on": (vis is None or p in vis)} for p in usable],
    })


@app.route("/api/job/<job_id>", methods=["GET"])
@login_required
def job_status_api(job_id):
    j = store.job_get(job_id, session["uid"])
    if not j:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "status": j["status"], "kind": j["kind"],
                    "result": j.get("result"), "error": j.get("error")})


@app.route("/api/jobs", methods=["GET"])
@login_required
def jobs_list_api():
    """앱을 다시 열었을 때: 돌고 있던 작업과 끝난 결과를 되찾아온다."""
    return jsonify({"ok": True, "jobs": store.jobs_recent(session["uid"])})


def _run_view_job(job_id, uid, view_fn, payload):
    """★서버 스레드에서 라우트를 그대로 실행한다.
    브라우저를 닫든 앱을 나가든 서버는 계속 돌린다. 돌아오면 결과가 기다린다."""
    def work():
        try:
            with app.test_request_context(json=payload, method="POST"):
                session["uid"] = uid
                rv = view_fn()
                if isinstance(rv, tuple):
                    rv = rv[0]
                data = rv.get_json()
            if data and data.get("ok"):
                store.job_finish(job_id, result=data)
            else:
                store.job_finish(job_id, error=(data or {}).get("error") or "실패")
        except Exception as e:
            store.job_finish(job_id, error=e)
    threading.Thread(target=work, daemon=True).start()
    return job_id


@app.route("/api/job/start", methods=["POST"])
@login_required
def job_start_api():
    """무거운 작업은 전부 여기로. 즉시 job_id만 돌려주고 서버가 뒤에서 돌린다."""
    import uuid as _uuid
    d = request.get_json(force=True, silent=True) or {}
    kind = d.get("kind")
    payload = d.get("params") or {}
    VIEWS = {"topics": claude_topics_api, "write": generate_manual}
    fn = VIEWS.get(kind)
    if not fn:
        return jsonify({"ok": False, "error": "unknown_kind"}), 400
    jid = f"{kind}-{_uuid.uuid4().hex[:12]}"
    store.job_create(jid, session["uid"], kind, payload)
    _run_view_job(jid, session["uid"], fn, payload)
    return jsonify({"ok": True, "job_id": jid})


LLM_NAMES = {
    "llm7":       "무료 AI (키 없이)",
    "cerebras":   "Cerebras",
    "groq":       "Groq",
    "gemini":     "Google Gemini",
    "github":     "GitHub Models",
    "nvidia":     "NVIDIA NIM",
    "zai":        "Z.AI (GLM)",
    "openrouter": "OpenRouter",
    "anthropic":  "Claude",
}
LLM_ORDER = ["cerebras", "groq", "gemini", "github", "nvidia", "zai", "openrouter", "anthropic"]
LLM_HINT = {
    "cerebras":   ("csk-…",  "cloud.cerebras.ai",                    "가장 빠름 · 초당 ~2,600토큰"),
    "groq":       ("gsk_…",  "console.groq.com/keys",                "빠름 · Llama 3.3 70B"),
    "gemini":     ("AIza…",  "aistudio.google.com/apikey",           "무료 · 카드 불필요"),
    "github":     ("ghp_…",  "github.com/settings/tokens",           "깃허브 계정만 있으면 무료"),
    "nvidia":     ("nvapi-…","build.nvidia.com",                     "일일 한도 없음"),
    "zai":        ("xxx.yyy","open.bigmodel.cn/usercenter/apikeys",  "GLM Flash 영구 무료"),
    "openrouter": ("sk-or-…","openrouter.ai/keys",                   "무료 모델은 큐 대기 (느림)"),
    "anthropic":  ("sk-ant-…","console.anthropic.com",               "유료 · 품질 최고"),
}


def _mask(k):
    k = k or ""
    if len(k) <= 10:
        return "•" * len(k)
    return k[:6] + "•" * 6 + k[-4:]


@app.route("/api/llm-keys", methods=["GET"])
@login_required
def llm_keys_api():
    """어떤 AI에 키가 들어가 있는지, 안 들어간 건 뭔지 한눈에."""
    keys = store.get_llm_keys(session["uid"])
    connected, available = [], []
    for p in LLM_ORDER:
        ph, url, note = LLM_HINT[p]
        row = {"id": p, "name": LLM_NAMES[p], "placeholder": ph, "url": url, "note": note}
        if p in keys:
            row["masked"] = _mask(keys[p])
            connected.append(row)
        else:
            available.append(row)
    return jsonify({"ok": True, "connected": connected, "available": available})


@app.route("/api/llm-key/<provider>", methods=["DELETE"])
@login_required
def llm_key_delete_api(provider):
    if provider not in LLM_ORDER:
        return jsonify({"ok": False, "error": "unknown_provider"}), 400
    store.delete_llm_key(session["uid"], provider)
    return jsonify({"ok": True, "message": f"{LLM_NAMES[provider]} 연결을 끊었어요"})


@app.route("/api/llm-visible", methods=["POST"])
@login_required
def llm_visible_api():
    """어떤 AI 도구를 목록에 보이게 할지 사용자가 직접 정한다."""
    d = request.get_json(force=True, silent=True) or {}
    ids = d.get("ids")
    if not isinstance(ids, list) or not ids:
        return jsonify({"ok": False, "error": "최소 한 개는 켜두세요."}), 400
    allowed = {"llm7", "cerebras", "groq", "gemini", "github", "nvidia", "zai", "openrouter", "anthropic"}
    ids = [i for i in ids if i in allowed]
    if not ids:
        return jsonify({"ok": False, "error": "최소 한 개는 켜두세요."}), 400
    store.set_llm_visible(session["uid"], ids)
    return jsonify({"ok": True, "count": len(ids)})


@app.route("/api/compare-write", methods=["POST"])
@login_required
def compare_write():
    """여러 AI로 같은 글을 써서 비교. ★병렬 호출 + 빠른모드(1패스)로 속도 확보."""
    d = request.get_json(force=True, silent=True) or {}
    product = (d.get("productName") or "").strip()
    deeplink = (d.get("deeplink") or "").strip()
    tone = d.get("tone") or "friendly"
    price = d.get("price")
    providers = d.get("providers") or []
    keys = store.get_llm_keys(session["uid"])
    keys["llm7"] = "__free__"          # 키 없이 쓰는 무료 AI (항상 사용 가능)
    if not keys:
        return jsonify({"ok": False, "need_key": True, "error": "설정에서 AI 키를 먼저 등록하세요"}), 403
    # ★키가 실제로 있는 것만 남긴다. (없는 걸 부르면 403이 뜬다 = 스샷의 실패 원인)
    targets = [p for p in providers if (p in keys or p == "llm7")]
    if not targets:
        targets = [p for p in ("cerebras", "groq", "gemini", "llm7") if (p in keys or p == "llm7")]
    if not targets:
        targets = ["llm7"]

    from core import claude_write_thread
    import concurrent.futures as _cf
    names = LLM_NAMES

    def _one(p):
        # 비교는 속도가 생명 → fast=True (1패스, 검수/폴리시 생략)
        r = claude_write_thread(keys[p], product, deeplink, tone, price, fast=True)
        return {"provider": p, "name": names.get(p, p),
                "ok": r.get("ok", False), "content": r.get("content", ""),
                "error": r.get("error", "")}

    results = []
    with _cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_one, p): p for p in targets[:4]}
        for f in _cf.as_completed(futs, timeout=110):
            try:
                results.append(f.result())
            except Exception as e:
                p = futs[f]
                results.append({"provider": p, "name": names.get(p, p),
                                "ok": False, "content": "", "error": str(e)[:60]})
    # 요청 순서대로 정렬
    order = {p: i for i, p in enumerate(targets)}
    results.sort(key=lambda r: order.get(r["provider"], 99))
    return jsonify({"ok": True, "results": results})


@app.route("/api/claude-topics", methods=["POST"])
@login_required
def claude_topics_api():
    """주제 먼저 생성 (등록된 AI 아무거나: Gemini/OpenRouter/Claude)."""
    d = request.get_json(force=True, silent=True) or {}
    user_topic = (d.get("topic") or "").strip()
    keys = store.get_llm_keys(session["uid"])
    keys["llm7"] = "__free__"          # 키 없이 쓰는 무료 AI (항상 사용 가능)
    if not keys:
        return jsonify({"ok": False, "need_key": True,
                        "error": "설정에서 AI 키를 먼저 등록하세요 (Gemini 무료 추천)"}), 403
    # 선택된 제공자 우선, 없으면 무료 우선
    prov = d.get("provider")
    if prov not in keys:
        prov = next((p for p in ("cerebras", "groq", "gemini", "github", "nvidia", "zai", "llm7", "openrouter", "anthropic") if p in keys), None)
    key = keys[prov]
    import time as _t
    from datetime import datetime, timezone, timedelta as _td
    kst = datetime.now(timezone.utc) + _td(hours=9)   # 한국 시간 (서버는 UTC)
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    ampm = "오전" if kst.hour < 12 else "오후"
    h12 = kst.hour if kst.hour <= 12 else kst.hour - 12
    if h12 == 0: h12 = 12
    now_str = f"{kst.year}년 {kst.month}월 {kst.day}일 {ampm} {h12}시 ({weekdays[kst.weekday()]}요일)"
    # 폴백은 최대 2번까지만. (예전엔 4개를 전부 순차 시도해서
    #  실패할 때마다 풀 타임아웃을 물었다 = 주제 기획이 하염없이 느려지던 원인)
    order = []
    if prov: order.append(prov)
    for p in ("cerebras", "groq", "gemini", "github", "nvidia", "zai", "llm7", "openrouter", "anthropic"):
        if p in keys and p not in order:
            order.append(p)
    # ★2개로 묶어놨더니 Gemini가 503(과부하) 한 번 뱉는 순간 통째로 실패했다.
    #  스티키 캐시 덕에 죽은 모델을 반복 시도하지 않으므로 체인을 넉넉히 준다.
    #  마지막에는 키 없이도 되는 llm7이 있으니 반드시 하나는 성공한다.
    if "llm7" in keys and "llm7" not in order:
        order.append("llm7")
    order = order[:4] + (["llm7"] if "llm7" in keys and "llm7" not in order[:4] else [])

    import time as _time
    import concurrent.futures as _cf
    from core import claude_generate_topics

    # ★속도: 빠른 무료 모델들을 병렬로 던지고 '가장 먼저 성공한' 것을 쓴다.
    #  (직렬로 llm7 하나만 55초 기다리던 것 → 병렬이면 제일 빠른 놈 속도로 끝난다)
    FAST = [p for p in ("cerebras", "groq", "gemini", "github") if p in keys]
    parallel = FAST[:3] if FAST else []
    timings = {}
    last_err = {"error": "no_provider"}

    if parallel:
        _t = _time.time()
        with _cf.ThreadPoolExecutor(max_workers=len(parallel)) as ex:
            futs = {ex.submit(claude_generate_topics, keys[p], user_topic, now_str, 8): p
                    for p in parallel}
            done_ok = None
            for f in _cf.as_completed(futs, timeout=40):
                p = futs[f]
                try:
                    r = f.result()
                except Exception as e:
                    last_err = {"error": str(e)[:80]}; continue
                timings[p] = int((_time.time() - _t) * 1000)
                if r.get("ok") and r.get("topics"):
                    done_ok = (p, r); break
                last_err = r
            if done_ok:
                p, r = done_ok
                return jsonify({"ok": True, "topics": r["topics"], "now": now_str,
                                "provider": p, "ms": timings, "parallel": parallel})

    # 병렬이 다 실패했거나 빠른 모델이 없으면: 순차 폴백 (llm7 포함)
    seq = [p for p in order if p not in parallel]
    for p in seq:
        _t = _time.time()
        r = claude_generate_topics(keys[p], user_topic, now_str, n=8)
        timings[p] = int((_time.time() - _t) * 1000)
        if r.get("ok") and r.get("topics"):
            return jsonify({"ok": True, "topics": r["topics"], "now": now_str,
                            "provider": p, "ms": timings})
        # ★한도(429)·일시거부(403)면 잠깐 쉬고 '적게' 다시 한 번. 실패로 끝내지 않는다.
        e = str(r.get("error", ""))
        if "429" in e or "403" in e or "timeout" in e.lower():
            _time.sleep(2)
            r2 = claude_generate_topics(keys[p], user_topic, now_str, n=4)
            if r2.get("ok") and r2.get("topics"):
                return jsonify({"ok": True, "topics": r2["topics"], "now": now_str,
                                "provider": p, "ms": timings, "retried": True})
            r = r2 or r
        last_err = r
    r = last_err
    # 에러 메시지
    err = r.get("error", "")
    if err.startswith("http_401") or err.startswith("http_403"):
        msg = "AI 키가 유효하지 않아요. 설정에서 다시 등록하세요."
    elif err.startswith("http_429"):
        msg = "이 AI의 사용량 한도예요. 다른 AI를 골라보세요 (설정에 여러 개 넣을 수 있어요)."
    elif err.startswith("http_503") or err.startswith("http_500") or err.startswith("http_502"):
        msg = "AI 서버가 지금 과부하예요. 다른 AI를 고르거나 잠시 뒤 다시 눌러주세요."
    elif err.startswith("http_400"): msg = "API 요청 오류: " + (r.get("detail","")[:120] or "형식 오류")
    else: msg = "주제 생성 실패: " + (err[:60] or "알 수 없음") + (" / "+r.get("detail","")[:80] if r.get("detail") else "")
    return jsonify({"ok": False, "error": msg, "detail": r.get("detail", ""), "ms": timings}), 502


@app.route("/api/search-product", methods=["POST"])
@login_required
def search_product_api():
    """키워드로 인기 상품 검색 → 딥링크 자동 생성. 캐시 우선(시간당 10회 제한 보호)."""
    d = request.get_json(force=True, silent=True) or {}
    keyword = (d.get("keyword") or "").strip()
    if not keyword or len(keyword) < 2:
        return jsonify({"ok": False, "error": "검색어를 2자 이상 입력하세요"}), 400

    # 1) 캐시 먼저 (API 호출 0회)
    cached = store.get_search_cache(keyword)
    if cached and cached.get("deeplink"):
        plist_cached = []
        try:
            plist_cached = json.loads(cached.get("products") or "[]")
        except Exception:
            plist_cached = []
        return jsonify({"ok": True, "cached": True,
                        "product_name": cached["product_name"], "deeplink": cached["deeplink"],
                        "image": cached.get("image"), "price": cached.get("price"),
                        "products": plist_cached})

    user = store.get_user(session["uid"])
    partners, own_key = _partners_for(user)
    if partners is None:
        return jsonify({"ok": False, "need_key": True,
                        "error": "본인 파트너스 키가 필요해요. 설정에서 등록하세요."}), 403

    # 2) 시간당 제한 보호 (검색 API는 시간당 10회) — 유저당 8회로 여유있게 제한
    recent = store.count_recent_searches(session["uid"], 3600)
    if recent >= 8:
        return jsonify({"ok": False, "rate_limited": True,
                        "error": "검색을 너무 많이 했어요. 1시간 후 다시 시도하거나, 링크를 직접 붙여넣어 주세요."}), 429

    # 3) 실제 검색 (본인 키, 1회)
    import time as _time
    _t0 = _time.time()
    try:
        store.log_search(session["uid"])
        plist = partners.search_products(keyword, limit=10)   # 쿠팡 최대 10
    except Exception:
        plist = []
    _t_search = int((_time.time() - _t0) * 1000)
    if not plist:
        why = getattr(partners, "last_error", None)
        msg = "상품을 찾지 못했어요. 다른 검색어를 써보세요."
        if why and "rCode" in why:
            msg = "쿠팡 검색 API가 거절했어요 (시간당 호출 제한일 수 있어요). 잠시 뒤 다시 시도해 주세요."
        elif why:
            msg = "쿠팡 검색 연결 실패. 잠시 뒤 다시 시도해 주세요."
        return jsonify({"ok": False, "error": msg, "detail": why,
                        "ms": {"search": _t_search}}), 404
    info = plist[0]

    # 3-b) 딥링크
    # 파트너스 검색 API가 돌려주는 productUrl은 이미 link.coupang.com 제휴링크다.
    # 예전 코드는 여기서 make_deeplinks()를 또 불렀는데, 반환값(dict)을 리스트처럼 순회해
    # 항상 예외가 나서 결과를 버렸다 = API 왕복 1회를 통째로 낭비. 제거한다.
    _t1 = _time.time()
    def _with_subid(u):
        if not u:
            return u
        if "link.coupang.com" in u:
            return u + ("&" if "?" in u else "?") + "subId=search"
        return u
    products = []
    need_dl = [p.get("url") for p in plist
               if p.get("url") and "link.coupang.com" not in p.get("url")]
    dmap = {}
    if need_dl:                      # 제휴링크가 아닌 것만 (보통 0개)
        try:
            res = partners.make_deeplinks(need_dl, sub_id="search")
            for dl in (res.get("data") or []):
                dmap[dl.get("originalUrl")] = dl.get("shortenUrl") or dl.get("landingUrl")
        except Exception:
            pass
    for p in plist:
        u = p.get("url")
        products.append({
            "name": p.get("name"), "price": p.get("price"),
            "image": p.get("image"), "productId": p.get("productId"),
            "isRocket": p.get("isRocket", False),
            "url": u,
            "deeplink": dmap.get(u) or _with_subid(u),
        })
    _t_deeplink = int((_time.time() - _t1) * 1000)

    # 4) 대표 상품 딥링크
    deeplink = (products[0].get("deeplink") if products else None) or info.get("url") or ""

    # 5) 캐시 저장 (다음엔 API 안 씀)
    store.set_search_cache(keyword, info["name"], deeplink, info.get("image"), info.get("price"), products)
    store.save_link(session["uid"], "", deeplink, info["name"], "search")

    return jsonify({"ok": True, "cached": False,
                    "ms": {"search": _t_search, "deeplink": _t_deeplink},
                    "product_name": info["name"], "deeplink": deeplink,
                    "image": info.get("image"), "price": info.get("price"),
                    "products": products})


@app.route("/api/sns-accounts", methods=["GET"])
@login_required
def sns_accounts():
    """연결된 SNS 계정 목록 (게시 대상 선택용)."""
    key = store.get_zernio_key(session["uid"])
    if not key:
        return jsonify({"ok": True, "accounts": []})
    from core import zernio_list_accounts
    return jsonify({"ok": True, "accounts": zernio_list_accounts(key)})


@app.route("/api/save-draft", methods=["POST"])
@login_required
def save_draft():
    """우리 앱에 임시저장. 나중에 앱에서 편집 후 게시 (Zernio 대시보드 안 거침)."""
    d = request.get_json(force=True, silent=True) or {}
    channel = (d.get("channel") or "").strip()
    content = (d.get("content") or "").strip()
    is_auto = d.get("auto", False)
    if not content:
        return jsonify({"ok": False, "error": "저장할 내용이 없어요"}), 400
    # 자동저장은 직전 자동저장 초안을 정리 (계속 쌓이지 않게, 최신 1개만)
    if is_auto:
        try: store.delete_auto_drafts(session["uid"])
        except Exception: pass
    pid = store.save_post(session["uid"], channel, d.get("productName", ""),
                          content, d.get("deeplink", ""), d.get("image"),
                          status=("autodraft" if is_auto else "draft"))
    msg = "자동 저장됨" if is_auto else "임시저장했어요 (내 게시물에서 편집·게시 가능)"
    return jsonify({"ok": True, "post_id": pid, "message": msg})


@app.route("/api/posts", methods=["GET"])
@login_required
def list_posts():
    """내 게시물 목록 (임시저장 + 게시완료)."""
    status = request.args.get("status")
    posts = store.get_posts(session["uid"], status)
    # 민감정보 제외하고 반환
    out = [{"id": p["id"], "channel": p["channel"], "product_name": p["product_name"],
            "content": p["content"][:200], "status": p["status"], "post_url": p.get("post_url"),
            "created_at": p["created_at"], "published_at": p.get("published_at")} for p in posts]
    return jsonify({"ok": True, "posts": out})


@app.route("/api/post/<int:post_id>", methods=["DELETE"])
@login_required
def delete_post_api(post_id):
    return jsonify(store.delete_post(session["uid"], post_id))


@app.route("/api/post/<int:post_id>/edit", methods=["POST"])
@login_required
def edit_post_api(post_id):
    """임시저장 글 내용 편집."""
    d = request.get_json(force=True, silent=True) or {}
    content = (d.get("content") or "").strip()
    if not content:
        return jsonify({"ok": False, "error": "내용이 비어있어요"}), 400
    store.update_post_content(session["uid"], post_id, content)
    return jsonify({"ok": True, "message": "수정했어요"})


@app.route("/api/post/<int:post_id>", methods=["GET"])
@login_required
def get_post_api(post_id):
    """게시물 전체 내용 (편집용)."""
    p = store.get_post(post_id)
    if not p or p["user_id"] != session["uid"]:
        return jsonify({"ok": False, "error": "없는 게시물이에요"}), 404
    return jsonify({"ok": True, "post": {"id": p["id"], "channel": p["channel"],
                    "product_name": p["product_name"], "content": p["content"],
                    "status": p["status"], "deeplink": p.get("deeplink")}})


@app.route("/api/post-safety", methods=["GET"])
@login_required
def post_safety_api():
    """게시 안전 상태 — 지금 게시해도 되는지, 대기 권장 시간은 얼마인지."""
    import time as _t
    now = int(_t.time())
    recent_1h = store.count_recent_published(session["uid"], hours=1)
    recent_24h = store.count_recent_published(session["uid"], hours=24)
    last_at = store.last_published_at(session["uid"])
    gap = (now - last_at) if last_at else None

    level = "safe"; msg = "지금 게시해도 안전해요."
    if recent_1h >= 5 or (gap is not None and gap < 300):
        level = "danger"; msg = "지금 게시하면 스팸으로 잡힐 수 있어요. 예약으로 분산하세요."
    elif recent_1h >= 3 or recent_24h >= 20 or (gap is not None and gap < 600):
        level = "caution"; msg = "게시 빈도가 조금 높아요. 간격을 두는 게 안전해요."

    return jsonify({"ok": True, "level": level, "message": msg,
                    "recent_1h": recent_1h, "recent_24h": recent_24h,
                    "minutes_since_last": (gap // 60) if gap is not None else None,
                    "guidelines": {
                        "per_hour_max": 5, "per_day_max": 20, "min_gap_minutes": 10}})


@app.route("/api/publish", methods=["POST"])
@login_required
def publish_sns():
    """SNS 게시 (Zernio). post_id(임시저장)를 게시하거나, 즉석 내용을 게시.
    게시 후 게시물 저장 + 프로필 URL 연결."""
    d = request.get_json(force=True, silent=True) or {}
    platforms = d.get("platforms") or []
    content = (d.get("content") or "").strip()
    media = d.get("media") or []
    post_id = d.get("post_id")   # 임시저장분 게시 시
    channel = (d.get("channel") or (platforms[0] if platforms else "")).strip()

    # 임시저장분을 게시하는 경우 → 내용 로드
    if post_id and not content:
        p = store.get_post(post_id)
        if p and p["user_id"] == session["uid"]:
            content = p["content"]; channel = p["channel"]
            if p.get("image"): media = [p["image"]]
            if not platforms: platforms = [channel]

    if not platforms or not content:
        return jsonify({"ok": False, "error": "게시할 플랫폼과 내용이 필요해요"}), 400

    # ★Meta 스팸 제재 예방 가드 (즉시 게시일 때만; 예약은 시간이 분산되므로 통과)
    if not d.get("scheduled_for") and not d.get("force"):
        recent_1h = store.count_recent_published(session["uid"], hours=1)
        last_at = store.last_published_at(session["uid"])
        import time as _t
        now = int(_t.time())
        # 규칙: 시간당 5건 초과 경고, 직전 게시 후 10분 미만이면 경고
        if recent_1h >= 5:
            return jsonify({"ok": False, "rate_warning": True,
                "error": f"지난 1시간에 이미 {recent_1h}건 게시했어요. Meta는 '짧은 시간 다량 게시'를 "
                         "스팸으로 봐요. 예약 게시로 시간을 분산하는 걸 권해요.",
                "suggest_schedule": True}), 429
        if last_at and (now - last_at) < 600:
            wait = 600 - (now - last_at)
            return jsonify({"ok": False, "rate_warning": True,
                "error": f"직전 게시가 {(now-last_at)//60}분 전이에요. Meta 스팸 필터를 피하려면 "
                         f"게시 간격을 10분 이상 두는 게 안전해요. {wait//60}분 뒤에 다시 시도하거나 예약하세요.",
                "suggest_schedule": True}), 429

    key = store.get_zernio_key(session["uid"])
    if not key:
        return jsonify({"ok": False, "need_connect": True,
                        "error": "먼저 설정에서 SNS를 연결해주세요"}), 403

    # 쓰레드/X: 6분할(본글+답글)을 답글 체인으로 게시
    thread_items = None
    if channel in ("threads", "x") and "\n===THREAD===\n" in content:
        thread_items = [p.strip() for p in content.split("\n===THREAD===\n") if p.strip()]

    r = zernio_publish(key, platforms, content, media,
                       account_ids=(d.get("account_ids") or {}),
                       thread_items=thread_items,
                       scheduled_for=d.get("scheduled_for"))
    if r.get("ok"):
        # 게시물 URL: Zernio가 permalink를 안 주므로 계정 프로필로 연결
        prof_url = _profile_url_from_zernio(r.get("data"), platforms[0])
        if post_id:
            if d.get("scheduled_for"):
                store.mark_scheduled(post_id, str((r.get("data") or {}).get("post", {}).get("_id", "")))
            else:
                store.mark_published(post_id, prof_url, str((r.get("data") or {}).get("post", {}).get("_id", "")))
        else:
            new_id = store.save_post(session["uid"], channel, d.get("productName", ""),
                                     content, d.get("deeplink", ""), (media[0] if media else None),
                                     status=("scheduled" if d.get("scheduled_for") else "published"))
            if new_id:
                store.mark_published(new_id, prof_url, str((r.get("data") or {}).get("post", {}).get("_id", "")))
        return jsonify({"ok": True, "message": "게시됐어요!", "post_url": prof_url})
    # ★실패 원인 상세 전달 (유저가 왜 안 됐는지 알 수 있게)
    return jsonify({"ok": False, "error": _publish_error_msg(r),
                    "detail": r.get("detail", "")}), 502


def _publish_error_msg(r):
    """Zernio 실패를 사람이 읽을 수 있는 메시지로."""
    err = r.get("error", "")
    if err == "no_accounts": return "연결된 SNS 계정이 없어요. Zernio에서 계정을 먼저 연결하세요."
    if err == "platform_not_connected": return r.get("detail", "해당 플랫폼이 Zernio에 연결 안 됐어요.")
    if err.startswith("http_401") or err.startswith("http_403"): return "Zernio 키가 유효하지 않아요. 설정에서 다시 연결하세요."
    if err.startswith("http_409"): return "이미 같은 내용을 게시했어요. 초안을 다시 만들면(매번 다른 글) 게시할 수 있어요."
    if err.startswith("http_429"): return "잠시 후 다시 시도해주세요. (너무 빠른 연속 게시)"
    if err.startswith("http_"): return f"게시 실패 ({err}). 잠시 후 다시 시도해주세요."
    return f"게시 실패: {err or '알 수 없는 오류'} / {r.get('detail','')[:100]}"


def _profile_url_from_zernio(data, platform):
    """게시 응답에서 계정 프로필 URL 구성 (permalink 대신)."""
    try:
        plats = (data or {}).get("post", {}).get("platforms", [])
        for pl in plats:
            acc = pl.get("accountId") or {}
            name = acc.get("displayName") or acc.get("username")
            plat = pl.get("platform", platform)
            if name:
                if plat == "threads": return f"https://www.threads.net/@{name}"
                if plat == "instagram": return f"https://www.instagram.com/{name}"
                if plat == "twitter": return f"https://x.com/{name}"
    except Exception:
        pass
    urls = {"threads": "https://www.threads.net", "instagram": "https://www.instagram.com", "x": "https://x.com"}
    return urls.get(platform, "")


@app.route("/api/handle", methods=["POST"])
@login_required
def set_handle_api():
    d = request.get_json(force=True, silent=True) or {}
    r = store.set_handle(session["uid"], d.get("handle"))
    return jsonify(r), (200 if r.get("ok") else 400)


@app.route("/api/link/<int:link_id>", methods=["DELETE"])
@login_required
def delete_link_api(link_id):
    return jsonify(store.delete_link(session["uid"], link_id))


@app.route("/api/link/<int:link_id>/toggle", methods=["POST"])
@login_required
def toggle_link_api(link_id):
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(store.toggle_link_profile(session["uid"], link_id, bool(d.get("on"))))


@app.route("/api/links/reorder", methods=["POST"])
@login_required
def reorder_links_api():
    d = request.get_json(force=True, silent=True) or {}
    ids = d.get("ids") or []
    return jsonify(store.reorder_links(session["uid"], ids))


@app.route("/api/key", methods=["POST"])
@login_required
def save_key():
    d = request.get_json(force=True, silent=True) or {}
    access = (d.get("access") or "").strip()
    secret = (d.get("secret") or "").strip()
    if not access or not secret:
        return jsonify({"ok": False, "error": "access/secret 키를 모두 입력하세요"}), 400
    test = CoupangPartners(access, secret).make_deeplinks(["https://www.coupang.com/"], sub_id="verify")
    if not test.get("ok"):
        return jsonify({"ok": False, "error": "이 키로 링크를 만들 수 없습니다. 파트너스 키를 다시 확인하세요"}), 422
    store.save_partners_key(session["uid"], access, secret)
    return jsonify({"ok": True, "message": "파트너스 키가 안전하게 저장되었습니다"})


@app.route("/api/generate", methods=["POST"])
@login_required
def generate():
    d = request.get_json(force=True, silent=True) or {}
    url = extract_coupang_url((d.get("url") or "").strip())
    channel = (d.get("channel") or "blog").strip()
    tone = (d.get("tone") or "friendly").strip()
    product_name = (d.get("productName") or "쿠팡 상품").strip()

    if not is_valid_coupang_url(url):
        return jsonify({"ok": False, "error": "올바른 쿠팡 URL이 아닙니다"}), 400

    # 폰 쿠팡 앱 공유링크(단축)는 딥링크 API가 못 받음 → 원본 상품 URL로 자동 펼침
    if is_short_coupang_link(url):
        origin = unshorten_coupang(url)
        if origin:
            url = origin  # 펼친 원본으로 교체 → 아래에서 정상 변환
        else:
            return jsonify({"ok": False,
                "error": "이 링크를 펼칠 수 없어요. 쿠팡 상품 페이지 주소를 직접 넣어주세요"}), 422

    user = store.get_user(session["uid"])
    ok, cur, limit = store.check_and_bump(user["id"], "link", user["plan"])
    if not ok:
        return jsonify({"ok": False, "error": f"무료 플랜 월 {limit}건을 다 썼어요. Pro로 업그레이드하면 무제한이에요",
                        "limit_reached": True}), 402

    partners, own_key = _partners_for(user)
    if partners is None:
        # 본인 파트너스 키가 없으면 자동생성 불가 → 유형B(직접 붙여넣기)로 유도
        return jsonify({"ok": False, "need_key": True,
            "error": "간편링크 자동생성은 내 쿠팡 파트너스 키가 필요해요. 설정에서 키를 등록하거나, '링크 직접 붙여넣기'로 만들어보세요"}), 403
    result = partners.make_deeplinks([url], sub_id=channel)
    if not result.get("ok"):
        return jsonify({"ok": False, "error": "링크 변환 실패", "detail": result.get("detail")}), 502
    items = result["data"]
    if not items or not items[0].get("shortenUrl"):
        return jsonify({"ok": False, "error": "이 URL은 변환할 수 없어요 (상품 페이지 URL인지 확인하세요)"}), 422

    deeplink = items[0]["shortenUrl"]

    # 상품명으로 파트너스 검색 → 정식명·가격·이미지 확보 (크롤 대체)
    info = None
    if product_name and product_name != "쿠팡 상품":
        info = partners.search_product(product_name)
        if info and info.get("name"):
            product_name = info["name"]

    draft = None
    if not d.get("skip_draft"):
        ok_d, _, _ = store.check_and_bump(user["id"], "draft", user["plan"])
        if ok_d:
            draft = _gen_draft(user["id"], product_name, deeplink, tone, channel, info, d.get("provider"), d.get("extra", ""), d.get("quality", False))

    store.save_link(user["id"], url, deeplink, product_name, channel)

    naver_html = build_naver_html(product_name, deeplink, draft, info) if draft else None
    return jsonify({
        "ok": True, "deeplink": deeplink, "landingUrl": items[0].get("landingUrl"),
        "disclosure": COUPANG_DISCLOSURE, "blogDraft": draft, "channel": channel,
        "usedOwnKey": own_key, "draftLimitReached": draft is None,
        "naverHtml": naver_html, "image": _auto_image(product_name, info),
        "productName": product_name,
    })


@app.route("/api/generate-manual", methods=["POST"])
@login_required
def generate_manual():
    """유형 B: 이미 만든 파트너스 링크를 붙여넣기. API 딥링크 생성 없이 초안+저장만."""
    d = request.get_json(force=True, silent=True) or {}
    deeplink = extract_coupang_url((d.get("deeplink") or "").strip())
    channel = (d.get("channel") or "blog").strip()
    tone = (d.get("tone") or "friendly").strip()
    product_name = (d.get("productName") or "쿠팡 상품").strip()
    # 쿠팡 파트너스 링크 형식 확인 (link.coupang.com 또는 coupang.com)
    if "coupang" not in deeplink:
        return jsonify({"ok": False, "error": "쿠팡 파트너스 링크를 붙여넣어 주세요 (link.coupang.com/...)"}), 400
    user = store.get_user(session["uid"])
    # ★실제 상품 확인: 본인 파트너스 키가 있고 상품명이 입력됐을 때만 검색 1회
    #   (폴백 키 절대 안 씀 / 검색 실패해도 앱 정상 / API 한도 보호 위해 링크당 최소 호출)
    info = None
    if product_name and product_name != "쿠팡 상품":
        partners, own_key = _partners_for(user)
        if partners is not None:   # 본인 키 있을 때만
            try:
                info = partners.search_product(product_name)
                if info and info.get("name"):
                    product_name = info["name"]   # 정식 상품명으로 교체
            except Exception:
                info = None   # 실패해도 계속 진행
    draft = None
    if not d.get("skip_draft"):
        ok_d, _, _ = store.check_and_bump(user["id"], "draft", user["plan"])
        if ok_d:
            draft = _gen_draft(user["id"], product_name, deeplink, tone, channel, info, d.get("provider"), d.get("extra", ""), d.get("quality", False))
    store.save_link(user["id"], "", deeplink, product_name, channel)
    naver_html = build_naver_html(product_name, deeplink, draft, info) if draft else None
    return jsonify({"ok": True, "deeplink": deeplink, "disclosure": COUPANG_DISCLOSURE,
                    "blogDraft": draft, "channel": channel, "manual": True,
                    "naverHtml": naver_html, "productName": product_name,
                    "image": _auto_image(product_name, info)})


@app.route("/api/my-links")
@login_required
def my_links():
    return jsonify({"ok": True, "links": store.get_user_links(session["uid"])})


@app.route("/r/<int:link_id>")
def redirect_link(link_id):
    """클릭 트래킹: 카운트 올리고 쿠팡으로 리디렉트."""
    from flask import redirect
    l = store.get_link(link_id)
    if not l or not l.get("deeplink"):
        return "링크를 찾을 수 없습니다", 404
    try:
        store.bump_click(link_id)
    except Exception:
        pass
    return redirect(l["deeplink"], code=302)


@app.route("/api/stats")
@login_required
def api_stats():
    s = store.get_click_stats(session["uid"])
    return jsonify({"ok": True, **s})


@app.route("/u/<handle>")
def public_profile(handle):
    u = store.get_user_by_handle(handle)
    if not u:
        return "존재하지 않는 프로필입니다", 404
    links = store.get_user_links(u["id"], profile_only=True)
    name = u["display_name"] or handle
    initial = (name or "?")[0].upper()

    CH_ICON = {"blog": "📝", "insta": "📷", "threads": "🧵", "x": "𝕏", "youtube": "▶️", "etc": "🔗"}
    if links:
        items = "".join(
            f'''<a class="lk" href="/r/{l["id"]}" target="_blank" rel="nofollow sponsored">
<span class="lk-ic">{CH_ICON.get(l["channel"], "🔗")}</span>
<span class="lk-name">{l["product_name"] or "쿠팡 상품"}</span>
<span class="lk-arrow">→</span></a>'''
            for l in links
        )
    else:
        items = '<div class="empty">아직 등록된 링크가 없어요</div>'

    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{name} · LinkLynk</title>
<meta property="og:title" content="{name}의 추천 링크">
<meta property="og:description" content="LinkLynk로 모은 추천 링크 모음">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root{{--bg:#0D1220;--surface:#141B2E;--surface2:#1B2540;--line:#243050;--mint:#22E9A4;--mint2:#3DF0B0;--ink:#08120D;--text:#EAF0FA;--text2:#A8B3C9;--muted:#6B7794}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Pretendard,-apple-system,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;max-width:520px;margin:0 auto;padding:48px 20px calc(40px + env(safe-area-inset-bottom));background-image:radial-gradient(circle at 50% 0%,rgba(34,233,164,.08),transparent 60%)}}
.av{{width:84px;height:84px;border-radius:50%;background:linear-gradient(135deg,var(--mint),var(--mint2));color:var(--ink);display:grid;place-items:center;font-size:36px;font-weight:800;margin:0 auto 16px;box-shadow:0 8px 32px rgba(34,233,164,.35)}}
h1{{font-size:22px;font-weight:800;text-align:center;letter-spacing:-.02em}}
.sub{{text-align:center;color:var(--text2);font-size:13px;margin-top:6px;margin-bottom:32px}}
.lk{{display:flex;align-items:center;gap:14px;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:17px 18px;margin:12px 0;text-decoration:none;color:var(--text);font-weight:600;font-size:15px;transition:transform .15s,border-color .15s,background .15s}}
.lk:active{{transform:scale(.98)}}
.lk:hover{{border-color:var(--mint);background:var(--surface2)}}
.lk-ic{{font-size:20px;flex:0 0 auto}}
.lk-name{{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;letter-spacing:-.01em}}
.lk-arrow{{color:var(--mint);font-weight:800;flex:0 0 auto}}
.empty{{text-align:center;color:var(--muted);padding:40px 0;font-size:14px}}
.ft{{margin-top:40px;text-align:center}}
.ft a{{display:inline-flex;align-items:center;gap:6px;color:var(--muted);font-size:12px;text-decoration:none;padding:8px 14px;border:1px solid var(--line);border-radius:999px;transition:color .15s,border-color .15s}}
.ft a:hover{{color:var(--mint);border-color:var(--mint)}}
.ft b{{color:var(--mint);font-weight:700}}
.disc{{margin-top:20px;text-align:center;color:var(--muted);font-size:10.5px;line-height:1.5;opacity:.7}}
</style></head>
<body>
<div class="av">{initial}</div>
<h1>{name}</h1>
<div class="sub">추천 링크 모음</div>
{items}
<div class="disc">이 페이지의 링크는 쿠팡 파트너스 활동의 일환으로,<br>이에 따른 일정액의 수수료를 제공받습니다.</div>
<div class="ft"><a href="/">✨ 나도 <b>LinkLynk</b>로 만들기</a></div>
</body></html>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
