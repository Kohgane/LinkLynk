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
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
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
#map{height:240px;border-radius:14px;margin-top:14px;display:none;background:#141a24}
#map.on{display:block}
.leaflet-container{background:#141a24}
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
<div id="map"></div>
<div id="out"><div class="msg">Tap the button to see the nearest restrooms.<div class="chips" id="chips"></div></div></div>
<p class="foot">Data &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors (ODbL). Opening hours are rarely mapped, so they are not shown. Always check on site.</p>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var OUT=document.getElementById("out"),GO=document.getElementById("go"),BACK=document.getElementById("back");
var MAPEL=document.getElementById("map");
var free=0,wc=0,last=null,map=null,layer=null,marks=[];
function esc(t){var d=document.createElement("div");d.textContent=t==null?"":t;return d.innerHTML;}
function home(){
  last=null; MAPEL.classList.remove("on"); BACK.classList.remove("on");
  OUT.innerHTML='<div class="msg">Tap the button to see the nearest restrooms.<div class="chips" id="chips"></div></div>';
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
BACK.onclick=function(){ if(history.state&&history.state.r){history.back();} else {home();} };
window.addEventListener("popstate",function(){ home(); });
function tg(id,set){var b=document.getElementById(id);
  b.onclick=function(){set();b.classList.toggle("on");if(last)query(last[0],last[1],true);};}
tg("ffree",function(){free=free?0:1;});
tg("fwc",function(){wc=wc?0:1;});
GO.onclick=function(){
  if(!navigator.geolocation){OUT.innerHTML='<div class="msg">Geolocation not supported.</div>';return;}
  GO.disabled=true;GO.textContent="Locating...";
  navigator.geolocation.getCurrentPosition(function(p){
    GO.disabled=false;GO.textContent="Find restrooms near me";
    query(p.coords.latitude,p.coords.longitude);
  },function(){
    GO.disabled=false;GO.textContent="Find restrooms near me";
    OUT.innerHTML='<div class="msg">Location permission denied.<br>Pick a city below.<div class="chips" id="chips2"></div></div>';
    fillChips("chips2");
  },{enableHighAccuracy:true,timeout:12000,maximumAge:60000});
};
function drawMap(lat,lng,items){
  MAPEL.classList.add("on");
  if(!map){
    map=L.map("map",{zoomControl:false,attributionControl:false}).setView([lat,lng],15);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19}).addTo(map);
    L.control.zoom({position:"topright"}).addTo(map);
  }
  if(layer)map.removeLayer(layer);
  marks=[];
  layer=L.layerGroup().addTo(map);
  L.circleMarker([lat,lng],{radius:7,color:"#7ff0e2",fillColor:"#1ab2aa",fillOpacity:1,weight:2})
    .addTo(layer).bindPopup("You are here");
  var pts=[[lat,lng]];
  items.forEach(function(it,i){
    var m=L.marker([it.lat,it.lng]).addTo(layer)
      .bindPopup("<b>"+esc(it.label||"Public restroom")+"</b><br>"+it.dist+" m &middot; "+it.walk+" min");
    marks.push(m); pts.push([it.lat,it.lng]);
  });
  map.fitBounds(pts,{padding:[28,28],maxZoom:16});
  setTimeout(function(){map.invalidateSize();},80);
}
function query(lat,lng,keep){
  last=[lat,lng];
  BACK.classList.add("on");
  if(!keep){ try{history.pushState({r:1},"","#results");}catch(e){} }
  OUT.innerHTML='<div class="msg">Searching...</div>';
  fetch("/api/gg/near?lat="+lat+"&lng="+lng+(free?"&free=1":"")+(wc?"&wc=1":""))
   .then(function(r){return r.json();}).then(function(d){
    if(!d.ok){OUT.innerHTML='<div class="msg">'+esc(d.error)+'</div>';return;}
    if(!d.covered){
      MAPEL.classList.remove("on");
      OUT.innerHTML='<div class="msg">Not covered here yet.<br>Nearest supported city: <b>'
        +esc(d.nearest)+'</b> ('+d.nearest_km+' km)<div class="chips" id="chips3"></div></div>';
      fillChips("chips3"); return;}
    if(!d.items.length){
      MAPEL.classList.remove("on");
      OUT.innerHTML='<div class="msg">Nothing within 4 km with these filters.</div>';return;}
    var h='<div class="city">'+esc(d.city)+' &middot; '+d.total+' mapped</div>';
    d.items.forEach(function(it,i){
      h+='<div class="row" data-i="'+i+'"><div class="n"><div class="lb'+(it.label?"":" dim")+'">'
        +esc(it.label||"Public restroom")+'</div><div class="tags">';
      h+='<span class="tag">'+(it.fee?"Paid":"Free")+'</span>';
      if(it.h24)h+='<span class="tag">24h</span>';
      if(it.wc)h+='<span class="tag">Wheelchair</span>';
      if(it.baby)h+='<span class="tag">Baby</span>';
      h+='</div></div><div class="d"><b>'+it.dist+'m</b><span>'+it.walk+' min</span></div></div>';
    });
    OUT.innerHTML=h;
    drawMap(lat,lng,d.items);
    Array.prototype.forEach.call(document.querySelectorAll(".row"),function(el){
      el.onclick=function(){
        var i=+el.getAttribute("data-i"); var it=d.items[i];
        Array.prototype.forEach.call(document.querySelectorAll(".row"),function(x){x.classList.remove("sel");});
        el.classList.add("sel");
        if(map&&marks[i]){map.setView([it.lat,it.lng],17);marks[i].openPopup();
          MAPEL.scrollIntoView({behavior:"smooth",block:"center"});}
      };
    });
   }).catch(function(){OUT.innerHTML='<div class="msg">Request failed.</div>';});
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
