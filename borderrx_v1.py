# -*- coding: utf-8 -*-
"""BorderRx / 약 반입 판정기 v1 — 로직부"""
import os, re, json, time, requests
from flask import Blueprint, request, jsonify, Response

rx_bp = Blueprint("borderrx", __name__)
UA = {"User-Agent": "BorderRx/1.0 (+https://linklynk.onrender.com/rx)"}
TO = 12
HERE = os.path.dirname(os.path.abspath(__file__))
_INCB = None
def incb():
    global _INCB
    if _INCB is None:
        try:
            _INCB = json.load(open(os.path.join(HERE, "data", "incb_db.json"), encoding="utf-8"))
        except Exception:
            _INCB = []
    return _INCB
_c = {}
def _get(k):
    v = _c.get(k)
    return v[1] if v and time.time() - v[0] < 86400 else None
def _put(k, v):
    _c[k] = (time.time(), v)
    if len(_c) > 900:
        for kk in sorted(_c, key=lambda x: _c[x][0])[:250]:
            _c.pop(kk, None)
    return v
COUNTRIES = [
    ("JP", "\U0001F1EF\U0001F1F5", "일본", "Japan"),
    ("KR", "\U0001F1F0\U0001F1F7", "한국", "South Korea"),
    ("US", "\U0001F1FA\U0001F1F8", "미국", "United States"),
    ("SG", "\U0001F1F8\U0001F1EC", "싱가포르", "Singapore"),
    ("AE", "\U0001F1E6\U0001F1EA", "UAE", "United Arab Emirates"),
    ("GB", "\U0001F1EC\U0001F1E7", "영국", "United Kingdom"),
]
SRC = {
    "JP": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iyakuhin/index.html",
    "KR": "https://www.customs.go.kr/",
    "US": "https://www.fda.gov/industry/import-basics/personal-importation",
    "SG": "https://www.hsa.gov.sg/",
    "AE": "https://mohap.gov.ae/",
    "GB": "https://www.gov.uk/take-medicine-in-or-out-uk",
}
NATIONAL = {
    "pseudoephedrine": {
        "JP": ("PROHIBITED", "각성제원료로 지정. 처방전이 있어도 반입 불가. 슈다페드 등 미국 감기약 해당", True),
        "US": ("LIMIT", "약국 판매 시 신분확인·수량제한 대상", True)},
    "amfetamine": {
        "JP": ("PROHIBITED", "각성제. 처방·약감증명으로도 반입 불가", True),
        "US": ("DECLARE", "처방전 원본 지참, 세관 신고", True)},
    "amphetamine": {
        "JP": ("PROHIBITED", "각성제. 애더럴 등 ADHD 약 해당. 반입 시 형사처벌", True),
        "US": ("DECLARE", "Schedule II. 처방전 지참 + 세관 신고", True)},
    "dextroamphetamine": {
        "JP": ("PROHIBITED", "각성제. 개인 반입 불가", True)},
    "methylphenidate": {
        "JP": ("PROHIBITED", "콘서타·리탈린. 개인 반입 불가", True),
        "KR": ("PERMIT", "마약류. 반입 시 사전 승인 필요", False),
        "US": ("DECLARE", "Schedule II. 처방전 지참", True)},
    "codeine": {
        "AE": ("PERMIT", "사전 허가 없이 반입 시 억류 사례 다수", False),
        "SG": ("PERMIT", "사전 승인 필요", False),
        "JP": ("LIMIT", "함량 기준 초과 시 약감증명 필요", False)},
    "diazepam": {
        "AE": ("PERMIT", "향정신성. 사전 허가 필요", False),
        "SG": ("PERMIT", "사전 승인 필요", False)},
}
NATIONAL_ONLY = {
    "tramadol": {
        "AE": ("PROHIBITED", "국제 통제물질이 아니지만 UAE에서 엄격 통제. 체포 사례 있음", False),
        "SG": ("PERMIT", "사전 승인 필요", False)},
    "ketamine": {
        "GB": ("PERMIT", "Class B로 국내 통제", False),
        "SG": ("PROHIBITED", "엄격 통제", False)},
}
def _fold(w):
    w = (w or "").lower()
    w = w.replace("ph", "f").replace("oe", "e").replace("ae", "e")
    w = w.replace("y", "i").replace("kh", "k").replace("cc", "c")
    return re.sub(r"(hydrochloride|sulfate|phosphate|maleate|tartrate|citrate|besylate)$", "", w).strip()
