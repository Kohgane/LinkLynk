# -*- coding: utf-8 -*-
"""가라고 세계화 — OSM 화장실 수집기 v1
   toilets_kr.json과 동일 스키마로 도시별 파일 생성.
   사용: python3 osm_toilet_collect_v1.py [도시키 ...]   (생략시 전체)
        python3 osm_toilet_collect_v1.py --list
"""
import json, os, re, sys, time, math, urllib.request, urllib.error

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "toilets_world")
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]
UA = "GottaGo/1.0 (+https://linklynk.onrender.com/gottago)"
TILE  = 0.05         # 타일 한 변(도). 요청을 잘게 쪼개 503을 피한다
PAUSE = 6            # 타일 간 대기(초). 공용 서버 예의
MAXTRY = 6           # 미러 순회 + 지수 백오프
COOLDOWN = 300       # 한 타일이 전부 실패하면 이만큼 쉬었다 계속

# 도시키: (표시명, 국가코드, UTC오프셋, s, w, n, e)
CITIES = {
    "tokyo":     ("도쿄",       "JP",  9, 35.60, 139.60, 35.82, 139.92),
    "osaka":     ("오사카",     "JP",  9, 34.60, 135.40, 34.75, 135.60),
    "fukuoka":   ("후쿠오카",   "JP",  9, 33.53, 130.32, 33.65, 130.48),
    "sapporo":   ("삿포로",     "JP",  9, 43.00, 141.28, 43.10, 141.42),
    "taipei":    ("타이베이",   "TW",  8, 25.00, 121.48, 25.13, 121.61),
    "bangkok":   ("방콕",       "TH",  7, 13.65, 100.40, 13.87, 100.68),
    "singapore": ("싱가포르",   "SG",  8,  1.23, 103.68,  1.46, 103.95),
    "hongkong":  ("홍콩",       "HK",  8, 22.19, 114.10, 22.42, 114.28),
    "danang":    ("다낭",       "VN",  7, 15.99, 108.15, 16.12, 108.28),
    "hanoi":     ("하노이",     "VN",  7, 20.96, 105.75, 21.10, 105.90),
    "london":    ("런던",       "GB",  0, 51.42,  -0.30, 51.60,  0.05),
    "paris":     ("파리",       "FR",  1, 48.78,   2.22, 48.92,  2.47),
    "rome":      ("로마",       "IT",  1, 41.84,  12.40, 41.98, 12.58),
    "barcelona": ("바르셀로나", "ES",  1, 41.34,   2.09, 41.45,  2.23),
    "prague":    ("프라하",     "CZ",  1, 50.02,  14.32, 50.13, 14.53),
    "newyork":   ("뉴욕",       "US", -5, 40.65, -74.05, 40.85, -73.88),
    "losangeles":("LA",         "US", -8, 33.95,-118.45, 34.15,-118.20),
    "sanfran":   ("샌프란시스코","US", -8, 37.71,-122.52, 37.83,-122.36),
    "vancouver": ("밴쿠버",     "CA", -8, 49.20,-123.25, 49.32,-123.02),
    "sydney":    ("시드니",     "AU", 10,-33.92, 151.16,-33.83, 151.29),
}

Q = """[out:json][timeout:90];
(
  node["amenity"="toilets"](%f,%f,%f,%f);
  way["amenity"="toilets"](%f,%f,%f,%f);
);
out center tags;"""

