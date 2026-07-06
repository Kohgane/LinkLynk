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
from flask import Flask, request, jsonify, send_from_directory, session

from core import CoupangPartners, is_valid_coupang_url, make_blog_draft, COUPANG_DISCLOSURE, unshorten_coupang, is_short_coupang_link
import store

app = Flask(__name__, static_folder=".")
app.secret_key = os.environ.get("LINKLYNK_SESSION_SECRET", "dev-secret-change-me")
from datetime import timedelta
app.permanent_session_lifetime = timedelta(days=30)  # 로그인 30일 유지

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
    key = store.get_partners_key(user["id"])
    if key:
        return CoupangPartners(key["access"], key["secret"]), True
    return CoupangPartners(FALLBACK_ACCESS, FALLBACK_SECRET), False


@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/app.js")
def appjs():
    return send_from_directory(".", "app.js", mimetype="application/javascript")

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
    draft = None
    ok_d, _, _ = store.check_and_bump(user["id"], "draft", user["plan"])
    if ok_d:
        draft = make_blog_draft(product_name, deeplink, tone, channel)
    store.save_link(user["id"], "", deeplink, product_name, channel)
    return jsonify({"ok": True, "deeplink": deeplink, "disclosure": COUPANG_DISCLOSURE,
                    "blogDraft": draft, "channel": channel, "manual": True})


@app.route("/api/my-links")
@login_required
def my_links():
    return jsonify({"ok": True, "links": store.get_user_links(session["uid"])})


@app.route("/u/<handle>")
def public_profile(handle):
    u = store.get_user_by_handle(handle)
    if not u:
        return "존재하지 않는 프로필입니다", 404
    links = store.get_user_links(u["id"], profile_only=True)
    items = "".join(
        f'<a class="lk" href="{l["deeplink"]}" target="_blank">{l["product_name"] or l["deeplink"]}</a>'
        for l in links
    )
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{u["display_name"]} · LinkLynk</title>
<style>body{{font-family:Pretendard,-apple-system,sans-serif;background:#F7F8FA;max-width:480px;margin:0 auto;padding:32px 20px;text-align:center}}
h1{{font-size:20px;color:#151B2E}}.lk{{display:block;background:#fff;border:1px solid #E4E7EC;border-radius:12px;padding:15px;margin:10px 0;text-decoration:none;color:#1A1F2C;font-weight:600}}
.ft{{margin-top:24px;font-size:11px;color:#B4BBC8}}</style></head>
<body><h1>{u["display_name"]}</h1>{items}<div class="ft">Powered by LinkLynk</div></body></html>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