def norm(s):
    return re.sub(r"[^a-z ]", " ", (s or "").lower())
def ingredients(name):
    k = "ing:" + name.lower()
    h = _get(k)
    if h is not None:
        return h
    B = "https://rxnav.nlm.nih.gov/REST"
    out = []
    try:
        r = requests.get(B + "/rxcui.json", params={"name": name, "search": 2},
                         headers=UA, timeout=TO).json()
        ids = (r.get("idGroup") or {}).get("rxnormId") or []
        if ids:
            rr = requests.get(B + "/rxcui/" + ids[0] + "/related.json",
                              params={"tty": "IN"}, headers=UA, timeout=TO).json()
            for g in ((rr.get("relatedGroup") or {}).get("conceptGroup") or []):
                for c in (g.get("conceptProperties") or []):
                    n = c["name"].strip().lower()
                    if n and n not in out:
                        out.append(n)
    except Exception:
        pass
    if not out:
        out = [x for x in norm(name).split() if len(x) >= 5]
    return _put(k, out)
def match_incb(ings, raw):
    pool, fold = set(), set()
    for s0 in list(ings) + [raw]:
        for w in re.findall(r"[a-z]{5,}", (s0 or "").lower()):
            pool.add(w); fold.add(_fold(w))
    out, seen = [], set()
    for rec in incb():
        toks = re.findall(r"[a-z]{5,}", rec["inn"])
        if not toks:
            continue
        hit = rec["inn"] in pool or _fold(rec["inn"]) in fold
        if not hit and len(toks) == 1:
            hit = toks[0] in pool or _fold(toks[0]) in fold
        if hit and rec["cas"] not in seen:
            seen.add(rec["cas"]); out.append(rec)
    return out
def national_rules(ings, raw):
    pool = set(x.lower() for x in ings) | {raw.lower().strip()}
    found = {}
    for table in (NATIONAL, NATIONAL_ONLY):
        for key, rules in table.items():
            if any(key == w or (" " + key) in w or w.endswith(key) for w in pool):
                found.setdefault(key, {}).update(rules)
    return found
RANK = {"PROHIBITED": 4, "PERMIT": 3, "DECLARE": 2, "LIMIT": 1, "OK": 0}
def build_verdict(ings, raw):
    hits = match_incb(ings, raw)
    nat = national_rules(ings, raw)
    rows = []
    for code, flag, ko, en in COUNTRIES:
        best, why, ver, sub = "OK", [], True, None
        for key, rules in nat.items():
            if code in rules:
                lvl, txt, v = rules[code]
                if RANK[lvl] > RANK[best]:
                    best, sub = lvl, key
                why.append(key + ": " + txt)
                ver = ver and v
        if best == "OK" and hits:
            best = "DECLARE"
            why.append("UN 국제통제물질(" + hits[0]["list"] + "). 대부분의 국가에서 처방전 지참·세관 신고가 요구된다")
        rows.append({"code": code, "flag": flag, "ko": ko, "en": en, "level": best,
                     "why": why, "verified": ver, "substance": sub, "src": SRC.get(code, "")})
    return hits, rows
