# -*- coding: utf-8 -*-
"""선물레이더 — 앱인토스 미니앱용 선물 큐레이션 엔진.
받는 사람+예산+취향 -> LLM이 '뻔하지 않은' 선물 방향 3개 -> 쿠팡 실상품+딥링크 매핑."""
import os
import re
import json
import time

from core import llm_chat, scrub_garbled, _parse_json_out, CoupangPartners

_SYS = (
    "너는 취향이 확고한 선물 큐레이터다. 힙하면서 고전적인 것, 유니크하면서 우아한 것 — "
    "'아는 사람만 아는' 물건을 고른다.\n"
    "\n"
    "★금지: 기프티콘·꽃다발·텀블러·무드등·스마트워치·전기면도기·커피머신·핸드크림 기본템·"
    "디퓨저 기본템·양말·머그컵·에어팟 케이스 등 대형마트 감성 전부. "
    "식재료·소모품 원물(밀가루·설탕·버터·벌크 원두)도 금지 — 선물은 도구·기물·오브제·"
    "패키지가 완성된 기호품(틴케이스 차, 초콜릿 등)으로.\n"
    "\n"
    "★★최우선 규칙 — 핵심 단서: 받는 사람 설명에서 가장 중요한 특성(고민·니즈·취향·상황)을 "
    "먼저 한 단어로 파악하고, 세 방향 전부 그 특성에 직접 답해야 한다. 특성과 무관한 물건은 "
    "아무리 세련돼도 탈락. 예: '땀 많은 남자친구' -> 핵심은 '땀' -> 쿨링·흡한속건·산뜻함 계열"
    "(예: 산타마리아노벨라 탈크 파우더, 프로라소 쿨링 애프터셰이브, 리넨 셔츠)이지, "
    "치약·휴지·일반 면도기가 아니다. reason에 왜 그 특성에 맞는지 반드시 연결해라.\n"
    "\n"
    "★지향: 헤리티지 브랜드(수십~백년), 장인·아날로그, 니치·소수 취향, 실물 질감. 감각 사전 —\n"
    "· 문구·필기: 카웨코, 라미, 펠리칸, 파버카스텔, 카렌다쉬, 로트링, 스테들러 마스, "
    "미도리 MD, 트래블러스노트, 블랙윙, 팔로미노, 라이프(LIFE) 노트, 츠바메 노트, 미츠비시 하이유니\n"
    "· 홈카페·차: 케멕스, 하리오, 킨토, 칼리타, 타임모어, 펠로우, 빌레로이앤보흐, 로얄코펜하겐, "
    "쿠스미티, 포트넘앤메이슨, 마리아쥬프레르, TWG, 로네펠트\n"
    "· 향·공간: 파피에르 다르메니, 산타마리아노벨라, 그랑핸드, 오드뮤제, 탬버린즈, 논픽션, "
    "아피프, 사티아, 이솝 아님(뻔함)\n"
    "· 주방·리빙: 이딸라, 아라비아핀란드, 카이보이슨, 오피넬, 조지루시, 팔라스, 야마자키, "
    "포그리넨워크, 라푸안칸쿠리트, HAY, 무토, 아스티에 드 빌라트\n"
    "· 주류·잔: 리델, 자페라노, 슈피겔라우, 우수이, 히비키·산토리 온더락, 스가하라 글라스\n"
    "· EDC·가죽: 오피넬, 빅토리녹스, 레더맨, 일 부세토, 에트비너, 트래블러스 컴퍼니, 오르빗키\n"
    "· 오디오·아날로그: 티볼리 오디오, 오디오테크니카 턴테이블, 젠하이저, 야마하 클래식, 크로슬리\n"
    "· 아웃도어 클래식: 스탠리 클래식, 페트로막스, 콜맨 빈티지, 스노우피크 티타늄, 트란지아\n"
    "· 바디·그루밍: 프로라소, 뮬 면도기, 켄트 브러시, 마비스 치약, 클라우스포르토\n"
    "· 보드게임·취미: 아즐, 카탄, 루빅스 스피드큐브, 곤(GAN), 버메일 타로\n"
    "(★사전은 '결'의 예시일 뿐 장바구니가 아니다 — 핵심 단서와 무관한 사전 브랜드를 "
    "꺼내는 것 금지. 매 추천에서 최소 1개는 사전 밖 브랜드를 같은 결로 발굴하고, "
    "매번 같은 브랜드 반복 금지.)\n"
    "\n"
    "★keyword 규칙: '브랜드명+품목명' 2~3단어, 쿠팡 검색창에 그대로 칠 법한 명사형만. "
    "수식어·형용사·감성 표현 금지(예: O '카웨코 스포츠 만년필' / X '무심한 가죽 커버 노트').\n"
    "★reason 규칙: 친구가 귀띔하는 한 줄. 그 브랜드·물건의 역사·출신·디테일 한 조각 필수 "
    "('1902년부터 프랑스 농부들이...'). 과장·강권 금지, '고급스러운·프리미엄' 형용사 금지.\n"
    "★정합 규칙: reason은 반드시 keyword의 그 브랜드·그 물건 얘기여야 한다. 다른 브랜드 "
    "스토리를 갖다 붙이면 안 된다.\n"
    "출력은 JSON만."
)