def slots_free(ep="https://overpass-api.de/api/status"):
    """Overpass 동시 슬롯은 IP당 2개뿐. 비기를 기다렸다 친다."""
    try:
        req = urllib.request.Request(ep)
        req.add_header("User-Agent", UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            txt = r.read().decode("utf-8", "replace")
        m = re.search(r"(\d+) slots available now", txt)
        if m:
            return int(m.group(1))
        m = re.search(r"in (\d+) seconds", txt)
        return -int(m.group(1)) if m else 0
    except Exception:
        return 1


def wait_slot(maxwait=180):
    t0 = time.time()
    while time.time() - t0 < maxwait:
        n = slots_free()
        if n > 0:
            return True
        time.sleep(8 if n == 0 else min(abs(n) + 2, 30))
    return False


def fetch(q):
    data = q.encode("utf-8")
    for attempt in range(MAXTRY):
        ep = MIRRORS[attempt % len(MIRRORS)]
        if "overpass-api.de" in ep:
            wait_slot()
        try:
            req = urllib.request.Request(ep, data=data, method="POST")
            req.add_header("Content-Type", "text/plain; charset=utf-8")
            req.add_header("User-Agent", UA)
            with urllib.request.urlopen(req, timeout=150) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            wait = PAUSE * (2 ** attempt)
            print("      재시도 %d/%d (%s) %ds 대기" % (attempt + 1, MAXTRY, str(e)[:40], wait))
            time.sleep(wait)
    return None

def norm(el, cc):
    t = el.get("tags", {}) or {}
    if el.get("type") == "way":
        c = el.get("center") or {}
        lat, lng = c.get("lat"), c.get("lon")
    else:
        lat, lng = el.get("lat"), el.get("lon")
    if lat is None or lng is None:
        return None
    name = (t.get("name") or t.get("name:en") or t.get("name:ko") or "").strip()[:40]
    fee_raw = (t.get("fee") or "").lower()
    fee = 1 if fee_raw in ("yes", "1", "true") else 0
    oh = (t.get("opening_hours") or "").strip()
    h24 = 1 if oh in ("24/7", "24 hours", "Mo-Su 00:00-24:00") else 0
    acc = []
    if (t.get("wheelchair") or "").lower() == "yes":
        acc.append("휠체어")
    if (t.get("changing_table") or "").lower() == "yes":
        acc.append("기저귀")
    if (t.get("toilets:disposal") or "") == "flush":
        pass
    return {"lat": round(float(lat), 6), "lng": round(float(lng), 6),
            "name": name, "fee": fee, "h24": h24,
            "access": " ".join(acc), "ty": "pub", "cc": cc, "oh": oh[:40]}

def tiles(s, w, n, e):
    y = s
    while y < n:
        x = w
        while x < e:
            yield (y, x, min(y + TILE, n), min(x + TILE, e))
            x += TILE
        y += TILE

def collect(key):
    label, cc, tz, s, w, n, e = CITIES[key]
    path = os.path.join(OUT, "%s.json" % key)
    seen, rows, fails = set(), [], []
    if os.path.exists(path):                      # 중단 후 이어받기
        rows = json.load(open(path, encoding="utf-8"))
        seen = set((r["lat"], r["lng"]) for r in rows)
        print("  기존 %d건 이어받음" % len(rows))
    tl = list(tiles(s, w, n, e))
    print("  %s(%s) 타일 %d개" % (label, cc, len(tl)))
    for i, (a, b, c, d) in enumerate(tl, 1):
        r = fetch(Q % (a, b, c, d, a, b, c, d))
        if r is None:
            fails.append((a, b, c, d))
            print("    [%d/%d] 실패 — 나중에 재시도 (누적실패 %d), %ds 쿨다운"
                  % (i, len(tl), len(fails), COOLDOWN))
            sys.stdout.flush()
            time.sleep(COOLDOWN)
            continue
        got = 0
        for el in r.get("elements", []):
            o = norm(el, cc)
            if not o:
                continue
            k = (o["lat"], o["lng"])
            if k in seen:
                continue
            seen.add(k); rows.append(o); got += 1
        print("    [%d/%d] +%d (누적 %d)" % (i, len(tl), got, len(rows)))
        json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(PAUSE)
    # 실패 타일 재시도 (최대 3바퀴)
    for rnd in range(3):
        if not fails:
            break
        print("  실패 타일 재시도 %d바퀴 (%d개)" % (rnd + 1, len(fails)))
        retry, fails = fails, []
        for (a, b, c, d) in retry:
            r = fetch(Q % (a, b, c, d, a, b, c, d))
            if r is None:
                fails.append((a, b, c, d)); time.sleep(COOLDOWN); continue
            got = 0
            for el in r.get("elements", []):
                o = norm(el, cc)
                if not o:
                    continue
                k = (o["lat"], o["lng"])
                if k in seen:
                    continue
                seen.add(k); rows.append(o); got += 1
            print("    재시도 +%d (누적 %d)" % (got, len(rows)))
            json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
            time.sleep(PAUSE)

    meta = {"key": key, "label": label, "cc": cc, "tz": tz, "failed_tiles": len(fails),
            "bbox": [s, w, n, e], "count": len(rows), "built": time.strftime("%Y-%m-%d")}
    json.dump(meta, open(os.path.join(OUT, "%s.meta.json" % key), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("  => %s.json  %d건" % (key, len(rows)))
    return len(rows)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if "--list" in sys.argv:
        for k, v in CITIES.items():
            print("  %-11s %s (%s)" % (k, v[0], v[1]))
        raise SystemExit
    keys = [a for a in sys.argv[1:] if a in CITIES] or list(CITIES)
    tot = 0
    for k in keys:
        print("=== %s" % k)
        tot += collect(k)
    print("총 %d건 / %d개 도시 -> %s/" % (tot, len(keys), OUT))
