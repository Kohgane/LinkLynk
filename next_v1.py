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
    # ★문구는 개수가 아니라 '가장 강한 등급'으로 정한다.
    #   반입불가(PROHIBITED)를 "사전 허가 필요"로 쓰면 정반대 정보가 된다(Sudafed 실측).
    if pro:
        n = len(pro) + len(per)
        head, tone = "%d개국에서 반입이 막힙니다" % n, "red"
        head_en = "Banned or restricted in %d countr%s" % (n, "y" if n == 1 else "ies")
    elif per:
        head, tone = "%d개국에서 사전 허가가 필요합니다" % len(per), "red"
        head_en = "Needs a permit in %d countr%s" % (len(per), "y" if len(per) == 1 else "ies")
    elif soft:
        head, tone = "%d개국에서 신고 대상입니다" % soft, "amber"
        head_en = "Must be declared in %d countr%s" % (soft, "y" if soft == 1 else "ies")
    else:
        head, tone = "어디든 가져갈 수 있는 몇 안 되는 약", "green"
        head_en = "One of the few you can take almost anywhere"
    out = {
        "ok": True, "q": q, "slug": slugify(q),
        "ings": ings[:4], "incb": [h["list"] for h in hits[:1]],
        "total": total, "hard": hard, "soft": soft,
        "head": head, "tone": tone, "head_en": head_en,
        "pro": [r["ko"] for r in pro], "per": [r["ko"] for r in per],
        "dec": [r["ko"] for r in dec][:8],
        "pro_en": [r["en"] for r in pro], "per_en": [r["en"] for r in per],
        "dec_en": [r["en"] for r in dec][:8],
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



# ── 인스타/릴스용 세로 카드 (1080x1350). 콘텐츠 제작 비용을 0으로 만드는 게 목적.
@nx_bp.route("/next/card/<path:name>")
def nx_card(name):
    q = re.sub(r"\.(png|jpg)$", "", name)
    d = verdict(q)
    if not d.get("ok"):
        return jsonify(d), 400
    key = hashlib.md5(("card|" + q + "|" + d["head"]).encode()).hexdigest()[:16]
    path = os.path.join(CACHE, key + ".png")
    if not os.path.exists(path):
        _card(d, path)
    return send_file(path, mimetype="image/png", max_age=86400)


def _card(d, path):
    from PIL import Image, ImageDraw, ImageFont
    C = {"red": (255, 92, 80), "amber": (240, 176, 76), "green": (110, 220, 180)}
    col = C.get(d["tone"], C["amber"])
    F = lambda n: ImageFont.truetype(FONT, n)
    W, H = 1080, 1350
    im = Image.new("RGB", (W, H), (11, 13, 18))
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, W, 10], fill=col)

    def wrap(txt, font, maxw):
        out, line = [], ""
        for ch in txt:
            t = line + ch
            if dr.textlength(t, font=font) > maxw and line:
                out.append(line); line = ch
            else:
                line = t
        if line:
            out.append(line)
        return out

    y = 118
    dr.text((78, y), "당신의 " + d["q"][:14] + "은", font=F(40), fill=(148, 160, 176))
    y += 74
    hf = F(76 if len(d["head"]) <= 14 else 58)
    for ln in wrap(d["head"], hf, W - 156):
        dr.text((78, y), ln, font=hf, fill=col); y += int(hf.size * 1.22)

    y += 34
    ing = " · ".join(d["ings"][:3]) or d["q"]
    for ln in wrap(ing, F(34), W - 156)[:2]:
        dr.text((78, y), ln, font=F(34), fill=(206, 216, 228)); y += 48

    if d["incb"]:
        y += 14
        dr.rounded_rectangle([78, y, W - 78, y + 96], radius=14,
                             fill=(22, 29, 40), outline=(39, 50, 63))
        dr.text((102, y + 18), "UN 국제통제물질 등재", font=F(30), fill=(230, 238, 246))
        dr.text((102, y + 56), "협약 가입국 전체에서 신고 대상", font=F(26), fill=(140, 154, 170))
        y += 128

    y += 20
    lab = [("반입 불가", d["pro"], (255, 92, 80)),
           ("사전 허가", d["per"], (240, 176, 76)),
           ("신고 대상", d["dec"], (127, 182, 232))]
    for name_, arr, c in lab:
        if not arr:
            continue
        dr.text((78, y), name_, font=F(30), fill=c)
        dr.text((78, y + 42), "  ".join(arr[:6])[:34], font=F(30), fill=(200, 210, 224))
        y += 106

    dr.text((78, H - 262), "약 이름만 넣으면 5초 만에", font=F(42), fill=(230, 238, 246))
    dr.text((78, H - 200), "linklynk.onrender.com/next", font=F(32), fill=(120, 200, 190))
    dr.line([78, H - 140, W - 78, H - 140], fill=(32, 41, 53), width=2)
    dr.text((78, H - 112), "출처: 유엔 마약통제위원회(INCB) 등재 목록", font=F(24), fill=(96, 110, 126))
    dr.text((78, H - 74), "각국 규정은 수시로 바뀝니다 · 출국 전 대사관 확인", font=F(24), fill=(96, 110, 126))
    dr.text((W - 230, H - 112), "BorderRx", font=F(36), fill=(120, 200, 190))
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
    h+='<div class="share" style="margin-top:8px"><a id="cd" style="flex:1;background:#141a24;'
      +'border:1px solid #27323f;color:#cfdae6;border-radius:12px;padding:13px;font-size:14px;'
      +'font-weight:600;text-align:center;text-decoration:none" download>카드 이미지 저장</a></div>';
    h+='<div class="more">'
      +'<a href="/rx">BorderRx 전체 판정<span>성분·국가별 상세</span></a>'
      +'<a href="/gottago/">GottaGo<span>해외 화장실 11,445곳</span></a>'
      +'<a href="/eats/">Local Bites<span>여행자가 고른 맛집</span></a></div>';
    R.innerHTML=h;
    var url=location.origin+"/next/r/"+encodeURIComponent(d.q)+"?via=share";
    var cd=document.getElementById("cd");
    if(cd){cd.href="/next/card/"+encodeURIComponent(d.q)+".png";}
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

