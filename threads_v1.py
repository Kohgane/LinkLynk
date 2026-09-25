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


# ── 측정 ──────────────────────────────────────────────────────────
# 올린 뒤 숫자를 본다. 안 보면 관객이 반응한 훅을 영영 못 찾는다.

def _gate():
    k = request.headers.get("X-Admin-Key") or request.args.get("key") or ""
    return bool(ADMIN) and k == ADMIN


def _get(path):
    u = API + path + ("&" if "?" in path else "?") + "access_token=" + TOK
    with urllib.request.urlopen(urllib.request.Request(u), timeout=30) as r:
        return json.loads(r.read().decode())


def _val(it):
    tv = it.get("total_value")
    if isinstance(tv, dict) and "value" in tv:
        return tv["value"]
    vs = it.get("values") or []
    if vs and isinstance(vs[0], dict):
        return vs[0].get("value") or 0
    return 0


_M_FULL = "views,likes,replies,reposts,quotes,shares"
_M_SAFE = "views,likes,replies"
_ENG = ("likes", "replies", "reposts", "quotes", "shares")


def _insights(mid):
    """지표 일부가 미지원이면 전체가 400 난다 -> 축소 재시도.
       둘 다 실패하면 조용히 넘기지 않고 오류를 돌려준다."""
    err = ""
    for m in (_M_FULL, _M_SAFE):
        try:
            d = _get("/%s/insights?metric=%s" % (mid, m))
            out = {}
            for it in (d.get("data") or []):
                out[it.get("name")] = _val(it)
            return out
        except Exception as e:
            err = str(e)[:80]
            try:
                err = e.read().decode()[:200]
            except Exception:
                pass
    return {"_err": err}


def _rows(n):
    uid = _resolve_uid()
    d = _get("/%s/threads?fields=id,text,media_type,permalink,timestamp&limit=%d"
             % (uid, n))
    rows = []
    for p in (d.get("data") or []):
        ins = _insights(p.get("id"))
        v = int(ins.get("views") or 0)
        e = sum(int(ins.get(k) or 0) for k in _ENG)
        rows.append({
            "id": p.get("id"),
            "when": (p.get("timestamp") or "")[:16].replace("T", " "),
            "type": p.get("media_type") or "",
            "views": v, "eng": e,
            "er": round(e * 100.0 / v, 1) if v else 0.0,
            "likes": int(ins.get("likes") or 0),
            "replies": int(ins.get("replies") or 0),
            "reposts": int(ins.get("reposts") or 0),
            "shares": int(ins.get("shares") or 0),
            "text": (p.get("text") or "").replace("\n", " ").strip(),
            "permalink": p.get("permalink") or "",
            "err": ins.get("_err") or "",
        })
    return rows


def _followers():
    try:
        d = _get("/%s/threads_insights?metric=followers_count" % _resolve_uid())
        for it in (d.get("data") or []):
            return int(_val(it) or 0)
    except Exception:
        pass
    return -1


def _txt(rows, fol):
    L = ["팔로워 %s" % ("확인불가" if fol < 0 else fol), ""]
    L.append("%-16s %7s %5s %6s  %s" % ("when", "views", "eng", "er%", "text"))
    L.append("-" * 72)
    for r in rows:
        L.append("%-16s %7d %5d %5.1f%%  %s"
                 % (r["when"], r["views"], r["eng"], r["er"], r["text"][:34]))
    tv = sum(r["views"] for r in rows)
    te = sum(r["eng"] for r in rows)
    L.append("-" * 72)
    L.append("%d건 · 노출 %d · 반응 %d · 평균 %.1f%%"
             % (len(rows), tv, te, (te * 100.0 / tv if tv else 0)))
    bad = [r for r in rows if r["err"]]
    if bad:
        L.append("")
        L.append("insights 오류: " + bad[0]["err"][:200])
        L.append("-> threads_manage_insights 권한이 토큰에 없을 가능성")
    return "\n".join(L) + "\n"


