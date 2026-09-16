# -*- coding: utf-8 -*-
"""YOU'RE NEXT 형식 바이럴 라우트 — 약 이름 하나로 통제 국가 수를 즉시 보여주고 공유.
   판정 엔진은 borderrx_v1 을 그대로 쓴다. 숫자는 INCB(단정) + 개별국(참고) 2층.
"""
import io, os, re, json, hashlib, threading
from flask import Blueprint, request, jsonify, Response, send_file
from borderrx_v1 import ingredients, build_verdict, COUNTRIES
from rx_ko_dict import lookup_ko

nx_bp = Blueprint("nextviral", __name__)
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "static", "fonts", "NotoKR-Bold.ttf")
CACHE = "/tmp/nx_og"
os.makedirs(CACHE, exist_ok=True)
_lock = threading.Lock()
_res = {}


def slugify(s):
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", (s or "").strip().lower())
    return s.strip("-")[:48] or "x"


def verdict(q):
    """성분 기준 판정. 같은 성분이면 같은 결과 → OG 캐시가 유한해진다."""
    k = (q or "").strip().lower()
    with _lock:
        if k in _res:
            return _res[k]
    # ★한글 약명은 사전을 먼저 본다 — RxNav 는 영문 DB라 한글을 못 읽고,
    #   폴백이 입력 문자열을 그대로 성분으로 써서 오판정을 만든다.
    ings = lookup_ko(q) or ingredients(q)
    # ★한글 입력 안전장치: RxNav 는 영문 DB라 한글 약명을 엉뚱한 성분으로 매핑한다
    #   (애더럴 -> citrate 실측). 오판정은 "가져가도 된다"는 거짓 안전 신호가 되므로
    #   매핑 근거가 약하면 판정을 내지 않고 되묻는다.
    import re as _re
    _ko = bool(_re.search(r"[가-힣]", q))
    _named = [i for i in ings if i and i.lower() not in ("citrate", "acid", "sodium",
                                                         "chloride", "hydrochloride")]
    if _ko and not _named:
        return {"ok": False, "need_en": True,
                "error": "한글 약 이름은 성분 확인이 어려워요. 포장에 적힌 영문 성분명을 넣어주세요 (예: acetaminophen, codeine)"}
    hits, rows = build_verdict(ings, q)
    pro = [r for r in rows if r["level"] == "PROHIBITED"]
    per = [r for r in rows if r["level"] == "PERMIT"]
    dec = [r for r in rows if r["level"] == "DECLARE"]
    lim = [r for r in rows if r["level"] == "LIMIT"]
    total = len(rows)
    hard = len(pro) + len(per)
    soft = len(dec) + len(lim)
    if hard >= 3:
        head, tone = "%d개국에서 반입이 막힙니다" % hard, "red"
    elif hard:
        head, tone = "%d개국에서 사전 허가가 필요합니다" % hard, "red"
    elif soft >= 3:
        head, tone = "%d개국에서 신고 대상입니다" % soft, "amber"
    elif soft:
        head, tone = "%d개국에서 신고 대상입니다" % soft, "amber"
    else:
        head, tone = "어디든 가져갈 수 있는 몇 안 되는 약", "green"
    out = {
        "ok": True, "q": q, "slug": slugify(q),
        "ings": ings[:4], "incb": [h["list"] for h in hits[:1]],
        "total": total, "hard": hard, "soft": soft,
        "head": head, "tone": tone,
        "pro": [r["ko"] for r in pro], "per": [r["ko"] for r in per],
        "dec": [r["ko"] for r in dec][:8],
        "rows": rows,
    }
    with _lock:
        if len(_res) > 400:
            _res.clear()
        _res[k] = out
    return out


@nx_bp.route("/api/nx/check")
def nx_check():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"ok": False, "error": "약 이름을 입력하세요"}), 400
    return jsonify(verdict(q))


@nx_bp.route("/next/og/<path:name>")
def nx_og(name):
    q = re.sub(r"\.png$", "", name)
    d = verdict(q)
    key = hashlib.md5((q + "|" + d["head"]).encode()).hexdigest()[:16]
    path = os.path.join(CACHE, key + ".png")
    if not os.path.exists(path):
        _draw(d, path)
    return send_file(path, mimetype="image/png", max_age=86400)


