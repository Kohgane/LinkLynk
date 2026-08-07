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
    "★신체·외형 단서('키 작은', '왜소한', '손이 작은', '추위 잘 타는' 등)는 특별 취급: "
    "무시하지 말고, 그 특성 때문에 겪는 일상 속 불편·필요를 딱 한 걸음만 추론해 우아하게 "
    "해결하는 물건으로 답하라. 예: 키 작은 사람 -> 디자인 좋은 스텝스툴(비트라 울머 호커, "
    "알레시), 높은 수납을 낮추는 도구, 프티 체형에 맞는 컴팩트 사이즈 백·의류 브랜드, "
    "소파·주방에서 발이 뜨는 불편을 해결하는 풋레스트. ★단 콤플렉스를 지적하는 물건"
    "(키높이 깔창·다이어트 용품·보정속옷)은 모욕이므로 절대 금지. 특성과 무관한 무난한 "
    "오브제로 도망가는 것도 금지 — 단서를 정면으로, 그러나 다정하게 받아라.\n"
    "\n"
    "★한글 입력 복원: 받는 사람·취향 힌트는 오타·구어·축약이 흔하다"
    "('빠려한거'->'화려한 거', '심플한거루'->'심플한 것', 'ㄱ성비'->'가성비'). "
    "구어 강조어는 '매우'로 읽어라: 겁나·겁내·개·짱·억수로·니무·댑따 = 매우. "
    "★초성 입력 해석: 자음만 입력되면 관계어로 복원하라 — ㅊㄱ=친구, ㅇㅁ=엄마, "
    "ㅇㅃ=아빠(문맥상 오빠 가능), ㄴㅊ=남자친구, ㅇㅊ=여자친구, ㄷㅅ=동생, ㅇㄷ=여동생, "
    "ㄴㄷ=남동생, ㅅㅂ=선배, ㅎㅂ=후배, ㅇㄴ=언니, ㄴㅍ=남편, ㅇㄴㄴ=?불명, ㅂㅁ=부모님, "
    "ㅈㅋ=조카, ㅆㅇ=상사. 복원한 관계를 clue에 쓰고 관계·연령 추론 규칙을 그대로 적용. "
    "복원이 불확실하면 두루 통하는 선물 모드로.\n"
    "가족·관계 애칭 사전: 딸랑구·딸램·딸내미·공주님=딸(아이 가능성 높음), "
    "아들램·아들내미·아들놈·왕자님=아들, 울엄니·어무니·엄니=엄마, 아부지·아빠님=아빠, "
    "마눌님·와이프·집사람=아내, 신랑·남푠=남편, 짝꿍·자기=연인, 베프·절친=가장 친한 친구, "
    "막둥이=막내 자녀, 할무니·할매=할머니, 할부지·할배=할아버지. "
    "그럴듯한 의도로 복원해 해석하고 복원된 단서를 clue에 써라. 이해 불가면 무시하고 "
    "받는 사람 정보만으로 추천하라(엉뚱한 직역 금지).\n"
    "\n"
    "★★수신자 나이 추론 — 관계어를 읽어라: '아들·딸·조카·손주·우리 애'처럼 어린 사람일 "
    "가능성이 큰 관계어가 있고 나이 단서가 없으면 초중등(8~14세)으로 가정하고, 그 나이가 "
    "진짜 기뻐할 것(레고·보드게임·스포츠용품·과학실험 키트·게이밍 주변기기·인라인·베이 "
    "블레이드류)으로 추천하라. 이때 어른 취향 헤리티지(향수·만년필·인센스·바디케어·차)는 "
    "전부 금지 — 아이에게 어른 물건은 실패다. 설명이나 괄호에 나이·연령대가 있으면 그것이 "
    "절대 기준(예: '(20대 남성)'이면 성인). '아빠·엄마·부모님·장인·장모'는 중장년 — "
    "실용+건강+격이 있는 물건으로.\n"
    "\n"
    "★★최우선 규칙 — 핵심 단서: 받는 사람 설명에서 가장 중요한 특성(고민·니즈·취향·상황)을 "
    "먼저 한 단어로 파악하고, 세 방향 전부 그 특성에 직접 답해야 한다. 특성과 무관한 물건은 "
    "아무리 세련돼도 탈락. 예: '땀 많은 남자친구' -> 핵심은 '땀' -> 쿨링·흡한속건·산뜻함 계열"
    "(예: 산타마리아노벨라 탈크 파우더, 프로라소 쿨링 애프터셰이브, 리넨 셔츠)이지, "
    "치약·휴지·일반 면도기가 아니다. ★연결이 두 단계 이상 건너뛰면 억지다"
    "(땀->체온->입안 텁텁->치약 같은 곡예 금지) — 특성에 한 걸음에 닿는 물건만. "
    "reason에 왜 그 특성에 맞는지 반드시 연결해라.\n"
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
    "· 바디·그루밍: 프로라소, 뮬 면도기, 켄트 브러시, 클라우스포르토, 산타마리아노벨라 파우더\n"
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
            if len(toks) >= 2 and not any(t in nm for t in toks[1:]):
                continue                 # 부분일치 함정 방지(라이프->라이프베리)
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