@th_bp.route("/api/th/posts")
def th_posts():
    """게시물 목록만 — insights 없이 빠르게."""
    if not _gate():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if not TOK:
        return jsonify({"ok": False, "error": "토큰 없음"}), 400
    n = max(1, min(int(request.args.get("limit") or 25), 50))
    try:
        d = _get("/%s/threads?fields=id,text,media_type,permalink,timestamp&limit=%d"
                 % (_resolve_uid(), n))
        return jsonify({"ok": True, "posts": d.get("data") or []})
    except Exception as e:
        body = ""
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        return jsonify({"ok": False, "error": str(e)[:120], "detail": body}), 502


@th_bp.route("/api/th/stats")
def th_stats():
    """게시물 + 지표. fmt=txt 면 터미널용 표로."""
    if not _gate():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if not TOK:
        return jsonify({"ok": False, "error": "토큰 없음"}), 400
    n = max(1, min(int(request.args.get("limit") or 25), 50))
    try:
        rows = _rows(n)
    except Exception as e:
        body = ""
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        return jsonify({"ok": False, "error": str(e)[:120], "detail": body}), 502
    fol = _followers()
    if (request.args.get("fmt") or "") == "txt":
        return Response(_txt(rows, fol), mimetype="text/plain; charset=utf-8")
    rows_s = sorted(rows, key=lambda r: r["views"], reverse=True)
    return jsonify({"ok": True, "followers": fol, "n": len(rows),
                    "total_views": sum(r["views"] for r in rows),
                    "total_eng": sum(r["eng"] for r in rows),
                    "posts": rows_s})


# ── 2차 측정용: 본문 링크 없이 올리고 링크는 첫 댓글로 ────────────
# 기존 publish() 는 건드리지 않는다. 살아있는 경로다.

def publish2(text, image_url=None, reply_to=None):
    """link_attachment 를 의도적으로 넣지 않는다 — 그게 이 실험의 변수다."""
    uid = _resolve_uid()
    if not (uid and TOK):
        return {"ok": False, "error": "THREADS_ACCESS_TOKEN 미설정"}
    p = {"access_token": TOK, "text": text[:480]}
    if image_url:
        p["media_type"] = "IMAGE"
        p["image_url"] = image_url
    else:
        p["media_type"] = "TEXT"
    if reply_to:
        p["reply_to_id"] = reply_to
    try:
        c = _post("/%s/threads" % uid, p)
        cid = c.get("id")
        if not cid:
            return {"ok": False, "error": "컨테이너 생성 실패", "detail": c}
        time.sleep(3 if image_url else 1)
        r = _post("/%s/threads_publish" % uid,
                  {"access_token": TOK, "creation_id": cid})
        return {"ok": True, "id": r.get("id")}
    except Exception as e:
        body = ""
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        return {"ok": False, "error": str(e)[:120], "detail": body}


@th_bp.route("/api/th/thread", methods=["POST"])
def th_thread():
    """본문 + 첫 댓글을 한 번에. dry=1 이면 올리지 않고 보여만 준다."""
    if not _gate():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    d = request.get_json(silent=True) or {}
    text = (d.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "text 필요"}), 400
    img = d.get("image_url") or None
    rep = (d.get("reply") or "").strip()
    if d.get("dry"):
        return jsonify({"ok": True, "dry": True, "text": text,
                        "chars": len(text), "image_url": img, "reply": rep})
    if img:
        try:
            with urllib.request.urlopen(img, timeout=20) as r:
                if r.status != 200:
                    return jsonify({"ok": False, "error": "이미지 200 아님"}), 400
        except Exception as e:
            return jsonify({"ok": False,
                            "error": "이미지 확인 실패: " + str(e)[:80]}), 400
    par = publish2(text, img)
    if not par.get("ok"):
        return jsonify(par), 502
    out = {"ok": True, "parent": par.get("id")}
    if rep:
        time.sleep(2)
        rr = publish2(rep, None, par.get("id"))
        out["reply"] = rr.get("id")
        out["reply_ok"] = rr.get("ok")
        if not rr.get("ok"):
            out["reply_error"] = rr.get("error")
    return jsonify(out)
