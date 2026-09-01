# -*- coding: utf-8 -*-
"""돼지레이다 세계화 — Wikivoyage 식당 큐레이션 수집기 v1 (Python 3.9 호환)
   여행자가 쓴 비상업 큐레이션. 광고를 받지 않으므로 바이럴 부풀림이 구조적으로 불가능.
   라이선스: CC BY-SA 4.0 — 출처·라이선스 표기 필수, 파생물도 동일 라이선스.

   흐름: geosearch로 도시/구역 문서 찾기 → 위키텍스트 listing 파싱
        → 좌표 없으면 Photon 정지오코딩(이름 유사도 검증 통과분만)
   사용: python3 wv_eat_collect_v1.py [도시키 ...] | --list | --stat
"""
import json, os, re, sys, time, math, difflib, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "eats_world")
UA = "PigRadar/1.0 (kohgane; +https://linklynk.onrender.com/eats)"
WV = "https://en.wikivoyage.org/w/api.php"
PHOTON = "https://photon.komoot.io/api/"
PAUSE = 0.6
SIM = 0.62          # 이름 유사도 하한. 미달이면 좌표를 붙이지 않는다

CITIES = {
    "tokyo":     ("도쿄", "JP", 35.6895, 139.6917),
    "osaka":     ("오사카", "JP", 34.6937, 135.5023),
    "kyoto":     ("교토", "JP", 35.0116, 135.7681),
    "fukuoka":   ("후쿠오카", "JP", 33.5904, 130.4017),
    "taipei":    ("타이베이", "TW", 25.0330, 121.5654),
    "bangkok":   ("방콕", "TH", 13.7563, 100.5018),
    "singapore": ("싱가포르", "SG", 1.3521, 103.8198),
    "hongkong":  ("홍콩", "HK", 22.3193, 114.1694),
    "hanoi":     ("하노이", "VN", 21.0278, 105.8342),
    "danang":    ("다낭", "VN", 16.0544, 108.2022),
    "london":    ("런던", "GB", 51.5074, -0.1278),
    "paris":     ("파리", "FR", 48.8566, 2.3522),
    "rome":      ("로마", "IT", 41.9028, 12.4964),
    "barcelona": ("바르셀로나", "ES", 41.3874, 2.1686),
    "prague":    ("프라하", "CZ", 50.0755, 14.4378),
    "newyork":   ("뉴욕", "US", 40.7128, -74.0060),
    "sanfran":   ("샌프란시스코", "US", 37.7749, -122.4194),
    "sydney":    ("시드니", "AU", -33.8688, 151.2093),
}


def get(url):
    r = urllib.request.Request(url)
    r.add_header("User-Agent", UA)
    return json.loads(urllib.request.urlopen(r, timeout=35).read().decode("utf-8"))


def wv(params):
    params.update({"format": "json", "formatversion": 2})
    return get(WV + "?" + urllib.parse.urlencode(params))


def pages_near(lat, lng, radius=14000, limit=40):
    """좌표 주변 위키보야지 문서 = 도시 및 구역 문서"""
    try:
        d = wv({"action": "query", "list": "geosearch",
                "gscoord": "%f|%f" % (lat, lng),
                "gsradius": str(radius), "gslimit": str(limit)})
        return [p["title"] for p in d["query"]["geosearch"]]
    except Exception as e:
        print("    geosearch 실패 %s" % str(e)[:40])
        return []


def wikitext(title):
    try:
        d = wv({"action": "parse", "page": title, "prop": "wikitext"})
        return d["parse"]["wikitext"]
    except Exception:
        return ""


LIST_RE = re.compile(r'\{\{\s*(eat|drink|listing)\b([^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*)\}\}', re.I | re.S)


def field(body, key):
    m = re.search(r'\|\s*' + key + r'\s*=\s*([^|\n]*)', body)
    return m.group(1).strip() if m else ""


