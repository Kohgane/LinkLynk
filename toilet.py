# -*- coding: utf-8 -*-
"""급해! — 전국 화장실 근접검색 (OSM 스냅샷, 서버 메모리 상주)"""
import json, math, os

_DATA = None

def _load():
    global _DATA
    if _DATA is None:
        p = os.path.join(os.path.dirname(__file__), "toilets_kr.json")
        _DATA = json.load(open(p, encoding="utf-8"))
    return _DATA

def near(lat, lng, n=15):
    data = _load()
    coslat = math.cos(math.radians(lat))
    out = []
    for t in data:
        dy = (t["lat"] - lat) * 111320.0
        dx = (t["lng"] - lng) * 111320.0 * coslat
        d = math.hypot(dx, dy)
        if d < 30000:
            out.append((d, t))
    out.sort(key=lambda x: x[0])
    res = []
    for d, t in out[:n]:
        res.append({**t, "dist": int(d), "walk": max(1, int(d / 67))})
    return res


def near_v2(lat, lng, n=15):
    """공중·역·마트는 확실 소스라 소폭 가중(체감거리 -15%), 나머지 순수 거리순."""
    data = _load()
    coslat = math.cos(math.radians(lat))
    out = []
    for t in data:
        dy = (t["lat"] - lat) * 111320.0
        dx = (t["lng"] - lng) * 111320.0 * coslat
        d = math.hypot(dx, dy)
        if d < 30000:
            w = d * (1.0 if t.get("ty") in ("cafe", "ff") else 0.85)
            out.append((w, d, t))
    out.sort(key=lambda x: x[0])
    res = []
    for w, d, t in out[:n]:
        res.append({**t, "dist": int(d), "walk": max(1, int(d / 67))})
    return res
