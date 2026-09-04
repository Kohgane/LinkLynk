# -*- coding: utf-8 -*-
"""돼지레이다 세계화 — Wikivoyage 여행자 큐레이션 (해외 전용)
   광고를 받지 않는 위키 데이터라 바이럴 부풀림이 구조적으로 불가능하다.
   라이선스: CC BY-SA 4.0 / Wikivoyage — 화면에 출처·라이선스 표기 필수.
"""
import json, math, os, threading
from flask import Blueprint, request, jsonify, Response, send_from_directory

ea_bp = Blueprint("eats", __name__)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "tools", "eats_world")
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
    """가장 가까운 도시와 거리(km). 60km 이내면 커버로 본다."""
    best, bd = None, 1e18
    for m in metas():
        c = m.get("center") or [0, 0]
        dy = (c[0] - lat) * 111.32
        dx = (c[1] - lng) * 111.32 * math.cos(math.radians(lat))
        d = math.hypot(dx, dy)
        if d < bd:
            bd, best = d, m
    return best, bd


def load(key):
    with _lock:
        if key not in _cache:
            try:
                _cache[key] = json.load(open(os.path.join(DATA, "%s.json" % key), encoding="utf-8"))
            except Exception:
                _cache[key] = []
            if len(_cache) > 6:
                for k in list(_cache)[:-6]:
                    _cache.pop(k, None)
        return _cache[key]


@ea_bp.route("/api/eats/cities")
def ea_cities():
    return jsonify({"ok": True, "cities": [
        {"key": m["key"], "label": m["label"], "cc": m.get("cc", ""),
         "count": m.get("count", 0),
         "lat": (m.get("center") or [0, 0])[0],
         "lng": (m.get("center") or [0, 0])[1]} for m in metas()]})


@ea_bp.route("/api/eats/near")
def ea_near():
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
    if dist > 60:
        return jsonify({"ok": True, "covered": False, "nearest": m["label"],
                        "nearest_km": int(dist), "items": []})
    rows = load(m["key"])
    kind = request.args.get("kind", "")
    coslat = math.cos(math.radians(lat))
    out = []
    for t in rows:
        if kind and t.get("kind") != kind:
            continue
        try:
            tlat, tlng = float(t.get("lat")), float(t.get("lng"))
        except Exception:
            continue
        dy = (tlat - lat) * 111320.0
        dx = (tlng - lng) * 111320.0 * coslat
        d = math.hypot(dx, dy)
        if d < 6000:
            out.append((d, t, tlat, tlng))
    out.sort(key=lambda x: x[0])
    items = []
    for d, t, tlat, tlng in out[:24]:
        items.append({"name": t.get("name", ""), "lat": tlat, "lng": tlng,
                      "desc": t.get("desc", ""), "addr": t.get("addr", ""),
                      "price": t.get("price", ""), "hours": t.get("hours", ""),
                      "kind": t.get("kind", "eat"), "src": t.get("src", ""),
                      "dist": int(d), "walk": max(1, int(d / 75))})
    return jsonify({"ok": True, "covered": True, "city": m["label"],
                    "cc": m.get("cc", ""), "total": len(rows), "items": items})


