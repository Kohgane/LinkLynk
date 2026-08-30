# -*- coding: utf-8 -*-
"""가라고 세계화 — 이름 보강 패스 v3  (Python 3.9 호환)
   이미 수집된 toilets_world/<도시>.json 의 무명 화장실에
   주변 명명 POI를 붙여 "신주쿠역 부근" 형태의 위치 설명을 채운다.

   - 화장실을 다시 긁지 않는다. 타일 단위로 명명 POI만 받아 로컬 최근접 매칭
   - 원본 name 은 보존하고 별도 필드 near 에 넣는다 (되돌릴 수 있음)
   - 중단돼도 타일마다 저장 → 이어받기

   사용: python3 osm_toilet_name_v3.py [도시키 ...]     (생략시 전체)
        python3 osm_toilet_name_v3.py --stat            현황만
"""
import json, os, re, sys, time, math, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "toilets_world")
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]
UA = "GottaGo/1.0 (+https://linklynk.onrender.com/gottago)"
TILE = 0.05
PAD = 0.01          # POI는 타일보다 조금 넓게 (경계 밖 역까지 잡기)
PAUSE = 10
MAXTRY = 6
COOLDOWN = 300
MAXDIST = 250       # 이보다 멀면 안 붙인다

# POI 종류 -> 한국어 접미
KIND = {
    "station": "역", "park": "공원", "department_store": "백화점",
    "mall": "몰", "supermarket": "마트", "convenience": "편의점",
    "library": "도서관", "townhall": "시청", "hospital": "병원",
    "university": "대학", "museum": "박물관", "place_of_worship": "사원",
    "marketplace": "시장", "bus_station": "버스터미널", "attraction": "명소",
}

QPOI = """[out:json][timeout:90];
(
  node["name"]["railway"="station"](%f,%f,%f,%f);
  way["name"]["railway"="station"](%f,%f,%f,%f);
  node["name"]["public_transport"="station"](%f,%f,%f,%f);
  way["name"]["leisure"="park"](%f,%f,%f,%f);
  node["name"]["leisure"="park"](%f,%f,%f,%f);
  way["name"]["shop"~"department_store|mall|supermarket"](%f,%f,%f,%f);
  node["name"]["shop"~"department_store|mall|supermarket"](%f,%f,%f,%f);
  node["name"]["amenity"~"library|townhall|hospital|university|marketplace|bus_station"](%f,%f,%f,%f);
  way["name"]["amenity"~"library|townhall|hospital|university|marketplace|bus_station"](%f,%f,%f,%f);
  node["name"]["tourism"~"museum|attraction"](%f,%f,%f,%f);
  way["name"]["tourism"~"museum|attraction"](%f,%f,%f,%f);
);
out center tags;"""


def slots_free():
    try:
        req = urllib.request.Request("https://overpass-api.de/api/status")
        req.add_header("User-Agent", UA)
        txt = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        m = re.search(r"(\d+) slots available now", txt)
        if m:
            return int(m.group(1))
        m = re.search(r"in (\d+) seconds", txt)
        return -int(m.group(1)) if m else 0
    except Exception:
        return 1


def wait_slot(maxwait=240):
    t0 = time.time()
    while time.time() - t0 < maxwait:
        n = slots_free()
        if n > 0:
            return True
        time.sleep(10 if n == 0 else min(abs(n) + 2, 30))
    return False


def fetch(q):
    data = q.encode("utf-8")
    for attempt in range(MAXTRY):
        ep = MIRRORS[attempt % len(MIRRORS)]
        if "overpass-api.de" in ep:
            wait_slot()
        try:
            req = urllib.request.Request(ep, data=data)
            req.add_header("Content-Type", "text/plain; charset=utf-8")
            req.add_header("User-Agent", UA)
            r = urllib.request.urlopen(req, timeout=150)
            return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            w = PAUSE * (2 ** attempt)
            print("      재시도 %d/%d (%s) %ds" % (attempt + 1, MAXTRY, str(e)[:38], w))
            sys.stdout.flush()
            time.sleep(w)
    return None


def pt(e):
    if e.get("type") == "way":
        c = e.get("center") or {}
        return c.get("lat"), c.get("lon")
    return e.get("lat"), e.get("lon")


