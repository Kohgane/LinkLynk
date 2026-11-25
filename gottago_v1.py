# -*- coding: utf-8 -*-
"""GottaGo — Restroom Finder (해외 전용 웹앱)
   toilets_world/<city>.json 을 도시 단위 지연 로드. toilet.py 는 건드리지 않는다.
"""
import json, math, os, threading
from flask import Blueprint, request, jsonify, Response, send_from_directory

gg_bp = Blueprint("gottago", __name__)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "tools", "toilets_world")
_cache, _lock = {}, threading.Lock()
_meta = None


def metas():
    global _meta
    if _meta is None:
        out = []
        try:
            for f in sorted(os.listdir(DATA)):
                if f.endswith(".meta.json"):
                    out.append(json.load(open(os.path.join(DATA, f), encoding="utf-8")))
        except Exception:
            pass
        _meta = out
    return _meta


def city_at(lat, lng):
    """좌표가 속한 도시. 없으면 가장 가까운 도시와 거리(km)."""
    best, bd = None, 1e18
    for m in metas():
        s, w, n, e = m["bbox"]
        if s <= lat <= n and w <= lng <= e:
            return m, 0.0
        clat, clng = (s + n) / 2.0, (w + e) / 2.0
        dy = (clat - lat) * 111.32
        dx = (clng - lng) * 111.32 * math.cos(math.radians(lat))
        d = math.hypot(dx, dy)
        if d < bd:
            bd, best = d, m
    return best, bd


def load(key):
    with _lock:
        if key not in _cache:
            p = os.path.join(DATA, "%s.json" % key)
            try:
                _cache[key] = json.load(open(p, encoding="utf-8"))
            except Exception:
                _cache[key] = []
            if len(_cache) > 6:                      # 메모리 보호: 6개 도시만 상주
                for k in list(_cache)[:-6]:
                    _cache.pop(k, None)
        return _cache[key]


def ident(r):
    """표시 라벨: name > near > addr 순"""
    return (r.get("name") or r.get("near") or r.get("addr") or "").strip()


# ── 사용자 제보: 신규 화장실 위치 (해외 전용, 국내 reports.json 과 분리)
import urllib.request, datetime, re as _re

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
SB_BUCKET = os.environ.get("SUPABASE_BUCKET", "linklynk")
_REP, _rlock = None, threading.Lock()


def _sb(method, data=None):
    url = "%s/storage/v1/object/%s/gottago/reports_world.json" % (SB_URL, SB_BUCKET)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + SB_KEY)
    req.add_header("apikey", SB_KEY)
    if method != "GET":
        req.add_header("Content-Type", "application/json")
        req.add_header("x-upsert", "true")
    return urllib.request.urlopen(req, timeout=12).read()


def reps():
    global _REP
    if _REP is None:
        try:
            _REP = json.loads(_sb("GET"))
        except Exception:
            _REP = {"new": []}
        _REP.setdefault("new", [])
    return _REP


@gg_bp.route("/api/gg/report", methods=["POST"])
def gg_report():
    d = request.get_json(silent=True) or {}
    try:
        lat, lng = float(d.get("lat")), float(d.get("lng"))
    except Exception:
        return jsonify({"ok": False, "error": "bad coords"}), 400
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({"ok": False, "error": "bad coords"}), 400
    m, dist = city_at(lat, lng)
    if m is None or dist > 0:
        return jsonify({"ok": False, "error": "outside covered cities"}), 400
    name = (d.get("name") or "").strip()[:40]
    fee = 1 if d.get("fee") else 0
    wc = 1 if d.get("wc") else 0
    with _rlock:
        r = reps()
        k = (round(lat, 4), round(lng, 4))
        r["new"] = [x for x in r["new"]
                    if (round(x["lat"], 4), round(x["lng"], 4)) != k]
        r["new"].append({"lat": round(lat, 6), "lng": round(lng, 6),
                         "name": name, "fee": fee,
                         "access": "휠체어" if wc else "",
                         "h24": 0, "ty": "user", "cc": m.get("cc", ""),
                         "city": m["key"],
                         "ts": datetime.datetime.utcnow().strftime("%Y-%m-%d")})
        r["new"] = r["new"][-4000:]
        try:
            _sb("POST", json.dumps(r, ensure_ascii=False).encode())
        except Exception:
            return jsonify({"ok": False, "error": "save failed"}), 502
    return jsonify({"ok": True, "count": len(r["new"])})


