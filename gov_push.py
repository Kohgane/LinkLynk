# -*- coding: utf-8 -*-
"""과태료레이더 기한 푸시 — 구독 수신 + 앱인토스 스마트발송 호출.

이 앱은 1년에 한두 번 쓰는 앱이라 재방문이 구조적으로 낮다.
기한이 다가올 때 먼저 찾아가는 게 이 앱의 본체다.

★ 설정이 없으면 전부 무해하게 꺼진다.
   AIT_NOTIF_TEMPLATE  : 콘솔 기능성 캠페인 템플릿 코드 (penaltyradar-...)
   AIT_MTLS_CERT_PEM   : 클라이언트 인증서 PEM
   AIT_MTLS_KEY_PEM    : 클라이언트 키 PEM
   셋 다 있어야 실제로 쏜다. 하나라도 없으면 집계만 하고 발송은 건너뛴다.
"""
import os, json, time, ssl, tempfile, datetime
import urllib.request
from flask import request, jsonify

API = "https://apps-in-toss-api.toss.im"
SEND_BULK = "/api-partner/v1/apps-in-toss/messenger/send-bulk-message"
MILESTONES = (30, 7, 1)      # D-30 · D-7 · D-1 에 한 번씩
MAX_PER_CALL = 2500          # 토스 제한


def _env(k):
    v = os.environ.get(k) or ""
    return v.strip()


def _pem(k):
    """PEM 전문 또는 base64 한 줄, 둘 다 받는다.
    Render 입력칸에 줄바꿈이 깨져 들어가는 사고를 막으려는 안전망이다."""
    v = _env(k)
    if not v:
        return ""
    if "-----BEGIN" in v:
        if not _valid_pem(v):
            return ""
        return v if v.endswith("\n") else v + "\n"
    try:
        import base64
        d = base64.b64decode(v, validate=True).decode("utf-8")
        return d if _valid_pem(d) else ""
    except Exception:
        return ""


def _valid_pem(v):
    """BEGIN/END 가 짝으로 있고 본문이 실제로 들어있어야 유효로 본다.
    ★첫 줄만 붙여넣어도 통과하던 거짓 양성을 막는다."""
    if "-----BEGIN" not in v or "-----END" not in v:
        return False
    try:
        body = v.split("-----\n", 1)[1].rsplit("-----END", 1)[0]
    except Exception:
        return False
    return len(body.strip()) >= 200


def template_code():
    """환경변수에 다른 값이 이어붙어 들어오는 사고를 자동 교정한다.
    템플릿 코드에는 공백·줄바꿈이 들어갈 수 없으므로 첫 토큰만 쓴다."""
    return (_env("AIT_NOTIF_TEMPLATE").split() or [""])[0]


def _mtls_ready():
    return bool(template_code() and _pem("AIT_MTLS_CERT_PEM") and _pem("AIT_MTLS_KEY_PEM"))


# ── 저장 ────────────────────────────────────────────────────────────────

def _q(sql, params=None, fetch=None):
    import store
    return store._q(sql, params, fetch)


def init():
    _q("""CREATE TABLE IF NOT EXISTS gov_push_sub(
            k TEXT PRIMARY KEY,
            items JSONB NOT NULL,
            sent JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at BIGINT)""")


def _save(k, items):
    init()
    _q("""INSERT INTO gov_push_sub(k, items, updated_at) VALUES(%s, %s, %s)
          ON CONFLICT (k) DO UPDATE SET items = EXCLUDED.items,
                                        updated_at = EXCLUDED.updated_at""",
       (k, json.dumps(items, ensure_ascii=False), int(time.time())))


# ── 발송 ────────────────────────────────────────────────────────────────

def _ctx():
    """mTLS 컨텍스트. PEM 을 임시파일로 떨궈 쓴다 (ssl 이 파일 경로만 받는다)."""
    c = ssl.create_default_context()
    cf = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
    kf = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
    try:
        cf.write(_pem("AIT_MTLS_CERT_PEM")); cf.close()
        kf.write(_pem("AIT_MTLS_KEY_PEM")); kf.close()
        os.chmod(cf.name, 0o600); os.chmod(kf.name, 0o600)
        c.load_cert_chain(cf.name, kf.name)
        return c, cf.name, kf.name
    except Exception:
        for p in (cf.name, kf.name):
            try: os.unlink(p)
            except Exception: pass
        raise