@rx_bp.route("/api/rx/check")
def rx_check():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"ok": False, "error": "약 이름을 입력하세요"}), 400
    k = "v:" + q.lower()
    h = _get(k)
    if h:
        return jsonify(h)
    ings = ingredients(q)
    hits, rows = build_verdict(ings, q)
    return jsonify(_put(k, {"ok": True, "q": q, "ingredients": ings[:8],
        "incb": [{"name": x["name"], "cas": x["cas"], "list": x["list"]} for x in hits[:6]],
        "rows": rows, "db_size": len(incb())}))
@rx_bp.route("/rx")
def rx_page():
    return Response(PAGE, mimetype="text/html; charset=utf-8")
PAGE = """<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>이 약 가져가도 되나요 — 국가별 의약품 반입 판정</title>
<meta name="description" content="Check whether your medication is allowed across borders. UN INCB controlled-substance list plus national rules.">
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:#0b0d11;color:#e9edf3;font:15px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif}
.wrap{max-width:700px;margin:0 auto;padding:24px 14px 90px}
h1{font-size:21px;margin:0 0 4px;letter-spacing:-.4px}
.sub{color:#8a95a6;font-size:13px;margin:0 0 18px}
input{width:100%;background:#161b22;border:1px solid #273143;color:#e9edf3;border-radius:12px;padding:13px 14px;font-size:16px;outline:none}
input:focus{border-color:#4b7bd8}
.pill{display:inline-block;background:#161b22;border:1px solid #273143;border-radius:999px;padding:5px 11px;font-size:12px;color:#9dabbd;margin:10px 6px 0 0;cursor:pointer}
.ing{color:#7c8899;font-size:12px;margin:18px 0 2px}
.ing b{color:#b8c4d4;font-weight:600}
.incb{background:#1b1410;border:1px solid #4a3520;border-radius:11px;padding:10px 12px;margin:12px 0 0;font-size:12.5px;color:#e0b87c}
.row{display:flex;gap:11px;align-items:flex-start;padding:13px 4px;border-bottom:1px solid #1a212c}
.cty{width:104px;flex:none;font-size:14px}
.lv{margin-left:auto;flex:none;font-size:12px;font-weight:700;padding:3px 9px;border-radius:7px;white-space:nowrap}
.PROHIBITED{background:#3a1114;color:#ff8a76}
.PERMIT{background:#3a2a0e;color:#f0b95e}
.DECLARE{background:#152a3a;color:#78b6e8}
.LIMIT{background:#1d2531;color:#9dabbd}
.OK{background:#122a1e;color:#6cd6a0}
.why{color:#8a95a6;font-size:12px;margin-top:3px}
.unv{color:#a98b5e;font-size:11px;margin-top:3px}
.src{font-size:11px}.src a{color:#5d82c4;text-decoration:none}
.dis{color:#697585;font-size:11px;margin-top:22px;line-height:1.55}
.empty{color:#8a95a6;text-align:center;padding:34px 0;font-size:14px}
.pw{margin-top:22px;background:#111820;border:1px solid #23303f;border-radius:14px;padding:16px}
.pw h3{margin:0 0 6px;font-size:15px}
.pw p{margin:0 0 10px;color:#8a95a6;font-size:12.5px}
.pw button{background:#3d6bd6;color:#fff;border:0;border-radius:10px;padding:10px 16px;font-size:14px;font-weight:600;cursor:pointer}
</style></head><body><div class="wrap">
<h1>이 약, 가져가도 되나요</h1>
<p class="sub">약 이름을 넣으면 성분을 찾아 국가별 반입 규정을 판정합니다.</p>
<input id="q" placeholder="Adderall / Sudafed / Concerta / tramadol" autocomplete="off">
<div id="pills"></div>
<div id="out"><div class="empty">약 이름을 입력하세요.</div></div>
<p class="dis">UN INCB 통제물질 목록과 각국 공개 규정을 근거로 계산한 <b>참고용 판정</b>입니다. 규정은 수시로 바뀌고 제형·함량·수량에 따라 결과가 달라집니다. 출국 전 반드시 도착국 대사관 또는 보건당국에 확인하십시오. 의료·법률 자문이 아닙니다.</p>
</div><script>
var Q=document.getElementById("q"),OUT=document.getElementById("out");
["Adderall","Sudafed","Concerta","tramadol","codeine","diazepam"].forEach(function(s){
 var b=document.createElement("span");b.className="pill";b.textContent=s;
 b.onclick=function(){Q.value=s;run();};document.getElementById("pills").appendChild(b);});
function esc(t){var d=document.createElement("div");d.textContent=t==null?"":t;return d.innerHTML;}
var LV={PROHIBITED:"\uBC18\uC785 \uBD88\uAC00",PERMIT:"\uC0AC\uC804 \uD5C8\uAC00",DECLARE:"\uC2E0\uACE0 \uD544\uC694",LIMIT:"\uC218\uB7C9 \uC81C\uD55C",OK:"\uC81C\uD55C \uC5C6\uC74C"};
function run(){
 var q=Q.value.trim(); if(q.length<2)return;
 OUT.innerHTML="<div class=\'empty\'>...</div>";
 fetch("/api/rx/check?q="+encodeURIComponent(q)).then(function(r){return r.json();}).then(function(d){
  if(!d.ok){OUT.innerHTML="<div class=\'empty\'>"+esc(d.error)+"</div>";return;}
  var h="";
  h+="<div class=\'ing\'>\u1109\u1165\u11BC\u1107\u116E\u11AB: <b>"+(d.ingredients.length?esc(d.ingredients.join(", ")):"-")+"</b></div>";
  if(d.incb.length){h+="<div class=\'incb\'>UN International control: "+d.incb.map(function(x){return esc(x.name)+" ("+esc(x.list)+")";}).join(", ")+"</div>";}
  var risky=0;
  d.rows.forEach(function(r){
   if(r.level==="PROHIBITED"||r.level==="PERMIT")risky++;
   h+="<div class=\'row\'><div class=\'cty\'>"+r.flag+" "+esc(r.ko)+"</div><div style=\'min-width:0;flex:1\'>";
   r.why.forEach(function(w){h+="<div class=\'why\'>"+esc(w)+"</div>";});
   if(!r.verified)h+="<div class=\'unv\'>seed data - verify source</div>";
   if(r.src)h+="<div class=\'src\'><a href=\'"+esc(r.src)+"\' target=\'_blank\' rel=\'noopener\'>official source</a></div>";
   h+="</div><span class=\'lv "+r.level+"\'>"+LV[r.level]+"</span></div>";
  });
  if(risky){h+="<div class=\'pw\'><h3>\uC138\uAD00 \uC81C\uC2DC\uC6A9 \uC11C\uB958\uD32D</h3><p>\uB3C4\uCC29\uAD6D \uC5B8\uC5B4 \uC18C\uACAC\uC11C \uC591\uC2DD, \uCC98\uBC29\uC804 \uBC88\uC5ED \uD15C\uD50C\uB9BF, \uC2E0\uACE0\uC11C \uC791\uC131 \uC608\uC2DC, \uADFC\uAC70 \uC870\uD56D \uC778\uC6A9\uBCF8\uC744 PDF \uD55C \uC7A5\uC73C\uB85C \uBB36\uC5B4 \uB4DC\uB9BD\uB2C8\uB2E4.</p><button id=\'buy\'>\uC11C\uB958\uD32D \uB9CC\uB4E4\uAE30</button></div>";}
  h+="<div class=\'ing\' style=\'margin-top:16px\'>DB "+d.db_size+" substances - INCB Yellow/Green List</div>";
  OUT.innerHTML=h;
  var bt=document.getElementById("buy");
  if(bt)bt.onclick=function(){alert("\uACB0\uC81C \uC5F0\uB3D9 \uC608\uC815");};
 }).catch(function(){OUT.innerHTML="<div class=\'empty\'>error</div>";});
}
Q.addEventListener("keydown",function(e){if(e.key==="Enter")run();});
</script></body></html>"""