# ── 한국(서울 포함 전국): 국내 앱용 toilet.py 데이터를 그대로 빌려 쓴다(읽기만) ──
def _in_kr(lat, lng):
    return 33.0 <= lat <= 38.7 and 124.5 <= lng <= 131.9


def _kr_near(lat, lng):
    try:
        import toilet
        rows = toilet.near_v2(lat, lng, n=20, mode="walk",
                              open_only=request.args.get("open") == "1")
    except Exception:
        return jsonify({"ok": False, "error": "kr data"}), 502
    free_only = request.args.get("free") == "1"
    acc_only = request.args.get("wc") == "1"
    items = []
    for t in rows:
        acc = t.get("access") or ""
        if free_only and t.get("fee"):
            continue
        if acc_only and "휠체어" not in acc:
            continue
        if t.get("dist", 0) > 4000 and items:
            break
        items.append({"lat": t["lat"], "lng": t["lng"], "label": ident(t),
                      "user": 1 if t.get("ty") == "user" else 0,
                      "fee": t.get("fee", 0), "h24": t.get("h24", 0),
                      "wc": 1 if "휠체어" in acc else 0,
                      "baby": 1 if "기저귀" in acc else 0,
                      "dist": t.get("dist", 0), "walk": t.get("walk", 1),
                      "open": t.get("open", ""), "open_label": t.get("open_label", "")})
    try:
        total = len(toilet._load())
    except Exception:
        total = 0
    return jsonify({"ok": True, "covered": True, "city": "한국", "cc": "KR",
                    "total": total, "items": items})


@gg_bp.route("/api/gg/near")
def gg_near():
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
    except Exception:
        return jsonify({"ok": False, "error": "bad coords"}), 400
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({"ok": False, "error": "bad coords"}), 400
    if _in_kr(lat, lng):                              # 한국: 국내 데이터(toilet.py, 공공데이터+OSM)로 바로 답한다
        return _kr_near(lat, lng)
    m, dist = city_at(lat, lng)
    if m is None:
        return jsonify({"ok": False, "error": "no data"}), 404
    if dist > 0:
        return jsonify({"ok": True, "covered": False, "nearest": m["label"],
                        "nearest_km": int(dist), "items": [],
                        "cities": [x["label"] for x in metas()]})
    rows = list(load(m["key"]))
    try:
        rows += [x for x in reps()["new"] if x.get("city") == m["key"]]
    except Exception:
        pass
    coslat = math.cos(math.radians(lat))
    free_only = request.args.get("free") == "1"
    acc_only = request.args.get("wc") == "1"
    out = []
    for t in rows:
        if free_only and t.get("fee"):
            continue
        if acc_only and "휠체어" not in (t.get("access") or ""):
            continue
        dy = (t["lat"] - lat) * 111320.0
        dx = (t["lng"] - lng) * 111320.0 * coslat
        d = math.hypot(dx, dy)
        if d < 4000:
            out.append((d, t))
    out.sort(key=lambda x: x[0])
    items = []
    for d, t in out[:20]:
        items.append({"lat": t["lat"], "lng": t["lng"], "label": ident(t),
                      "user": 1 if t.get("ty") == "user" else 0,
                      "fee": t.get("fee", 0), "h24": t.get("h24", 0),
                      "wc": 1 if "휠체어" in (t.get("access") or "") else 0,
                      "baby": 1 if "기저귀" in (t.get("access") or "") else 0,
                      "dist": int(d), "walk": max(1, int(d / 75))})
    return jsonify({"ok": True, "covered": True, "city": m["label"],
                    "cc": m.get("cc", ""), "total": len(rows), "items": items})


