"""
LinkLynk — 백엔드 API 서버 (멀티테넌트)
- 회원가입/로그인 (세션)
- 유저별 쿠팡 파트너스 키 등록 (암호화 저장)
- 유저 자기 키로 딥링크 생성
- 무료/Pro 사용량 제한
- 링크 히스토리 + 링크인바이오 프로필
"""
import os
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
            r = claude_write_thread(akey, product_name, deeplink, tone, price, extra=extra, fast=(not quality))
            if r.get("ok"):
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
    if p == "unknown":
        return jsonify({"ok": False, "error": "키 형식을 인식할 수 없어요. AIza…(Gemini 무료) / sk-or-…(OpenRouter 무료) / sk-ant-…(Claude)"}), 400
    store.save_llm_key(session["uid"], p, key)
    if p == "anthropic":
        store.save_anthropic_key(session["uid"], key)   # 하위호환
    names = {"gemini": "Google Gemini (무료)", "openrouter": "OpenRouter (무료)", "groq": "Groq (무료)", "anthropic": "Claude"}
    return jsonify({"ok": True, "provider": p, "message": f"{names[p]} 연결됐어요"})


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
    names = {"gemini": "Gemini (무료)", "openrouter": "OpenRouter (무료)", "groq": "Groq (무료)", "anthropic": "Claude"}
    return jsonify({"ok": True, "providers": [{"id": p, "name": names[p]} for p in keys]})


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
    if not keys:
        return jsonify({"ok": False, "need_key": True, "error": "설정에서 AI 키를 먼저 등록하세요"}), 403
    targets = [p for p in providers if p in keys]
    if not targets:
        targets = [p for p in ("gemini", "groq", "openrouter") if p in keys]   # 유료(Claude) 자동 사용 안 함

    from core import claude_write_thread
    import concurrent.futures as _cf
    names = {"gemini": "Gemini (무료)", "openrouter": "OpenRouter (무료)",
             "groq": "Groq (무료)", "anthropic": "Claude"}

    def _one(p):
        # 비교는 속도가 생명 → fast=True (1패스, 검수/폴리시 생략)
        r = claude_write_thread(keys[p], product, deeplink, tone, price, fast=True)
        return {"provider": p, "name": names.get(p, p),
                "ok": r.get("ok", False), "content": r.get("content", ""),
                "error": r.get("error", "")}

    results = []
    with _cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(_one, p): p for p in targets[:4]}
        for f in _cf.as_completed(futs, timeout=75):
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
    if not keys:
        return jsonify({"ok": False, "need_key": True,
                        "error": "설정에서 AI 키를 먼저 등록하세요 (Gemini 무료 추천)"}), 403
    # 선택된 제공자 우선, 없으면 무료 우선
    prov = d.get("provider")
    if prov not in keys:
        prov = next((p for p in ("groq", "gemini", "openrouter", "anthropic") if p in keys), None)
    key = keys[prov]
    import time as _t
    from datetime import datetime, timezone, timedelta as _td
    kst = datetime.now(timezone.utc) + _td(hours=9)   # 한국 시간 (서버는 UTC)
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    ampm = "오전" if kst.hour < 12 else "오후"
    h12 = kst.hour if kst.hour <= 12 else kst.hour - 12
    if h12 == 0: h12 = 12
    now_str = f"{kst.year}년 {kst.month}월 {kst.day}일 {ampm} {h12}시 ({weekdays[kst.weekday()]}요일)"
    # 등록된 AI들을 순서대로 시도 (하나 실패하면 다음 것)
    order = []
    if prov: order.append(prov)
    for p in ("groq", "gemini", "openrouter", "anthropic"):
        if p in keys and p not in order:
            order.append(p)

    from core import claude_generate_topics
    last_err = {}
    for p in order:
        r = claude_generate_topics(keys[p], user_topic, now_str, n=3)
        if r.get("ok") and r.get("topics"):
            return jsonify({"ok": True, "topics": r["topics"], "now": now_str, "provider": p})
        last_err = r
    r = last_err
    # 에러 메시지
    err = r.get("error", "")
    if err.startswith("http_401"): msg = "Claude API 키가 유효하지 않아요. 설정에서 다시 등록하세요."
    elif err.startswith("http_429"): msg = "Claude API 사용량 한도예요. 잠시 후 다시 시도하세요."
    elif err.startswith("http_400"): msg = "API 요청 오류: " + (r.get("detail","")[:120] or "형식 오류")
    else: msg = "주제 생성 실패: " + (err[:60] or "알 수 없음") + (" / "+r.get("detail","")[:80] if r.get("detail") else "")
    return jsonify({"ok": False, "error": msg, "detail": r.get("detail", "")}), 502


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

    # 3) 실제 검색 (본인 키, 1회) — 상품 최대 20개
    try:
        store.log_search(session["uid"])
        plist = partners.search_products(keyword, limit=12)
    except Exception:
        plist = []
    if not plist:
        return jsonify({"ok": False, "error": "상품을 찾지 못했어요. 다른 검색어를 써보세요."}), 404
    info = plist[0]

    # 3-b) 각 상품 딥링크 생성 → 카드 3개로 반환
    products = []
    try:
        urls = [p.get("url") for p in plist if p.get("url")]
        dls = partners.make_deeplinks(urls, sub_id="search") if urls else []
        dmap = {}
        for dl in (dls or []):
            dmap[dl.get("originalUrl")] = dl.get("shortenUrl") or dl.get("landingUrl")
        for p in plist:
            products.append({
                "name": p.get("name"), "price": p.get("price"),
                "image": p.get("image"), "productId": p.get("productId"),
                "isRocket": p.get("isRocket", False),
                "url": p.get("url"),
                "deeplink": dmap.get(p.get("url")) or p.get("url"),
            })
    except Exception:
        for p in plist:
            products.append({"name": p.get("name"), "price": p.get("price"),
                             "image": p.get("image"), "productId": p.get("productId"),
                             "isRocket": p.get("isRocket", False),
                             "url": p.get("url"), "deeplink": p.get("url")})

    # 4) 대표 상품 딥링크 — 위 배치 결과 재사용 (API 재호출 제거)
    deeplink = (products[0].get("deeplink") if products else None) or info.get("url") or ""

    # 5) 캐시 저장 (다음엔 API 안 씀)
    store.set_search_cache(keyword, info["name"], deeplink, info.get("image"), info.get("price"), products)
    store.save_link(session["uid"], "", deeplink, info["name"], "search")

    return jsonify({"ok": True, "cached": False,
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