import urllib.request
import urllib.parse


_OWN_MALLS = ("나의 코스모스", "나의코스모스", "셰고가")   # 자사 스토어 — 커미션이 아니라 마진 전체


_OWN_CACHE = {"at": 0, "rows": []}


def _own_index_search(toks, lo, hi, limit=3):
    """자사 상품 인덱스(Supabase) 토큰 매칭 — 10분 캐시. 마진 전체가 걸린 최우선 소스."""
    if not toks:
        return []
    try:
        import store as _store
        now = time.time()
        if now - _OWN_CACHE["at"] > 600:
            rows = _store._q(
                "SELECT store,name,price,image,link FROM linklynk_gift_own", fetch="all") or []
            _OWN_CACHE.update(at=now, rows=rows)
        out = []
        brand = toks[0]   # ★자연스러움 가드: 추천된 그 브랜드를 실제로 팔 때만 등장.
        for r in _OWN_CACHE["rows"]:
            nm = r.get("name") or ""
            if brand not in nm:      # 일반 토큰 매칭으로 끼어들기 금지 — 어색하면 안 나온다
                continue
            pr = r.get("price")
            if pr and not (lo <= pr <= hi):
                continue
            out.append({"name": nm[:60], "price": pr, "image": r.get("image"),
                        "link": r.get("link"), "own": True})
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []


def _naver_shop_search(kw, limit=8):
    """네이버 쇼핑 검색 API (openapi.naver.com, IP 제한 없음).
    NAVER_SEARCH_ID/SECRET 없으면 빈 목록 — 쿠팡 단독으로 동작."""
    nid = os.environ.get("NAVER_SEARCH_ID", "").strip()
    nsec = os.environ.get("NAVER_SEARCH_SECRET", "").strip()
    if not nid or not nsec:
        return []
    try:
        u = ("https://openapi.naver.com/v1/search/shop.json?query="
             + urllib.parse.quote(kw) + f"&display={limit}&sort=sim")
        req = urllib.request.Request(u, headers={
            "X-Naver-Client-Id": nid, "X-Naver-Client-Secret": nsec})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        out = []
        for it in data.get("items", []):
            name = re.sub(r"</?b>", "", it.get("title") or "")[:60]
            mall = (it.get("mallName") or "").strip()
            out.append({
                "name": name,
                "price": int(it.get("lprice") or 0) or None,
                "image": it.get("image"),
                "link": it.get("link"),
                "own": any(m in mall for m in _OWN_MALLS),
                "mall": mall,
            })
        return out
    except Exception:
        return []


_BUDGET_RANGES = {
    "1만원 이하": (3000, 12000),
    "1~3만원": (8000, 36000),
    "3~5만원": (20000, 60000),
    "5~10만원": (35000, 120000),
    "10~20만원": (70000, 240000),
    "20~50만원": (140000, 600000),
    "50만원 이상": (350000, 99999999),
}


def _budget_range(budget):
    """예산 문자열 -> (하한, 상한) KRW. 하한은 예산의 ~70% (너무 싼 건 선물 격 훼손),
    상한은 ~120% (약간 초과는 허용)."""
    for k, v in _BUDGET_RANGES.items():
        if k in (budget or ""):
            return v
    return (0, 99999999)