@gg_bp.route("/api/gg/cities")
def gg_cities():
    try:
        import toilet
        kr = [{"key": "korea", "label": "서울·한국 전국", "cc": "KR", "count": len(toilet._load()), "lat": 37.5665, "lng": 126.978}]
    except Exception:
        kr = []
    return jsonify({"ok": True, "cities": kr + [
        {"key": m["key"], "label": m["label"], "cc": m.get("cc", ""),
         "count": m.get("count", 0),
         "lat": (m["bbox"][0] + m["bbox"][2]) / 2.0,
         "lng": (m["bbox"][1] + m["bbox"][3]) / 2.0} for m in metas()]})


@gg_bp.route("/gottago/manifest.json")
def gg_manifest():
    return jsonify({
        "name": "GottaGo - Restroom Finder",
        "short_name": "GottaGo",
        "start_url": "/gottago/",
        "scope": "/gottago/",
        "display": "standalone",
        "background_color": "#0b0f16",
        "theme_color": "#0b0f16",
        "orientation": "portrait",
        "icons": [
            {"src": "/gottago/icon-192.png", "sizes": "192x192", "type": "image/png",
             "purpose": "any"},
            {"src": "/gottago/icon-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "any"},
            {"src": "/gottago/maskable-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"}
        ]
    })


@gg_bp.route("/gottago/<path:fname>")
def gg_static(fname):
    return send_from_directory(os.path.join(HERE, "static", "gottago"), fname)


@gg_bp.route("/gottago/privacy")
def gg_privacy():
    return Response(PRIVACY, mimetype="text/html; charset=utf-8")


@gg_bp.route("/gottago")
@gg_bp.route("/gottago/")
def gg_page():
    return Response(PAGE, mimetype="text/html; charset=utf-8")


PAGE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>GottaGo - Restroom Finder</title>
<meta name="description" content="Find the nearest public restroom in 20 cities worldwide. Free, wheelchair-accessible filters and a map.">
<link rel="manifest" href="/gottago/manifest.json">
<meta name="theme-color" content="#0b0f16">
<link rel="apple-touch-icon" href="/gottago/icon-192.png">
<link rel="stylesheet" href="/gottago/lf/leaflet.css">
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{max-width:100%;overflow-x:hidden}
body{margin:0;background:#0b0f16;color:#e9eef5;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif}
.wrap{max-width:660px;margin:0 auto;padding:18px 14px 40px;overflow-x:hidden}
.hd{display:flex;align-items:center;gap:10px;margin:0 0 2px}
.hd img{width:36px;height:36px;border-radius:10px;flex:none}
.hd h1{font-size:18px;margin:0;letter-spacing:-.3px}
.back{background:#141a24;border:1px solid #24303f;color:#9fb0c2;border-radius:10px;
  width:36px;height:36px;font-size:17px;line-height:1;flex:none;display:none;cursor:pointer}
.back.on{display:block}
.sub{color:#7f8ea0;font-size:12.5px;margin:0 0 14px 46px}
button{font:inherit;cursor:pointer}
.go{width:100%;background:#1ab2aa;color:#04211f;border:0;border-radius:13px;padding:15px;font-size:16px;font-weight:700}
.go:disabled{opacity:.55}
.f{display:flex;gap:7px;margin:12px 0 0;flex-wrap:wrap}
.f button{background:#141a24;border:1px solid #24303f;color:#9fb0c2;border-radius:999px;padding:7px 13px;font-size:12.5px}
.f button.on{background:#123430;border-color:#1ab2aa;color:#7ff0e2}
#map{height:min(46vh,380px);position:relative;border-radius:14px;margin-top:14px;display:none;background:#141a24}
#map.on{display:block}
.leaflet-container{background:#141a24}
.me{width:18px;height:18px;border-radius:50%;background:#2f8cff;border:3px solid #fff;box-shadow:0 0 0 0 rgba(47,140,255,.6);animation:mep 1.8s infinite}
@keyframes mep{0%{box-shadow:0 0 0 0 rgba(47,140,255,.55)}80%{box-shadow:0 0 0 22px rgba(47,140,255,0)}100%{box-shadow:0 0 0 0 rgba(47,140,255,0)}}
.locb{position:absolute;right:10px;bottom:12px;z-index:800;width:44px;height:44px;border-radius:12px;border:1px solid #24303f;background:#0f1520;color:#7ff0e2;font-size:20px;line-height:1;box-shadow:0 4px 14px rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center}
.locb:active{transform:scale(.94)}
.city{color:#7f8ea0;font-size:12px;margin:14px 0 4px}
.row{display:flex;gap:10px;align-items:center;padding:12px 2px;border-bottom:1px solid #18202b;cursor:pointer}
.row.sel{background:#111a1f}
.row .n{min-width:0;flex:1}
.lb{font-size:14.5px;font-weight:600;line-height:1.35;word-break:break-word}
.lb.dim{color:#8b98a8;font-weight:500}
.tags{margin-top:3px}
.tag{display:inline-block;background:#141a24;border:1px solid #24303f;color:#7f8ea0;
  border-radius:6px;padding:1px 6px;margin:2px 4px 0 0;font-size:11.5px}
.d{text-align:right;flex:none}
.d b{display:block;font-size:16px;color:#7ff0e2}
.d span{font-size:11px;color:#7f8ea0}
.msg{color:#8b98a8;text-align:center;padding:32px 8px;font-size:14px;line-height:1.7}
.chips{display:flex;gap:6px;flex-wrap:wrap;justify-content:center;margin-top:12px}
.chips button{background:#141a24;border:1px solid #24303f;color:#9fb0c2;border-radius:999px;padding:6px 12px;font-size:12px}
.add{width:100%;background:#141a24;border:1px dashed #35485f;color:#9fb0c2;
 border-radius:12px;padding:13px;font-size:14px;margin-top:14px;display:none}
.add.on{display:block}
.add:active{background:#1a2430}
.utag{background:#122a1e;border-color:#1f5c46;color:#6cd6a0}
.foot{color:#5d6b7c;font-size:11px;margin-top:22px;line-height:1.6}
.foot a{color:#5f9fe0}
</style></head><body><div class="wrap">
<div class="hd">
  <button class="back" id="back" aria-label="Back">&#8592;</button>
  <img src="/gottago/icon-192.png" alt=""><h1>GottaGo</h1>
</div>
<p class="sub">Restroom Finder</p>
<button class="go" id="go">Find restrooms near me</button>
<div class="f"><button id="ffree">Free only</button><button id="fwc">Wheelchair</button></div>
<div id="map"><button class="locb" id="locb" aria-label="My location" title="My location">&#10148;</button></div>
<button class="add" id="addBtn">+ Add a restroom you found here</button>
<div id="out"><div class="msg">Tap the button to see the nearest restrooms.<div class="chips" id="chips"></div></div></div>
<p class="foot">Data &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors (ODbL). Opening hours are rarely mapped, so they are not shown. Always check on site.</p>
</div>
<script src="/gottago/lf/leaflet.js"></script>
<script>
var OUT=document.getElementById("out"),GO=document.getElementById("go"),BACK=document.getElementById("back");
var MAPEL=document.getElementById("map");
var free=0,wc=0,last=null,map=null,layer=null,marks=[],me=null,meMark=null;
var KO=/^ko/i.test(navigator.language||"");
var KD={"Find restrooms near me":"내 주변 화장실 찾기","Locating...":"내 위치 찾는 중…","Free only":"무료만","Wheelchair":"휠체어",
"Tap the button to see the nearest restrooms.":"위치를 켜면 가장 가까운 화장실이 바로 나옵니다.","Geolocation not supported.":"이 기기는 위치를 지원하지 않습니다.",
"Location permission denied.":"위치 권한이 꺼져 있습니다.","Pick a city below.":"아래에서 도시를 고르세요.","You are here":"내 위치",
"Searching...":"찾는 중…","Not covered here yet.":"여기는 아직 데이터가 없습니다.","Nearest supported city: ":"가장 가까운 지원 도시: ",
"Nothing within 4 km with these filters.":"이 조건으로 4km 안에 없습니다.","mapped":"곳 등록","Paid":"유료","Free":"무료","Reported":"제보","Baby":"기저귀대",
"Public restroom":"공중화장실","min":"분","Request failed.":"요청 실패","+ Add a restroom you found here":"+ 여기 있는 화장실 제보하기","Restroom Finder":"화장실 레이다","My location":"내 위치"};
function T(t){return KO&&KD[t]?KD[t]:t;}
function esc(t){var d=document.createElement("div");d.textContent=t==null?"":t;return d.innerHTML;}
function home(){
  last=null; MAPEL.classList.remove("on"); BACK.classList.remove("on");
  OUT.innerHTML='<div class="msg">'+T("Tap the button to see the nearest restrooms.")+'<div class="chips" id="chips"></div></div>';
  fillChips("chips");
}
function fillChips(id){
  fetch("/api/gg/cities").then(function(r){return r.json();}).then(function(d){
    var c=document.getElementById(id); if(!c||!d.ok)return;
    d.cities.forEach(function(x){
      var b=document.createElement("button");
      b.textContent=x.label+" ("+x.count+")";
      b.onclick=function(){query(x.lat,x.lng);};
      c.appendChild(b);
    });
  });
}
fillChips("chips");
if(KO){document.documentElement.lang="ko";GO.textContent=T(GO.textContent);
  ["ffree","fwc"].forEach(function(id){var b=document.getElementById(id);b.textContent=T(b.textContent);});
  var ab=document.getElementById("addBtn");ab.textContent=T(ab.textContent);
  var sb=document.querySelector(".sub");if(sb)sb.textContent=T(sb.textContent);}
BACK.onclick=function(){ if(history.state&&history.state.r){history.back();} else {home();} };
window.addEventListener("popstate",function(){ home(); });
function tg(id,set){var b=document.getElementById(id);
  b.onclick=function(){set();b.classList.toggle("on");if(last)query(last[0],last[1],true);};}
tg("ffree",function(){free=free?0:1;});
tg("fwc",function(){wc=wc?0:1;});
GO.onclick=function(){
  if(!navigator.geolocation){OUT.innerHTML='<div class="msg">'+T("Geolocation not supported.")+'</div>';return;}
  GO.disabled=true;GO.textContent=T("Locating...");
  navigator.geolocation.getCurrentPosition(function(p){
    GO.disabled=false;GO.textContent=T("Find restrooms near me");
    me=[p.coords.latitude,p.coords.longitude];
    query(me[0],me[1],!!last);
  },function(){
    GO.disabled=false;GO.textContent=T("Find restrooms near me");
    OUT.innerHTML='<div class="msg">'+T("Location permission denied.")+'<br>'+T("Pick a city below.")+'<div class="chips" id="chips2"></div></div>';
    fillChips("chips2");
  },{enableHighAccuracy:true,timeout:12000,maximumAge:30000});
};
// 내 위치 버튼: 지도 위 오른쪽 아래 — 누르면 다시 내 위치로
document.getElementById("locb").onclick=function(e){e.stopPropagation();
  if(map&&me){map.setView(me,17);if(meMark)meMark.openPopup();}
  GO.onclick();};
// 앱을 열면 바로 내 위치로 찾는다(버튼 누를 필요 없음)
setTimeout(function(){GO.onclick();},250);
function drawMap(lat,lng,items){
  MAPEL.classList.add("on");
  if(!map){
    map=L.map("map",{zoomControl:false,attributionControl:false}).setView([lat,lng],15);
    // 지도 타일: OSM 이 막히거나 느리면(중국 등) Esri 로 한 번 갈아탄다
    var tl=L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19}).addTo(map),te=0;
    tl.on("tileerror",function(){if(++te===3){map.removeLayer(tl);
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",{maxZoom:19}).addTo(map)}});
    L.control.zoom({position:"topright"}).addTo(map);
  }
  if(layer)map.removeLayer(layer);
  marks=[];
  layer=L.layerGroup().addTo(map);
  if(me){meMark=L.marker(me,{icon:L.divIcon({className:"",html:'<div class="me"></div>',iconSize:[18,18],iconAnchor:[9,9]}),zIndexOffset:1000})
    .addTo(layer).bindPopup(T("You are here"));}
  var pts=[[lat,lng]];
  items.forEach(function(it,i){
    var m=L.marker([it.lat,it.lng]).addTo(layer)
      .bindPopup("<b>"+esc(it.label||T("Public restroom"))+"</b><br>"+it.dist+" m &middot; "+it.walk+" "+T("min"));
    marks.push(m); pts.push([it.lat,it.lng]);
  });
  // 내 위치가 한가운데, 가장 가까운 세 곳까지만 보이게 — 손가락으로 확대할 일 없게
  var near=pts.slice(0,4);
  if(near.length>1){var b=L.latLngBounds(near);var z=Math.min(map.getBoundsZoom(b.pad(.25)),17);
    var c=[lat,lng];var dl=0;near.forEach(function(p){dl=Math.max(dl,Math.abs(p[0]-c[0]),Math.abs(p[1]-c[1]))});
    map.setView(c,Math.max(Math.min(map.getBoundsZoom(L.latLngBounds([[c[0]-dl,c[1]-dl],[c[0]+dl,c[1]+dl]]).pad(.15)),17),14));}
  else map.setView([lat,lng],16);
  setTimeout(function(){map.invalidateSize();},80);
}
document.getElementById("addBtn").onclick=function(){
  var b=this;
  if(!navigator.geolocation){alert("Geolocation not supported.");return;}
  if(!confirm("Add a restroom at your current location?\\nOnly do this if you are standing at one."))return;
  b.disabled=true;b.textContent="Getting your position...";
  navigator.geolocation.getCurrentPosition(function(p){
    var nm=prompt("Name or landmark (optional)","")||"";
    var fee=confirm("Is it free?\\nOK = free, Cancel = paid")?0:1;
    var wc=confirm("Wheelchair accessible?\\nOK = yes, Cancel = no")?1:0;
    b.textContent="Sending...";
    fetch("/api/gg/report",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({lat:p.coords.latitude,lng:p.coords.longitude,name:nm,fee:fee,wc:wc})})
     .then(function(r){return r.json();}).then(function(d){
       b.disabled=false;b.textContent=T("+ Add a restroom you found here");
       if(d.ok){alert("Thanks. Your report is live.");query(p.coords.latitude,p.coords.longitude,true);}
       else alert("Could not save: "+(d.error||"unknown"));
     }).catch(function(){b.disabled=false;
       b.textContent=T("+ Add a restroom you found here");alert("Request failed.");});
  },function(){b.disabled=false;
    b.textContent=T("+ Add a restroom you found here");alert("Location permission denied.");},
  {enableHighAccuracy:true,timeout:15000,maximumAge:0});
};
function query(lat,lng,keep){
  last=[lat,lng];
  BACK.classList.add("on");
  if(!keep){ try{history.pushState({r:1},"","#results");}catch(e){} }
  OUT.innerHTML='<div class="msg">'+T("Searching...")+'</div>';
  fetch("/api/gg/near?lat="+lat+"&lng="+lng+(free?"&free=1":"")+(wc?"&wc=1":""))
   .then(function(r){return r.json();}).then(function(d){
    if(!d.ok){OUT.innerHTML='<div class="msg">'+esc(d.error)+'</div>';return;}
    if(!d.covered){
      MAPEL.classList.remove("on");
      document.getElementById("addBtn").classList.remove("on");
      OUT.innerHTML='<div class="msg">'+T("Not covered here yet.")+'<br>'+T("Nearest supported city: ")+'<b>'
        +esc(d.nearest)+'</b> ('+d.nearest_km+' km)<div class="chips" id="chips3"></div></div>';
      fillChips("chips3"); return;}
    if(!d.items.length){
      MAPEL.classList.remove("on");
      document.getElementById("addBtn").classList.remove("on");
      OUT.innerHTML='<div class="msg">'+T("Nothing within 4 km with these filters.")+'</div>';return;}
    var h='<div class="city">'+esc(d.city)+' &middot; '+d.total+' '+T("mapped")+'</div>';
    d.items.forEach(function(it,i){
      h+='<div class="row" data-i="'+i+'"><div class="n"><div class="lb'+(it.label?"":" dim")+'">'
        +esc(it.label||T("Public restroom"))+'</div><div class="tags">';
      h+='<span class="tag">'+(it.fee?T("Paid"):T("Free"))+'</span>';
   if(it.user)h+='<span class="tag utag">'+T("Reported")+'</span>';
      if(it.h24)h+='<span class="tag">24h</span>';
      if(it.wc)h+='<span class="tag">'+T("Wheelchair")+'</span>';
      if(it.baby)h+='<span class="tag">'+T("Baby")+'</span>';
      h+='</div></div><div class="d"><b>'+it.dist+'m</b><span>'+it.walk+' '+T("min")+'</span></div></div>';
    });
    OUT.innerHTML=h;
    drawMap(lat,lng,d.items);
    document.getElementById("addBtn").classList.add("on");
    Array.prototype.forEach.call(document.querySelectorAll(".row"),function(el){
      el.onclick=function(){
        var i=+el.getAttribute("data-i"); var it=d.items[i];
        Array.prototype.forEach.call(document.querySelectorAll(".row"),function(x){x.classList.remove("sel");});
        el.classList.add("sel");
        if(map&&marks[i]){map.setView([it.lat,it.lng],17);marks[i].openPopup();
          MAPEL.scrollIntoView({behavior:"smooth",block:"center"});}
      };
    });
   }).catch(function(){OUT.innerHTML='<div class="msg">'+T("Request failed.")+'</div>';});
}
</script></body></html>"""


PRIVACY = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GottaGo - Privacy Policy</title>
<style>
body{margin:0;background:#0b0f16;color:#e9eef5;font:15px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.w{max-width:720px;margin:0 auto;padding:28px 18px 80px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:26px 0 6px;color:#7ff0e2}
p,li{color:#c3cedb;font-size:14px}
.d{color:#7f8ea0;font-size:12.5px;margin:0 0 20px}
a{color:#5f9fe0}
code{background:#141a24;padding:1px 5px;border-radius:4px;font-size:13px}
</style></head><body><div class="w">
<h1>Privacy Policy</h1>
<p class="d">GottaGo - Restroom Finder &middot; Last updated: 2 September 2026</p>

<h2>Who we are</h2>
<p>GottaGo is operated by alaz ltd. Contact: <a href="mailto:cigua7134@gmail.com">cigua7134@gmail.com</a></p>

<h2>What we collect</h2>
<p><b>Location.</b> When you tap "Find restrooms near me", your device asks for
permission and sends your coordinates to our server so we can calculate which
restrooms are nearest to you. This happens only when you tap that button.</p>
<p>We do <b>not</b> store your location. The coordinates are used to compute
distances and are discarded once the response is sent. They are not linked to
any identifier and are not used to build a profile of you.</p>

<h2>What we do not collect</h2>
<ul>
<li>No account, name, email address or phone number</li>
<li>No advertising identifiers</li>
<li>No contacts, photos, files or device identifiers</li>
<li>No analytics or tracking cookies</li>
<li>No background or continuous location tracking</li>
</ul>

<h2>Third parties</h2>
<p>Map tiles are served by <a href="https://www.openstreetmap.org/" target="_blank" rel="noopener">OpenStreetMap</a>.
When the map is displayed, your browser requests tiles directly from their
servers, which receive your IP address as part of any normal web request.
See the <a href="https://wiki.osmfoundation.org/wiki/Privacy_Policy" target="_blank" rel="noopener">OSM Foundation privacy policy</a>.</p>
<p>Our servers are hosted by Render. Standard web server logs (IP address,
timestamp, requested path) are retained for operational and security purposes.</p>

<h2>Data source</h2>
<p>Restroom locations come from OpenStreetMap contributors and are licensed
under the <a href="https://opendatacommons.org/licenses/odbl/" target="_blank" rel="noopener">Open Database License (ODbL)</a>.
Street and district names are resolved using the Photon geocoding service.</p>

<h2>Children</h2>
<p>This app is not directed at children under 13 and we do not knowingly
collect any information from them.</p>

<h2>Your rights</h2>
<p>Because we do not store personal data, there is nothing to export or erase
on request. If you believe we hold information about you, write to the address
above and we will respond within 30 days.</p>

<h2>Changes</h2>
<p>If this policy changes, the date at the top of this page will be updated.</p>
</div></body></html>"""
