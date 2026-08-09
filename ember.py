# -*- coding: utf-8 -*-
"""불씨(ember) — 둘이서 잇는 공동 스트릭. Supabase Storage를 KV로 사용(재배포 생존).
pair JSON: {code, a:{did,name}, b:{did,name}|None, streak, freeze,
            day: 'YYYY-MM-DD', a_done, b_done, a_mood, b_mood, last_complete}"""
import os, json, random, string, urllib.request, datetime, threading

SB_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or ""
BUCKET = os.environ.get("SUPABASE_BUCKET", "linklynk-media")
_cache = {}
_lock = threading.Lock()

def _kst_today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")

def _yesterday(day):
    d = datetime.datetime.strptime(day, "%Y-%m-%d") - datetime.timedelta(days=1)
    return d.strftime("%Y-%m-%d")

def _sb(method, key, data=None):
    # GET도 인증 경로(오리진 직행) — public URL CDN 전파 지연 회피
    url = "%s/storage/v1/object/%s/ember/%s.json" % (SB_URL, BUCKET, key)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + SB_KEY)
    req.add_header("apikey", SB_KEY)
    if method != "GET":
        req.add_header("Content-Type", "application/json")
        req.add_header("x-upsert", "true")
    return urllib.request.urlopen(req, timeout=12).read()

def load(code):
    """멀티워커 정합성: 스토리지가 항상 진실, 메모리 캐시는 장애 폴백."""
    code = (code or "").upper()
    if SB_URL and SB_KEY:
        try:
            p = json.loads(_sb("GET", code))
            with _lock:
                _cache[code] = p
            return dict(p)
        except Exception:
            pass
    with _lock:
        if code in _cache:
            return dict(_cache[code])
    return None

def save(p):
    with _lock:
        _cache[p["code"]] = dict(p)
    if SB_URL and SB_KEY:
        try:
            _sb("POST", p["code"], json.dumps(p, ensure_ascii=False).encode())
        except Exception:
            pass