def kind_of(t):
    for k in ("railway", "public_transport"):
        if t.get(k) == "station":
            return "station"
    if t.get("leisure") == "park":
        return "park"
    if t.get("shop"):
        return t["shop"]
    if t.get("amenity"):
        return t["amenity"]
    if t.get("tourism"):
        return t["tourism"]
    return ""


def label(t):
    nm = (t.get("name:ko") or t.get("name:en") or t.get("name") or "").strip()
    if not nm:
        return ""
    suf = KIND.get(kind_of(t), "")
    if suf and not nm.endswith(suf):
        nm = nm + suf
    return nm[:34]


def tiles(s, w, n, e):
    out = []
    y = s
    while y < n:
        x = w
        while x < e:
            out.append((y, x, min(y + TILE, n), min(x + TILE, e)))
            x += TILE
        y += TILE
    return out


def enrich(key):
    mp = os.path.join(DIR, "%s.meta.json" % key)
    dp = os.path.join(DIR, "%s.json" % key)
    if not (os.path.exists(mp) and os.path.exists(dp)):
        print("  건너뜀 (수집 미완): %s" % key)
        return
    meta = json.load(open(mp, encoding="utf-8"))
    rows = json.load(open(dp, encoding="utf-8"))
    s, w, n, e = meta["bbox"]
    todo = [r for r in rows if not r.get("near")]
    print("  %s %d건 중 미보강 %d건" % (meta["label"], len(rows), len(todo)))
    if not todo:
        return
    sys.stdout.flush()
    tl = tiles(s, w, n, e)
    coslat = math.cos(math.radians((s + n) / 2))
    for i, (a, b, c, d) in enumerate(tl, 1):
        tgt = [r for r in rows
               if not r.get("near") and a <= r["lat"] < c and b <= r["lng"] < d]
        if not tgt:
            continue
        box = (a - PAD, b - PAD, c + PAD, d + PAD)
        q = QPOI % (box * 11)
        res = fetch(q)
        if res is None:
            print("    [%d/%d] 실패 %ds 쿨다운" % (i, len(tl), COOLDOWN))
            sys.stdout.flush()
            time.sleep(COOLDOWN)
            continue
        pois = []
        for el in res.get("elements", []):
            la, lo = pt(el)
            if la is None:
                continue
            lb = label(el.get("tags") or {})
            if lb:
                pois.append((la, lo, lb))
        hit = 0
        for r in tgt:
            best, bd = None, 1e9
            for la, lo, lb in pois:
                dy = (la - r["lat"]) * 111320.0
                dx = (lo - r["lng"]) * 111320.0 * coslat
                dd = math.hypot(dx, dy)
                if dd < bd:
                    bd, best = dd, lb
            if best and bd <= MAXDIST:
                r["near"] = "%s 부근" % best
                r["near_m"] = int(bd)
                hit += 1
            else:
                r["near"] = ""
        print("    [%d/%d] 대상 %d · POI %d · 매칭 %d" % (i, len(tl), len(tgt), len(pois), hit))
        sys.stdout.flush()
        json.dump(rows, open(dp, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(PAUSE)
    named = sum(1 for r in rows if r.get("name"))
    withnear = sum(1 for r in rows if r.get("near"))
    print("  => %s 이름 %d · 위치설명 %d / %d (%d%%)"
          % (key, named, withnear, len(rows), 100 * (named + withnear) // max(len(rows), 1)))
    sys.stdout.flush()


def stat():
    tot = idn = 0
    for f in sorted(os.listdir(DIR)):
        if not f.endswith(".json") or f.endswith(".meta.json"):
            continue
        rows = json.load(open(os.path.join(DIR, f), encoding="utf-8"))
        a = sum(1 for r in rows if r.get("name") or r.get("near"))
        tot += len(rows); idn += a
        print("  %-12s %5d건  식별가능 %5d (%d%%)"
              % (f[:-5], len(rows), a, 100 * a // max(len(rows), 1)))
    print("  합계 %d건 · 식별가능 %d (%d%%)" % (tot, idn, 100 * idn // max(tot, 1)))


if __name__ == "__main__":
    if "--stat" in sys.argv:
        stat(); sys.exit(0)
    keys = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not keys:
        keys = sorted(f[:-10] for f in os.listdir(DIR) if f.endswith(".meta.json"))
    for k in keys:
        print("=== %s" % k)
        sys.stdout.flush()
        enrich(k)
    stat()
