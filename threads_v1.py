# -*- coding: utf-8 -*-
"""Threads 게시 — 카드 이미지를 공개 URL 그대로 올린다.
   컨테이너 생성 -> 게시 2단계. 이미지는 /next/card, /duty/card 를 그대로 쓴다.
"""
import os, json, time, urllib.parse, urllib.request
from flask import Blueprint, request, jsonify, Response

th_bp = Blueprint("threads", __name__)
API = "https://graph.threads.net/v1.0"
UID = os.environ.get("THREADS_USER_ID", "").strip()
TOK = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
ADMIN = os.environ.get("TH_ADMIN_KEY", "").strip()


def _post(path, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(API + path, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


_UID_CACHE = {"v": None}


def _resolve_uid():
    """환경변수 UID 오타로 막히는 걸 없앤다 — 토큰에서 직접 읽어 캐시한다."""
    if _UID_CACHE["v"]:
        return _UID_CACHE["v"]
    if not TOK:
        return UID
    try:
        u = API + "/me?fields=id&access_token=" + TOK
        with urllib.request.urlopen(u, timeout=25) as r:
            _UID_CACHE["v"] = json.loads(r.read().decode()).get("id") or UID
    except Exception:
        _UID_CACHE["v"] = UID
    return _UID_CACHE["v"]


def publish(text, image_url=None, link=None):
    uid = _resolve_uid()
    if not (uid and TOK):
        return {"ok": False, "error": "THREADS_ACCESS_TOKEN 미설정"}
    p = {"access_token": TOK, "text": text[:480]}
    if image_url:
        p["media_type"] = "IMAGE"
        p["image_url"] = image_url
    else:
        p["media_type"] = "TEXT"
        if link:
            p["link_attachment"] = link
    try:
        c = _post("/%s/threads" % uid, p)
        cid = c.get("id")
        if not cid:
            return {"ok": False, "error": "컨테이너 생성 실패", "detail": c}
        time.sleep(3)   # 미디어 처리 대기
        r = _post("/%s/threads_publish" % uid,
                  {"access_token": TOK, "creation_id": cid})
        return {"ok": True, "id": r.get("id"), "container": cid}
    except Exception as e:
        body = ""
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        return {"ok": False, "error": str(e)[:120], "detail": body}


@th_bp.route("/api/th/cb")
def th_cb():
    """Meta 리디렉션 콜백 — 검증용. code 를 받아 화면에 표시만 한다."""
    code = request.args.get("code") or ""
    err = request.args.get("error_description") or request.args.get("error") or ""
    if err:
        return Response("<h3>인증 실패</h3><p>%s</p>" % err[:200],
                        mimetype="text/html; charset=utf-8")
    if code:
        return Response("<h3>코드 수신</h3><p style='word-break:break-all'>%s</p>"
                        "<p>이 값을 토큰 교환에 사용하세요.</p>" % code[:400],
                        mimetype="text/html; charset=utf-8")
    return Response("<h3>Threads callback ready</h3>", mimetype="text/html; charset=utf-8")


@th_bp.route("/api/th/status")
def th_status():
    return jsonify({"ok": True, "uid_set": bool(UID), "token_set": bool(TOK),
                    "admin_set": bool(ADMIN)})


@th_bp.route("/api/th/post", methods=["POST"])
def th_post():
    if not ADMIN or (request.headers.get("X-Admin-Key") or "") != ADMIN:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    text = (d.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text 필요"}), 400
    return jsonify(publish(text, d.get("image_url"), d.get("link")))


@th_bp.route("/api/th/me")
def th_me():
    """토큰에 물린 계정 확인 — 첫 게시 전에 어느 계정인지 반드시 본다."""
    if not TOK:
        return jsonify({"ok": False, "error": "토큰 없음"}), 400
    u = API + "/me?fields=id,username,name,threads_profile_picture_url&access_token=" + TOK
    try:
        with urllib.request.urlopen(u, timeout=30) as r:
            return jsonify({"ok": True, "me": json.loads(r.read().decode())})
    except Exception as e:
        body = ""
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        return jsonify({"ok": False, "error": str(e)[:120], "detail": body}), 502


@th_bp.route("/api/th/refresh")
def th_refresh():
    """장기 토큰 갱신 — 60일마다 필요. 만료 전에 호출하면 60일 연장된다.
       결과 토큰을 Render 환경변수에 다시 넣어야 반영된다."""
    if not ADMIN or (request.args.get("key") or "") != ADMIN:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if not TOK:
        return jsonify({"ok": False, "error": "토큰 없음"}), 400
    u = (API + "/refresh_access_token?grant_type=th_refresh_token"
         "&access_token=" + TOK)
    try:
        with urllib.request.urlopen(u, timeout=30) as r:
            d = json.loads(r.read().decode())
        return jsonify({"ok": True, "new_token": d.get("access_token"),
                        "expires_in_days": round(d.get("expires_in", 0) / 86400),
                        "note": "이 값을 THREADS_ACCESS_TOKEN 에 다시 넣으세요"})
    except Exception as e:
        body = ""
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        return jsonify({"ok": False, "error": str(e)[:120], "detail": body}), 502


_TMPL = {
    "rx": ("해외 나가기 전에 확인하세요.\n\n{q} — {head}\n{src}\n\n"
           "약 이름만 넣으면 21개국 반입 가능 여부가 5초 만에 나옵니다.\n"
           "linklynk.onrender.com/next"),
}


@th_bp.route("/api/th/quick", methods=["POST"])
def th_quick():
    """약 이름 하나로 카드+문구를 자동 구성해 게시한다."""
    if not ADMIN or (request.headers.get("X-Admin-Key") or "") != ADMIN:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    q = (d.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "error": "q(약 이름) 필요"}), 400
    try:
        from next_v1 import verdict
        v = verdict(q)
    except Exception as e:
        return jsonify({"ok": False, "error": "판정 실패: " + str(e)[:80]}), 500
    if not v.get("ok"):
        return jsonify({"ok": False, "error": v.get("error")}), 400
    src = "UN 국제통제물질 등재" if v.get("incb") else "각국 개별 규제"
    text = _TMPL["rx"].format(q=q, head=v["head"], src=src)
    if d.get("text"):
        text = d["text"]
    img = ("https://linklynk.onrender.com/next/card/"
           + urllib.parse.quote(q) + ".png")
    if d.get("dry"):
        return jsonify({"ok": True, "dry": True, "text": text, "image_url": img})
    r = publish(text, img)
    r["text"] = text
    return jsonify(r)