def create(did, name, solo=False):
    code = "".join(random.choices(string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789", k=6))
    b = {"did": "bot", "name": "불씨봇 🤖"} if solo else None
    p = {"code": code, "a": {"did": did, "name": name[:12]}, "b": b,
         "streak": 0, "freeze": 0, "day": _kst_today(),
         "a_done": False, "b_done": False, "a_mood": "", "b_mood": "",
         "last_complete": ""}
    if solo:
        p["b_done"] = True; p["b_mood"] = "🤖"; p["b_note"] = "오늘도 자동으로 지켰다"
    save(p)
    return p

def join(code, did, name):
    p = load(code)
    if not p:
        return None, "코드를 찾을 수 없어요"
    if p.get("b") and p["b"]["did"] != did and p["a"]["did"] != did:
        return None, "이미 두 명이 연결된 불씨예요"
    if p["a"]["did"] == did:
        return p, None
    if not p.get("b"):
        p["b"] = {"did": did, "name": name[:12]}
        save(p)
    return p, None

def _rollover(p):
    """날짜가 바뀌었으면 스트릭 정산: 어제 완성 못 했으면 프리즈 소모 또는 소멸."""
    today = _kst_today()
    if p["day"] == today:
        return p
    completed = p["a_done"] and p["b_done"]
    if not completed and p["streak"] > 0:
        # 하루 이상 공백: 어제까지가 p['day']였는지 확인
        gap_end = _yesterday(today)
        if p["day"] < gap_end or not completed:
            if p.get("freeze", 0) > 0 and p["day"] == gap_end:
                p["freeze"] -= 1        # 프리즈 1개로 하루 방어
            else:
                p["streak"] = 0
    if p.get("a_note") or p.get("b_note") or p.get("a_mood") or p.get("b_mood"):
        p.setdefault("log", []).append({
            "d": p["day"], "a": p.get("a_note", ""), "b": p.get("b_note", ""),
            "am": p.get("a_mood", ""), "bm": p.get("b_mood", ""),
            "full": bool(p.get("a_done") and p.get("b_done"))})
        p["log"] = p["log"][-40:]
    p["m_off"] = 0
    p["chat"] = []
    p["day"] = today
    p["a_done"] = False; p["b_done"] = False
    if p.get("b") and p["b"].get("did") == "bot":
        p["b_done"] = True; p["b_mood"] = "🤖"; p["b_note"] = "오늘도 자동으로 지켰다"
    p["a_mood"] = ""; p["b_mood"] = ""
    p["a_note"] = ""; p["b_note"] = ""
    p["a_vibe"] = ""; p["b_vibe"] = ""
    save(p)
    return p

BOT_FALLBACK = [
    "오 그거 좋다, 내일도 이어가자 🔥", "듣기만 해도 따뜻하네", "역시 너답다 ㅋㅋ",
    "장작 하나 더 넣은 기분이야", "그 얘기 내일 더 해줘", "오늘도 불가에 와줘서 고마워",
    "그럴 때가 제일 어렵지, 잘했어", "내일은 더 좋은 일 있을 거야", "불꽃이 살짝 커진 것 같아",
]


CHAT_FALLBACK = [
    "ㅋㅋ 그래서 그래서?", "오 더 얘기해봐", "불멍이나 같이 때리자 🔥", "그럴 수 있지",
    "장작이나 하나 더 넣자", "듣고 있어, 계속해봐", "음… 그 말 좀 깊다", "내일은 뭐 할 거야?",
    "네 얘기 들으니까 불이 더 따뜻해졌어", "그건 나도 궁금했어", "오늘 하늘은 봤어?", "탁— (장작 튀는 소리)",
]


def _bot_reply(note, name, kind="checkin"):
    import os, random
    if not note:
        return "오늘도 자동으로 지켰다"
    try:
        from core import llm_chat
        key = os.environ.get("BOIM_LLM_KEY", "").strip() or "__free__"
        if kind == "chat":
            sys_p = ("너는 '불씨봇'. 모닥불 앞에서 사용자와 수다 떠는 불친구다. "
                     "사용자의 말에 자연스럽게 반말로 대화를 이어가라. 궁금하면 되물어도 좋다. "
                     "40자 이내 딱 한 문장. 이모지 최대 1개.")
        else:
            sys_p = ("너는 '불씨봇'. 모닥불 앱에서 혼자 스트릭을 잇는 사용자의 유일한 불친구다. "
                     "사용자의 오늘 미션 답/한마디에 짧고 따뜻하게, 반말로, 재치있게 답해라. "
                     "40자 이내 딱 한 문장. 이모지 최대 1개. 설교 금지.")
        r = llm_chat(key, sys_p, "%s: %s" % (name, note[:60]), max_tokens=80)
        r = (r or "").strip().strip('"').replace("\n", " ")
        if 2 <= len(r) <= 60:
            return r[:44]
    except Exception:
        pass
    return random.choice(CHAT_FALLBACK if kind == "chat" else BOT_FALLBACK)


def checkin(code, did, mood, note="", av="", vibe=""):
    p = load(code)
    if not p:
        return None, "불씨를 찾을 수 없어요"
    p = _rollover(p)
    side = "a" if p["a"]["did"] == did else ("b" if p.get("b") and p["b"]["did"] == did else None)
    if not side:
        return None, "이 불씨의 멤버가 아니에요"
    p[side + "_done"] = True
    p[side + "_mood"] = (mood or "")[:4]
    p[side + "_note"] = (note or "")[:40]
    if av:
        p[side + "_av"] = av[:4]
    if vibe:
        p[side + "_vibe"] = vibe[:16]
    # 솔로 페어: 봇이 내 한마디에 AI로 답장
    if p.get("b") and p["b"].get("did") == "bot" and side == "a":
        p["b_note"] = _bot_reply(note, p["a"].get("name", "친구"))
        import random as _r
        p["b_mood"] = _r.choice(["😊", "🔥", "🤗", "😎", "🥰"])
    if p["a_done"] and p["b_done"] and p["last_complete"] != p["day"]:
        p["streak"] += 1
        p["last_complete"] = p["day"]
        # ★7일마다 프리즈 1개 보상 (최대 2)
        if p["streak"] % 7 == 0:
            p["freeze"] = min(p.get("freeze", 0) + 1, 2)
    save(p)
    return p, None


_TITLES = [(365, "🌅 영원한 불"), (100, "🔥 화톳불"), (60, "🗼 봉화"), (30, "🕯 횃불"),
           (14, "🏮 화롯불"), (7, "🪵 모닥불"), (3, "✨ 불꽃지기"), (1, "🔥 불씨"), (0, "🌱 첫 불씨 전")]

_QS = ["오늘 최고의 한 입은 뭐였어?", "오늘 나를 웃게 한 순간은?", "지금 제일 듣고 싶은 노래는?",
 "오늘 하루를 색으로 표현하면?", "요즘 제일 기다려지는 게 뭐야?", "오늘 가장 고마웠던 사람은?",
 "지금 창밖 날씨 어때?", "오늘의 나에게 점수를 준다면?", "요즘 빠져있는 거 하나만!",
 "내일 꼭 하고 싶은 것 하나는?", "오늘 들은 말 중 기억에 남는 건?", "지금 먹고 싶은 야식은?",
 "오늘 걸은 길 중 제일 좋았던 곳은?", "요즘 고민 한 줄로 하면?", "오늘 산 것 중 제일 잘 산 건?",
 "어릴 때 이맘때 뭐 하고 놀았어?", "지금 당장 떠난다면 어디로?", "오늘의 BGM은 뭐였어?",
 "요즘 제일 자주 쓰는 이모지는?", "오늘 처음 해본 게 있다면?", "지금 옆에 있으면 좋겠는 것?",
 "오늘 하루 중 다시 돌리고 싶은 순간은?", "요즘 최애 간식은?", "오늘 나의 MVP 순간은?",
 "함께 가보고 싶은 곳 하나만!", "오늘 배운 것 하나는?", "지금 기분을 날씨로 말하면?",
 "요즘 아침에 눈 뜨면 제일 먼저 뭐 해?", "오늘 제일 오래 본 화면은?", "이번 주말에 뭐 하고 싶어?",
 "최근에 참은 것 중 제일 힘들었던 건?", "오늘 스스로 칭찬할 일 하나는?", "요즘 새로 알게 된 맛집은?",
 "지금 생각나는 옛날 추억 하나는?", "오늘 하루가 영화라면 제목은?", "요즘 위시리스트 1순위는?",
 "오늘 마신 것 중 제일 맛있던 건?", "함께 해보고 싶은 챌린지 있어?", "오늘 만난 귀여운 것은?",
 "지금 딱 한 시간 자유시간이 생기면?", "요즘 제일 편한 옷은?", "오늘 나를 버티게 한 건?",
 "최근 웃긴 짤 하나 소환한다면?", "오늘 밥 뭐 먹었어? 솔직히!", "요즘 잠들기 전에 뭐 해?",
 "우리 처음 만났을 때 첫인상 기억나?", "오늘 하늘 봤어? 어땠어?", "요즘 제일 아끼는 물건은?",
 "다음에 만나면 뭐 먹을까?", "오늘의 컨디션 몇 %였어?", "요즘 도전해보고 싶은 건?",
 "오늘 지나가다 본 것 중 인상 깊은 건?", "겨울/여름 중 지금 어느 쪽이 그리워?", "요즘 나의 스트레스 해소법은?",
 "오늘 누군가에게 들키고 싶지 않았던 순간은?", "지금 당장 순간이동 된다면?", "요즘 제일 보고 싶은 사람은?",
 "오늘 한 결정 중 제일 잘한 건?", "나의 요즘을 한 단어로 하면?", "오늘 밤 꿈에서 보고 싶은 장면은?"]


def title_of(streak):
    return next(t for th, t in _TITLES if streak >= th)


def q_today():
    doy = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).timetuple().tm_yday
    return _QS[doy % len(_QS)]


def state(code, did):
    p = load(code)
    if not p:
        return None
    p = _rollover(p)
    me, other = ("a", "b") if p["a"]["did"] == did else ("b", "a")
    if me == "b" and not p.get("b"):
        return None
    o = p.get(other) or {}
    return {"code": p["code"], "streak": p["streak"], "freeze": p.get("freeze", 0),
            "partner": o.get("name") or "", "connected": bool(p.get("b")),
            "my_done": p[me + "_done"], "partner_done": p[other + "_done"] if p.get(other) else False,
            "partner_mood": p[other + "_mood"] if p.get(other) else "",
            "partner_note": p.get(other + "_note", "") if p.get(other) else "",
            "my_note": p.get(me + "_note", ""),
            "partner_av": p.get(other + "_av", "") if p.get(other) else "",
            "my_av": p.get(me + "_av", ""),
            "my_vibe": p.get(me + "_vibe", ""),
            "partner_vibe": p.get(other + "_vibe", "") if p.get(other) else "",
            "packs": p.get("packs", ["daily"]),
            "custom": p.get("custom", []),
            "m_off": p.get("m_off", 0),
            "solo": bool(p.get("b") and p["b"].get("did") == "bot"),
            "chat": [{**c, "me": c["s"] == me} for c in p.get("chat", [])[-24:]],
            "log": list(reversed(p.get("log", [])[-30:])),
            "title": title_of(p["streak"]), "q": q_today(),
            "week_full": sum(1 for x in p.get("log", [])[-7:] if x.get("full")),
            "both_done": p["a_done"] and p["b_done"]}

def add_freeze(code):
    p = load(code)
    if not p:
        return None
    p["freeze"] = min(p.get("freeze", 0) + 1, 2)
    save(p)
    return p


def set_missions(code, packs, custom):
    p = load(code)
    if not p:
        return None
    p["packs"] = [str(x)[:12] for x in packs][:6] or ["daily"]
    p["custom"] = [str(x)[:60] for x in custom][:10]
    save(p)
    return p


def reroll(code):
    p = load(code)
    if not p:
        return None, "불씨를 찾을 수 없어요"
    p = _rollover(p)
    if p.get("m_off", 0) >= 6:
        return None, "오늘 미션 바꾸기를 다 썼어요"
    p["m_off"] = p.get("m_off", 0) + 1
    save(p)
    return p, None


def reroll_refill(code):
    p = load(code)
    if not p:
        return None
    p["m_off"] = max(0, p.get("m_off", 0) - 3)
    save(p)
    return p


def bot_set(code, av="", mood="", vibe="", name=""):
    p = load(code)
    if not p or not p.get("b") or p["b"].get("did") != "bot":
        return None
    if av:
        p["b_av"] = av[:4]
    if mood:
        p["b_mood"] = mood[:4]
    if vibe:
        p["b_vibe"] = vibe[:16]
    if name:
        p["b"]["name"] = name[:12]
    save(p)
    return p


def say(code, did, text):
    p = load(code)
    if not p:
        return None, "불씨를 찾을 수 없어요"
    p = _rollover(p)
    side = "a" if p["a"]["did"] == did else ("b" if p.get("b") and p["b"]["did"] == did else None)
    if not side:
        return None, "이 불씨의 멤버가 아니에요"
    text = (text or "").strip()[:60]
    if not text:
        return None, "내용이 비었어요"
    chat = p.setdefault("chat", [])
    if len(chat) >= 60:
        return None, "오늘 대화가 가득 찼어요"
    import datetime as _dt
    chat.append({"s": side, "t": text, "ts": _dt.datetime.utcnow().strftime("%H:%M")})
    if p.get("b") and p["b"].get("did") == "bot" and side == "a":
        chat.append({"s": "b", "t": _bot_reply(text, p["a"].get("name", "친구"), kind="chat"),
                     "ts": _dt.datetime.utcnow().strftime("%H:%M")})
    p["chat"] = chat[-60:]
    save(p)
    return p, None
