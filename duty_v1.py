# -*- coding: utf-8 -*-
"""관세 폭탄 계산기 — 해외직구 예상 세액.
   근거: 관세법 제81조 간이세율 (시행령 별표2), 목록통관 면세한도.
   개인 자가사용 특송·우편 기준. 사업자 수입·대량반입은 대상이 아니다.
"""
import io, os, re, json, hashlib, threading
from flask import Blueprint, request, jsonify, Response, send_file

dt_bp = Blueprint("duty", __name__)
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "static", "fonts", "NotoKR-Bold.ttf")
CACHE = "/tmp/dt_og"
os.makedirs(CACHE, exist_ok=True)

# 간이세율 (관세+부가세 통합). 관세청 간이세율표 기준.
CATS = [
    {"id": "clothes", "ko": "의류", "rate": 0.18,
     "ex": "상의·하의·아우터·속옷·양말"},
    {"id": "shoes", "ko": "신발", "rate": 0.18, "ex": "운동화·구두·부츠·샌들"},
    {"id": "textile", "ko": "섬유·가죽제품", "rate": 0.18,
     "ex": "스카프·장갑·벨트·모포·커튼"},
    {"id": "fur", "ko": "모피제품", "rate": 0.19, "ex": "모피의류·모피목도리"},
    {"id": "bag", "ko": "가방·지갑", "rate": 0.15, "lux": True,
     "ex": "백팩·핸드백·캐리어 (고급가방은 별도 산식)"},
    {"id": "watch", "ko": "시계", "rate": 0.15, "lux": True,
     "ex": "손목시계 (고급시계는 별도 산식)"},
    {"id": "cosmetic", "ko": "화장품", "rate": 0.15, "ex": "스킨·로션·색조·향수"},
    {"id": "health", "ko": "건강기능식품", "rate": 0.15, "ex": "비타민·영양제"},
    {"id": "electronics", "ko": "전자제품·가전", "rate": 0.15,
     "ex": "이어폰·소형가전·주변기기"},
    {"id": "etc", "ko": "그 밖의 물품", "rate": 0.15, "ex": "장난감·문구·스포츠용품"},
]
_CAT = {c["id"]: c for c in CATS}

LUX_BASE = 1923000     # 고급가방·고급시계 기준금액
LUX_FIX = 288450       # 기준금액까지의 세액
LUX_RATE = 0.45        # 초과분 세율
JEWEL_BASE = 4808000
JEWEL_FIX = 721200


# ★과세환율은 관세청이 주 단위로 고시하며 시중 환율과 다르다(전주 평균).
#   2026-09-20~26 기준 USD 1,358.72 → $150 = 203,808원 / $200 = 271,744원
#   시중 환율(1,386원)을 쓰면 오히려 틀린다. 매주 환경변수로 갱신한다.
#   출처: unipass.customs.go.kr > 정보조회 > 주간환율
CUSTOMS_FX = float(os.environ.get("CUSTOMS_FX_USD", "1358.72"))
CUSTOMS_FX_WEEK = os.environ.get("CUSTOMS_FX_WEEK", "2026-09-20~26")


def calc(price_krw, cat_id, ship_krw=0, origin="US", fx=None):
    """price: 물품가(원), ship: 운임·보험(원), origin: US면 $200 아니면 $150."""
    c = _CAT.get(cat_id) or _CAT["etc"]
    base = max(0, int(price_krw)) + max(0, int(ship_krw))   # 과세가격(CIF)
    limit_usd = 200 if origin == "US" else 150
    rate_fx = fx or CUSTOMS_FX
    limit_krw = int(limit_usd * rate_fx)
    # 목록통관 면세 판정은 '물품가격' 기준 (운임 제외)
    duty_free = int(price_krw) <= limit_krw
    if duty_free:
        return {"ok": True, "free": True, "base": base, "tax": 0,
                "total": base, "rate": 0.0, "cat": c["ko"],
                "limit_usd": limit_usd, "limit_krw": limit_krw,
                "fx": rate_fx, "fx_week": CUSTOMS_FX_WEEK,
                "note": "목록통관 면세 한도 이내"}
    if c.get("lux") and base > LUX_BASE:
        tax = int(LUX_FIX + (base - LUX_BASE) * LUX_RATE)
        note = "고급%s 별도 산식 (기준 192.3만원 초과분 45%%)" % c["ko"][:2]
    else:
        tax = int(base * c["rate"])
        note = "간이세율 %d%% (관세+부가세 통합)" % round(c["rate"] * 100)
    return {"ok": True, "free": False, "base": base, "tax": tax,
            "total": base + tax, "rate": round(tax / max(base, 1), 4),
            "cat": c["ko"], "limit_usd": limit_usd, "limit_krw": limit_krw,
            "fx": rate_fx, "fx_week": CUSTOMS_FX_WEEK,
            "note": note}