def _dedupe_products(items):
    """같은 상품의 색상·옵션 변형 중복 제거 — 이름 앞 12자가 같으면 한 개만."""
    seen, out = set(), []
    for it in items:
        key = (it.get("name") or "")[:12]
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def recommend(api_key, who, budget, taste, exclude=None):
    ex = ""
    if exclude:
        ex = "\n★이전에 추천한 방향이니 겹치지 않게 완전히 다른 계열로: " + ", ".join(exclude[:12])
    user = (
        f"받는 사람: {who or '특정하지 않음 — 누구에게든 두루 통하는 세련된 선물로'}\n"
        f"예산: {budget}\n취향 힌트: {taste or '없음'}{ex}\n\n"
        "먼저 받는 사람의 핵심 단서(고민·니즈·취향) 하나를 파악하고, "
        "그 단서에 직접 답하는 선물 방향 3개를 서로 완전히 다른 계열로.\n"
        "★keyword의 상품 실구매가가 반드시 예산 범위 안이어야 한다. 저 예산이면 그 값어치의 물건을 — "
        "20만원대 예산에 만원짜리 소품 금지, 3만원대 예산에 30만원짜리 금지.\n"
        "★쿠팡에서 실제 판매될 법한 키워드만 (에르메스·까르띠에급 하이엔드 명품 주얼리는 쿠팡에 없다 — "
        "그 예산대라면 리델 잔 세트, 이딸라 풀세트, 빈티지 그릇, 니치 향수, 만년필, 오디오 같은 걸로).\n"
        "angle(계열 이름)도 세련되게 — '감각적 소품' 같은 밋밋한 말 대신 "
        "그 방향의 매력을 담은 짧은 이름(예: '백년 된 물건의 힘', '책상 위의 의식', '아날로그 한 조각').\n"
        'JSON: {"picks":[{"keyword":"브랜드명+상품유형(2~4단어)","reason":"한 줄 이유","angle":"계열 이름"}x3]}'
    )
    r = llm_chat(api_key, _SYS, user, max_tokens=900)
    if not r.get("ok"):
        return {"ok": False, "error": "추천 생성 실패",
                "detail": str(r.get("error") or "")[:120] + " " + str(r.get("detail") or "")[:150]}
    try:
        picks = _parse_json_out(r["text"]).get("picks", [])[:3]
    except Exception:
        return {"ok": False, "error": "추천 형식 오류"}
    if not picks:
        return {"ok": False, "error": "추천이 비었어요"}
    used_model = r.get("model") or "?"

    # 쿠팡 실상품 매핑 (서버 파트너스 키)
    # Render엔 COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY 로 들어있음 — 양쪽 이름 모두 지원
    ck = os.environ.get("COUPANG_ACCESS_KEY", "") or os.environ.get("COUPANG_ACCESS", "")
    cs = os.environ.get("COUPANG_SECRET_KEY", "") or os.environ.get("COUPANG_SECRET", "")
    cp = CoupangPartners(ck, cs) if ck and cs else None

    _KW_STOP = {"세트", "선물", "추천", "제품", "용품", "아이템", "고급", "감성", "프리미엄"}

    def _kw_tokens(kw):
        return [w for w in re.split(r"\s+", kw) if len(w) >= 2 and w not in _KW_STOP]

    def _search_once(kw):
        found = cp.search_products(kw, limit=8) or []
        return _dedupe_products([{
            "name": f.get("name", "")[:60],
            "price": f.get("price"),
            "image": f.get("image"),
            "link": f.get("url"),   # 파트너스 검색 결과 URL은 이미 수익 트래킹 링크
        } for f in found])

    _lo, _hi = _budget_range(budget)

    def _price_ok_range(u, lo, hi):
        pr = u.get("price")
        try:
            pr = int(pr)
        except Exception:
            return False
        return lo <= pr <= hi

    def _price_ok(u):
        return _price_ok_range(u, _lo, _hi)

    def _relevant(items, toks):
        return [u for u in items if any(t in u["name"] for t in toks)] if toks else items

    def _fetch(kw):
        """멀티소스: 자사 스토어(마진 전체) > 쿠팡 브랜드 진품 > 쿠팡 일반.
        관련성(콜라·화장지 차단) + 가격대(예산 격 훼손 차단) 이중 검증은 전 소스 공통."""
        try:
            toks = _kw_tokens(kw)
            brand = toks[0] if toks else ""

            cp_items = _search_once(kw) if cp else []
            nv_items = _naver_shop_search(kw)
            rel_cp = _relevant(cp_items, toks)
            rel_nv = _relevant(nv_items, toks)
            # 전멸이면 앞 2단어 축약 재검색 (쿠팡만 — 네이버는 1차로 충분)
            if not rel_cp and cp and len(toks) > 2:
                rel_cp = _relevant(_search_once(" ".join(toks[:2])), toks[:2])

            wide_lo, wide_hi = int(_lo * 0.7), int(_hi * 1.4)
            picked = []

            # ⓪ 자사 상품 — 단, ★브랜드가 정확히 일치할 때만 최대 1개 (자연스러움 > 수익.
            # 어색한 끼워넣기는 '어떻게 알았지'를 '광고네'로 무너뜨린다)
            picked += _own_index_search(toks, wide_lo, wide_hi, limit=1)

            # ① 네이버 검색 own — 같은 원칙: 브랜드 토큰 일치분만
            if not picked:
                brand = toks[0] if toks else ""
                own = [u for u in rel_nv if u.get("own") and brand and brand in u["name"]
                       and _price_ok_range(u, wide_lo, wide_hi)]
                picked += own[:1]

            # ② 쿠팡 브랜드 진품 — 넓은 가격창 (선물은 브랜드 정합 > 엄격한 예산)
            if len(picked) < 3:
                bh = [u for u in rel_cp if brand and brand in u["name"]
                      and _price_ok_range(u, wide_lo, wide_hi)]
                picked += [u for u in bh if u not in picked][:3 - len(picked)]

            # ③ 쿠팡 일반 — ★토큰 2개 이상 일치만 (브랜드 없이 '파우더' 한 단어로
            # 로즈마리 요리 파우더가 끼는 것 차단. 1개 일치는 실격 -> 빈 결과가
            # 재추천 루프를 발동시켜 쿠팡에 실재하는 브랜드로 교체됨)
            if len(picked) < 3:
                def _score(u):
                    return sum(1 for t in toks if t in u["name"])
                need = 2 if len(toks) >= 2 else 1
                gen = [u for u in rel_cp
                       if _price_ok(u) and u not in picked and _score(u) >= need]
                picked += gen[:3 - len(picked)]


            # 내부 필드 정리
            for u in picked:
                u.pop("mall", None)
            return _dedupe_products(picked)[:3]
        except Exception:
            return []

    def _clean_kw(k):
        k = scrub_garbled(str(k or ""))
        k = re.sub(r"[\"'\u201c\u201d\u2018\u2019]|쿠팡", "", k)
        return re.sub(r"\s+", " ", k).strip()[:40]

    kws = [_clean_kw(p.get("keyword")) for p in picks]
    results = {}
    if cp:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = {kw: pool.submit(_fetch, kw) for kw in kws if kw}
            results = {kw: f.result() for kw, f in futs.items()}

    out = []
    for p, kw in zip(picks, kws):
        out.append({"keyword": kw,
                    "reason": scrub_garbled(str(p.get("reason") or ""))[:160],
                    "angle": scrub_garbled(str(p.get("angle") or ""))[:20],
                    "products": results.get(kw, [])})

    # ★재추천 루프: 상품 매칭 실패한 계열은 폴백(스토리-상품 모순의 원흉)이 아니라
    # LLM에게 되물어 '쿠팡에 실재하는 다른 브랜드'로 통째 교체 — 훅과 물건이 항상 일치.
    failed_idx = [i for i, o in enumerate(out) if not o["products"]]
    if failed_idx and cp:
        failed_kws = [out[i]["keyword"] for i in failed_idx]
        ok_kws = [o["keyword"] for o in out if o["products"]]
        user2 = (
            f"받는 사람: {who or '특정하지 않음'}\n예산: {budget}\n취향 힌트: {taste or '없음'}\n"
            f"다음 키워드는 쿠팡에 실재 상품이 없어 실패: {', '.join(failed_kws)}\n"
            f"이미 성공한 방향(겹치지 말 것): {', '.join(ok_kws) or '없음'}\n\n"
            f"실패분을 대체할 방향 {len(failed_idx)}개 — 같은 감각의 결이되 "
            "쿠팡에서 확실히 팔릴 대중 유통 브랜드로. keyword·reason 정합 규칙 동일.\n"
            '"JSON: {"picks":[{"keyword":"...","reason":"...","angle":"..."}]}"'
        )
        r2 = llm_chat(api_key, _SYS, user2, max_tokens=700)
        if r2.get("ok"):
            try:
                repl = _parse_json_out(r2["text"]).get("picks", [])[:len(failed_idx)]
            except Exception:
                repl = []
            for slot, p2 in zip(failed_idx, repl):
                kw2 = _clean_kw(p2.get("keyword"))
                prods2 = _fetch(kw2) if kw2 else []
                if prods2:
                    out[slot] = {"keyword": kw2,
                                 "reason": scrub_garbled(str(p2.get("reason") or ""))[:160],
                                 "angle": scrub_garbled(str(p2.get("angle") or ""))[:20],
                                 "products": prods2}
    return {"ok": True, "picks": out, "src": used_model,
            "coupang": bool(cp), "coupang_err": (cp.last_error if cp else "no_keys")}