# ★정밀 가격창: 명목 구간 ±10% 안쪽 — "10~20만원"이면 9만~22만까지만.
# (느슨한 창은 예산 격을 훼손: 10~20만에 7만원짜리가 끼면 성의 없어 보인다)
_BUDGET_RANGES = {
    "1만원 이하": (5000, 12000),
    "1~3만원": (10000, 33000),
    "3~5만원": (27000, 55000),
    "5~10만원": (45000, 110000),
    "10~20만원": (90000, 220000),
    "20~50만원": (180000, 550000),
    "50만원 이상": (450000, 99999999),
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


def _style_line(taste):
    """추천 스타일 3모드: 취향 힌트 속 칩 문구로 감지.
    '정석'이면 뻔함 환영, '의외'면 뻔함 금지, 무표기면 혼합(기본)."""
    t = taste or ""
    if "정석" in t or "뻔해도" in t or "무난" in t:
        return ("★스타일=정석: 스테디셀러·검증된 정석 환영. 의외성 강박 금지 — "
                "받는 사람이 확실히 쓸 물건이 최우선. 다만 같은 정석이라도 급이 다른 버전으로.")
    if "의외" in t or "특이" in t or "남다른" in t:
        return "★스타일=의외: 전부 의외의 계열 — 뻔한 조합 절대 금지, 듣도 보도 못한 결로."
    return "★스타일=혼합(기본): 정석 1~2개 + 나머지는 의외의 계열로 섞어라."


def recommend(api_key, who, budget, taste, exclude=None):
    reroll = bool(exclude)
    n_dir = 5 if reroll else 4     # ★재뽑기 = 폭 확장: 방향 4->5
    n_prod = 5 if reroll else 4    # ★픽당 상품도 4->5
    ex = ""
    if exclude:
        ex = ("\n★재뽑기다. 이전에 추천한 키워드: " + ", ".join(exclude[:20]) +
              "\n위 브랜드는 물론 그 카테고리 계열(같은 품목군) 자체를 전부 피하라 — "
              "머그를 냈으면 잔·컵·포트 전부 금지, 만년필을 냈으면 필기구 전부 금지. "
              "완전히 다른 카테고리 패밀리에서만 골라라.")
    user = (
        f"받는 사람: {who or '특정하지 않음 — 누구에게든 두루 통하는 세련된 선물로'}\n"
        f"예산: {budget}\n취향 힌트: {taste or '없음'}{ex}\n\n"
        "먼저 받는 사람의 핵심 단서(고민·니즈·취향) 하나를 파악하고, "
        f"그 단서에 직접 답하는 선물 방향 {n_dir}개를 서로 완전히 다른 계열로.\n"
        + _style_line(taste) + "\n"
        + ("★각 방향은 서로 다른 카테고리 패밀리에서 하나씩만: 문구·필기 / 홈카페·차 / "
           "향·공간 / 주방·리빙 / 주류·잔 / EDC·가죽 / 오디오·아날로그 / 아웃도어 / "
           "바디·그루밍 / 보드게임·취미 / 패션잡화(모자·스카프·장갑) / 도자·유리 공예 / "
           "조명·오브제 / 데스크셋업. 이전 추천이 속한 패밀리는 제외하고 남은 것에서 고른다.\n"
           if reroll else "")
        +
        "★keyword의 상품 실구매가가 반드시 예산 범위 안이어야 한다. 저 예산이면 그 값어치의 물건을 — "
        "20만원대 예산에 만원짜리 소품 금지, 3만원대 예산에 30만원짜리 금지.\n"
        "★쿠팡에서 실제 판매될 법한 키워드만 (에르메스·까르띠에급 하이엔드 명품 주얼리는 쿠팡에 없다 — "
        "그 예산대라면 리델 잔 세트, 이딸라 풀세트, 빈티지 그릇, 니치 향수, 만년필, 오디오 같은 걸로).\n"
        "angle(계열 이름)도 세련되게 — '감각적 소품' 같은 밋밋한 말 대신 "
        "그 방향의 매력을 담은 짧은 이름(예: '백년 된 물건의 힘', '책상 위의 의식', '아날로그 한 조각').\n"
        "★keyword는 검색 정밀도가 생명: '브랜드+라인/모델명+사양' 3~5단어. "
        "라인·모델명이 있는 브랜드는 반드시 라인까지 명시하라(이딸라 떼에마, 라미 사파리, "
        "카웨코 스포츠, 스탠리 클래식 진공, 하리오 V60). 사양은 실검색에 쓰는 것 하나 — "
        "용량(300ml)·닙 굵기(EF)·심 굵기(0.5mm)·사이즈·재질(티타늄) "
        "(예: '이딸라 떼에마 머그 300ml', '라미 사파리 만년필 EF' — '예쁜 머그컵' 금지). "
        "단 쿠팡 검색에 안 걸릴 과도한 수식은 빼라. "
        "★브랜드명은 반드시 붙여 써라: 카이보이슨(O) 카이 보이슨(X), "
        "로얄코펜하겐(O) 로얄 코펜하겐(X) — 띄어 쓰면 검색이 엉뚱한 상품에 걸린다.\n"
        "★alt는 같은 방향의 다른 브랜드 대체 검색어(2~4단어) — keyword가 쿠팡에 없을 때 대비.\n"
        'JSON: {"clue":"받는 사람의 핵심 단서(형용사·상황) 한 단어",'
        f'"picks":[{{"keyword":"브랜드+라인+사양(3~5단어)","alt":"대체 브랜드 검색어","reason":"한 줄 이유","angle":"계열 이름"}}x{n_dir}]}}'
    )
    r = llm_chat(api_key, _SYS, user, max_tokens=1500)
    if not r.get("ok"):
        return {"ok": False, "error": "추천 생성 실패",
                "detail": str(r.get("error") or "")[:120] + " " + str(r.get("detail") or "")[:150]}
    try:
        picks = _parse_json_out(r["text"]).get("picks", [])[:n_dir]
    except Exception:
        return {"ok": False, "error": "추천 형식 오류"}
    if not picks:
        return {"ok": False, "error": "추천이 비었어요"}
    # ★배제 강제 집행: LLM이 금지를 무시하고 이전 라운드 브랜드를 또 내면(실측 2/5)
    # 검색 전에 강제 실패시켜 재추천 루프가 다른 브랜드로 교체하게 한다.
    banned = {k.split()[0] for k in (exclude or []) if k and k.split()}
    for p in picks:
        _t0 = str(p.get("keyword") or "").split()
        if _t0 and _t0[0] in banned:
            p["keyword"] = ""
            p["alt"] = ""
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
            "link": f.get("url"),
            "pid": f.get("productId"),   # 딥링크 정착륙 변환용
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

    def _score2(u, toks):
        return sum(1 for t in toks if t in u.get("name", ""))

    def _relevant(items, toks):
        return [u for u in items if any(t in u["name"] for t in toks)] if toks else items

    def _fetch(kw, _retry=True):
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

            # 브랜드 우대 창도 정밀화: 0.9~1.2배 (정밀 테이블 위에 얹으므로 충분)
            wide_lo, wide_hi = int(_lo * 0.9), int(_hi * 1.2)
            picked = []

            # ⓪ 자사 상품 — 단, ★브랜드가 정확히 일치할 때만 최대 1개 (자연스러움 > 수익.
            # 어색한 끼워넣기는 '어떻게 알았지'를 '광고네'로 무너뜨린다)
            picked += _own_index_search(toks, wide_lo, wide_hi, limit=1)

            # ① 네이버 검색 own — 같은 원칙: 브랜드 토큰 일치분만
            if not picked:
                brand = toks[0] if toks else ""
                own = [u for u in rel_nv if u.get("own") and brand and brand in u["name"]
                       and (len(toks) < 2 or any(t in u["name"] for t in toks[1:]))
                       and _price_ok_range(u, wide_lo, wide_hi)]
                picked += own[:1]

            # ② 쿠팡 브랜드 진품 — 넓은 가격창 (선물은 브랜드 정합 > 엄격한 예산)
            if len(picked) < n_prod:
                # ★부분일치 함정 방지: '라이프' 노트 -> '라이프베리' 립글로스 사태.
                # 브랜드 + 품목 토큰까지 맞아야 진품 취급 (키워드 1단어면 브랜드만)
                bh = [u for u in rel_cp if brand and brand in u["name"]
                      and (len(toks) < 2 or any(t in u["name"] for t in toks[1:]))
                      and _price_ok_range(u, wide_lo, wide_hi)]
                picked += [u for u in bh if u not in picked][:n_prod - len(picked)]

            # ③ 쿠팡 일반 — ★토큰 2개 이상 일치만 (브랜드 없이 '파우더' 한 단어로
            # 로즈마리 요리 파우더가 끼는 것 차단. 1개 일치는 실격 -> 빈 결과가
            # 재추천 루프를 발동시켜 쿠팡에 실재하는 브랜드로 교체됨)
            if len(picked) < n_prod:
                def _score(u):
                    return sum(1 for t in toks if t in u["name"])
                need = 2 if len(toks) >= 2 else 1
                gen = [u for u in rel_cp
                       if _price_ok(u) and u not in picked and _score(u) >= need
                       and (not brand or brand in u["name"])]
                picked += gen[:n_prod - len(picked)]


            # ★가격 전멸 구제 2단: 정밀 키워드가 저가/고가 실상품에 꽂혀
            # 예산창이 전부 걸러버리는 역설 방지 (0개 노출 >> 예산 약간 이탈)
            if not picked:
                r_lo, r_hi = int(_lo * 0.5), int(_hi * 1.6)
                resc = [u for u in rel_cp if _score2(u, toks) >= (2 if len(toks) >= 2 else 1)
                        and (not brand or brand in u.get("name", ""))
                        and _price_ok_range(u, r_lo, r_hi)]
                resc.sort(key=lambda u: abs(int(u.get("price") or 0) - (_lo + _hi) // 2))
                picked += resc[:3]
            if not picked and rel_cp:
                resc = sorted(rel_cp, key=lambda u: -_score2(u, toks))
                picked += [u for u in resc
                           if brand and brand in u.get("name", "")
                           and int(u.get("price") or 0) <= _hi * 2][:2]

            # 내부 필드 정리
            for u in picked:
                u.pop("mall", None)
            # ★검색 실패 시 간소 키워드 재시도 — 수식어·용량이 검색을 죽이는 경우
            # ('산타마리아노벨라 탈크 파우더 100g' -> '산타마리아노벨라 파우더')
            if not picked and _retry:
                _tk = _kw_tokens(kw)
                if len(_tk) >= 3:
                    return _fetch(f"{_tk[0]} {_tk[-1]}", _retry=False)
            return _dedupe_products(picked)[:n_prod]
        except Exception:
            import traceback
            globals()["LAST_FETCH_ERR"] = traceback.format_exc()[-800:]
            return []

    def _clean_kw(k):
        k = scrub_garbled(str(k or ""))
        k = re.sub(r"[\"'\u201c\u201d\u2018\u2019]|쿠팡", "", k)
        return re.sub(r"\s+", " ", k).strip()[:40]

    kws = [_clean_kw(p.get("keyword")) for p in picks]
    alts = [_clean_kw(p.get("alt")) for p in picks]
    results = {}
    if cp:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = {kw: pool.submit(_fetch, kw) for kw in kws if kw}
            results = {kw: f.result() for kw, f in futs.items()}
        need_alt = [(kw, alt) for kw, alt in zip(kws, alts)
                    if alt and len(results.get(kw, [])) < 2]
        if need_alt:
            with ThreadPoolExecutor(max_workers=3) as pool:
                afuts = {kw: pool.submit(_fetch, alt) for kw, alt in need_alt}
                for kw, f in afuts.items():
                    extra = [u for u in f.result() if u not in results.get(kw, [])]
                    results[kw] = _dedupe_products(results.get(kw, []) + extra)[:n_prod]

    out = []
    for p, kw in zip(picks, kws):
        out.append({"keyword": kw,
                    "reason": scrub_garbled(str(p.get("reason") or ""))[:160],
                    "angle": scrub_garbled(str(p.get("angle") or ""))[:20],
                    "products": results.get(kw, [])})

    # ★재추천 루프: 상품 매칭 실패한 계열은 폴백(스토리-상품 모순의 원흉)이 아니라
    # LLM에게 되물어 '쿠팡에 실재하는 다른 브랜드'로 통째 교체 — 훅과 물건이 항상 일치.
    for _round in range(2):   # 재추천 최대 2라운드
      failed_idx = [i for i, o in enumerate(out) if not o["products"]]
      if failed_idx and cp:
         failed_kws = [out[i]["keyword"] for i in failed_idx]
         ok_kws = [o["keyword"] for o in out if o["products"]]
         user2 = (
             f"받는 사람: {who or '특정하지 않음'}\n예산: {budget}\n취향 힌트: {taste or '없음'}\n"
             f"다음 키워드는 쿠팡에 실재 상품이 없어 실패: {', '.join(failed_kws)}\n"
             f"이미 성공한 방향(겹치지 말 것): {', '.join(ok_kws) or '없음'}\n\n"
             + (f"★이전 라운드 브랜드 재등장 절대 금지: {', '.join(sorted(banned))}\n" if banned else "") +
             f"실패분을 대체할 방향 {len(failed_idx)}개 — 같은 감각의 결이되 "
             "쿠팡에서 확실히 팔릴 대중 유통 브랜드로. keyword·reason 정합 규칙 동일.\n"
             "★쿠팡에 확실히 재고가 있는 안전 브랜드 예(이 결에서 골라도 좋다): "
             "킨토, 하리오, 칼리타, 미도리, 라미, 카웨코, 로디아, 몰스킨, 스탠리, "
             "프로라소, 이딸라, 로얄코펜하겐, 조지젠슨, 야마자키, 브라운, 마샬, "
             "인스탁스, 레고, 반다이, 무인양품, 펜텔, 파이롯트, 트래블러스컴퍼니\n"
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
                 if kw2 and kw2.split() and kw2.split()[0] in banned:
                     continue   # 교체분마저 금지 브랜드면 그 슬롯은 버린다(빈 픽 제거가 수습)
                 prods2 = _fetch(kw2) if kw2 else []
                 if prods2:
                     out[slot] = {"keyword": kw2,
                                  "reason": scrub_garbled(str(p2.get("reason") or ""))[:160],
                                  "angle": scrub_garbled(str(p2.get("angle") or ""))[:20],
                                  "products": prods2}
    # ★빈 픽 제거: '상품을 찾지 못했어요' 카드는 체감 품질을 죽인다 —
    # 꽉 찬 2장이 빈칸 낀 3장보다 낫다 (전부 비면 그대로 두고 에러 노출)
    filled = [o for o in out if o["products"]]
    if filled:
        out = filled

    # ★링크 정착륙: 검색 API productUrl은 가끔 다른 상품/검색결과로 떨어진다.
    # productId로 정식 상품 URL 재구성 -> 딥링크 API 일괄 변환(파트너스 수익 유지).
    try:
        url_map = {}
        for o in out:
            for u in o.get("products", []):
                pid = u.pop("pid", None)
                if pid:
                    url_map[f"https://www.coupang.com/vp/products/{pid}"] = u
        if url_map:
            _urls = list(url_map.keys())[:30]
            links = []
            for _i in range(0, len(_urls), 10):   # 딥링크는 10개 단위 배치 (25개까지 커버)
                res = cp.make_deeplinks(_urls[_i:_i + 10], sub_id="giftradar")
                if isinstance(res, dict) and res.get("ok"):
                    links += res.get("data", [])
            for l in links:
                u = url_map.get(l.get("originalUrl"))
                # ★landingUrl(/re/*) 우선: 쿠팡 iOS 앱의 유니버설링크는 link.coupang.com의
                # /re/*·/re2/*만 클레임한다(AASA 실측 2026-08-06). 숏링크(/a/*)는 사파리로
                # 빠지고, landingUrl은 lptag 추적 파라미터를 문 채로 쿠팡앱을 직접 연다.
                if u and (l.get("landingUrl") or l.get("shortenUrl")):
                    u["link"] = l.get("landingUrl") or l["shortenUrl"]
    except Exception:
        pass   # 변환 실패 시 기존 링크 유지

    return {"ok": True, "picks": out, "src": used_model,
            "coupang": bool(cp), "coupang_err": (cp.last_error if cp else "no_keys")}
