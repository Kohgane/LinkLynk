# -*- coding: utf-8 -*-
"""돼지레이다 예비 경로 — 브리가네(블루호스트)가 막혀도 렌더 안에서 바로 실존 가게 후보를 긁는다.
국내: 네이버 지역검색(지도 등록 가게) + 블로그 후기 발췌(체험단·협찬 글 제외)
해외: 오픈스트리트맵(노미나팀) 식당 + 한국인 블로그 후기 발췌
키는 렌더 환경변수 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 만 쓴다."""
import os, re, json, time, urllib.request, urllib.parse, urllib.error
from concurrent.futures import ThreadPoolExecutor

AD = re.compile(r'체험단|협찬|원고료|소정의|제공받아|지원받아|업체로부터')
CHAIN = re.compile(r'(맥도날드|버거킹|롯데리아|KFC|스타벅스|이디야|투썸|파리바게뜨|뚜레쥬르|본죽|김밥천국|맘스터치|서브웨이|도미노|피자헛|교촌|BBQ|bhc|굽네|'
                   r'McDonald|Burger King|Starbucks|Subway|Domino|Pizza Hut|Hooters|Costa|Luckin|瑞幸|麦当劳|肯德基|星巴克|必胜客|汉堡王|德克士|Tim Hortons|Shake Shack|Wagas)', re.I)
FOODK = {'국밥': '국밥', '고기': '고기집', '회': '횟집', '면': '칼국수', '백반': '백반', '분식': '분식', '중식': '중국집', '빵': '빵집'}
NUA = {'User-Agent': 'DwaejiRadar/1.0 (+https://apps.kohganemultishop.org/dwaeji)'}


def _strip(s):
    return re.sub(r'<[^>]+>|&[a-z#0-9]+;', '', s or '').strip()


DIAG = {}
import threading as _th
_RL, _RL_T = _th.Lock(), [0.0]
_KEYS = {'ok': None, 'at': 0}


def _key_pool():
    """검색 API 키 후보: 전용 환경변수 → 로그인용 환경변수 → 회원이 저장해 둔 네이버 키(암호화 저장분)."""
    pool = []
    for a, b in (('NAVER_SEARCH_ID', 'NAVER_SEARCH_SECRET'), ('NAVER_CLIENT_ID', 'NAVER_CLIENT_SECRET')):
        if os.environ.get(a) and os.environ.get(b):
            pool.append((os.environ[a], os.environ[b], 'env:' + a))
    try:
        import store
        rows = store._q("SELECT id FROM linklynk_users WHERE naver_id_enc IS NOT NULL LIMIT 8", (), fetch="all") or []
        for r in rows:
            k = store.get_naver_keys(r.get('id') if isinstance(r, dict) else r[0])
            if k:
                pool.append((k['client_id'], k['client_secret'], 'user'))
    except Exception as e:
        DIAG['store'] = type(e).__name__
    return pool


def _naver_raw(kind, q, n, cid, csec):
    rq = urllib.request.Request('https://openapi.naver.com/v1/search/%s.json?display=%d&query=%s' % (kind, n, urllib.parse.quote(q)),
                                headers={'X-Naver-Client-Id': cid, 'X-Naver-Client-Secret': csec})
    for att in range(3):
        with _RL:                                      # 네이버 검색 API는 초당 10건 — 몰아 쏘면 429로 후기가 통째로 빈다
            w = _RL_T[0] + 0.12 - time.time()
            if w > 0:
                time.sleep(w)
            _RL_T[0] = time.time()
        try:
            return json.load(urllib.request.urlopen(rq, timeout=6)).get('items', [])
        except urllib.error.HTTPError as e:
            if e.code != 429 or att == 2:
                raise
            DIAG['429'] = DIAG.get('429', 0) + 1
            time.sleep(0.6 * (att + 1))