def _draw(d, path):
    from PIL import Image, ImageDraw
    from PIL import ImageFont
    C = {"red": (255, 92, 80), "amber": (240, 176, 76), "green": (110, 220, 180)}
    col = C.get(d["tone"], C["amber"])
    F = lambda n: ImageFont.truetype(FONT, n)
    im = Image.new("RGB", (1200, 630), (11, 13, 18))
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, 1200, 7], fill=col)
    dr.text((70, 84), "당신의 " + (d["q"][:16]) + "은", font=F(30), fill=(148, 160, 176))
    h = d["head"]
    dr.text((70, 130), h[:22], font=F(60 if len(h) < 18 else 46), fill=col)
    ing = " · ".join(d["ings"][:3]) or d["q"]
    dr.text((70, 244), ing[:34], font=F(30), fill=(206, 216, 228))
    y = 300
    if d["incb"]:
        dr.text((70, y), "UN 국제통제물질 — 협약 가입국 전체 신고 대상",
                font=F(24), fill=(150, 164, 180)); y += 44
    names = (d["pro"] + d["per"] + d["dec"])[:7]
    if names:
        dr.text((70, y), "  ".join(names)[:40], font=F(24), fill=(150, 164, 180))
    dr.text((70, 474), "약 이름만 넣으면 5초 만에 확인", font=F(30), fill=(230, 238, 246))
    dr.text((70, 534), "출처: 유엔 마약통제위원회(INCB) 등재 목록",
            font=F(22), fill=(96, 110, 126))
    dr.text((946, 534), "BorderRx", font=F(30), fill=(120, 200, 190))
    im.save(path, optimize=True)