@dt_bp.route("/api/duty/calc")
def dt_calc():
    try:
        price = int(float(request.args.get("price") or 0))
    except Exception:
        return jsonify({"ok": False, "error": "가격을 숫자로 입력하세요"}), 400
    if price <= 0:
        return jsonify({"ok": False, "error": "가격을 입력하세요"}), 400
    cat = (request.args.get("cat") or "etc").strip()
    origin = "US" if (request.args.get("origin") or "US").upper() == "US" else "XX"
    try:
        ship = int(float(request.args.get("ship") or 0))
    except Exception:
        ship = 0
    d = calc(price, cat, ship, origin)
    d["q"] = request.args.get("q") or ""
    return jsonify(d)


@dt_bp.route("/api/duty/cats")
def dt_cats():
    return jsonify({"ok": True, "cats": [
        {"id": c["id"], "ko": c["ko"], "rate": c["rate"], "ex": c["ex"]} for c in CATS]})



def _dfmt(n):
    return format(int(n), ",") + "원"


@dt_bp.route("/duty/og/<path:name>")
@dt_bp.route("/duty/card/<path:name>")
def dt_card(name):
    """관세 결과 카드. /duty/og/... = 1200x630, /duty/card/... = 1080x1350"""
    vertical = request.path.startswith("/duty/card")
    m = re.match(r"^(\d+)-([a-z]+)-([A-Z]{2})", name or "")
    if not m:
        return jsonify({"ok": False, "error": "형식: 600000-electronics-US.png"}), 400
    price, cat, origin = int(m.group(1)), m.group(2), m.group(3)
    d = calc(price, cat, 0, origin)
    key = hashlib.md5(("%s|%s|%s|%s" % (price, cat, origin, vertical)).encode()).hexdigest()[:16]
    path = os.path.join(CACHE, key + ".png")
    if not os.path.exists(path):
        _draw_duty(d, price, origin, path, vertical)
    return send_file(path, mimetype="image/png", max_age=86400)


def _draw_duty(d, price, origin, path, vertical):
    from PIL import Image, ImageDraw, ImageFont
    F = lambda n: ImageFont.truetype(FONT, n)
    free = d["free"]
    col = (110, 220, 180) if free else (240, 176, 76)
    W, H = (1080, 1350) if vertical else (1200, 630)
    px = 78 if vertical else 70
    im = Image.new("RGB", (W, H), (11, 13, 18))
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, W, 10 if vertical else 7], fill=col)
    sc = 1.0 if vertical else 0.78
    S = lambda n: F(max(18, int(n * sc)))

    y = 118 if vertical else 84
    dr.text((px, y), "%s %s 직구하면" % (d["cat"], _dfmt(price)), font=S(38), fill=(148, 160, 176))
    y += int(72 * sc)
    head = "세금 없음" if free else ("세금 " + _dfmt(d["tax"]))
    dr.text((px, y), head, font=S(76), fill=col)
    y += int(112 * sc)
    sub = ("면세 한도 $%d 이내" % d["limit_usd"]) if free else \
          ("물품가의 %d%%가 더 붙습니다" % round(d["rate"] * 100))
    dr.text((px, y), sub, font=S(34), fill=(206, 216, 228))
    y += int(78 * sc)

    for lab, val in (("과세가격", _dfmt(d["base"])), ("세금", _dfmt(d["tax"])),
                     ("실제로 내는 돈", _dfmt(d["total"]))):
        dr.text((px, y), lab, font=S(30), fill=(147, 162, 179))
        tw = dr.textlength(val, font=S(30))
        dr.text((W - px - tw, y), val, font=S(30), fill=(230, 238, 246))
        y += int(54 * sc)
        dr.line([px, y - 12, W - px, y - 12], fill=(26, 33, 44), width=2)

    y += int(18 * sc)
    dr.text((px, y), d["note"][:30], font=S(26), fill=(140, 154, 170))

    fy = H - (262 if vertical else 156)
    dr.text((px, fy), "직구 전 5초면 확인합니다", font=S(42), fill=(230, 238, 246))
    dr.text((px, fy + int(62 * sc)), "linklynk.onrender.com/duty", font=S(32), fill=(224, 160, 74))
    dr.text((px, H - (112 if vertical else 62)),
            "관세청 간이세율 기준 · 실제 세액은 HS코드·FTA에 따라 다름",
            font=S(24), fill=(96, 110, 126))
    im.save(path, optimize=True)


