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


@gg_bp.route("/api/gg/near")
def gg_near():
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
    except Exception:
        return jsonify({"ok": False, "error": "bad coords"}), 400
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return jsonify({"ok": False, "error": "bad coords"}), 400
    m, dist = city_at(lat, lng)
    if m is None:
        return jsonify({"ok": False, "error": "no data"}), 404
    if dist > 0:
        return jsonify({"ok": True, "covered": False, "nearest": m["label"],
                        "nearest_km": int(dist), "items": [],
                        "cities": [x["label"] for x in metas()]})
    rows = load(m["key"])
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
                      "fee": t.get("fee", 0), "h24": t.get("h24", 0),
                      "wc": 1 if "휠체어" in (t.get("access") or "") else 0,
                      "baby": 1 if "기저귀" in (t.get("access") or "") else 0,
                      "dist": int(d), "walk": max(1, int(d / 75))})
    return jsonify({"ok": True, "covered": True, "city": m["label"],
                    "cc": m.get("cc", ""), "total": len(rows), "items": items})


@gg_bp.route("/api/gg/cities")
def gg_cities():
    return jsonify({"ok": True, "cities": [
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


@gg_bp.route("/gottago")
@gg_bp.route("/gottago/")
def gg_page():
    return Response(PAGE, mimetype="text/html; charset=utf-8")


PAGE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>GottaGo - Restroom Finder</title>
<meta name="description" content="Find the nearest public restroom in 20 cities worldwide. Free, wheelchair-accessible and 24h filters.">
<link rel="manifest" href="/gottago/manifest.json">
<meta name="theme-color" content="#0b0f16">
<link rel="apple-touch-icon" href="/gottago/icon-192.png">
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:#0b0f16;color:#e9eef5;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif}
.wrap{max-width:660px;margin:0 auto;padding:20px 14px 96px}
.top{display:flex;align-items:center;gap:10px;margin:0 0 4px}
.top img{width:38px;height:38px;border-radius:10px}
h1{font-size:19px;margin:0;letter-spacing:-.3px}
.sub{color:#7f8ea0;font-size:12.5px;margin:0 0 16px 48px}
button{font:inherit;cursor:pointer}
.go{width:100%;background:#1ab2aa;color:#04211f;border:0;border-radius:13px;padding:15px;font-size:16px;font-weight:700}
.go:disabled{opacity:.55}
.f{display:flex;gap:7px;margin:14px 0 4px;flex-wrap:wrap}
.f button{background:#141a24;border:1px solid #24303f;color:#9fb0c2;border-radius:999px;padding:7px 13px;font-size:12.5px}
.f button.on{background:#123430;border-color:#1ab2aa;color:#7ff0e2}
.city{color:#7f8ea0;font-size:12px;margin:16px 0 6px}
.row{display:flex;gap:12px;align-items:center;padding:13px 4px;border-bottom:1px solid #18202b}
.row .n{min-width:0;flex:1}
.lb{font-size:14.5px;font-weight:600;line-height:1.35}
.lb.dim{color:#8b98a8;font-weight:500}
.tags{color:#7f8ea0;font-size:11.5px;margin-top:3px}
.tag{display:inline-block;background:#141a24;border:1px solid #24303f;border-radius:6px;padding:1px 6px;margin-right:4px}
.d{text-align:right;flex:none}
.d b{display:block;font-size:16px;color:#7ff0e2}
.d span{font-size:11px;color:#7f8ea0}
.msg{color:#8b98a8;text-align:center;padding:36px 10px;font-size:14px;line-height:1.7}
.chips{display:flex;gap:6px;flex-wrap:wrap;justify-content:center;margin-top:12px}
.chips button{background:#141a24;border:1px solid #24303f;color:#9fb0c2;border-radius:999px;padding:6px 12px;font-size:12px}
.foot{color:#5d6b7c;font-size:11px;margin-top:26px;line-height:1.6}
a{color:#5f9fe0}
</style></head><body><div class="wrap">
<div class="top"><img src="/gottago/icon-192.png" alt=""><h1>GottaGo</h1></div>
<p class="sub">Restroom Finder</p>
<button class="go" id="go">Find restrooms near me</button>
<div class="f">
  <button id="ffree">Free only</button>
  <button id="fwc">Wheelchair</button>
</div>
<div id="out"><div class="msg">Tap the button to see the nearest restrooms.<div class="chips" id="chips"></div></div></div>
<p class="foot">Data from OpenStreetMap contributors (ODbL). Opening hours are rarely mapped, so they are not shown. Always check on site.</p>
</div><script>
var OUT=document.getElementById("out"), GO=document.getElementById("go");
var free=0, wc=0, last=null;
function esc(t){var d=document.createElement("div");d.textContent=t==null?"":t;return d.innerHTML;}
function tg(id,set){var b=document.getElementById(id);
 b.onclick=function(){set(); b.classList.toggle("on"); if(last)query(last[0],last[1]);};}
tg("ffree",function(){free=free?0:1;});
tg("fwc",function(){wc=wc?0:1;});
fetch("/api/gg/cities").then(function(r){return r.json();}).then(function(d){
  var c=document.getElementById("chips"); if(!c||!d.ok)return;
  d.cities.forEach(function(x){
    var b=document.createElement("button");
    b.textContent=x.label+" ("+x.count+")";
    b.onclick=function(){query(x.lat,x.lng);};
    c.appendChild(b);
  });
});
GO.onclick=function(){
  if(!navigator.geolocation){OUT.innerHTML='<div class="msg">Geolocation not supported.</div>';return;}
  GO.disabled=true; GO.textContent="Locating...";
  navigator.geolocation.getCurrentPosition(function(p){
    GO.disabled=false; GO.textContent="Find restrooms near me";
    query(p.coords.latitude,p.coords.longitude);
  },function(){
    GO.disabled=false; GO.textContent="Find restrooms near me";
    OUT.innerHTML='<div class="msg">Location permission denied.<br>Pick a city below instead.<div class="chips" id="chips2"></div></div>';
    fetch("/api/gg/cities").then(function(r){return r.json();}).then(function(d){
      var c=document.getElementById("chips2"); if(!c)return;
      d.cities.forEach(function(x){var b=document.createElement("button");
        b.textContent=x.label; b.onclick=function(){query(x.lat,x.lng);}; c.appendChild(b);});
    });
  },{enableHighAccuracy:true,timeout:12000,maximumAge:60000});
};
function query(lat,lng){
  last=[lat,lng];
  OUT.innerHTML='<div class="msg">Searching...</div>';
  fetch("/api/gg/near?lat="+lat+"&lng="+lng+(free?"&free=1":"")+(wc?"&wc=1":""))
   .then(function(r){return r.json();}).then(function(d){
    if(!d.ok){OUT.innerHTML='<div class="msg">'+esc(d.error)+'</div>';return;}
    if(!d.covered){
      OUT.innerHTML='<div class="msg">Not covered here yet.<br>Nearest supported city: <b>'
        +esc(d.nearest)+'</b> ('+d.nearest_km+' km away)</div>';return;}
    if(!d.items.length){
      OUT.innerHTML='<div class="msg">Nothing within 4 km with these filters.</div>';return;}
    var h='<div class="city">'+esc(d.city)+' &middot; '+d.total+' mapped</div>';
    d.items.forEach(function(it){
      var lab=it.label||"Public restroom";
      h+='<div class="row"><div class="n"><div class="lb'+(it.label?"":" dim")+'">'+esc(lab)+'</div><div class="tags">';
      h+='<span class="tag">'+(it.fee?"Paid":"Free")+'</span>';
      if(it.h24)h+='<span class="tag">24h</span>';
      if(it.wc)h+='<span class="tag">Wheelchair</span>';
      if(it.baby)h+='<span class="tag">Baby</span>';
      h+='</div></div><div class="d"><b>'+it.dist+'m</b><span>'+it.walk+' min</span></div></div>';
    });
    OUT.innerHTML=h;
   }).catch(function(){OUT.innerHTML='<div class="msg">Request failed.</div>';});
}
</script></body></html>"""