def _post(path, payload):
    ctx, cp, kp = _ctx()
    try:
        req = urllib.request.Request(
            API + path, method="POST",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    finally:
        for p in (cp, kp):
            try: os.unlink(p)
            except Exception: pass


def due_today():
    """오늘 쏴야 할 (k, 항목, 남은일수) 목록. 이미 보낸 마일스톤은 건너뛴다."""
    init()
    rows = _q("SELECT k, items, sent FROM gov_push_sub", fetch="all") or []
    today = datetime.date.today()
    out = []
    for row in rows:
        items = row["items"] or []
        sent = row["sent"] or {}
        for it in items:
            due = it.get("due")
            if not due:
                continue
            try:
                d = (datetime.date.fromisoformat(due) - today).days
            except Exception:
                continue
            if d not in MILESTONES:
                continue
            key = "%s@%s" % (it.get("title", ""), due)
            if str(d) in (sent.get(key) or []):
                continue
            out.append((row["k"], it.get("title", ""), d, due, key))
    return out


def run(limit=MAX_PER_CALL):
    """크론에서 부른다. 설정이 없으면 셀 뿐 쏘지 않는다."""
    pend = due_today()
    if not pend:
        return {"ok": True, "pending": 0, "sent": 0, "armed": _mtls_ready(),
                "diag": diag()}
    if not _mtls_ready():
        return {"ok": True, "pending": len(pend), "sent": 0, "armed": False,
                "note": "AIT_NOTIF_TEMPLATE / AIT_MTLS_* 미설정 — 발송 건너뜀"}

    batch, meta = [], []
    for k, title, d, due, key in pend[:limit]:
        batch.append({"anonKey": k, "context": {"title": title, "dday": str(d)}})
        meta.append((k, key, d))

    res = _post(SEND_BULK, {"templateSetCode": template_code(), "contextList": batch})
    if (res or {}).get("resultType") != "SUCCESS":
        return {"ok": False, "pending": len(pend), "sent": 0, "resp": res}

    for k, key, d in meta:                      # 보낸 마일스톤 기록 (중복 발송 방지)
        _q("""UPDATE gov_push_sub
                 SET sent = jsonb_set(sent, %s,
                        COALESCE(sent->%s, '[]'::jsonb) || %s::jsonb, true)
               WHERE k = %s""",
           ("{%s}" % key.replace('"', ''), key, json.dumps([str(d)]), k))

    return {"ok": True, "pending": len(pend), "sent": len(batch),
            "detail": (res.get("success") or {}).get("msgCount")}


# ── 라우트 ──────────────────────────────────────────────────────────────

def register(app):
    @app.route("/api/gov/sub", methods=["POST", "OPTIONS"])
    def gov_sub_api():
        if request.method == "OPTIONS":
            r = app.make_response(("", 204))
            r.headers["Access-Control-Allow-Origin"] = "*"
            r.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
            r.headers["Access-Control-Allow-Headers"] = "Content-Type"
            return r

        d = request.get_json(force=True, silent=True) or {}
        k = (d.get("k") or "").strip()
        raw = d.get("items") or []
        # 받는 건 익명키와 기한뿐. 생년·차량번호 같은 입력값은 받지 않는다.
        today = datetime.date.today()
        items = []
        for it in raw[:20]:
            try:
                days = int(it.get("days"))
                title = str(it.get("title") or "")[:40]
            except Exception:
                continue
            if not title or days < -400 or days > 4000:
                continue
            items.append({"title": title,
                          "due": (today + datetime.timedelta(days=days)).isoformat()})

        if not k or len(k) < 8 or not items:
            r = jsonify({"ok": False, "error": "bad request"})
            r.headers["Access-Control-Allow-Origin"] = "*"
            return r, 400
        try:
            _save(k, items)
            ok = True
        except Exception:
            ok = False
        r = jsonify({"ok": ok, "n": len(items)})
        r.headers["Access-Control-Allow-Origin"] = "*"
        return r


def diag():
    """설정 점검용. 비밀값은 절대 내보내지 않고 길이와 유효성만 돌려준다."""
    out = {"template": template_code(),
           "template_raw_len": len(_env("AIT_NOTIF_TEMPLATE"))}
    for k, label in (("AIT_MTLS_CERT_PEM", "cert"), ("AIT_MTLS_KEY_PEM", "key")):
        raw = _env(k)
        pem = _pem(k)
        out[label] = {"raw_len": len(raw), "valid": bool(pem)}
    if out["cert"]["valid"] and out["key"]["valid"]:
        try:
            _ctx_t = _ctx()
            for f in _ctx_t[1:]:
                try: os.unlink(f)
                except Exception: pass
            out["handshake_ready"] = True
        except Exception as e:
            out["handshake_ready"] = False
            out["handshake_error"] = type(e).__name__
    else:
        out["handshake_ready"] = False
    return out
