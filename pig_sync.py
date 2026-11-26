"""돼지레이다 — 손님이 지도 앱에 저장해 둔 맛집을 공유 링크로 받아 취향을 뽑는다.
네이버: 저장 리스트 공유(naver.me → /favorite/myPlace/folder/<id>) 전부, 또는 가게 한 곳 공유(pinId).
카카오·구글: 공유 링크를 따라가 가게 이름·좌표를 최대한 건진다. 서버에는 저장 안 함(취향은 손님 휴대폰에만)."""
import json, re, threading, time, urllib.parse, urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
_CAT = {}          # 네이버 업종코드(끝자리) → 업종 이름 (모든 손님 공용 캐시)
_LK = threading.Lock()


class _NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def _get(url, ref=None, timeout=12, follow=True):
    h = {"User-Agent": UA}
    if ref:
        h["Referer"] = ref
    rq = urllib.request.Request(url, headers=h)
    op = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedir)
    try:
        r = op.open(rq, timeout=timeout)
        return r.geturl(), r.read()
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return e.headers.get("Location", ""), b""
        raise


def _resolve(url, hops=4):
    for _ in range(hops):
        if not re.match(r"https?://(naver\.me|kko\.to|kakaomap\.page\.link|maps\.app\.goo\.gl|goo\.gl)/", url):
            return url
        nxt, _b = _get(url, follow=False)
        if not nxt or nxt == url:
            return url
        url = urllib.parse.urljoin(url, nxt)
    return url


def _naver_cat(sid):
    try:
        _u, b = _get("https://map.naver.com/p/api/place/summary/%s" % sid, ref="https://map.naver.com/", timeout=8)
        d = json.loads(b)["data"]["placeDetail"]
        c = d.get("category") or {}
        return c.get("category") or "", c.get("categoryCodeList") or [], d
    except Exception:
        return "", [], {}


def _naver_folder(fid):
    _u, b = _get("https://pages.map.naver.com/save-pages/api/maps-bookmark/v3/shares/%s/bookmarks?start=0&limit=5000&sort=lastUseTime" % fid,
                 ref="https://map.naver.com/", timeout=15)
    d = json.loads(b)
    rows = [x for x in d.get("bookmarkList") or [] if x.get("available", True)]
    # 업종 이름: 같은 업종코드는 한 번만 물어본다(코드 하나에 대표 가게 하나)
    rep = {}
    for x in rows:
        cp = x.get("cidPath") or []
        if cp and cp[-1] not in _CAT and cp[-1] not in rep and x.get("sid"):
            rep[cp[-1]] = x["sid"]
    todo = list(rep.items())[:60]
    if todo:
        with ThreadPoolExecutor(8) as ex:
            for (code, _sid), (nm, _cl, _d) in zip(todo, ex.map(lambda t: _naver_cat(t[1]), todo)):
                if nm:
                    with _LK:
                        _CAT[code] = nm
    out = []
    for x in rows:
        cp = x.get("cidPath") or []
        cat = _CAT.get(cp[-1]) if cp else None
        out.append({"n": x.get("displayName") or x.get("name") or "", "lat": x.get("py"), "lng": x.get("px"),
                    "c": cat or x.get("mcidName") or "", "k": x.get("mcidName") or "", "a": x.get("address") or "",
                    "m": (x.get("memo") or "")[:60]})
    return (d.get("folder") or {}).get("name") or "", out


def _naver_one(sid, q):
    nm, _cl, d = _naver_cat(sid)
    co = d.get("coordinate") or {}
    return [{"n": d.get("name") or q.get("title", [""])[0], "lat": co.get("latitude") or float(q.get("lat", [0])[0] or 0),
             "lng": co.get("longitude") or float(q.get("lng", [0])[0] or 0), "c": nm, "k": "음식점",
             "a": (d.get("address") or {}).get("roadAddress") or "", "m": ""}]


def _generic(url):
    """카카오·구글 공유: 페이지 제목/좌표만이라도 건진다."""
    u, b = _get(url, timeout=12)
    t = b.decode("utf-8", "ignore")
    title = (re.search(r'<meta property="og:title" content="([^"]+)"', t) or re.search(r"<title>([^<]+)", t) or [None, ""])[1]
    m = re.search(r"(-?\d{1,2}\.\d{4,})[,%2C]+(-?\d{2,3}\.\d{4,})", urllib.parse.unquote(u + " " + t[:20000]))
    if not title:
        return []
    return [{"n": re.sub(r"\s*[-|:]\s*(카카오맵|Google 지도|Google Maps).*$", "", title).strip(), "lat": float(m.group(1)) if m else None,
             "lng": float(m.group(2)) if m else None, "c": "", "k": "음식점", "a": "", "m": ""}]


def load(url):
    url = (url or "").strip()
    if not re.match(r"https?://", url):
        raise ValueError("링크를 붙여 주세요")
    real = _resolve(url)
    m = re.search(r"/favorite/(?:myPlace/)?folder/([0-9a-f]{16,})", real)
    if m:
        return _naver_folder(m.group(1))
    q = urllib.parse.parse_qs(urllib.parse.urlparse(real).query)
    if "map.naver.com" in real and q.get("pinId"):
        return "", _naver_one(q["pinId"][0], q)
    m = re.search(r"place(?:\.naver\.com/\w+|/)/?(\d{5,})", real) if "naver" in real else None
    if m:
        return "", _naver_one(m.group(1), {})
    return "", _generic(real)


_SKIP = {"음식점", "", "기타", "생활/문화", "쇼핑"}


def profile(places):
    """취향 요약 — 업종 상위, 자주 가는 동네, 술집·카페 비중."""
    cats = Counter(p["c"] for p in places if p["c"] not in _SKIP)
    kinds = Counter(p["k"] for p in places)
    areas = Counter(" ".join(p["a"].split()[:2]) for p in places if p.get("a"))
    n = max(1, len(places))
    return {"top": cats.most_common(8), "areas": areas.most_common(5),
            "bar": round(kinds.get("BAR", 0) / n, 2), "cafe": round(kinds.get("카페", 0) / n, 2), "n": len(places)}