# ── English card 1080x1350 + OG 1200x630
@nx_bp.route("/next/card-en/<path:name>")
@nx_bp.route("/next/og-en/<path:name>")
def nx_card_en(name):
    vertical = request.path.startswith("/next/card-en")
    q = re.sub(r"\.png$", "", name)
    d = verdict(q)
    if not d.get("ok"):
        return jsonify(d), 400
    key = hashlib.md5(("en|%s|%s|%s" % (q, d["head_en"], vertical)).encode()).hexdigest()[:16]
    path = os.path.join(CACHE, key + ".png")
    if not os.path.exists(path):
        _card_en(d, path, vertical)
    return send_file(path, mimetype="image/png", max_age=86400)


def _card_en(d, path, vertical):
    from PIL import Image, ImageDraw, ImageFont
    C = {"red": (255, 92, 80), "amber": (240, 176, 76), "green": (110, 220, 180)}
    col = C.get(d["tone"], C["amber"])
    F = lambda n: ImageFont.truetype(FONT, n)
    W, H = (1080, 1350) if vertical else (1200, 630)
    sc = 1.0 if vertical else 0.74
    S = lambda n: F(max(16, int(n * sc)))
    px = 78 if vertical else 66
    im = Image.new("RGB", (W, H), (11, 13, 18))
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, W, 10 if vertical else 7], fill=col)

    def wrap(txt, font, maxw):
        out, line = [], ""
        for w in txt.split(" "):
            t = (line + " " + w).strip()
            if dr.textlength(t, font=font) > maxw and line:
                out.append(line); line = w
            else:
                line = t
        if line:
            out.append(line)
        return out

    y = int(118 * sc) if vertical else 62
    dr.text((px, y), "Your " + d["q"][:22], font=S(40), fill=(148, 160, 176))
    y += int(70 * sc)
    hf = S(70 if len(d["head_en"]) <= 26 else 56)
    for ln in wrap(d["head_en"], hf, W - 2 * px)[:3]:
        dr.text((px, y), ln, font=hf, fill=col); y += int(hf.size * 1.2)
    y += int(24 * sc)
    ing = " · ".join(d["ings"][:3]) or d["q"]
    dr.text((px, y), ing[:44], font=S(32), fill=(206, 216, 228)); y += int(56 * sc)
    if d["incb"]:
        dr.rounded_rectangle([px, y, W - px, y + int(92 * sc)], radius=12,
                             fill=(22, 29, 40), outline=(39, 50, 63))
        dr.text((px + 22, y + int(16 * sc)), "UN-controlled substance (INCB)",
                font=S(30), fill=(230, 238, 246))
        dr.text((px + 22, y + int(54 * sc)), "Declare it in every signatory country",
                font=S(24), fill=(140, 154, 170))
        y += int(122 * sc)
    for lab, arr, c in (("Banned / restricted", d.get("pro_en"), (255, 92, 80)),
                        ("Permit required", d.get("per_en"), (240, 176, 76)),
                        ("Must declare", d.get("dec_en"), (127, 182, 232))):
        if not arr or (not vertical and y > H - 190):
            continue
        dr.text((px, y), lab, font=S(28), fill=c)
        names = ", ".join(a.replace("United Arab Emirates", "UAE") for a in arr[:6])
        for ln in wrap(names, S(28), W - 2 * px)[:2]:
            y += int(40 * sc)
            dr.text((px, y), ln, font=S(28), fill=(200, 210, 224))
        y += int(58 * sc)
    fy = H - (262 if vertical else 132)
    dr.text((px, fy), "Check yours in 5 seconds", font=S(42), fill=(230, 238, 246))
    dr.text((px, fy + int(60 * sc)), "linklynk.onrender.com/next/en", font=S(32), fill=(120, 200, 190))
    if vertical:
        dr.line([px, H - 140, W - px, H - 140], fill=(32, 41, 53), width=2)
        dr.text((px, H - 112), "Source: UN INCB controlled substance lists", font=S(24), fill=(96, 110, 126))
        dr.text((px, H - 74), "Rules change. Verify with the embassy before you fly.", font=S(24), fill=(96, 110, 126))
    im.save(path, optimize=True)