def _pick_key():
    if _KEYS['ok'] and time.time() - _KEYS['at'] < 3600:
        return _KEYS['ok']
    tried = []
    for cid, csec, src in _key_pool():
        try:
            _naver_raw('local', '서울 맛집', 1, cid, csec)
            _KEYS.update(ok=(cid, csec), at=time.time())
            DIAG['key'] = src
            DIAG['tried'] = tried
            return _KEYS['ok']
        except urllib.error.HTTPError as e:
            tried.append('%s:%s' % (src, e.code))
        except Exception as e:
            tried.append('%s:%s' % (src, type(e).__name__))
    DIAG['key'] = None
    DIAG['tried'] = tried
    return None


def _naver(kind, q, n=5):
    k = _pick_key()
    if not k:
        raise RuntimeError('no naver search key')
    return _naver_raw(kind, q, n, k[0], k[1])


def diag():
    _pick_key()
    return dict(DIAG)


def _nom(path, params, t=8):
    u = 'https://nominatim.openstreetmap.org/' + path + '?' + urllib.parse.urlencode(params)
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=NUA), timeout=t))


def _in_kr(lat, lng):
    return 33.0 <= lat <= 38.7 and 124.5 <= lng <= 131.9


def _reviews(names, area):
    """가게 이름(들)로 블로그를 찾아, 그 가게 얘기이면서 먹은 얘기인 발췌만 최대 4개."""
    its = []
    for nm in [x for x in names if x][:2]:
        try:
            its += _naver('blog', '%s %s' % (area, nm), 10)
        except Exception:
            pass
    out, seen = [], set()
    keys = [re.sub(r'\s', '', k)[:5].lower() for k in names if k]
    for it in its:
        d, t = _strip(it.get('description')), _strip(it.get('title'))
        if len(d) < 30 or d[:40] in seen or AD.search(d + t):
            continue
        if keys and not any(k in re.sub(r'\s', '', d + t).lower() for k in keys):
            continue
        if not re.search(r'맛|메뉴|먹|식당|국물|고기|면|가격|원|위안|엔|웨이팅|주문', d):
            continue
        seen.add(d[:40]); out.append(d[:170])
        if len(out) >= 4:
            break
    return out


def _kr(region, food):
    toks = [t for t in re.split(r'\s+', region) if len(t) >= 2]
    fk = next((v for k, v in FOODK.items() if k in (food or '')), '')
    qs = ['%s %s' % (region, x) for x in ([fk + ' 맛집', fk + ' 노포', fk] if fk else []) + ['맛집', '노포', '현지인 맛집', '오래된 식당', '한식', '밥집']]
    rows, seen = [], set()

    def one(q):
        try:
            return _naver('local', q, 5)
        except Exception:
            return []
    with ThreadPoolExecutor(8) as ex:
        for res in ex.map(one, qs[:9]):
            for r in res:
                t = _strip(r.get('title')); road = r.get('roadAddress') or r.get('address') or ''
                if not t or t in seen or CHAIN.search(t):
                    continue
                if toks and not any(k in road for k in toks):
                    continue
                cat = r.get('category') or ''
                if re.search(r'카페|커피|술집|호프|바\b', cat) and '빵' not in (food or ''):
                    continue
                seen.add(t)
                rows.append({'title': t, 'road': road, 'cat': cat, 'cc': ''})
    area = ' '.join(toks[-2:]) if toks else region     # '서울 종로'처럼 시+동네 — 첫 토큰(서울)만 쓰면 후기가 다른 동네로 샌다
    with ThreadPoolExecutor(12) as ex:
        revs = list(ex.map(lambda c: _reviews([c['title']], area), rows[:16]))
    for c, rv in zip(rows, revs):
        c['rev'] = rv
    rows = rows[:16]
    rows.sort(key=lambda c: -len(c.get('rev') or []))
    return rows