def clean(s):
    s = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", s or "")
    s = re.sub(r"''+", "", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse(w, page):
    out = []
    for m in LIST_RE.finditer(w):
        kind, body = m.group(1).lower(), m.group(2)
        typ = field(body, "type").lower()
        if kind == "listing" and typ not in ("eat", "drink"):
            continue
        nm = clean(field(body, "name"))
        if len(nm) < 2:
            continue
        out.append({
            "name": nm[:60],
            "lat": field(body, "lat"), "lng": field(body, "long"),
            "addr": clean(field(body, "address"))[:70],
            "price": clean(field(body, "price"))[:40],
            "hours": clean(field(body, "hours"))[:50],
            "desc": clean(field(body, "content"))[:220],
            "kind": typ or kind, "src": page,
        })
    return out


def geocode(name, addr, lat, lng):
    q = ("%s %s" % (name, addr)).strip()[:80]
    url = PHOTON + "?" + urllib.parse.urlencode(
        {"q": q, "lat": "%f" % lat, "lon": "%f" % lng, "limit": 1, "lang": "en"})
    try:
        d = get(url)
    except Exception:
        return None
    f = (d.get("features") or [None])[0]
    if not f:
        return None
    p = f.get("properties", {}) or {}
    cand = p.get("name") or ""
    # 이름 유사도 검증 — 엉뚱한 가게 좌표를 붙이지 않는다
    sim = difflib.SequenceMatcher(None, name.lower(), cand.lower()).ratio()
    if sim < SIM:
        return None
    c = f["geometry"]["coordinates"]
    return (c[1], c[0], round(sim, 2))


def collect(key):
    label, cc, lat, lng = CITIES[key]
    path = os.path.join(OUT, "%s.json" % key)
    rows, seen = [], set()
    if os.path.exists(path):
        rows = json.load(open(path, encoding="utf-8"))
        seen = set((r["name"], r["src"]) for r in rows)
        print("  기존 %d건 이어받음" % len(rows))
    pages = pages_near(lat, lng)
    print("  %s(%s) 문서 %d개" % (label, cc, len(pages)))
    sys.stdout.flush()
    for i, pg in enumerate(pages, 1):
        w = wikitext(pg)
        if not w:
            continue
        got = 0
        for it in parse(w, pg):
            k = (it["name"], it["src"])
            if k in seen:
                continue
            seen.add(k)
            it["cc"] = cc
            it["city"] = label
            rows.append(it)
            got += 1
        print("    [%d/%d] %-34s +%d (누적 %d)" % (i, len(pages), pg[:34], got, len(rows)))
        sys.stdout.flush()
        json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(PAUSE)
    # 좌표 보강
    need = [r for r in rows if not (r.get("lat") and r.get("lng"))]
    print("  좌표 미보유 %d건 정지오코딩" % len(need))
    sys.stdout.flush()
    hit = 0
    for j, r in enumerate(need, 1):
        g = geocode(r["name"], r.get("addr", ""), lat, lng)
        if g:
            r["lat"], r["lng"], r["geo_sim"] = "%.6f" % g[0], "%.6f" % g[1], g[2]
            hit += 1
        else:
            r["geo_sim"] = 0
        if j % 20 == 0:
            json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
            print("    [%d/%d] 성공 %d" % (j, len(need), hit))
            sys.stdout.flush()
        time.sleep(0.4)
    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    withxy = sum(1 for r in rows if r.get("lat") and r.get("lng"))
    meta = {"key": key, "label": label, "cc": cc, "center": [lat, lng],
            "count": len(rows), "with_coord": withxy,
            "license": "CC BY-SA 4.0 / Wikivoyage",
            "built": time.strftime("%Y-%m-%d")}
    json.dump(meta, open(os.path.join(OUT, "%s.meta.json" % key), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("  => %s %d건 · 좌표 %d (%d%%)" % (key, len(rows), withxy,
                                            100 * withxy // max(len(rows), 1)))
    sys.stdout.flush()


def stat():
    if not os.path.isdir(OUT):
        print("  아직 없음"); return
    tot = xy = 0
    for f in sorted(os.listdir(OUT)):
        if not f.endswith(".json") or f.endswith(".meta.json"):
            continue
        rows = json.load(open(os.path.join(OUT, f), encoding="utf-8"))
        w = sum(1 for r in rows if r.get("lat") and r.get("lng"))
        tot += len(rows); xy += w
        print("  %-12s %4d건  좌표 %4d (%d%%)" % (f[:-5], len(rows), w,
                                                 100 * w // max(len(rows), 1)))
    print("  합계 %d건 · 좌표 %d (%d%%)" % (tot, xy, 100 * xy // max(tot, 1)))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if "--list" in sys.argv:
        for k in CITIES:
            print("  %-11s %s (%s)" % (k, CITIES[k][0], CITIES[k][1]))
        sys.exit(0)
    if "--stat" in sys.argv:
        stat(); sys.exit(0)
    keys = [x for x in sys.argv[1:] if x in CITIES] or list(CITIES)
    for k in keys:
        print("=== %s" % k); sys.stdout.flush()
        collect(k)
    stat()