@ea_bp.route("/eats/manifest.json")
def ea_manifest():
    return jsonify({
        "name": "Local Bites - Traveller Picks",
        "short_name": "LocalBites",
        "start_url": "/eats/", "scope": "/eats/",
        "display": "standalone", "background_color": "#0b0f16",
        "theme_color": "#0b0f16", "orientation": "portrait",
        "icons": [
            {"src": "/gottago/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/gottago/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}
        ]})


@ea_bp.route("/eats")
@ea_bp.route("/eats/")
def ea_page():
    return Response(PAGE, mimetype="text/html; charset=utf-8")


PAGE = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Local Bites - Traveller Picks</title>
<meta name="description" content="Places to eat and drink picked by travellers, not by ads. 3,900 spots across 18 cities.">
<link rel="manifest" href="/eats/manifest.json">
<meta name="theme-color" content="#0b0f16">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{max-width:100%;overflow-x:hidden}
body{margin:0;background:#0b0f16;color:#e9eef5;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif}
.wrap{max-width:660px;margin:0 auto;padding:18px 14px 40px;overflow-x:hidden}
.hd{display:flex;align-items:center;gap:10px;margin:0 0 2px}
.hd h1{font-size:19px;margin:0;letter-spacing:-.3px}
.back{background:#141a24;border:1px solid #24303f;color:#9fb0c2;border-radius:10px;
 width:36px;height:36px;font-size:17px;line-height:1;flex:none;display:none;cursor:pointer}
.back.on{display:block}
.sub{color:#7f8ea0;font-size:12.5px;margin:0 0 14px}
button{font:inherit;cursor:pointer}
.go{width:100%;background:#e0a04a;color:#231502;border:0;border-radius:13px;padding:15px;font-size:16px;font-weight:700}
.f{display:flex;gap:7px;margin:12px 0 0;flex-wrap:wrap}
.f button{background:#141a24;border:1px solid #24303f;color:#9fb0c2;border-radius:999px;padding:7px 13px;font-size:12.5px}
.f button.on{background:#33260f;border-color:#e0a04a;color:#f5d29a}
#map{height:240px;border-radius:14px;margin-top:14px;display:none;background:#141a24}
#map.on{display:block}
.city{color:#7f8ea0;font-size:12px;margin:14px 0 4px}
.card{padding:13px 2px;border-bottom:1px solid #18202b;cursor:pointer}
.card.sel{background:#1a1408}
.t{display:flex;gap:10px;align-items:baseline}
.nm{font-size:15px;font-weight:600;line-height:1.35;word-break:break-word;flex:1;min-width:0}
.dd{flex:none;text-align:right;color:#f0c78a;font-size:13px;font-weight:600}
.dd span{display:block;color:#7f8ea0;font-size:11px;font-weight:400}
.ds{color:#b6c2d0;font-size:13px;margin-top:5px;word-break:break-word}
.mt{margin-top:5px}
.tag{display:inline-block;background:#141a24;border:1px solid #24303f;color:#8b98a8;
 border-radius:6px;padding:1px 6px;margin:2px 4px 0 0;font-size:11.5px}
.msg{color:#8b98a8;text-align:center;padding:32px 8px;font-size:14px;line-height:1.7}
.chips{display:flex;gap:6px;flex-wrap:wrap;justify-content:center;margin-top:12px}
.chips button{background:#141a24;border:1px solid #24303f;color:#9fb0c2;border-radius:999px;padding:6px 12px;font-size:12px}
.foot{color:#5d6b7c;font-size:11px;margin-top:22px;line-height:1.6}
.foot a{color:#5f9fe0}
</style></head><body><div class="wrap">
<div class="hd"><button class="back" id="back" aria-label="Back">&#8592;</button><h1>Local Bites</h1></div>
<p class="sub">Eat &amp; drink spots picked by travellers &mdash; not by ads</p>
<button class="go" id="go">Find places near me</button>
<div class="f"><button id="feat">Food</button><button id="fdrink">Drinks</button></div>
<div id="map"></div>
<div id="out"><div class="msg">Tap the button or pick a city.<div class="chips" id="chips"></div></div></div>
<p class="foot">Text and locations from <a href="https://en.wikivoyage.org/" target="_blank" rel="noopener">Wikivoyage</a>,
licensed <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener">CC BY-SA 4.0</a>.
Written by travellers, not by owners. Prices and hours may be out of date &mdash; check before you go.</p>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var OUT=document.getElementById("out"),GO=document.getElementById("go"),BACK=document.getElementById("back");
var MAPEL=document.getElementById("map");
var kind="",last=null,map=null,layer=null,marks=[];
function esc(t){var d=document.createElement("div");d.textContent=t==null?"":t;return d.innerHTML;}
function fillChips(id){
 fetch("/api/eats/cities").then(function(r){return r.json();}).then(function(d){
  var c=document.getElementById(id); if(!c||!d.ok)return;
  d.cities.forEach(function(x){
   var b=document.createElement("button");
   b.textContent=x.label+" ("+x.count+")";
   b.onclick=function(){query(x.lat,x.lng);};
   c.appendChild(b);});});}
function home(){last=null;MAPEL.classList.remove("on");BACK.classList.remove("on");
 OUT.innerHTML='<div class="msg">Tap the button or pick a city.<div class="chips" id="chips"></div></div>';
 fillChips("chips");}
fillChips("chips");
BACK.onclick=function(){if(history.state&&history.state.r){history.back();}else{home();}};
window.addEventListener("popstate",function(){home();});
function tg(id,val){var b=document.getElementById(id);
 b.onclick=function(){
  var others=["feat","fdrink"];
  kind=(kind===val)?"":val;
  others.forEach(function(o){document.getElementById(o).classList.remove("on");});
  if(kind)b.classList.add("on");
  if(last)query(last[0],last[1],true);};}
tg("feat","eat"); tg("fdrink","drink");
GO.onclick=function(){
 if(!navigator.geolocation){OUT.innerHTML='<div class="msg">Geolocation not supported.</div>';return;}
 GO.disabled=true;GO.textContent="Locating...";
 navigator.geolocation.getCurrentPosition(function(p){
  GO.disabled=false;GO.textContent="Find places near me";
  query(p.coords.latitude,p.coords.longitude);
 },function(){
  GO.disabled=false;GO.textContent="Find places near me";
  OUT.innerHTML='<div class="msg">Location denied. Pick a city.<div class="chips" id="c2"></div></div>';
  fillChips("c2");},{enableHighAccuracy:true,timeout:12000,maximumAge:60000});};
function drawMap(lat,lng,items){
 MAPEL.classList.add("on");
 if(!map){map=L.map("map",{zoomControl:false,attributionControl:false}).setView([lat,lng],15);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19}).addTo(map);
  L.control.zoom({position:"topright"}).addTo(map);}
 if(layer)map.removeLayer(layer);
 marks=[];layer=L.layerGroup().addTo(map);
 L.circleMarker([lat,lng],{radius:7,color:"#f0c78a",fillColor:"#e0a04a",fillOpacity:1,weight:2})
  .addTo(layer).bindPopup("You are here");
 var pts=[[lat,lng]];
 items.forEach(function(it){
  marks.push(L.marker([it.lat,it.lng]).addTo(layer)
   .bindPopup("<b>"+esc(it.name)+"</b><br>"+it.dist+" m &middot; "+it.walk+" min"));
  pts.push([it.lat,it.lng]);});
 map.fitBounds(pts,{padding:[28,28],maxZoom:16});
 setTimeout(function(){map.invalidateSize();},80);}
function query(lat,lng,keep){
 last=[lat,lng];BACK.classList.add("on");
 if(!keep){try{history.pushState({r:1},"","#results");}catch(e){}}
 OUT.innerHTML='<div class="msg">Searching...</div>';
 fetch("/api/eats/near?lat="+lat+"&lng="+lng+(kind?"&kind="+kind:""))
  .then(function(r){return r.json();}).then(function(d){
   if(!d.ok){OUT.innerHTML='<div class="msg">'+esc(d.error)+'</div>';return;}
   if(!d.covered){MAPEL.classList.remove("on");
    OUT.innerHTML='<div class="msg">Not covered here yet.<br>Nearest city: <b>'+esc(d.nearest)
     +'</b> ('+d.nearest_km+' km)<div class="chips" id="c3"></div></div>';fillChips("c3");return;}
   if(!d.items.length){MAPEL.classList.remove("on");
    OUT.innerHTML='<div class="msg">Nothing nearby with this filter.</div>';return;}
   var h='<div class="city">'+esc(d.city)+' &middot; '+d.total+' spots</div>';
   d.items.forEach(function(it,i){
    h+='<div class="card" data-i="'+i+'"><div class="t"><div class="nm">'+esc(it.name)
      +'</div><div class="dd">'+it.dist+'m<span>'+it.walk+' min</span></div></div>';
    if(it.desc)h+='<div class="ds">'+esc(it.desc)+'</div>';
    var tg2="";
    tg2+='<span class="tag">'+(it.kind==="drink"?"Drinks":"Food")+'</span>';
    if(it.price)tg2+='<span class="tag">'+esc(it.price)+'</span>';
    if(it.hours)tg2+='<span class="tag">'+esc(it.hours)+'</span>';
    h+='<div class="mt">'+tg2+'</div></div>';});
   OUT.innerHTML=h;
   drawMap(lat,lng,d.items);
   Array.prototype.forEach.call(document.querySelectorAll(".card"),function(el){
    el.onclick=function(){var i=+el.getAttribute("data-i");var it=d.items[i];
     Array.prototype.forEach.call(document.querySelectorAll(".card"),function(x){x.classList.remove("sel");});
     el.classList.add("sel");
     if(map&&marks[i]){map.setView([it.lat,it.lng],17);marks[i].openPopup();
      MAPEL.scrollIntoView({behavior:"smooth",block:"center"});}};});
  }).catch(function(){OUT.innerHTML='<div class="msg">Request failed.</div>';});}
</script></body></html>"""
