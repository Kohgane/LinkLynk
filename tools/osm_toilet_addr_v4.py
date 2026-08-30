# -*- coding: utf-8 -*-
"""가라고 세계화 — 주소 보강 v4 (Nominatim 역지오코딩, Python 3.9 호환)
   name / near 로 식별 안 되는 화장실에 '도로명 · 동네' 를 채운다.
   Nominatim 공용 서버 규칙: 초당 1회. 어기면 IP 차단.
   사용: python3 osm_toilet_addr_v4.py [도시키 ...]
        python3 osm_toilet_addr_v4.py --stat
"""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "toilets_world")
UA = "GottaGo/1.0 (kohgane; +https://linklynk.onrender.com/gottago)"
RATE = 1.6          # 초당 1회 규칙 + 여유
MAXFAIL = 8         # 연속 실패 이만큼이면 중단(차단 방지)


def rev(lat, lng):
    url = ("https://nominatim.openstreetmap.org/reverse?format=jsonv2"
           "&lat=%f&lon=%f&zoom=18&addressdetails=1&accept-language=ko,en") % (lat, lng)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    r = urllib.request.urlopen(req, timeout=30)
    return json.loads(r.read().decode("utf-8"))


def compose(d):
    a = d.get("address") or {}
    road = (a.get("road") or a.get("pedestrian") or a.get("footway")
            or a.get("path") or a.get("square") or "")
    area = (a.get("quarter") or a.get("neighbourhood") or a.get("suburb")
            or a.get("city_district") or a.get("village") or a.get("town") or "")
    nm = d.get("name") or ""
    if nm and nm != road:
        head = nm
    else:
        head = road
    if head and area:
        return "%s · %s" % (head[:30], area[:22])
    return (head or area)[:52]


def run(key):
    dp = os.path.join(DIR, "%s.json" % key)
    if not os.path.exists(dp):
        print("  없음: %s" % key); return
    rows = json.load(open(dp, encoding="utf-8"))
    todo = [r for r in rows
            if not r.get("name") and not r.get("near") and r.get("addr") is None]
    print("  %s %d건 중 대상 %d건 (예상 %d분)" % (key, len(rows), len(todo), int(len(todo) * RATE / 60) + 1))
    sys.stdout.flush()
    fail = 0
    for i, r in enumerate(todo, 1):
        try:
            r["addr"] = compose(rev(r["lat"], r["lng"]))
            fail = 0
        except Exception as e:
            msg = str(e)
            if "429" in msg or "403" in msg:
                fail += 1
                back = min(60 * fail, 600)
                print("    레이트리밋 %d회 — %ds 대기 후 같은 건 재시도" % (fail, back))
                sys.stdout.flush()
                if fail >= MAXFAIL:
                    print("    반복 차단 — 중단"); break
                time.sleep(back)
                try:
                    r["addr"] = compose(rev(r["lat"], r["lng"]))
                    fail = 0
                except Exception:
                    pass
                time.sleep(RATE)
                continue
            fail += 1
            print("    실패 %d회 (%s)" % (fail, msg[:34]))
            sys.stdout.flush()
            if fail >= MAXFAIL:
                print("    연속 실패 %d회 — 중단" % MAXFAIL); break
            time.sleep(8)
            continue
        if i % 25 == 0 or i == len(todo):
            json.dump(rows, open(dp, "w", encoding="utf-8"), ensure_ascii=False)
            print("    [%d/%d] %s" % (i, len(todo), r["addr"][:44]))
            sys.stdout.flush()
        time.sleep(RATE)
    json.dump(rows, open(dp, "w", encoding="utf-8"), ensure_ascii=False)
    ok = sum(1 for x in rows if x.get("name") or x.get("near") or x.get("addr"))
    print("  => %s 식별 %d/%d (%d%%)" % (key, ok, len(rows), 100 * ok // max(len(rows), 1)))
    sys.stdout.flush()


def stat():
    tot = idn = 0
    for f in sorted(os.listdir(DIR)):
        if not f.endswith(".json") or f.endswith(".meta.json"):
            continue
        rows = json.load(open(os.path.join(DIR, f), encoding="utf-8"))
        a = sum(1 for r in rows if r.get("name") or r.get("near") or r.get("addr"))
        tot += len(rows); idn += a
        print("  %-12s %5d건  식별 %5d (%d%%)" % (f[:-5], len(rows), a, 100 * a // max(len(rows), 1)))
    print("  합계 %d건 · 식별 %d (%d%%)" % (tot, idn, 100 * idn // max(tot, 1)))


if __name__ == "__main__":
    if "--stat" in sys.argv:
        stat(); sys.exit(0)
    keys = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not keys:
        keys = sorted(f[:-5] for f in os.listdir(DIR)
                      if f.endswith(".json") and not f.endswith(".meta.json"))
    for k in keys:
        print("=== %s" % k); sys.stdout.flush()
        run(k)
    stat()