PAGE = """<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>이거 직구하면 얼마 뜯기나 — 관세 계산기</title>
<meta name="description" content="해외직구 예상 세액을 5초 만에. 간이세율·목록통관 면세한도 기준, 관세청 공식 세율표.">
<meta property="og:title" content="이거 직구하면 얼마 뜯기나">
<meta property="og:description" content="150달러 넘으면 얼마가 붙을까. 관세청 간이세율 기준 5초 계산.">
<meta name="twitter:card" content="summary_large_image">
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{max-width:100%;overflow-x:hidden}
body{margin:0;background:#0b0d12;color:#e9eef5;
 font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif}
.w{max-width:620px;margin:0 auto;padding:28px 16px 70px}
h1{font-size:26px;margin:0 0 6px;letter-spacing:-.4px;line-height:1.3}
.sub{color:#8b98a8;font-size:13.5px;margin:0 0 22px}
button,input,select{font:inherit}
label{display:block;font-size:13px;color:#8b98a8;margin:16px 0 6px}
.inp,select{width:100%;background:#141a24;border:1px solid #27323f;color:#e9eef5;
 border-radius:13px;padding:14px 15px;font-size:16px;outline:none}
.inp:focus,select:focus{border-color:#e0a04a}
.row2{display:flex;gap:8px}
.row2>div{flex:1}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.chips button{background:#141a24;border:1px solid #27323f;color:#9fb0c2;
 border-radius:999px;padding:7px 13px;font-size:12.5px;cursor:pointer}
.chips button.on{background:#33260f;border-color:#e0a04a;color:#f5d29a}
.go{width:100%;background:#e0a04a;color:#231502;border:0;border-radius:13px;
 padding:15px;font-size:16px;font-weight:700;margin-top:18px;cursor:pointer}
.res{margin-top:24px;display:none}
.res.on{display:block}
.hero{border-radius:16px;padding:24px 20px;border:1px solid #27323f;background:#111620}
.hero.free{border-color:#1c4438}.hero.tax{border-color:#463519}
.hero .t{font-size:13px;color:#8b98a8}
.hero .n{font-size:34px;font-weight:800;margin:6px 0 4px;letter-spacing:-.6px}
.free .n{color:#6edcb4}.tax .n{color:#f0b04c}
.hero .s{font-size:13px;color:#93a2b3}
.bd{margin-top:16px}
.bd .r{display:flex;justify-content:space-between;padding:10px 2px;
 border-bottom:1px solid #1a212c;font-size:14px}
.bd .r span:first-child{color:#93a2b3}
.bd .r.tot{border-bottom:0;font-weight:700;font-size:16px;padding-top:14px}
.note{margin-top:14px;font-size:12.5px;color:#8b98a8;background:#161d28;
 border:1px solid #27323f;border-radius:9px;padding:10px 12px}
.share{display:flex;gap:8px;margin-top:18px}
.share button{flex:1;background:#141a24;border:1px solid #27323f;color:#cfdae6;
 border-radius:12px;padding:13px;font-size:14px;font-weight:600;cursor:pointer}
.share button.p{background:#e0a04a;color:#231502;border-color:#e0a04a}
.warn{margin-top:22px;font-size:11.5px;color:#7d8a99;line-height:1.75;
 border-top:1px solid #1a212c;padding-top:16px}
.warn b{color:#9fb0c2}
.more{margin-top:20px;display:flex;gap:8px;flex-wrap:wrap}
.more a{flex:1;min-width:150px;background:#141a24;border:1px solid #27323f;
 border-radius:12px;padding:13px;text-decoration:none;color:#cfdae6;font-size:13px}
.more a span{display:block;color:#7d8a99;font-size:11.5px;margin-top:2px}
</style></head><body><div class="w">
<h1>이거 직구하면 얼마 뜯기나</h1>
<p class="sub">관세청 간이세율 기준 · 개인 자가사용 특송·우편</p>

<label>물품 가격 (원)</label>
<input class="inp" id="price" inputmode="numeric" placeholder="예: 600000">
<div class="row2">
  <div><label>운임·보험 (원, 선택)</label>
    <input class="inp" id="ship" inputmode="numeric" placeholder="0"></div>
</div>
<label>어디서 사나요</label>
<div class="chips" id="org">
  <button data-v="US" class="on">미국 ($200까지 면세)</button>
  <button data-v="XX">그 외 국가 ($150까지)</button>
</div>
<label>품목</label>
<div class="chips" id="cat"></div>
<button class="go" id="go">세금 계산</button>
<div class="res" id="res"></div>

<p class="warn"><b>이 결과는 예상치입니다.</b> 실제 세액은 HS코드·원산지·FTA 적용·
개별소비세 대상 여부에 따라 달라집니다. 면세 한도 판정은 물품가격 기준이지만
과세가격은 운임·보험을 포함합니다. 같은 날 여러 건이 도착하면 합산과세될 수 있습니다.
<b>정확한 금액은 관세청 예상세액 조회 또는 관세사에게 확인하세요.</b></p>
</div>
<script>
var org="US", cat="etc", last=null;
function esc(t){var d=document.createElement("div");d.textContent=t==null?"":t;return d.innerHTML;}
function won(n){return Number(n).toLocaleString("ko-KR")+"원";}
document.getElementById("org").addEventListener("click",function(e){
  var b=e.target.closest("button"); if(!b)return; org=b.dataset.v;
  this.querySelectorAll("button").forEach(function(x){x.classList.remove("on");});
  b.classList.add("on");});
fetch("/api/duty/cats").then(function(r){return r.json();}).then(function(d){
  var c=document.getElementById("cat");
  (d.cats||[]).forEach(function(x,i){
    var b=document.createElement("button");
    b.textContent=x.ko+" "+Math.round(x.rate*100)+"%";
    b.title=x.ex; b.dataset.v=x.id;
    if(x.id==="etc"){b.classList.add("on");}
    b.onclick=function(){cat=x.id;
      c.querySelectorAll("button").forEach(function(y){y.classList.remove("on");});
      b.classList.add("on");};
    c.appendChild(b);});});
document.getElementById("go").onclick=run;
["price","ship"].forEach(function(id){
  document.getElementById(id).addEventListener("keydown",function(e){
    if(e.key==="Enter")run();});});
function run(){
  var p=(document.getElementById("price").value||"").replace(/[^0-9]/g,"");
  var sh=(document.getElementById("ship").value||"").replace(/[^0-9]/g,"");
  if(!p){return;}
  var R=document.getElementById("res"); R.className="res on";
  R.innerHTML='<div style="color:#8b98a8;text-align:center;padding:22px">계산 중...</div>';
  fetch("/api/duty/calc?price="+p+"&ship="+(sh||0)+"&cat="+cat+"&origin="+org)
   .then(function(r){return r.json();}).then(function(d){
    if(!d.ok){R.innerHTML='<div style="color:#8b98a8;text-align:center;padding:22px">'+esc(d.error)+'</div>';return;}
    last=d;
    var h='<div class="hero '+(d.free?"free":"tax")+'">';
    h+='<div class="t">'+esc(d.cat)+' · '+(org==="US"?"미국":"그 외")+'발</div>';
    h+='<div class="n">'+(d.free?"세금 없음":won(d.tax))+'</div>';
    h+='<div class="s">'+(d.free
      ? "면세 한도 $"+d.limit_usd+" ("+won(d.limit_krw)+") 이내"
      : "물품가의 "+Math.round(d.rate*100)+"%가 붙습니다")+'</div></div>';
    h+='<div class="bd">';
    h+='<div class="r"><span>과세가격 (물품+운임)</span><span>'+won(d.base)+'</span></div>';
    h+='<div class="r"><span>세금</span><span>'+won(d.tax)+'</span></div>';
    h+='<div class="r tot"><span>실제로 내는 돈</span><span>'+won(d.total)+'</span></div>';
    h+='</div><div class="note">'+esc(d.note)
      +'<br>과세환율 '+Number(d.fx).toLocaleString("ko-KR",{maximumFractionDigits:2})
      +'원/USD ('+esc(d.fx_week)+' 관세청 고시)</div>';
    h+='<div class="share"><button class="p" id="sh">공유</button>'
      +'<button id="cp">링크 복사</button></div>';
    h+='<div class="more">'
      +'<a href="/next">이 약, 몇 개국에서 잡히나<span>21개국 반입 판정</span></a>'
      +'<a href="/gottago/">GottaGo<span>해외 화장실 11,445곳</span></a></div>';
    R.innerHTML=h;
    var url=location.origin+"/duty?via=share";
    var txt=d.free ? esc(d.cat)+" "+won(d.base)+" 직구 — 세금 0원"
                   : esc(d.cat)+" "+won(d.base)+" 직구하면 세금 "+won(d.tax)+" 더 냅니다";
    document.getElementById("sh").onclick=function(){
      if(navigator.share){navigator.share({title:"이거 직구하면 얼마 뜯기나",text:txt,url:url});}
      else{navigator.clipboard.writeText(txt+"\n"+url);this.textContent="복사됨";}};
    document.getElementById("cp").onclick=function(){
      navigator.clipboard.writeText(url);this.textContent="복사됨";};
   }).catch(function(){R.innerHTML='<div style="color:#8b98a8;text-align:center;padding:22px">요청 실패</div>';});
}
</script></body></html>"""



@dt_bp.route("/duty")
@dt_bp.route("/duty/")
def dt_page():
    return Response(PAGE, mimetype="text/html; charset=utf-8")