PAGE = """<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>이 약, 몇 개국에서 잡히나 — BorderRx</title>
<meta name="description" content="약 이름 하나만 넣으면 전 세계 21개국 반입 가능 여부를 5초 만에. 출처는 유엔 마약통제위원회 등재 목록.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="BorderRx">
<meta property="og:title" content="이 약, 몇 개국에서 잡히나">
<meta property="og:description" content="상비약 하나가 나라를 넘으면 범죄가 됩니다. 5초 만에 확인하세요.">
<meta property="og:image" content="https://linklynk.onrender.com/next/og/codeine.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{max-width:100%;overflow-x:hidden}
body{margin:0;background:#0b0d12;color:#e9eef5;
 font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif}
.w{max-width:620px;margin:0 auto;padding:28px 16px 70px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.4px;line-height:1.3}
.sub{color:#8b98a8;font-size:13.5px;margin:0 0 22px}
button,input{font:inherit}
.inp{width:100%;background:#141a24;border:1px solid #27323f;color:#e9eef5;
 border-radius:13px;padding:15px 16px;font-size:16px;outline:none}
.inp:focus{border-color:#5ec8bb}
.go{width:100%;background:#1ab2aa;color:#04211f;border:0;border-radius:13px;
 padding:15px;font-size:16px;font-weight:700;margin-top:10px;cursor:pointer}
.go:disabled{opacity:.5}
.ex{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
.ex button{background:#141a24;border:1px solid #27323f;color:#9fb0c2;
 border-radius:999px;padding:6px 12px;font-size:12.5px;cursor:pointer}
.res{margin-top:26px;display:none}
.res.on{display:block}
.hero{border-radius:16px;padding:24px 20px;border:1px solid #27323f;background:#111620}
.hero .t{font-size:13px;color:#8b98a8}
.hero .n{font-size:30px;font-weight:800;line-height:1.28;margin:6px 0 10px;letter-spacing:-.5px}
.red .n{color:#ff5c50}.amber .n{color:#f0b04c}.green .n{color:#6edcb4}
.red{border-color:#4a1f1c}.amber{border-color:#463519}.green{border-color:#1c4438}
.ing{font-size:13.5px;color:#b9c6d4}
.un{margin-top:12px;font-size:12.5px;color:#8b98a8;background:#161d28;
 border:1px solid #27323f;border-radius:9px;padding:9px 11px}
.grid{margin-top:18px}
.row{display:flex;gap:10px;align-items:flex-start;padding:11px 2px;border-bottom:1px solid #1a212c}
.row .c{flex:0 0 96px;font-size:14px;font-weight:600}
.row .d{flex:1;min-width:0;font-size:12.5px;color:#93a2b3;word-break:break-word}
.lv{display:inline-block;border-radius:6px;padding:1px 7px;font-size:11px;margin-left:6px;vertical-align:1px}
.PROHIBITED{background:#3a1114;color:#ff8a76}
.PERMIT{background:#3a2a11;color:#f0b04c}
.DECLARE{background:#1b2a3a;color:#7fb6e8}
.LIMIT{background:#26223a;color:#a89ae8}
.OK{background:#14261f;color:#6edcb4}
.share{display:flex;gap:8px;margin-top:20px}
.share button{flex:1;background:#141a24;border:1px solid #27323f;color:#cfdae6;
 border-radius:12px;padding:13px;font-size:14px;font-weight:600;cursor:pointer}
.share button.p{background:#1ab2aa;color:#04211f;border-color:#1ab2aa}
.warn{margin-top:22px;font-size:11.5px;color:#7d8a99;line-height:1.75;
 border-top:1px solid #1a212c;padding-top:16px}
.warn b{color:#9fb0c2}
.more{margin-top:20px;display:flex;gap:8px;flex-wrap:wrap}
.more a{flex:1;min-width:140px;background:#141a24;border:1px solid #27323f;
 border-radius:12px;padding:13px;text-decoration:none;color:#cfdae6;font-size:13px}
.more a span{display:block;color:#7d8a99;font-size:11.5px;margin-top:2px}
.msg{color:#8b98a8;text-align:center;padding:26px;font-size:14px}
</style></head><body><div class="w">
<h1>이 약, 몇 개국에서 잡히나</h1>
<p class="sub">상비약 하나가 나라를 넘으면 범죄가 됩니다 · 21개국 · 출처 UN INCB</p>
<input class="inp" id="q" placeholder="약 이름 (예: 타이레놀, 게보린, 애더럴)" autocomplete="off">
<button class="go" id="go">확인하기</button>
<div class="ex" id="ex"></div>
<div class="res" id="res"></div>
<p class="warn"><b>이 결과는 참고용입니다.</b> 각국 규정은 수시로 바뀌며, 같은 성분이라도
함량·제형·수량에 따라 판정이 달라집니다. 국제통제물질 등재 여부는 유엔 INCB 공식 목록을
따르지만, 개별국 규정은 확인이 필요한 참고 정보입니다.
<b>출국 전 반드시 해당국 대사관 또는 보건당국에 확인하세요.</b>
이 서비스는 의료·법률 자문이 아닙니다.</p>
</div>
<script>
var EX=["타이레놀","게보린","애더럴","판콜","콘서타","졸피뎀","베나드릴","CBD오일"];
var last=null;
function esc(t){var d=document.createElement("div");d.textContent=t==null?"":t;return d.innerHTML;}
var exb=document.getElementById("ex");
EX.forEach(function(n){var b=document.createElement("button");b.textContent=n;
  b.onclick=function(){document.getElementById("q").value=n;run(n);};exb.appendChild(b);});
document.getElementById("go").onclick=function(){run(document.getElementById("q").value);};
document.getElementById("q").addEventListener("keydown",function(e){
  if(e.key==="Enter") run(this.value);});
var m=location.pathname.match(/[/]next[/]r[/](.+)$/);
if(m){var v=decodeURIComponent(m[1]);document.getElementById("q").value=v;run(v);}
function run(q){
  q=(q||"").trim(); if(q.length<2){return;}
  var R=document.getElementById("res");
  R.className="res on"; R.innerHTML='<div class="msg">확인하는 중...</div>';
  fetch("/api/nx/check?q="+encodeURIComponent(q)).then(function(r){return r.json();})
  .then(function(d){
    if(!d.ok){R.innerHTML='<div class="msg">'+esc(d.error||"실패")+'</div>';return;}
    last=d;
    var h='<div class="hero '+d.tone+'"><div class="t">당신의 '+esc(d.q)+'은</div>';
    h+='<div class="n">'+esc(d.head)+'</div>';
    h+='<div class="ing">'+esc((d.ings||[]).join(" · ")||d.q)+'</div>';
    if(d.incb&&d.incb.length){
      h+='<div class="un">UN 국제통제물질 등재 — 협약 가입국 전체에서 처방전 지참·세관 신고가 요구됩니다</div>';}
    h+='</div><div class="grid">';
    var order={PROHIBITED:0,PERMIT:1,DECLARE:2,LIMIT:3,OK:4};
    (d.rows||[]).slice().sort(function(a,b){return order[a.level]-order[b.level];})
     .forEach(function(r){
      if(r.level==="OK")return;
      h+='<div class="row"><div class="c">'+esc(r.flag)+' '+esc(r.ko)
        +'<span class="lv '+r.level+'">'+({PROHIBITED:"반입불가",PERMIT:"사전허가",DECLARE:"신고",LIMIT:"제한"}[r.level]||r.level)+'</span></div>';
      h+='<div class="d">'+esc((r.why||[])[0]||"")+'</div></div>';
    });
    h+='</div>';
    h+='<div class="share"><button class="p" id="sh">친구에게 공유</button>'
      +'<button id="cp">링크 복사</button></div>';
    h+='<div class="more">'
      +'<a href="/rx">BorderRx 전체 판정<span>성분·국가별 상세</span></a>'
      +'<a href="/gottago/">GottaGo<span>해외 화장실 11,445곳</span></a>'
      +'<a href="/eats/">Local Bites<span>여행자가 고른 맛집</span></a></div>';
    R.innerHTML=h;
    var url=location.origin+"/next/r/"+encodeURIComponent(d.q)+"?via=share";
    document.getElementById("sh").onclick=function(){
      var txt="내 "+d.q+"은 "+d.head+" — 당신 약도 확인해보세요";
      if(navigator.share){navigator.share({title:"이 약, 몇 개국에서 잡히나",text:txt,url:url});}
      else{navigator.clipboard.writeText(txt+"\n"+url);this.textContent="복사됨";}
    };
    document.getElementById("cp").onclick=function(){
      navigator.clipboard.writeText(url);this.textContent="복사됨";
      var b=this;setTimeout(function(){b.textContent="링크 복사";},1600);
    };
  }).catch(function(){R.innerHTML='<div class="msg">요청 실패</div>';});
}
</script></body></html>"""



@nx_bp.route("/next")
@nx_bp.route("/next/")
@nx_bp.route("/next/r/<path:q>")
def nx_page(q=None):
    return Response(PAGE, mimetype="text/html; charset=utf-8")
