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

from core import CoupangPartners, is_valid_coupang_url, make_blog_draft, COUPANG_DISCLOSURE, unshorten_coupang, is_short_coupang_link
import store

app = Flask(__name__, static_folder=".")
app.secret_key = os.environ.get("LINKLYNK_SESSION_SECRET", "dev-secret-change-me")
from datetime import timedelta
app.permanent_session_lifetime = timedelta(days=365)  # 로그인 1년 유지 (자동로그인)
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,     # HTTPS(onrender)에서 쿠키 유지
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_REFRESH_EACH_REQUEST=True,  # 매 요청마다 만료 갱신
)

FALLBACK_ACCESS = os.environ.get("COUPANG_PT_ACCESS", "39659f61-3eaa-4d1a-8195-82c8d37136cf")
FALLBACK_SECRET = os.environ.get("COUPANG_PT_SECRET", "cc9a76dd51b73fbf1c09d50fa46ac137ecaba435")

store.init_db()


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
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
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
    return send_from_directory(".", "icon-192.png", mimetype="image/png")

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

@app.route("/api/me")
@login_required
def me():
    u = store.get_user(session["uid"])
    key = store.get_partners_key(u["id"])
    usage = store.get_usage(u["id"])
    return jsonify({"ok": True, "email": u["email"], "handle": u["handle"],
                    "plan": u["plan"], "has_key": bool(key),
                    "usage": usage, "limits": store.FREE_LIMITS})


@app.route("/api/handle", methods=["POST"])
@login_required
def set_handle_api():
    d = request.get_json(force=True, silent=True) or {}
    r = store.set_handle(session["uid"], d.get("handle"))
    return jsonify(r), (200 if r.get("ok") else 400)


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
    url = (d.get("url") or "").strip()
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
    ok_d, _, _ = store.check_and_bump(user["id"], "draft", user["plan"])
    if ok_d:
        draft = make_blog_draft(product_name, deeplink, tone, channel, info)

    store.save_link(user["id"], url, deeplink, product_name, channel)

    return jsonify({
        "ok": True, "deeplink": deeplink, "landingUrl": items[0].get("landingUrl"),
        "disclosure": COUPANG_DISCLOSURE, "blogDraft": draft, "channel": channel,
        "usedOwnKey": own_key, "draftLimitReached": draft is None,
    })


@app.route("/api/generate-manual", methods=["POST"])
@login_required
def generate_manual():
    """유형 B: 이미 만든 파트너스 링크를 붙여넣기. API 딥링크 생성 없이 초안+저장만."""
    d = request.get_json(force=True, silent=True) or {}
    deeplink = (d.get("deeplink") or "").strip()
    channel = (d.get("channel") or "blog").strip()
    tone = (d.get("tone") or "friendly").strip()
    product_name = (d.get("productName") or "쿠팡 상품").strip()
    # 쿠팡 파트너스 링크 형식 확인 (link.coupang.com 또는 coupang.com)
    if "coupang" not in deeplink:
        return jsonify({"ok": False, "error": "쿠팡 파트너스 링크를 붙여넣어 주세요 (link.coupang.com/...)"}), 400
    user = store.get_user(session["uid"])
    # 상품검색은 딥링크 생성이 아니므로 폴백 키로 정보만 조회 (이미지·가격·정식명)
    info = None
    if product_name and product_name != "쿠팡 상품":
        try:
            searcher = CoupangPartners(FALLBACK_ACCESS, FALLBACK_SECRET)
            info = searcher.search_product(product_name)
            if info and info.get("name"):
                product_name = info["name"]
        except Exception:
            info = None
    draft = None
    ok_d, _, _ = store.check_and_bump(user["id"], "draft", user["plan"])
    if ok_d:
        draft = make_blog_draft(product_name, deeplink, tone, channel, info)
    store.save_link(user["id"], "", deeplink, product_name, channel)
    return jsonify({"ok": True, "deeplink": deeplink, "disclosure": COUPANG_DISCLOSURE,
                    "blogDraft": draft, "channel": channel, "manual": True})


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