PAGE_EN = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Can I bring this medicine? — 21 countries in 5 seconds</title>
<meta name="description" content="Check if your medication is banned or needs a permit in Japan, UAE, Singapore and 18 more countries. Source: UN INCB controlled substance lists.">
<meta property="og:title" content="Can I bring this medicine abroad?">
<meta property="og:description" content="Your cold medicine could get you arrested in Japan. Check any medication in 5 seconds.">
<meta property="og:image" content="https://linklynk.onrender.com/next/og-en/Sudafed.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<style>
*{box-sizing:border-box}html,body{max-width:100%;overflow-x:hidden}
body{margin:0;background:#0b0d12;color:#e9eef5;font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.w{max-width:620px;margin:0 auto;padding:28px 16px 70px}
h1{font-size:27px;margin:0 0 6px;letter-spacing:-.4px;line-height:1.25}
.sub{color:#8b98a8;font-size:13.5px;margin:0 0 22px}
.inp{width:100%;background:#141a24;border:1px solid #27323f;color:#e9eef5;border-radius:13px;padding:15px 16px;font-size:16px;outline:none}
.go{width:100%;background:#1ab2aa;color:#04211f;border:0;border-radius:13px;padding:15px;font-size:16px;font-weight:700;margin-top:10px;cursor:pointer}
.ex{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}
.ex button{background:#141a24;border:1px solid #27323f;color:#9fb0c2;border-radius:999px;padding:6px 12px;font-size:12.5px;cursor:pointer}
.hero{margin-top:24px;border-radius:16px;padding:22px 20px;border:1px solid #27323f;background:#111620}
.hero .n{font-size:28px;font-weight:800;line-height:1.25;margin:4px 0 10px}
.red .n{color:#ff5c50}.amber .n{color:#f0b04c}.green .n{color:#6edcb4}
.un{margin-top:12px;font-size:12.5px;color:#8b98a8;background:#161d28;border:1px solid #27323f;border-radius:9px;padding:9px 11px}
.row{display:flex;gap:10px;padding:11px 2px;border-bottom:1px solid #1a212c}
.row .c{flex:0 0 130px;font-weight:600;font-size:14px}.row .d{flex:1;font-size:12.5px;color:#93a2b3}
.lv{display:inline-block;border-radius:6px;padding:1px 7px;font-size:11px;margin-left:6px}
.PROHIBITED{background:#3a1114;color:#ff8a76}.PERMIT{background:#3a2a11;color:#f0b04c}
.DECLARE{background:#1b2a3a;color:#7fb6e8}.LIMIT{background:#26223a;color:#a89ae8}
.sh{display:flex;gap:8px;margin-top:18px}.sh a,.sh button{flex:1;text-align:center;background:#141a24;border:1px solid #27323f;color:#cfdae6;border-radius:12px;padding:13px;font-size:14px;font-weight:600;cursor:pointer;text-decoration:none}
.warn{margin-top:22px;font-size:12px;color:#7d8a99;line-height:1.75;border-top:1px solid #1a212c;padding-top:16px}
.warn b{color:#cfdae6}
</style></head><body><div class="w">
<h1>Can I bring this medicine abroad?</h1>
<p class="sub">21 countries · Source: UN INCB controlled substance lists</p>
<input class="inp" id="q" placeholder="Medicine name (e.g. Sudafed, Adderall, Xanax)" autocomplete="off">
<button class="go" id="go">Check</button>
<div class="ex" id="ex"></div>
<div id="res"></div>
<p class="warn"><b>This is not legal or medical advice.</b> Rules change often and depend on dose,
form and quantity. UN-controlled status comes from official INCB lists; country rules are
reference information that you must confirm. <b>Always verify with the destination country's
embassy or health authority before you fly.</b> We never say a medicine is "safe" to carry.</p>
</div><script>
var EX=["Sudafed","Adderall","Xanax","Ambien","codeine","Tylenol","Benadryl","melatonin"];
function esc(t){var d=document.createElement("div");d.textContent=t==null?"":t;return d.innerHTML;}
EX.forEach(function(n){var b=document.createElement("button");b.textContent=n;
 b.onclick=function(){document.getElementById("q").value=n;run(n);};document.getElementById("ex").appendChild(b);});
document.getElementById("go").onclick=function(){run(document.getElementById("q").value);};
document.getElementById("q").addEventListener("keydown",function(e){if(e.key==="Enter")run(this.value);});
var m=location.pathname.match(/[/]next[/]en[/]r[/](.+)$/);
if(m){var v=decodeURIComponent(m[1]);document.getElementById("q").value=v;run(v);}
var LV={PROHIBITED:"Banned",PERMIT:"Permit",DECLARE:"Declare",LIMIT:"Limit"};
function run(q){q=(q||"").trim();if(q.length<2)return;var R=document.getElementById("res");
 R.innerHTML='<div class="hero">Checking...</div>';
 fetch("/api/nx/check?q="+encodeURIComponent(q)).then(function(r){return r.json();}).then(function(d){
  if(!d.ok){R.innerHTML='<div class="hero">'+esc(d.error||"Not found — try the active ingredient name")+'</div>';return;}
  var h='<div class="hero '+d.tone+'"><div style="font-size:13px;color:#8b98a8">Your '+esc(d.q)+'</div>';
  h+='<div class="n">'+esc(d.head_en)+'</div><div style="font-size:13.5px;color:#b9c6d4">'+esc((d.ings||[]).join(" · "))+'</div>';
  if(d.incb&&d.incb.length)h+='<div class="un">UN-controlled substance — declare it in every signatory country</div>';
  h+='</div>';
  var o={PROHIBITED:0,PERMIT:1,DECLARE:2,LIMIT:3,OK:4};
  (d.rows||[]).slice().sort(function(a,b){return o[a.level]-o[b.level];}).forEach(function(r){
   if(r.level==="OK")return;
   h+='<div class="row"><div class="c">'+esc(r.flag)+' '+esc(r.en.replace("United Arab Emirates","UAE"))
     +'<span class="lv '+r.level+'">'+LV[r.level]+'</span></div><div class="d">'+esc(r.src?"Official source":"")+'</div></div>';});
  var url=location.origin+"/next/en/r/"+encodeURIComponent(d.q)+"?via=share";
  h+='<div class="sh"><button id="sb">Share</button><a href="/next/card-en/'+encodeURIComponent(d.q)+'.png" download>Save card</a></div>';
  R.innerHTML=h;
  document.getElementById("sb").onclick=function(){var t="My "+d.q+": "+d.head_en+". Check yours:";
   if(navigator.share)navigator.share({title:"Can I bring this medicine?",text:t,url:url});
   else{navigator.clipboard.writeText(t+" "+url);this.textContent="Copied";}};
 }).catch(function(){R.innerHTML='<div class="hero">Request failed</div>';});}
</script></body></html>"""


@nx_bp.route("/next/en")
@nx_bp.route("/next/en/")
@nx_bp.route("/next/en/r/<path:q>")
def nx_page_en(q=None):
    return Response(PAGE_EN, mimetype="text/html; charset=utf-8")