def _glob(region, food, lat, lng):
    if lat is None:
        try:
            g = _nom('search', {'q': region, 'format': 'jsonv2', 'limit': 1, 'accept-language': 'ko'})
            if not g:
                return []
            lat, lng = float(g[0]['lat']), float(g[0]['lon'])
        except Exception:
            return []
    city, cc = region, ''
    try:
        a = _nom('reverse', {'lat': lat, 'lon': lng, 'format': 'jsonv2', 'zoom': 10, 'accept-language': 'ko'}).get('address') or {}
        cc = (a.get('country_code') or '').upper()
        city = re.sub(r'(특별시|광역시|시|성)$', '', a.get('city') or a.get('state') or region) or region
    except Exception:
        pass
    am = 'cafe' if '빵' in (food or '') else 'restaurant'
    rows, seen = [], set()
    for span in (0.015, 0.03):
        vb = '%f,%f,%f,%f' % (lng - span, lat + span, lng + span, lat - span)
        try:
            rs = _nom('search', {'format': 'jsonv2', 'amenity': am, 'viewbox': vb, 'bounded': 1, 'limit': 50,
                                 'extratags': 1, 'namedetails': 1, 'addressdetails': 1, 'accept-language': 'ko'})
        except Exception:
            rs = []
        for r in rs:
            nd = r.get('namedetails') or {}; ex = r.get('extratags') or {}
            nm = nd.get('name') or r.get('name') or ''
            if not nm or nm in seen or ex.get('brand') or CHAIN.search(nm + ' ' + (nd.get('name:en') or '')):
                continue
            seen.add(nm)
            ad = r.get('address') or {}
            rows.append({'title': nd.get('name:ko') or nm, 'local': nm, 'ko': nd.get('name:ko') or '', 'en': nd.get('name:en') or '',
                         'road': ' '.join(x for x in [ad.get('road'), ad.get('house_number'), ad.get('suburb')] if x),
                         'cat': (ex.get('cuisine') or am).replace(';', ', '), 'oh': ex.get('opening_hours', ''),
                         'lat': float(r['lat']), 'lng': float(r['lon']), 'cc': cc})
        if len(rows) >= 12:
            break
    rows = rows[:24]
    with ThreadPoolExecutor(12) as ex:
        revs = list(ex.map(lambda c: _reviews([c['ko'], c['en'], c['local']], city), rows))
    for c, rv in zip(rows, revs):
        c['rev'] = rv or ['(한국어 후기 없음 — 지도 정보: %s%s)' % (c['cat'], (' · 영업 ' + c['oh']) if c['oh'] else '')]
    rows.sort(key=lambda c: c['rev'][0].startswith('('))
    return rows[:16]


def discover(region, food='', lat=None, lng=None):
    t0 = time.time()
    if lat is not None and not _in_kr(lat, lng):
        return {'ok': True, 'cands': _glob(region, food, lat, lng)}
    rows = _kr(region, food)
    if len(rows) < 3 and lat is None and time.time() - t0 < 6:
        g = _glob(region, food, None, None)
        if len(g) >= 3:
            rows = g
    return {'ok': True, 'cands': rows}


def verify(picks, region=''):
    """AI가 낸 가게 이름을 네이버 지역검색으로 실존·지역 확인. 키가 없으면 None(확인 없이 보여 준다)."""
    if not _pick_key():
        return None
    toks = [t for t in re.split(r'\s+', region or '') if len(t) >= 2]
    nz = lambda s: re.sub(r'[\s·\-_.,()]|본점$', '', _strip(s or '')).lower()

    def one(ip):
        i, p = ip
        nm = str(p.get('name') or '').split('(')[0].strip()
        if not nm:
            return None
        try:
            items = _naver('local', '%s %s' % (region, nm), 5)
        except Exception:
            return None
        k = nz(nm)
        for it in items:
            t = _strip(it.get('title')); road = it.get('roadAddress') or it.get('address') or ''
            if toks and not any(x in road for x in toks):
                continue
            if k and (k in nz(t) or nz(t) in k):
                return {'i': i, 'title': t, 'road': road}
        return None
    with ThreadPoolExecutor(8) as ex:
        res = [r for r in ex.map(one, list(enumerate(picks))) if r]
    return {r['i']: r for r in res}
