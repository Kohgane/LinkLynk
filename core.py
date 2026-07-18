"""
LinkLynk — 코어 모듈
쿠팡 파트너스 딥링크 생성 + 고지문구 삽입 + 블로그 초안 생성
서버(app.py)에서 import해서 사용.
"""
import hmac, hashlib, time, urllib.request, json, ssl, re, random, threading

# ── 살아있는 모델 기억 (죽은 모델 타임아웃 반복 방지) ──
_GOOD_MODEL = {}   # provider -> (model, ts)
_STICKY_TTL = 1800

def _sticky(p):
    v = _GOOD_MODEL.get(p)
    if v and time.time() - v[1] < _STICKY_TTL:
        return v[0]
    return None

def _sticky_ok(p, m):
    _GOOD_MODEL[p] = (m, time.time())

def _sticky_drop(p):
    """과부하·레이트리밋을 맞은 모델은 '지금은 아픈 것'이다.
    기억해두면 다음 요청도 같은 모델로 가서 또 죽는다. 즉시 버린다."""
    _GOOD_MODEL.pop(p, None)

RETRYABLE = (408, 409, 425, 429, 500, 502, 503, 504, 529)

def _order(p, models):
    m = _sticky(p)
    if m and m in models:
        return [m] + [x for x in models if x != m]
    return models


_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

COUPANG_DOMAIN = "https://api-gateway.coupang.com"
DEEPLINK_PATH = "/v2/providers/affiliate_open_api/apis/openapi/v1/deeplink"

# 공정위 필수 고지문구 (쿠팡 파트너스)
COUPANG_DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."


class CoupangPartners:
    """유저별 파트너스 키로 딥링크 생성. 키는 유저가 등록(멀티테넌트 대비)."""

    def __init__(self, access_key: str, secret_key: str):
        self.access = access_key
        self.secret = secret_key

    def _auth(self, method: str, path: str) -> str:
        dt = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        msg = dt + method + path
        sig = hmac.new(self.secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return f"CEA algorithm=HmacSHA256, access-key={self.access}, signed-date={dt}, signature={sig}"

    def search_product(self, keyword, limit=1):
        """파트너스 상품검색 API — 상품명/가격/이미지 반환 (크롤 대체)."""
        import urllib.parse
        q = f"keyword={urllib.parse.quote(keyword)}&limit={limit}"
        path = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
        dt = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        sig = hmac.new(self.secret.encode(), (dt+"GET"+path+q).encode(), hashlib.sha256).hexdigest()
        auth = f"CEA algorithm=HmacSHA256, access-key={self.access}, signed-date={dt}, signature={sig}"
        req = urllib.request.Request(COUPANG_DOMAIN+path+"?"+q,
            headers={"Authorization": auth, "Content-Type": "application/json"}, method="GET")
        try:
            res = json.loads(urllib.request.urlopen(req, context=_ctx, timeout=8).read())
        except Exception:
            return None
        if res.get("rCode") != "0":
            return None
        pd = (res.get("data") or {}).get("productData") or []
        if not pd:
            return None
        p = pd[0]
        return {"name": p.get("productName"), "price": p.get("productPrice"),
                "image": p.get("productImage"), "url": p.get("productUrl"),
                "productId": p.get("productId")}

    def search_products(self, keyword, limit=10):
        """파트너스 상품검색. 실패 사유는 self.last_error에 남긴다(예전엔 통째로 삼켰음).
        ★쿠팡 제한: limit 최대 10. 11 이상이면 rCode 400 'limit is out of range' (2026-07-13 실측)."""
        import urllib.parse
        self.last_error = None
        limit = max(1, min(int(limit or 10), 10))
        q = f"keyword={urllib.parse.quote(keyword)}&limit={limit}"
        path = "/v2/providers/affiliate_open_api/apis/openapi/products/search"
        dt = time.strftime('%y%m%dT%H%M%SZ', time.gmtime())
        sig = hmac.new(self.secret.encode(), (dt+"GET"+path+q).encode(), hashlib.sha256).hexdigest()
        auth = f"CEA algorithm=HmacSHA256, access-key={self.access}, signed-date={dt}, signature={sig}"
        req = urllib.request.Request(COUPANG_DOMAIN+path+"?"+q,
            headers={"Authorization": auth, "Content-Type": "application/json"}, method="GET")
        try:
            res = json.loads(urllib.request.urlopen(req, context=_ctx, timeout=8).read())
        except urllib.error.HTTPError as e:
            body = ""
            try: body = e.read().decode()[:200]
            except Exception: pass
            self.last_error = f"http_{e.code}: {body}"
            return []
        except Exception as e:
            self.last_error = f"net: {type(e).__name__} {str(e)[:120]}"
            return []
        if res.get("rCode") != "0":
            self.last_error = f"coupang rCode={res.get('rCode')} {str(res.get('rMessage'))[:120]}"
            return []
        pd = (res.get("data") or {}).get("productData") or []
        out = []
        for p in pd[:limit]:
            out.append({"name": p.get("productName"), "price": p.get("productPrice"),
                        "image": p.get("productImage"), "url": p.get("productUrl"),
                        "productId": p.get("productId"),
                        "isRocket": p.get("isRocket", False)})
        return out

    def make_deeplinks(self, coupang_urls, sub_id="linklynk"):
        """
        쿠팡 URL 리스트 → 수익 딥링크 변환.
        반환: [{originalUrl, shortenUrl, landingUrl}, ...]
        subId는 채널 추적용(블로그/인스타 등 유입 구분).
        """
        auth = self._auth("POST", DEEPLINK_PATH)
        body = json.dumps({"coupangUrls": coupang_urls, "subId": sub_id}).encode()
        req = urllib.request.Request(
            COUPANG_DOMAIN + DEEPLINK_PATH, data=body,
            headers={"Authorization": auth, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            res = json.loads(urllib.request.urlopen(req, context=_ctx, timeout=10).read())
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": e.code, "detail": e.read().decode()[:300]}
        if res.get("rCode") != "0":
            return {"ok": False, "error": res.get("rCode"), "detail": res.get("rMessage")}
        return {"ok": True, "data": res.get("data", [])}


def unshorten_coupang(short_url: str):
    """쿠팡 단축링크(link.coupang.com/a/...)를 원본 상품 URL로 펼침.
    폰 쿠팡 앱 공유링크는 단축형이라 딥링크 API가 못 받음 → 원본으로 변환 필요.
    단축링크 페이지의 JS(redirectWebUrl)에 원본이 hex 인코딩돼 있음."""
    mob_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
    try:
        req = urllib.request.Request(short_url, headers={"User-Agent": mob_ua})
        body = urllib.request.urlopen(req, context=_ctx, timeout=15).read().decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(r"redirectWebUrl\s*=\s*'([^']+)'", body)
    if not m:
        return None
    decoded = re.sub(r'\\x([0-9A-Fa-f]{2})', lambda x: chr(int(x.group(1), 16)), m.group(1))
    pm = re.search(r'https://www\.coupang\.com/vp/products/\d+', decoded)
    return pm.group(0) if pm else None


def is_short_coupang_link(url: str) -> bool:
    return "link.coupang.com/a/" in url or ".coupang.com/re/" in url


def extract_coupang_url(text: str) -> str:
    """모바일 쿠팡 '공유' 텍스트에서 순수 URL만 뽑아냄.
    예: "쿠팡을 추천합니다! [나우푸드...] https://link.coupang.com/a/XXX" → URL만.
    안내 문구·제품명·이모지가 섞여 있어도 링크만 깔끔히 추출."""
    if not text:
        return ""
    text = text.strip()
    # 쿠팡 관련 URL 패턴 전부 (단축·정식·모바일)
    patterns = [
        r'https?://link\.coupang\.com/[^\s\'"<>)\]]+',      # 단축링크
        r'https?://(?:www\.|m\.)?coupang\.com/[^\s\'"<>)\]]+', # 정식/모바일
        r'https?://[\w.]*coupang\.com/[^\s\'"<>)\]]+',       # 기타 서브도메인
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            url = m.group(0).rstrip('.,)')  # 끝 문장부호 제거
            return url
    # URL 없으면 원문 그대로 (혹시 이미 순수 URL이거나 다른 형식)
    return text


def is_valid_coupang_url(url: str) -> bool:
    """쿠팡 URL인지 확인 (원본 상품 + 단축 공유링크 link.coupang.com 모두 허용)."""
    u = url.strip()
    return bool(re.match(r'https?://([\w.]+\.)?coupang\.com/', u))


def append_disclosure(text: str) -> str:
    """블로그 초안 하단에 고지문구 자동 삽입 (없으면)."""
    if COUPANG_DISCLOSURE[:20] in text:
        return text
    return text.rstrip() + "\n\n---\n" + COUPANG_DISCLOSURE


def guess_category(name: str):
    """상품명에서 카테고리·특성을 추론 → 맞춤 문구용. 파트너스 API 안 씀(이름만 분석)."""
    n = (name or "").lower()
    cats = {
        "beauty":  (["비타민","영양제","콜라겐","유산균","오메가","마그네슘","프로바이오","루테인"],
                    ["꾸준히 챙겨 먹으니", "몸이 가벼워진 느낌", "요즘 건강 신경 쓰는데"]),
        "skincare":(["크림","세럼","토너","앰플","선크림","클렌징","마스크팩","로션","에센스"],
                    ["피부에 발라보니", "흡수도 빠르고", "건조할 때 딱"]),
        "kitchen": (["냄비","프라이팬","도마","칼","텀블러","밀폐용기","주방","식기","컵"],
                    ["요리할 때 써보니", "설거지도 편하고", "주방에 두니"]),
        "home":    (["청소기","걸레","수납","정리함","선반","행거","빨래","세제","방향제"],
                    ["집안일 할 때", "정리해두니 깔끔하고", "청소가 한결 수월"]),
        "digital": (["충전기","케이블","이어폰","마우스","키보드","보조배터리","거치대","usb"],
                    ["써보니 반응 속도도 좋고", "책상에 두니", "휴대하기 편하고"]),
        "baby":    (["기저귀","분유","젖병","유아","아기","신생아","물티슈","이유식","베이비"],
                    ["아이한테 써보니", "육아할 때", "부모 입장에서"]),
        "fashion": (["티셔츠","바지","원피스","신발","가방","양말","모자","니트","자켓"],
                    ["입어보니 핏도 좋고", "코디하기 편하고", "데일리로 두기 좋"]),
        "food":    (["과자","커피","간식","라면","음료","견과","초콜릿","젤리","비스킷","시리얼","차 티백","녹차","홍차"],
                    ["먹어보니", "맛도 괜찮고", "간식으로 딱"]),
        "car":     (["차량","자동차","와이퍼","방향제","거치대","블랙박스","트렁크"],
                    ["차에 달아보니", "운전할 때", "차량용으로"]),
        "sleep":   (["베개","이불","매트리스","침구","수면","안대","토퍼"],
                    ["베고 자보니", "잠들 때", "숙면에"]),
    }
    for cat, (kws, phrases) in cats.items():
        if any(k in n for k in kws):
            return cat, phrases
    return "general", ["써보니", "생각보다 괜찮고", "실사용해보니"]


def extract_keywords(name: str):
    """상품명에서 핵심 제품종류 추출. 쿠팡 상품명 구조(브랜드 수식어 제품종류, 수량, 색상)에 맞게.
    예: 'HOMEY NEST ... 메모리폼 베개, 1개, 화이트' → core='베개' (1개/화이트 무시)"""
    if not name:
        return {"core": "이거", "brand": "", "features": []}

    # 1) 쉼표 앞부분만 사용 (쉼표 뒤는 보통 수량·색상·옵션)
    main = name.split(",")[0].strip()
    # + 뒤도 옵션인 경우가 많음 (예: 홈캠 + 스탠드) → 앞부분 우선
    main_head = main.split(" + ")[0].split("+")[0].strip() if (" + " in main or "+" in main) else main
    words_all = main.split()
    brand = words_all[0] if words_all else ""

    # 2) 노이즈 단어 제거 (수량·색상·사이즈·순수숫자)
    JUNK = re.compile(r'^\d+(개|매|매입|p|P|ea|세트|팩|입|장|병|포|캡슐|정|ml|L|g|kg|cm|mm|호|단)?$', re.I)
    COLORS = {"화이트","블랙","그레이","네이비","블루","레드","핑크","베이지","브라운","그린",
              "옐로우","퍼플","실버","골드","아이보리","카키","민트","라벤더","연그레이","다크그레이"}
    SIZE = {"s","m","l","xl","xxl","free","프리","대","중","소","특대"}
    def is_junk(w):
        wl = w.lower()
        return JUNK.match(w) or w in COLORS or wl in SIZE or w.startswith("타입") or w.startswith("type")

    # 3) 제품종류 명사 사전 (실제 core가 될 명사들 — 길이순으로 최장 매칭)
    PRODUCT_NOUNS = [
        "무선청소기","로봇청소기","핸디청소기","차량용청소기","물걸레청소기","스팀청소기","청소기",
        "냉감이불","여름이불","차렵이불","극세사이불","이불","매트리스","토퍼","침구",
        "메모리폼베개","경추베개","다리베개","목베개","바디필로우","베개",
        "넥밴드선풍기","목걸이선풍기","휴대용선풍기","탁상용선풍기","서큘레이터","선풍기",
        "넥쿨러","넥밴드","아이스밴드","쿨링밴드","쿨토시","쿨스카프",
        "베이비모니터","홈캠","홈카메라","cctv","웹캠","액션캠",
        "안마의자","마사지건","마사지기","안마기","지압기","발마사지기","눈마사지기","두피마사지기",
        "가습기","제습기","공기청정기","에어프라이어","전기포트","커피머신","믹서기","블렌더","전기그릴",
        "무선이어폰","블루투스이어폰","이어폰","헤드폰","이어버드","스피커","블루투스스피커",
        "보조배터리","고속충전기","무선충전기","충전기","케이블","멀티탭","거치대","차량거치대","핸드폰거치대","스탠드",
        "무선마우스","마우스","키보드","기계식키보드","모니터암","노트북거치대","웹캠",
        "니트릴장갑","고무장갑","주방장갑","목장갑","작업장갑","장갑",
        "모기퇴치기","포충기","살충기","해충퇴치기","모기향","전기모기채",
        "아기띠","힙시트","유모차","카시트","젖병","분유포트","기저귀","물티슈","치발기",
        "무드등","led등","스탠드조명","무선조명","취침등","독서등","조명",
        "텀블러","보온병","물병","밀폐용기","도시락","보냉백","텀블러세트",
        "수면안경","수면유도등","안대","수면양말","귀마개",
        "전동칫솔","구강세정기","치실","가글","면도기","전기면도기","제모기","코털제거기",
        "드라이어","고데기","매직기","헤어드라이어","롤빗","두피브러시",
        "러닝화","운동화","슬리퍼","샌들","실내화","구두","부츠","스니커즈",
        "백팩","크로스백","토트백","에코백","파우치","지갑","카드지갑",
        "무선키보드","태블릿거치대","폰케이스","강화유리","보호필름","그립톡",
        "전기장판","온수매트","전기요","핫팩","손난로","무릎담요","담요",
        "요가매트","폼롤러","아령","덤벨","resistance밴드","짐볼","훌라후프",
    ]
    low = name.lower().replace(" ", "")
    core = None
    for noun in PRODUCT_NOUNS:  # 사전 순서 = 구체적인 것 먼저(최장 매칭)
        if noun.lower() in low:
            core = noun
            break
    if not core:
        # 사전에 없으면: 쉼표+옵션 제거 후 마지막 의미 단어. 단 애매한 일반명사는 건너뜀
        VAGUE = {"본체","세트","구성","패키지","키트","증정","사은품","옵션","단품","기본","선택",
                 "정품","국내","해외","특가","할인","무료배송","당일발송","최신형","신형","구형"}
        head_words = [w for w in main_head.split() if not is_junk(w) and w not in VAGUE]
        # 뒤에서부터 '~기/~기기/~용품' 등 제품스러운 단어 우선
        core = None
        for w in reversed(head_words):
            if len(w) >= 2:
                core = w; break
        if not core:
            core = head_words[-1] if head_words else (words_all[-1] if words_all else "이거")

    # 4) 특징 = 중간 단어들 (core·브랜드·노이즈 제외)
    features = []
    for w in words_all[1:]:
        if is_junk(w): continue
        if w == core or (core in w) or (w in core): continue
        if len(w) >= 2:
            features.append(w)
    features = features[:3]
    return {"core": core, "brand": brand, "features": features}


def make_blog_draft(product_name: str, deeplink: str, tone: str = "friendly", channel: str = "blog", info: dict = None) -> str:
    """플랫폼별 맞춤 초안. ★매번 다른 글 + ★상품 키워드 반영 + ★사람같은 문체."""
    name = product_name
    first = name.split()[0] if name else "이거"
    kw = extract_keywords(name)
    core = kw["core"]        # 제품 종류 (선풍기, 청소기 등)
    feats = kw["features"]   # 특징들
    feat = random.choice(feats) if feats else ""
    price_txt = ""
    if info and info.get("price"):
        price_txt = f"{int(info['price']):,}원"
    R = random.choice   # 짧게
    _cat, cat_phrases = guess_category(name)   # 상품 특성 문구
    cat_line = R(cat_phrases)   # 예: "피부에 발라보니", "아이한테 써보니"
    # ★유저 커스텀 톤: friendly(친근)/polite(정중)/expert(전문가)/casual(솔직담백)
    TONE = tone or "friendly"

    # ── X (트위터): 짧고 임팩트, 매번 다른 훅 ──
    if channel == "x":
        hooks = [
            f"{name} 써봤는데 이거 물건이네 👀",
            f"요즘 {core} 이거 하나로 버팀",
            f"{name} 진작 살걸 후회 중",
            f"별 기대 안 했는데 {core} 이거 의외로 대박",
            f"{name} 3주째 쓰는 중인데 만족도 높음",
            f"솔직히 {core} 이 가격이면 안 살 이유가 없음",
        ]
        tails = [
            f"{'지금 '+price_txt+' ' if price_txt else ''}👉 {deeplink}",
            f"필요한 사람 링크 👉 {deeplink}",
            f"밑에 링크 둠 {deeplink}",
            f"{'가격 '+price_txt+' ' if price_txt else ''}{deeplink}",
        ]
        tags = R([f"#쿠팡추천 #{core}", f"#{core} #추천템", f"#내돈내산 #{core}"])
        return append_disclosure(f"{R(hooks)}\n\n{R(tails)}\n\n{tags}")

    # ── 쓰레드: 6분할, 매번 다른 골격·말투 (THREADS 가이드) ──
    if channel == "threads":
        # feat 있으면 "OO 되는" 식으로 자연스럽게
        featph = f"{feat} 되는 거" if feat else "이런 거"
        POOLS = {
            "polite": {
                "posts": [
                    f"{core} 고르는 게 생각보다 어렵더라고요\n다들 어떤 기준으로 보시나요?",
                    f"{core} 관련해서 여쭤보는 분들이 많아서 정리해봤어요",
                    f"{core}, 사기 전에 저처럼 고민하시는 분 계실까요?",
                    f"{core} 써보신 분 있으신가요? 후기 남겨봐요",
                    f"{core} 하나 새로 들였는데 생각보다 괜찮아서 공유드려요",
                    f"요즘 {core} 찾는 분들 많으시더라고요. 제 경험 적어볼게요",
                    f"{featph} {core} 찾다가 이거로 정착했어요",
                ],
                "r1": [f"며칠 고민하다 구매했는데\n{cat_line} 만족스러웠어요", f"여러 {core} 비교하다 이걸로 정했어요", f"{feat+' 기능이 마음에 들어서 골랐어요' if feat else '리뷰 보고 골랐는데 괜찮네요'}"],
                "r2": [f"{'가격도 '+price_txt+' 정도라 부담 없었고요' if price_txt else '가격도 합리적이었고요'}\n품질도 괜찮았어요", "실사용해보니 기대 이상이었어요", f"{core}치고 마감도 깔끔하더라고요"],
                "r3": ["지금은 잘 쓰고 있습니다", "재구매 의사도 있어요", "주변에도 추천하고 있어요"],
                "link": ["필요하신 분 계실까 봐 링크 남겨둘게요:)", "구매처는 아래에 남겨드려요"],
                "end": [f"도움이 되셨으면 좋겠어요\n{deeplink}", f"참고되셨길 바라요\n{deeplink}"],
            },
            "expert": {
                "posts": [
                    f"{core} 구매 전 체크할 핵심 포인트 정리",
                    f"{core} 고를 때 이것만 보면 됩니다",
                    f"{core}, 실사용 기준으로 평가해봤습니다",
                    f"{feat+' 사양 ' if feat else ''}{core} 살 때 놓치기 쉬운 것",
                    f"{core} 스펙만 보면 안 되는 이유",
                    f"{core} 실측 후기입니다",
                ],
                "r1": [f"핵심은 실사용 만족도인데\n{cat_line} 합격점이었습니다", "스펙보다 실제 사용감이 중요합니다", f"{feat+' 성능은 기대 이상이었습니다' if feat else '기본기가 탄탄합니다'}"],
                "r2": [f"{'가격 대비 성능이 '+price_txt+' 기준 우수합니다' if price_txt else '가성비가 뛰어납니다'}", "동급 대비 경쟁력 있습니다"],
                "r3": ["쓸 만합니다", "재구매 가치 있다고 판단됩니다"],
                "link": ["구매 링크 첨부합니다", "아래에서 확인 가능합니다"],
                "end": [f"판단에 도움 되시길\n{deeplink}", f"참고하시기 바랍니다\n{deeplink}"],
            },
            "casual": {
                "posts": [
                    f"{core} 이런 거 찾다가 시간 다 씀…\n다들 어떻게 고름?",
                    f"솔직히 {core} 다 거기서 거기 아님? 했는데",
                    f"{core} 없을 때랑 있을 때랑 삶의 질이 다름 진짜",
                    f"{core} 하나 잘못 사서 돈 날린 적 있어서 이번엔 빡세게 알아봄",
                    f"{feat+' ' if feat else ''}{core} 이거 왜 이제 샀지 싶음",
                    f"{core} 3시간 검색하다 현타 와서 그냥 이거 삼ㅋㅋ",
                    f"남들 {core} 뭐 쓰나 궁금해서 물어봤더니 다들 이거더라",
                    f"{core} 이거 은근 물건임 아는 사람만 아는 듯",
                ],
                "r1": [f"며칠 고민하다 그냥 질렀는데\n{cat_line} 생각보다 만족", f"반신반의하면서 샀는데\n{cat_line} 웬걸", f"{feat+' 이거 생각보다 쓸만함' if feat else '기대 안 했는데 의외로 좋음'}"],
                "r2": [f"{'가격도 '+price_txt+'이라 부담 없었고' if price_txt else '가격도 착했고'}\n써보니 확실히 다름", "비싼 거랑 비교해봤는데 이걸로 충분", f"{core}치고 이 정도면 훌륭"],
                "r3": ["이젠 없으면 아쉬울 듯", "이제 딴 거 안 씀", "주변에 다 영업하고 다니는 중ㅋㅋ"],
                "link": ["찾기 귀찮을까 봐 밑에 링크 둠 👇", "광고 맞음ㅋㅋ 그래도 쓰는 건 진짜", "밑에 링크.", "혹시 몰라 남겨둠"],
                "end": [f"나만 알기 아까워서 공유함ㅋㅋ\n{deeplink}", f"필요한 사람 참고하셈\n{deeplink}", f"암튼 강추임\n{deeplink}"],
            },
            "friendly": {
                "posts": [
                    f"{core} 이런 거 찾다가 시간 다 썼어요ㅎㅎ\n다들 어떻게 고르세요?",
                    f"요즘 {core} 뭐 쓰냐고 물어보는 분 많아서 적어봐요",
                    f"{core} 하나 샀는데 생각보다 좋아서 공유해요~",
                    f"{feat+' ' if feat else ''}{core} 고민 중이신 분들 이거 어때요?",
                    f"{core} 바꿨더니 확실히 편해졌어요ㅎㅎ",
                    f"{core} 써보고 있는데 만족 중이에요",
                    f"{core} 살까 말까 고민 많이 했는데 잘 산 것 같아요",
                ],
                "r1": [f"며칠 고민하다 샀는데\n{cat_line} 만족해요", f"처음엔 반신반의했는데\n{cat_line} 웬걸요ㅎㅎ", f"{feat+' 기능 은근 잘 써요' if feat else '생각보다 손이 자주 가요'}"],
                "r2": [f"{'가격도 '+price_txt+'이라 부담 없었어요' if price_txt else '가격도 착했어요'}\n써보니 좋더라고요", "이 값이면 충분한 것 같아요"],
                "r3": ["지금은 주변에도 추천 중이에요ㅎㅎ", "당분간 딴 거 안 볼 듯해요"],
                "link": ["찾기 귀찮을까 봐 링크 둘게요 👇", "궁금한 분 있을까 봐 걸어둬요~"],
                "end": [f"도움 됐으면 좋겠어요\n{deeplink}", f"필요한 분 참고하세요~\n{deeplink}"],
            },
            "excited": {
                "posts": [f"{core} 이거 진짜 대박이에요!!! 🔥\n왜 이제 샀지 싶음", f"{core} 사고 완전 신세계 열림ㅠㅠ 미쳤다", f"{feat+' ' if feat else ''}{core} 이건 진짜 사야 함!! 강추!!"],
                "r1": [f"{cat_line} 첫날부터 감동;;;", "기대 이상이라 소리 질렀어요 진짜"],
                "r2": [f"{'가격 '+price_txt+'에 이 퀄?! 말도 안 됨' if price_txt else '이 가격에 이 퀄리티 실화?!'}", "가성비 미쳤어요 완전 이득!!"],
                "r3": ["벌써 하나 더 사려고요ㅋㅋㅋ", "친구한테도 보냈음"],
                "link": ["빨리 봐요 이거 👇🔥", "링크 여기!! 놓치지 마세요"],
                "end": [f"안 샀으면 아쉬웠을 듯\n{deeplink}", f"안 사면 손해예요ㅠㅠ\n{deeplink}"],
            },
            "minimal": {
                "posts": [f"{core}.\n괜찮음.", f"{core} 추천.\n이유는 밑에.", f"{feat+' ' if feat else ''}{core}. 만족."],
                "r1": [f"{cat_line} 좋음.", "군더더기 없음."],
                "r2": [f"{price_txt+'. 적당.' if price_txt else '가격 적당.'}", "품질 무난."],
                "r3": ["재구매 예정.", "추천함."],
                "link": ["링크.", "여기."],
                "end": [f"{deeplink}", f"끝.\n{deeplink}"],
            },
            "story": {
                "posts": [f"{core} 사게 된 이야기 좀 풀자면…", f"사실 {core} 원래 관심 없었는데 계기가 있었어요", f"{core} 하나 때문에 일상이 바뀐 썰"],
                "r1": [f"어느 날 문득 필요해서 찾아봤는데\n{cat_line} 이거였어요", "여러 번 실패하다 만난 게 이거"],
                "r2": [f"{'가격도 '+price_txt+'이고' if price_txt else '가격도 괜찮고'}\n써보니 왜 진작 안 샀나 싶더라고요", "쓰면 쓸수록 정드는 그런 거"],
                "r3": ["지금은 없으면 허전할 정도예요", "그날의 선택을 후회 안 해요"],
                "link": ["혹시 저 같은 분 있을까 봐 👇", "제 이야기가 도움 되길"],
                "end": [f"긴 글 읽어줘서 고마워요\n{deeplink}", f"당신의 이야기도 궁금해요\n{deeplink}"],
            },
            "curious": {
                "posts": [f"{core}, 다들 이거 하나로 뭘 하는지 알아요?", f"{core} 이거 왜 다들 사는지 궁금하지 않아요?", f"{feat} 이거 뭔지 아세요? {core} 얘기예요"],
                "r1": [f"저도 궁금해서 사봤는데\n{cat_line} 답이 나왔어요", "직접 써보니 이유를 알겠더라고요"],
                "r2": [f"{'가격이 '+price_txt+'인데 왜 인기인지' if price_txt else '왜 인기인지'}\n이제 알 것 같아요", "비밀은 여기 있었어요"],
                "r3": ["궁금하면 직접 써보시길", "저처럼 궁금한 분 많을 듯"],
                "link": ["답은 여기 👇", "확인해보세요"],
                "end": [f"궁금증 풀리셨나요?\n{deeplink}", f"직접 보는 게 빨라요\n{deeplink}"],
            },
            "warm": {
                "posts": [f"{core} 필요하신 분께 조심스레 추천드려요", f"오늘은 제가 아끼는 {core} 하나 소개할게요", f"{core} 덕분에 하루가 조금 더 편안해졌어요"],
                "r1": [f"{cat_line} 마음에 쏙 들었어요", "작은 것 하나로 위로받는 느낌이에요"],
                "r2": [f"{'가격도 '+price_txt+'이라 부담 없이' if price_txt else '부담 없이'}\n곁에 두기 좋아요", "소소하지만 확실한 만족이에요"],
                "r3": ["오래 함께하고 싶은 물건이에요", "당신에게도 그런 존재가 되길"],
                "link": ["필요하신 분께 살며시 남겨요 👇", "따뜻한 마음으로 공유해요"],
                "end": [f"오늘도 좋은 하루 되세요\n{deeplink}", f"작은 도움이 되길 바라요\n{deeplink}"],
            },
            "witty": {
                "posts": [f"{core} 없이 살던 과거의 나 반성합니다ㅋㅋ", f"{core} 사려고 통장을 열었다… 후회는 없다", f"{core} 이거 사면 인생 안 바뀜. 근데 삶은 편해짐ㅋㅋ"],
                "r1": [f"{cat_line} 생각보다 쓸만해서 당황", "기대 0이었는데 배신감(좋은 쪽)"],
                "r2": [f"{'가격 '+price_txt+'? 커피 몇 잔 값' if price_txt else '커피 몇 잔 값'}\n근데 훨씬 오래 씀", "가성비 하나는 인정"],
                "r3": ["이제 없으면 불편함ㅋㅋ", "중독성 주의"],
                "link": ["지갑 조심하고 클릭 👇", "책임 안 짐(농담) 링크임"],
                "end": [f"암튼 웃돈 주고도 살 만함ㅋㅋ\n{deeplink}", f"내 지갑은 울지만 난 웃음\n{deeplink}"],
            },
            "honest": {
                "posts": [f"내돈내산 {core} 찐후기 갑니다", f"{core} 광고 아니고 진짜 제 돈 주고 산 후기", f"{feat+' ' if feat else ''}{core} 솔직하게 장단점 다 말할게요"],
                "r1": [f"장점부터: {cat_line} 확실히 좋아요", "단점도 있는데 감수할 만해요"],
                "r2": [f"{'가격 '+price_txt+' 값은 함' if price_txt else '값은 하는 편'}\n과대광고는 아니에요", "딱 쓴 만큼 정직한 제품"],
                "r3": ["재구매? 네, 할 거예요", "솔직히 추천합니다"],
                "link": ["진짜 링크(광고비 0원) 👇", "제 돈 주고 산 그 링크"],
                "end": [f"찐후기 끝. 판단은 각자\n{deeplink}", f"솔직함이 최고의 리뷰죠\n{deeplink}"],
            },
            "trendy": {
                "posts": [f"{core} 요즘 이거 없으면 인싸 아님ㅋㅋ", f"{core} 이거 알고리즘 타서 샀는데 성공각", f"{feat} {core} 요즘 핫한 거 나만 없나 했잖아"],
                "r1": [f"{cat_line} 갓성비 인정이요", "왜 다들 사는지 바로 이해함"],
                "r2": [f"{'가격 '+price_txt+' 개꿀' if price_txt else '가격 개꿀'}\n이건 사야 정신건강 이득", "요즘 트렌드 그잡채"],
                "r3": ["짱친한테도 바로 추천함", "손민수 각 나옴ㅋㅋ"],
                "link": ["여기서 득템 ㄱㄱ 👇", "링크 박아둠"],
                "end": [f"이건 못 참지ㅋㅋ\n{deeplink}", f"트렌드 놓치지 마셈\n{deeplink}"],
            },
            "calm": {
                "posts": [f"{core} 하나로 일상이 조금 정돈됐어요", f"요란하지 않게, {core} 이야기를 해볼게요", f"{core} — 조용히 곁에 두기 좋은 물건"],
                "r1": [f"{cat_line} 잔잔하게 만족스러웠어요", "과하지 않아서 오히려 좋아요"],
                "r2": [f"{'가격도 '+price_txt+'로 합리적이고' if price_txt else '가격도 합리적이고'}\n오래 쓰기 좋아요", "군더더기 없이 제 몫을 해요"],
                "r3": ["차분히 만족하며 쓰고 있어요", "조용한 추천을 남겨요"],
                "link": ["필요하시면 아래에 👇", "조용히 링크 둡니다"],
                "end": [f"평온한 하루 되세요\n{deeplink}", f"천천히 살펴보세요\n{deeplink}"],
            },
            "urgent": {
                "posts": [f"{core} 지금 아니면 후회할 수도\n재고 있을 때 얘기해요", f"{core} 이거 품절되기 전에 알려드려요", f"{feat+' ' if feat else ''}{core} 지금이 딱 살 타이밍"],
                "r1": [f"{cat_line} 왜 지금 사야 하냐면요", "고민할수록 손해예요 진짜"],
                "r2": [f"{'가격 '+price_txt+', 이 가격 오래 안 갈 듯' if price_txt else '이 가격 오래 안 갈 듯'}", "지금이 제일 합리적일 때"],
                "r3": ["미루면 아쉬워요", "결정은 빠를수록 좋아요"],
                "link": ["늦기 전에 확인 👇", "지금 바로 여기"],
                "end": [f"기회 놓치지 마세요\n{deeplink}", f"지금 확인하세요\n{deeplink}"],
            },
            "friend": {
                "posts": [f"야 {core} 이거 진짜 사라\n내가 써봤는데 좋음", f"너 {core} 아직도 안 샀어? 이거 봐봐", f"{core} 하나 샀는데 너 생각나서 알려줌"],
                "r1": [f"{cat_line} 나 완전 만족 중임", "너도 분명 좋아할 듯"],
                "r2": [f"{'가격도 '+price_txt+'밖에 안 해' if price_txt else '가격도 안 비쌈'}\n부담 없이 질러", "이 값이면 개이득이지"],
                "r3": ["진짜 후회 안 함", "나 믿고 사"],
                "link": ["여기 링크 보냄 👇", "이거 눌러봐"],
                "end": [f"암튼 사 후회 안 해\n{deeplink}", f"나중에 고맙다고 해라ㅋㅋ\n{deeplink}"],
            },
            # ── 심리학 기반 훅 (정보격차·손실회피·문제증폭·사회적증거) ──
            "gap": {  # 정보격차: "진짜 원인은 따로 있다"
                "posts": [f"{core} 고를 때 다들 엉뚱한 걸 본다.", f"{core}, 진짜 중요한 건 따로 있더라.", f"{core} 이거 하나 바꿨더니 알겠더라. 원인이 딴 데 있었음.", f"{core} 살 때 이거 모르면 돈 버림."],
                "r1": [f"{core} 살 때 대부분 이걸 놓침.\n나도 한참 헤맸고.", f"{feat+' 이거부터 봐야 하는데' if feat else '진짜 중요한 건'} 아무도 안 알려줌.", f"{core}, 스펙만 보다 낭패 봄."],
                "r2": [f"{feat+' 이게 핵심이더라' if feat else '핵심은 딴 데 있었음'}.\n그래서 이걸로 바꿈.", f"{core} 제대로 고르니까 바로 해결됨.", f"{feat+' 되는 걸로 바꾸니' if feat else '바꾸니'} 세상 편함."],
                "r3": ["바꾸고 며칠 만에 확 달라짐.", "진작 알았으면 좋았을 걸.", f"{core}는 이제 이걸로 정착."],
                "link": ["밑에 링크.", "여기 남겨둠."],
                "end": [f"원인 알고 나니 허무하더라.\n{deeplink}", f"아는 사람만 아는 거였음.\n{deeplink}"],
            },
            "loss": {  # 손실회피: "싼 거 여러 번 = 더 비쌌다"
                "posts": [f"{core} 사느라 날린 돈 계산해봤다.", f"싼 {core} 여러 번 사다 결국 손해 본 썰.", f"{core}, 처음부터 제대로 살 걸 그랬음."],
                "r1": [f"몇 개 사서 다 버렸으니 돈 날린 셈.\n결국 안 쓰게 되더라고.", "싼 맛에 샀다가 계속 다시 삼."],
                "r2": [f"그 돈이면 {'제대로 된 거 ('+price_txt+') ' if price_txt else '제대로 된 거 '}하나 살 걸.\n이건 계속 씀.", "제대로 된 거 하나가 답이었음."],
                "r3": ["이제 딴 거 안 사도 됨.", "진작 이걸로 갈 걸."],
                "link": ["밑에.", "여기 있음."],
                "end": [f"싼 거 여러 번이 결국 더 비쌌음.\n{deeplink}", f"돈 아끼려다 더 씀. 참고하셈.\n{deeplink}"],
            },
            "amplify": {  # 문제증폭: 작은 증상 → 방치하면 커진다 (공감)
                "posts": [f"{core} 관련 작은 신호, 그냥 넘기면 안 돼요.", f"이 증상 방치하면 나중에 후회해요.", f"{core}, 사소해 보여도 쌓이면 커져요."],
                "r1": [f"처음엔 별거 아닌 것 같지만\n방치하면 점점 심해지더라고요 ㅠㅠ", "저도 그냥 뒀다가 고생했어요."],
                "r2": [f"저는 {'이거 ('+price_txt+') ' if price_txt else '이거 '}하나로 확 줄였어요.\n{feat+' 덕분에' if feat else '이걸로'} 관리되더라고요.", "미리 잡으니 훨씬 편해요."],
                "r3": ["일찍 챙기길 잘했어요.", "지금은 걱정 안 해요."],
                "link": ["궁금하신 분들 걸어둬요~", "필요하시면 여기요."],
                "end": [f"작은 신호 놓치지 마세요.\n{deeplink}", f"미리 챙기는 게 답이에요.\n{deeplink}"],
            },
            "social": {  # 사회적증거: "요즘 다들 조용히 쓰는 거"
                "posts": [f"요즘 {core} 조용히 많이들 쓰더라고요.", f"아는 사람들 사이에서 {core} 이거 유명해요.", f"{core}, 알 만한 사람은 다 쓰는 듯."],
                "r1": [f"주변에서 하나둘 쓰길래 저도 샀는데\n왜 인기인지 알겠더라고요.", "다들 쓰는 데는 이유가 있었어요."],
                "r2": [f"{feat+' 이 부분이 특히 좋아요' if feat else '써보니 확실히 다르고'}.\n{'가격도 '+price_txt+'고요' if price_txt else '부담도 없고요'}.", "괜히 입소문 난 게 아니더라고요."],
                "r3": ["이제 제가 추천하고 다녀요.", "안 써본 사람만 있는 듯."],
                "link": ["찾으시는 분 계실까 봐 :)", "여기 남겨둘게요~"],
                "end": [f"다들 쓰는 데는 이유가 있어요.\n{deeplink}", f"조용한 스테디셀러예요.\n{deeplink}"],
            },
            "parent": {  # 부모불안(공감): 실재하는 걱정에 공감+안심 (윤리선 준수)
                "posts": [f"아이 키울 때 {core}, 걱정되는 부모라면 아실 거예요.", f"밤마다 아이 때문에 신경 쓰이는 분들께.", f"육아하면서 {core} 고민, 저만 그런 거 아니죠?"],
                "r1": [f"밤에 몇 번씩 깨서 확인하고…\n저만 그런 거 아니죠? 정작 엄마가 못 자요.", "부모 마음이 다 그렇더라고요."],
                "r2": [f"{feat+' ' if feat else ''}이거 하나 두고부터\n마음이 놓이더라고요. 알림도 오고요.", "안심되니까 저도 잘 자게 됐어요."],
                "r3": ["아이도 덜 깨고 저도 편해졌어요.", "진작 둘 걸 그랬어요."],
                "link": ["저처럼 걱정인 분들께 남겨둘게요.", "필요하신 분 계실까 봐요."],
                "end": [f"마음 편한 게 육아엔 제일이더라고요.\n{deeplink}", f"온 가족 편한 밤 되시길요.\n{deeplink}"],
            },
            "reverse": {  # 통념반전: "비쌀수록 좋을 줄 알았는데 아니더라"
                "posts": [f"비싼 {core}일수록 좋을 거라 생각했는데 아니더라.", f"{core}, 가격이 답이 아니었음.", f"{core} 비싼 거 쓰다 오히려 손해 본 적 있음."],
                "r1": [f"가격이 아니라 '나한테 맞냐'가 전부였음.\n비싼 거 쓰다 더 안 좋았던 적도 있고.", "핵심은 가격표가 아니더라."],
                "r2": [f"{feat+' 되는 걸로' if feat else '나한테 맞는 걸로'} 바꾸니까\n오히려 그게 제일 나았음.", "이게 딱이더라."],
                "r3": ["비쌀 필요 없고 맞으면 되는 거였음.", "괜히 돈 썼다 싶음."],
                "link": ["밑에.", "여기 있음."],
                "end": [f"{core}는 가격표가 아니더라.\n{deeplink}", f"비싼 게 답은 아니었음.\n{deeplink}"],
            },
            "overshare": {  # 정밀오버셰어링: 아주 구체적인 순간 고백 (POV)
                "posts": [f"{core} 관련해서, 남들은 안 하는데 나만 하는 짓이 있음.", f"이거 나만 이러나 싶은데… {core} 얘기임.", f"솔직히 {core} 때문에 이런 것까지 해봤어요."],
                "r1": [f"별거 아닌 것 같은데 계속 신경 쓰이더라고요.\n이 마음, 겪어본 사람은 알 거예요.", "저만 유난인가 했는데 아니더라고요."],
                "r2": [f"{feat+' ' if feat else ''}이거 두고부터는\n그 신경 쓰임이 확 줄었어요.", "이제 그럴 일이 없어졌어요."],
                "r3": ["작은 건데 삶의 질이 달라져요.", "진작 살 걸 그랬어요."],
                "link": ["혹시 저 같은 분 있을까 봐요.", "필요하시면 밑에요."],
                "end": [f"저 같은 분께 도움 되길요.\n{deeplink}", f"나만 이런 거 아니었네요.\n{deeplink}"],
            },
            "observe": {  # 구체적관찰: 디테일한 순간 묘사로 몰입
                "posts": [f"어제 {core} 쓰다가 문득 깨달은 거.", f"{core}, 사소한 순간에 차이를 느낌.", f"별생각 없이 {core} 쓰다가 '어?' 한 순간."],
                "r1": [f"평소엔 몰랐는데 그 순간 확 와닿더라고요.\n작은 차이가 이렇게 크구나 싶었어요.", "디테일에서 갈리더라고요."],
                "r2": [f"{feat+' 이 부분이' if feat else '이 부분이'} 은근 컸어요.\n써본 사람만 아는 그런 거요.", "겪어보니 알겠더라고요."],
                "r3": ["이제 딴 거 못 쓸 듯해요.", "이런 게 진짜 차이죠."],
                "link": ["궁금하신 분 밑에요.", "여기 남겨둬요."],
                "end": [f"사소한 게 제일 크더라고요.\n{deeplink}", f"직접 느껴보셔야 알아요.\n{deeplink}"],
            },
            "onlyme": {  # 나만그런줄: 공감대 형성 후 해결
                "posts": [f"{core}, 나만 불편한 줄 알았는데 아니었음.", f"이거 다들 참고 쓰는 거였어? {core} 얘기.", f"{core} 이 불편함, 나만 느낀 거 아니지?"],
                "r1": [f"다들 그냥 참고 쓰길래 나만 예민한 줄 알았음.\n근데 물어보니 다 불편했다더라.", "말 안 해서 그렇지 다들 겪더라고요."],
                "r2": [f"{feat+' 되는 걸로' if feat else '이걸로'} 바꾸니까\n그 불편함이 사라짐.", "바꾸고 나서야 알았음, 참을 필요 없었다는 걸."],
                "r3": ["왜 진작 안 바꿨나 싶음.", "이제 그 불편함 없음."],
                "link": ["같이 불편했던 분들 밑에.", "여기요."],
                "end": [f"참지 말고 바꾸세요.\n{deeplink}", f"나만 그런 거 아니었음.\n{deeplink}"],
            },
            "pov": {  # POV: 특정 상황 시점 몰입
                "posts": [f"[POV] 당신은 방금 {core}를 잘못 골랐습니다.", f"상황극) {core} 없이 버티는 당신에게.", f"{core} 살까 말까 3일째 고민 중인 사람 여기 모여."],
                "r1": [f"그 고민 제가 해봤는데요,\n결론부터 말하면 그냥 사는 게 맞아요.", "고민할 시간에 써보는 게 나아요."],
                "r2": [f"{'가격도 '+price_txt+'이고' if price_txt else '부담도 없고'}\n{feat+' 되니까' if feat else '막상 쓰니'} 후회 없어요.", "고민이 무색할 만큼 만족이에요."],
                "r3": ["3일 고민한 게 아까울 정도예요.", "그냥 사세요, 후회 안 해요."],
                "link": ["고민 끝내드릴게요 밑에.", "여기요."],
                "end": [f"당신의 3일을 아껴드립니다.\n{deeplink}", f"고민 끝. 여기요.\n{deeplink}"],
            },
        }
        P = POOLS.get(TONE, POOLS["friendly"])
        r4 = f"{R(P['link'])}\n{deeplink}\n\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다"
        r5 = f"{R(P['end'])}\n\n#{core} " + R(["#추천템", "#내돈내산", "#꿀템", f"#{core}"])
        parts = [R(P["posts"]), R(P["r1"]), R(P["r2"]), R(P["r3"]), r4, r5]
        return "\n===THREAD===\n".join(parts)

    # ── 인스타: 감성, 매번 다른 캡션·해시태그 ──
    if channel == "insta":
        opens = [
            f"✨ {name} ✨", f"🤍 {core} 기록 🤍", f"📌 요즘 최애템 : {core}",
            f"⭐ {name} ⭐", f"💫 데일리 {core} 💫",
        ]
        bodies = [
            f"요즘 데일리로 챙기는 {core} 🤍",
            f"{core} 몇 번을 재구매하는지 모르겠어요",
            f"한번 쓰면 계속 찾게 되는 {core} 있잖아요",
            "친구들이 자꾸 물어봐서 공유해요",
            "고민하다 샀는데 완전 만족 중이에요",
            f"{feat+' ' if feat else ''}{core} 찾다가 정착한 아이템",
            f"{core} 이거 진짜 물건이에요",
        ]
        guides = [
            "자세한 건 프로필 링크 확인 👆", "구매처는 프로필 링크에 🔗",
            "링크는 프로필에 걸어뒀어요 👆",
        ]
        base_tags = ["#쿠팡추천", "#데일리템", "#추천템", "#내돈내산", "#일상템", "#꿀템", "#살림템"]
        tags = f"#{core} " + " ".join(random.sample(base_tags, 4))
        body = (f"{R(opens)}\n\n{R(bodies)}\n"
                f"{'가격 '+price_txt+' / ' if price_txt else ''}{R(guides)}\n\n"
                f"👉 {deeplink}\n\n{tags}")
        return append_disclosure(body)

    # ── 유튜브: 설명란, 매번 다른 인트로 ──
    if channel == "youtube":
        intros = [
            f"📌 {name} 상세정보",
            f"📌 오늘 영상에서 소개한 {core}",
            f"📌 많이 물어보신 {name} 정보",
        ]
        descs = [
            "영상에서 소개한 제품이에요! 아래 링크에서 확인하실 수 있습니다.",
            "많은 분들이 궁금해하셔서 링크 남겨드려요.",
            "제가 직접 쓰고 추천드리는 제품입니다.",
        ]
        body = (f"{R(intros)}\n\n{R(descs)}\n"
                f"{'💰 가격: '+price_txt if price_txt else ''}\n\n"
                f"🔗 구매 링크\n{deeplink}\n\n"
                f"───────────\n"
                f"⏱ 타임스탬프\n00:00 인트로\n00:30 제품 소개\n02:00 사용 후기\n\n"
                f"👍 도움 되셨다면 좋아요와 구독 부탁드려요!")
        return append_disclosure(body)

    # ── 블로그(네이버): 긴 글, 매번 다른 제목·인트로·소제목 ──
    titles = [
        f"[{name} 솔직 후기 & 구매 정보]",
        f"[내돈내산] {name} 3주 사용 후기",
        f"{name}, 사기 전에 이거 보세요",
        f"[추천] {core} 고민이라면 {name} 어때요?",
        f"{name} 써보고 정리한 장단점",
        f"요즘 뜨는 {name}, 진짜 괜찮을까?",
        f"{core} 뭐 살지 고민이라면 (feat. {name})",
        f"{name} 한 달 써본 리얼 후기",
        f"솔직히 말하는 {name} 후기",
        f"{name} 구매 전 꼭 알아야 할 것",
        f"[비교] {name} 사길 잘했다 싶은 이유",
    ]
    intros_by_tone = {
        "friendly": [
            f"안녕하세요! 오늘은 요즘 많이 찾으시는 {name}에 대해 소개해드릴게요.",
            f"안녕하세요~ 이번 포스팅은 제가 직접 써본 {name} 후기예요.",
            f"제가 최근에 산 {name}, 생각보다 만족스러워서 공유해요.",
        ],
        "polite": [
            f"안녕하세요. 오늘은 {name}에 대한 정보를 정리해 소개드리겠습니다.",
            f"이번 포스팅에서는 {name}을(를) 직접 사용한 후기를 말씀드리겠습니다.",
            f"{name} 구매를 고민하시는 분들께 도움이 되고자 후기를 남깁니다.",
        ],
        "expert": [
            f"{name}의 특징과 실사용 성능을 항목별로 분석해보겠습니다.",
            f"이 글에서는 {name}을(를) 객관적 기준으로 살펴봅니다.",
            f"{name} 구매 전 체크해야 할 핵심 포인트를 정리했습니다.",
        ],
        "casual": [
            f"{name} 써봤는데 솔직하게 적어봄.",
            f"{core} 살까 말까 고민했는데 그냥 질렀다. 후기 시작.",
            f"{name} 별 기대 안 했는데 의외였음. 정리해봄.",
        ],
    }
    intros = intros_by_tone.get(TONE, intros_by_tone["friendly"])
    sub1 = R(["■ 어떤 제품인가요?", "■ 왜 이걸 골랐나요?", "■ 첫인상은?", "■ 구매 계기", "■ 이 제품을 선택한 이유"])
    desc1 = R([
        f"{cat_line} 만족도가 높아서 추천드리는 제품이에요. ",
        f"여러 제품 비교하다가 이걸로 정착했어요. {cat_line} 확실히 다르더라고요. ",
        f"가성비랑 품질 둘 다 잡은 느낌이라 소개드려요. {cat_line} 좋았어요. ",
        f"솔직히 처음엔 반신반의했는데 {cat_line} 생각이 바뀌었어요. ",
        f"{cat_line} 왜 인기 있는지 알겠더라고요. ",
    ])
    sub2 = R(["■ 구매는 여기서", "■ 어디서 사나요?", "■ 최저가 확인", "■ 구매 링크", "■ 어디서 사는 게 좋을까"])
    sub3 = R(["■ 마무리", "■ 총평", "■ 정리하며", "■ 끝으로", "■ 한줄 요약"])
    outro = R([
        "구매에 도움이 되셨길 바라요. 궁금한 점은 댓글로 남겨주세요!",
        "긴 글 읽어주셔서 감사해요. 궁금한 거 있으면 댓글 주세요!",
        "다음에 더 좋은 정보로 찾아올게요. 도움 되셨다면 공감 눌러주세요!",
        "제 후기가 선택에 도움이 됐으면 좋겠어요. 다음에 또 봐요!",
        "고민하시는 분들께 조금이나마 도움이 됐길 바랍니다:)",
    ])
    body = (f"{R(titles)}\n\n{R(intros)}\n\n"
            f"{sub1}\n{desc1}"
            f"{'현재 가격은 '+price_txt+' 정도예요. ' if price_txt else ''}"
            f"자세한 스펙과 최신 가격은 아래 링크에서 확인하실 수 있어요.\n\n"
            f"{sub2}\n👉 {name} 최저가 확인하기: {deeplink}\n\n"
            f"{sub3}\n{outro}")
    if info and info.get("image"):
        body += f"\n\n[상품 이미지]\n{info['image']}"
    return append_disclosure(body)


# ══════════════ 자동 게시 / HTML 내보내기 ══════════════

def build_naver_html(product_name, deeplink, draft_text, info=None):
    """네이버 블로그용 완성 HTML — 이미지+글+링크 포함. 복붙/다운로드용.
    네이버 에디터에 붙여넣으면 이미지와 서식이 그대로 들어가게 인라인 스타일."""
    img = (info or {}).get("image")
    price = ""
    if info and info.get("price"):
        price = f"{int(info['price']):,}원"
    # 본문 줄바꿈 → <p>/<br>
    paras = []
    for block in draft_text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        safe = (block.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                     .replace("\n", "<br>"))
        # 소제목(■ 로 시작)은 강조
        if block.startswith("■"):
            paras.append(f'<h3 style="font-size:18px;font-weight:700;color:#1a1a1a;margin:24px 0 8px">{safe.replace("■","").strip()}</h3>')
        elif block.startswith("---") or "쿠팡 파트너스 활동" in block:
            paras.append(f'<p style="font-size:12px;color:#888;margin-top:28px;padding-top:12px;border-top:1px solid #eee">{safe}</p>')
        else:
            paras.append(f'<p style="font-size:15px;line-height:1.8;color:#333;margin:12px 0">{safe}</p>')
    body_html = "\n".join(paras)

    img_html = ""
    if img:
        img_html = f'<p style="text-align:center;margin:20px 0"><img src="{img}" alt="{product_name}" style="max-width:100%;border-radius:8px"></p>'

    btn_html = (f'<p style="text-align:center;margin:28px 0">'
                f'<a href="{deeplink}" target="_blank" rel="nofollow sponsored" '
                f'style="display:inline-block;background:#03c75a;color:#fff;font-weight:700;'
                f'padding:14px 28px;border-radius:8px;text-decoration:none;font-size:16px">'
                f'👉 {product_name} 최저가 확인하기</a></p>')

    return f'''<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>{product_name} 후기</title></head>
<body style="max-width:700px;margin:0 auto;padding:20px;font-family:'맑은 고딕',sans-serif">
{img_html}
{body_html}
{btn_html}
</body></html>'''


def zernio_list_accounts(api_key):
    """연결된 계정 상세 목록 → [{platform, accountId, name}]. 계정 선택용."""
    try:
        req = urllib.request.Request("https://zernio.com/api/v1/accounts",
            headers={"Authorization": f"Bearer {api_key}"}, method="GET")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            data = json.loads(r.read().decode())
        out = []
        for acc in data.get("accounts", []):
            out.append({"platform": acc.get("platform"),
                        "accountId": acc.get("_id"),
                        "name": acc.get("displayName") or acc.get("username") or "계정",
                        "active": acc.get("isActive", True)})
        return out
    except Exception:
        return []


def _zernio_accounts(api_key):
    """연결된 계정 목록 조회 → {platform: accountId} 매핑."""
    try:
        req = urllib.request.Request("https://zernio.com/api/v1/accounts",
            headers={"Authorization": f"Bearer {api_key}"}, method="GET")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            data = json.loads(r.read().decode())
        mapping = {}
        for acc in data.get("accounts", []):
            plat = acc.get("platform")
            aid = acc.get("_id")
            if plat and aid and plat not in mapping:
                mapping[plat] = aid
        return mapping
    except Exception:
        return {}


def zernio_publish(api_key, platforms, content, media_urls=None, account_ids=None, thread_items=None, as_draft=False, scheduled_for=None):
    """Zernio API로 SNS 게시. scheduled_for(ISO8601) 주면 예약 게시.
    as_draft=True면 발행 안 하고 Zernio에 초안 저장."""
    if not api_key:
        return {"ok": False, "error": "not_connected"}
    accounts = _zernio_accounts(api_key)
    if not accounts:
        return {"ok": False, "error": "no_accounts", "detail": "연결된 SNS 계정이 없어요"}
    plat_map = {"x": "twitter"}
    account_ids = account_ids or {}
    targets = []
    for p in platforms:
        zp = plat_map.get(p, p)
        aid = account_ids.get(p) or account_ids.get(zp) or accounts.get(zp)
        if aid:
            entry = {"platform": zp, "accountId": aid}
            if thread_items and zp in ("threads", "twitter", "bluesky"):
                items = []
                for i, txt in enumerate(thread_items):
                    it = {"content": txt}
                    if i == 0 and media_urls:
                        it["mediaItems"] = [{"type": "image", "url": u} for u in media_urls]
                    items.append(it)
                entry["platformSpecificData"] = {"threadItems": items}
            targets.append(entry)
    if not targets:
        connected = ", ".join(accounts.keys()) or "없음"
        return {"ok": False, "error": "platform_not_connected",
                "detail": f"해당 플랫폼이 연결 안 됨 (연결된 것: {connected})"}
    payload = {"content": content, "platforms": targets}
    # 예약 게시 > 초안 > 즉시 게시
    if scheduled_for:
        payload["scheduledFor"] = scheduled_for
    elif not as_draft:
        payload["publishNow"] = True
    if media_urls and not thread_items:
        payload["mediaItems"] = [{"type": "image", "url": u} for u in media_urls]
    try:
        req = urllib.request.Request("https://zernio.com/api/v1/posts",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
            return {"ok": True, "data": json.loads(r.read().decode())}
    except urllib.error.HTTPError as e:
        detail = ""
        try: detail = e.read().decode()[:250]
        except Exception: pass
        return {"ok": False, "error": f"http_{e.code}", "detail": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


# ── Claude API: 주제 먼저 생성 (개인 API 키 사용) ──
# ── 쿠팡 검색 키워드 규칙 ────────────────────────────────
# 키워드는 "주제"가 아니다. 쿠팡 검색창에 그대로 쳤을 때 상품이 나오는 말이어야 한다.
KEYWORD_RULES = '''키워드 규칙 (가장 자주 틀리는 부분이다. 정확히 지켜라):

키워드 = 쿠팡 검색창에 그대로 붙여넣었을 때 "상품이 쭉 나오는" 말.
주제·현상·감정·행동이 아니라 ★사람이 돈 주고 사는 물건★의 이름이다.

[통과] 냉감 매트 / 제습기 / 실내 건조대 / 세탁조 클리너 / 차량용 햇빛가리개
       무선 선풍기 / 방수팩 / 펫 쿨매트 / 코세척기 / 온수매트
[탈락] 열대야 극복 (현상)      → 냉감 매트
[탈락] 숙면 방법 (행동)        → 냉감 이불
[탈락] 여름철 관리 (추상)      → 제습기
[탈락] 빨래 냄새 (증상)        → 세탁조 클리너
[탈락] 시원함 (감정)           → 서큘레이터
[탈락] 다이슨 에어랩 (브랜드)  → 고데기   ※특정 브랜드명 금지, 일반 상품군으로
[탈락] 아이 건강 (범주)        → 유아 비타민

체크:
- 2~4어절, 12자 이내.
- "~하는 법", "~방법", "~이유", "~관리", "~극복", "~팁", "~추천" 이 붙으면 전부 탈락.
- 명사로 끝나야 한다. 동사·형용사로 끝나면 탈락.
- 주제 제목을 그대로 베끼지 마라. 그 주제를 해결해줄 ★물건★을 써라.
- 한 주제당 서로 다른 물건 3~4개. (같은 물건의 변형 나열 금지)
'''

_KW_BAD_TAIL = ("방법", "하는 법", "이유", "관리", "극복", "예방", "대처", "팁", "추천",
                "습관", "생활", "노하우", "가이드", "총정리", "비교", "후기", "체험")
_KW_ABSTRACT = ("건강", "행복", "시원함", "쾌적", "청결", "위생", "안전", "편안",
                "스트레스", "피로", "고민", "문제", "효과", "증상")


def keyword_gate(kw, topic_title=""):
    """이 키워드를 쿠팡 검색창에 치면 상품이 나오는가? 아니면 사유를 돌려준다."""
    k = (kw or "").strip()
    if not k:
        return "빈 키워드"
    if len(k) > 12:
        return f"'{k}' — 너무 길다(12자 초과). 물건 이름만 남겨라"
    if len(k.split()) > 4:
        return f"'{k}' — 어절이 너무 많다. 물건 이름만 남겨라"
    for t in _KW_BAD_TAIL:
        if t in k:
            return f"'{k}' — '{t}'는 행동·개념이다. 그걸 해결해줄 물건 이름으로 바꿔라"
    if k in _KW_ABSTRACT:
        return f"'{k}' — 추상어다. 살 수 있는 물건이 아니다"
    if topic_title and k.replace(" ", "") == topic_title.replace(" ", ""):
        return f"'{k}' — 주제 제목을 그대로 썼다. 그 주제를 해결할 물건을 써라"
    if re.search(r"(하다|되다|한다|된다|는다|었다|았다)$", k):
        return f"'{k}' — 서술형으로 끝난다. 명사(물건)로 끝내라"
    return None


# ── 상황→실제 쿠팡 상품 사전 (LLM 없이 키워드를 채우는 원천) ──
_TOPIC_PRODUCTS = {
    "더위|열대야|폭염|에어컨|냉방|시원": ["냉감 매트", "쿨패드", "서큘레이터", "무선 선풍기", "넥밴드 선풍기", "제빙기", "쿨토시"],
    "장마|습도|습기|눅눅|곰팡이|제습": ["제습기", "제습제", "실내 건조대", "곰팡이 제거제", "제습 봉", "빨래 건조기"],
    "빨래|세탁|냄새|쉰내|섬유": ["세탁조 클리너", "세탁세제", "섬유유연제", "빨래 건조대", "탈취제", "실내 건조대"],
    "잠|숙면|불면|잠자리|수면|베개|매트리스": ["냉감 이불", "경추 베개", "쿨매트", "메모리폼 토퍼", "수면 안대", "바디필로우"],
    "모기|벌레|해충|방충": ["모기 퇴치기", "방충망", "모기향", "해충 트랩", "전기 모기채", "포충기"],
    "세균|위생|살균|소독|청결": ["살균기", "손소독제", "행주", "식기 건조대", "도마 살균", "청소 티슈"],
    "차|자동차|운전|주차|차량": ["차량용 햇빛가리개", "차량용 선풍기", "블랙박스", "차량 방향제", "핸드폰 거치대", "썬팅 필름"],
    "반려|강아지|고양이|펫|댕댕|냥": ["펫 쿨매트", "펫 급수기", "쿨 밴드", "탈취 스프레이", "빗", "자동 급식기"],
    "아기|육아|유아|신생아|기저귀": ["기저귀", "물티슈", "젖병 소독기", "베이비 모니터", "아기 쿨매트", "수유등"],
    "피부|햇빛|자외선|건조|보습": ["선크림", "수분 크림", "미스트", "핸드크림", "보습 마스크팩", "바디로션"],
    "운동|다이어트|홈트|헬스": ["요가 매트", "폼롤러", "아령", "저항 밴드", "단백질 쉐이크", "스마트 워치"],
    "청소|정리|수납|먼지": ["무선 청소기", "정리 수납함", "밀대 걸레", "먼지 떨이", "수납 정리대", "청소포"],
    "주방|설거지|요리|식기": ["주방세제", "수세미", "실리콘 장갑", "식기 건조대", "밀폐용기", "도마"],
    "캠핑|차박|아웃도어|등산": ["폴딩 체어", "캠핑 랜턴", "타프", "아이스박스", "휴대용 버너", "매트"],
    "커피|카페|음료|텀블러": ["텀블러", "보온병", "핸드드립 세트", "커피 원두", "휴대용 믹서", "제빙기"],
}
_FALLBACK_PRODUCTS = ["보조배터리", "USB 선풍기", "수납함", "물티슈", "멀티탭", "차량용 거치대"]


def _rule_products_for(title):
    """제목이 매칭되는 카테고리의 상품 리스트 전체를 돌려준다(규칙 우선용)."""
    for pat, prods in _TOPIC_PRODUCTS.items():
        if any(w in title for w in pat.split("|")):
            return prods
    return []


def _suggest_keyword(title, seen):
    """제목에 맞는 실제 쿠팡 상품 하나를 즉석에서 고른다. (LLM 안 부름)"""
    for pat, prods in _TOPIC_PRODUCTS.items():
        if any(w in title for w in pat.split("|")):
            for p in prods:
                if p not in seen and not keyword_gate(p, title):
                    return p
    for p in _FALLBACK_PRODUCTS:
        if p not in seen:
            return p
    return None


def _fix_keywords(api_key, topics, max_tokens=1500):
    """탈락한 키워드만 콕 집어 다시 뽑는다. 주제 본문은 건드리지 않는다."""
    bad = []
    for t in topics:
        title = t.get("title", "")
        for k in (t.get("keywords") or []):
            why = keyword_gate(k, title)
            if why:
                bad.append({"topic": title, "keyword": k, "why": why})
    if not bad:
        return topics
    sys_p = (
        "너는 쿠팡 검색 키워드 전문가다. 아래 '탈락한 키워드'를 규칙에 맞는 것으로 교체하라.\n"
        "주제 제목은 절대 바꾸지 마라. 키워드만 바꾼다.\n\n" + KEYWORD_RULES +
        '\n출력은 JSON만: {"fixed":[{"topic":"주제제목","old":"탈락키워드","new":"대체키워드"}]}'
    )
    user_p = "탈락 목록:\n" + "\n".join(
        f"- 주제 [{b['topic']}] 의 '{b['keyword']}' → {b['why']}" for b in bad[:12])
    r = llm_chat(api_key, sys_p, user_p, max_tokens=max_tokens)
    if not r.get("ok"):
        return topics
    try:
        fixes = _parse_json_out(r["text"]).get("fixed", [])
    except Exception:
        return topics
    fmap = {(f.get("topic", ""), f.get("old", "")): f.get("new", "")
            for f in fixes if isinstance(f, dict)}
    for t in topics:
        title = t.get("title", "")
        out = []
        for k in (t.get("keywords") or []):
            if keyword_gate(k, title):
                nk = fmap.get((title, k), "")
                if nk and not keyword_gate(nk, title):
                    out.append(nk)          # 고쳐졌으면 채택
                # 못 고쳤으면 버린다 (나쁜 키워드를 남기느니 없는 게 낫다)
            else:
                out.append(k)
        t["keywords"] = out[:4]
    return topics


def claude_generate_topics(api_key, user_topic="", now_str="", n=8):
    """주제 생성 (무료 Gemini/OpenRouter 또는 Claude). 상품이 아니라 '주제'가 먼저."""
    if not api_key:
        return {"ok": False, "error": "no_key"}
    # ★가볍게. 키워드는 서버 규칙이 채운다 → 모델은 주제·훅·상품씨앗 1개만.
    #  출력 토큰이 확 줄어 = 생성이 훨씬 빠르다.
    sys_prompt = (
        "당신은 쿠팡 파트너스 쓰레드 마케팅 전략가입니다. "
        "상품이 아니라 '주제'가 먼저입니다. 사람들이 공감할 상황·고민을 주제로 잡고, "
        "죄책감 반전('내 탓이 아니라 구조 탓')·상황 공감·의외의 사실 같은 훅을 씁니다.\n"
        "각 주제마다: 제목(title), 훅 한 문장(hook), 그 상황을 해결할 대표 상품군 1개(seed).\n"
        "seed는 쿠팡에서 파는 '물건 이름'이어야 합니다 (예: 제습기, 냉감 매트, 세탁조 클리너). "
        "'방법'·'관리'·'극복' 같은 개념어 금지.\n"
        "반드시 JSON만 출력. 형식: "
        '{"topics":[{"title":"...","hook":"...","seed":"물건이름"}]}'
    )
    user_msg = f"현재: {now_str}\n"
    if user_topic.strip():
        user_msg += f"요청 주제/방향: {user_topic}\n{n}개의 세부 주제를 뽑아주세요."
    else:
        user_msg += f"지금 시각·계절에 맞는 주제 {n}개를 제안해주세요. 표본이 넓은 걸로."

    # ★max_tokens를 1400으로 줄였더니 JSON이 중간에 잘려 parse_error가 났다(2026-07-13).
    #  반대로 약한 모델(LLM7 등)에 8개를 시키면 출력이 잘려서 또 깨진다.
    #  → 모델 체급에 맞게 부담을 조절한다. 최후 보루는 '적게, 확실히'.
    _prov = detect_llm_provider(api_key)
    if _prov in SLOW_FREE:
        n = min(n, 5)
        _budget = 1400
    else:
        _budget = 2200
    user_msg = re.sub(r"\d+개의 세부 주제", f"{n}개의 세부 주제", user_msg)
    user_msg = re.sub(r"주제 \d+개를 제안", f"주제 {n}개를 제안", user_msg)
    r = llm_chat(api_key, sys_prompt, user_msg, max_tokens=_budget)
    if not r.get("ok"):
        return r
    raw = r.get("text") or ""
    try:
        parsed = _parse_json_out(raw)
    except Exception as e:
        return {"ok": False, "error": "parse_error",
                "detail": f"{type(e).__name__}: {str(e)[:60]} | 응답머리: {raw[:80]}"}
    # 모델이 {"topics":[...]} 대신 배열만 뱉는 경우도 받아준다
    if isinstance(parsed, list):
        topics = parsed
    elif isinstance(parsed, dict):
        topics = parsed.get("topics") or parsed.get("items") or parsed.get("data") or []
        if isinstance(topics, dict):
            topics = [topics]
    else:
        topics = []
    topics = [t for t in topics if isinstance(t, dict) and t.get("title")]
    if not topics:
        return {"ok": False, "error": "empty_topics",
                "detail": f"파싱은 됐는데 주제가 비었어요. 응답머리: {raw[:80]}"}
    # seed(대표 상품 1개)를 keywords 리스트로 승격 → 아래 규칙 확장이 3~4개로 채운다
    for t in topics:
        t["title"] = scrub_garbled(t.get("title", ""))
        if t.get("hook"): t["hook"] = scrub_garbled(t["hook"])
        if not t.get("keywords"):
            sd = scrub_garbled((t.get("seed") or "").strip())
            # seed가 깨졌거나 게이트 탈락이면 제목 기반 규칙 추천으로 대체
            if not sd or len(sd) < 2 or keyword_gate(sd, t.get("title","")):
                sd = _suggest_keyword(t.get("title",""), set())
            t["keywords"] = [sd] if sd else []

    # ★키워드는 규칙으로 즉시 정리한다 (LLM 재호출 없음 = 속도).
    #  ★규칙이 주제를 알아보면(예: 열대야→냉감매트) 규칙 상품을 '앞세운다'.
    #   모델 seed(예: 열대야→백열전구 같은 엉뚱한 연상)보다 규칙을 신뢰한다.
    for t in topics:
        title = t.get("title", "")
        good, seen = [], set()

        # 1) 규칙이 이 주제를 아는지 먼저 본다 → 알면 규칙 상품을 맨 앞에
        rule_prods = _rule_products_for(title)
        for rp in rule_prods:
            if rp not in seen and not keyword_gate(rp, title):
                good.append(rp); seen.add(rp)
            if len(good) >= 2:      # 규칙 상품 최대 2개 선점
                break

        # 2) 모델 seed/키워드 중 게이트 통과한 것만 뒤에 붙인다
        for k in (t.get("keywords") or []):
            k = scrub_garbled((k or "").strip())
            if len(k) < 2 or keyword_gate(k, title):
                continue
            if k not in seen:
                good.append(k); seen.add(k)

        # 3) 3개 미만이면 규칙 상품으로 더 채운다
        while len(good) < 3:
            repl = _suggest_keyword(title, seen)
            if not repl: break
            good.append(repl); seen.add(repl)
        t["keywords"] = good[:4]
    topics = [t for t in topics if (t.get("keywords") or [])]
    if not topics:
        return {"ok": False, "error": "no_keywords",
                "detail": "쓸만한 쿠팡 검색 키워드를 못 뽑았어요. 다시 시도해 주세요."}
    return {"ok": True, "topics": topics}


# ── Claude가 직접 쓰레드 글 작성 (템플릿 아님 → 제품마다 완전히 다른 글) ──
TONE_GUIDE = {
    "friendly": "친근한 존댓말", "polite": "정중한 존댓말",
    "expert": "전문가 톤, 단정적", "casual": "반말 솔직담백",
    "excited": "텐션 높은 반말", "minimal": "아주 짧고 건조한 단문",
    "story": "경험담 서사체", "curious": "질문형 호기심 유발",
    "warm": "다정하고 따뜻한 존댓말", "witty": "위트있는 자조 섞인 반말",
    "honest": "내돈내산 찐후기, 장단점 다 말함", "trendy": "MZ 인터넷 밈 말투",
    "calm": "차분하고 담백한 존댓말", "urgent": "지금 아니면 늦는다는 긴박함",
    "friend": "친구한테 말하듯 반말",
    "gap": "정보격차 — '진짜 원인은 따로 있다'로 궁금증 유발, 답글에서 반드시 해소",
    "loss": "손실회피 — '싼 거 여러 번 사다 결국 더 비쌌다'는 후회 프레임",
    "amplify": "문제증폭 — 작은 증상 방치하면 커진다(과장·공포조장 금지, 실제 공감만)",
    "social": "사회적증거 — '요즘 조용히 다들 쓰더라'",
    "parent": "부모 공감 — 실재하는 육아 걱정에 공감하고 안심시킴(불안 조장 금지)",
    "reverse": "통념반전 — '비쌀수록 좋을 줄 알았는데 아니더라'",
    "overshare": "정밀 오버셰어링 — 아주 구체적이고 사적인 순간 고백",
    "observe": "구체적 관찰 — 디테일한 순간 묘사로 몰입",
    "onlyme": "나만그런줄 — '나만 불편한 줄 알았는데 다들 그렇더라'",
    "pov": "POV 상황극 — 특정 순간에 독자를 놓기",
}

# ══════════════════════════════════════════════════════════════
#  상품 이해 계층
#  쿠팡 상품명은 마케팅 수식어 범벅이다.
#  "○○ 초강력 원샷 세탁세제 대용량 3L" 를 그대로 던지면
#  모델이 '원샷'을 술 마시는 원샷으로 읽고 엉뚱한 글을 쓴다. (2026-07-13 실제 사고)
#  → 이름을 씻고, 이 물건이 "무엇인지"를 먼저 확정한 뒤 글을 쓰게 한다.
# ══════════════════════════════════════════════════════════════

# 상품명에 붙는 마케팅 수식어 = 뜻이 아니라 장식. 문자 그대로 읽으면 안 된다.
_PROMO_WORDS = [
    "초강력", "강력", "원샷", "한방", "끝판왕", "역대급", "프리미엄", "명품", "고급",
    "정품", "국내생산", "국산", "무료배송", "당일발송", "로켓배송", "무료", "특가", "할인",
    "대용량", "초대용량", "가정용", "업소용", "다용도", "만능", "신상", "신형", "최신",
    "인기", "베스트", "히트", "추천", "필수", "가성비", "혜자", "리뉴얼", "업그레이드",
    "실속", "알뜰", "묶음", "세트", "기획", "증정", "사은품", "선물용", "휴대용",
]
_UNIT_PAT = r"\d+\s*(개입|개|매|장|팩|박스|세트|ml|mL|L|리터|g|kg|호|인용|단|겹|구|롤|캔|병|포|정)"


def clean_product_name(name):
    """마케팅 노이즈를 벗겨 '이게 무슨 물건인지'만 남긴다."""
    n = str(name or "")
    n = re.sub(r"[\[\(\{][^\]\)\}]*[\]\)\}]", " ", n)      # [로켓배송] (1+1) 제거
    n = re.sub(r"\d+\s*[+＋]\s*\d+", " ", n)                    # 1+1
    n = re.sub(_UNIT_PAT, " ", n)                                  # 3L, 20개입
    for w in _PROMO_WORDS:
        n = n.replace(w, " ")
    n = re.sub(r"[^가-힣A-Za-z0-9 ]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n or str(name or "")


_BRIEF_CACHE = {}

# ── 규칙 기반 상품 판별 (LLM 안 부르고 즉시 끝내는 빠른 길) ──
# (분류, 매칭어, 하는 일, 쓰는 상황, 금지 소재)
_RULE_BRIEF = [
    ("세탁세제", ["세탁세제", "세제", "섬유유연", "울샴푸", "표백제", "산소계"],
     "빨래할 때 세탁기에 넣어 때와 냄새를 빼는 화학용품",
     "빨래를 돌릴 때", ["술", "음주", "마시", "원샷", "먹", "복용", "맛"]),
    ("세탁조 클리너", ["세탁조", "통세척"],
     "세탁기 통 안쪽의 물때와 곰팡이를 녹여내는 세정제",
     "세탁기에서 쉰내가 날 때", ["술", "마시", "먹", "복용"]),
    ("주방세제", ["주방세제", "설거지"],
     "기름때를 닦아내는 설거지용 세제", "설거지할 때", ["술", "마시", "먹", "복용"]),
    ("청소용 세정제", ["클리너", "세정제", "락스", "곰팡이제거", "탈취제", "제거제"],
     "때·곰팡이·냄새를 제거하는 청소용 화학용품", "청소할 때", ["술", "마시", "먹", "복용", "맛"]),
    ("냉감 침구", ["쿨매트", "냉감", "쿨패드", "인견", "대나무매트"],
     "체온과 열을 빼앗아 잘 때 덜 덥게 해주는 침구", "여름밤 잘 때", ["먹", "마시", "복용", "충전"]),
    ("매트리스·토퍼", ["토퍼", "매트리스", "침대패드"],
     "침대 위에 깔아 잠자리 느낌을 바꾸는 침구", "잘 때", ["먹", "마시", "복용"]),
    ("베개", ["베개", "경추", "필로우"],
     "머리와 목을 받쳐주는 침구", "잘 때", ["먹", "마시", "복용"]),
    ("제습기", ["제습기", "제습"], "공기 중 습기를 빨아들여 눅눅함을 없애는 가전",
     "장마철·습한 날", ["먹", "마시", "복용", "바르"]),
    ("선풍기·서큘레이터", ["선풍기", "서큘레이터", "무선팬", "넥밴드"],
     "바람을 만들어 공기를 돌리는 가전", "더울 때", ["먹", "마시", "복용", "바르"]),
    ("에어컨 관련", ["에어컨", "냉방기"], "실내 온도를 낮추는 가전", "더울 때", ["먹", "마시", "복용"]),
    ("공기청정기", ["공기청정", "청정기"], "미세먼지를 걸러내는 가전", "공기가 나쁠 때",
     ["먹", "마시", "복용", "바르"]),
    ("건조기·건조대", ["건조기", "건조대", "빨래건조"], "빨래를 말리는 물건", "빨래를 넌 뒤",
     ["먹", "마시", "복용"]),
    ("영양제", ["영양제", "비타민", "유산균", "홍삼", "오메가", "루테인", "프로바이오"],
     "몸에 부족한 성분을 채우려고 먹는 것", "매일 챙겨 먹을 때", ["바르", "세탁", "청소"]),
    ("스킨케어", ["크림", "로션", "세럼", "선크림", "토너", "에센스", "마스크팩"],
     "피부에 바르는 화장품", "세수 후", ["먹", "마시", "원샷", "복용", "섭취"]),
    ("샴푸·바디", ["샴푸", "린스", "트리트먼트", "바디워시", "비누", "폼클렌징"],
     "몸이나 머리를 씻는 데 쓰는 것", "씻을 때", ["먹", "마시", "원샷", "복용"]),
    ("모기·해충 용품", ["모기", "해충", "벌레", "방충", "살충"],
     "벌레를 쫓거나 잡는 물건", "벌레가 나올 때", ["먹", "마시", "복용", "맛"]),
    ("차량용품", ["차량용", "자동차", "타이어", "블랙박스", "햇빛가리개", "썬팅"],
     "차에 쓰는 물건", "운전하거나 주차할 때", ["먹", "마시", "복용", "세탁"]),
    ("반려동물 용품", ["반려", "강아지", "고양이", "펫 ", "사료", "캣", "댕댕"],
     "반려동물에게 쓰는 물건", "아이를 돌볼 때", ["원샷", "술"]),
    # ── 확장 ──
    ("면도기·그루밍", ["면도기", "쉐이버", "제모", "트리머", "면도날"],
     "털을 깎거나 정리하는 도구", "면도할 때", ["먹", "마시", "복용", "세탁"]),
    ("칫솔·구강", ["칫솔", "치실", "구강세정", "가글", "치약", "워터픽"],
     "이를 닦고 입안을 관리하는 물건", "양치할 때", ["원샷", "술", "세탁"]),
    ("헤어 도구", ["드라이기", "고데기", "에어랩", "매직기", "헤어롤"],
     "머리를 말리거나 스타일링하는 도구", "머리 손질할 때", ["먹", "마시", "복용"]),
    ("가방·파우치", ["가방", "백팩", "파우치", "크로스백", "토트백", "에코백"],
     "물건을 담아 드는 물건", "외출할 때", ["먹", "마시", "복용", "충전"]),
    ("텀블러·보온병", ["텀블러", "보온병", "물병", "워터보틀"],
     "음료를 담아 다니는 용기", "물·커피 마실 때", ["세탁", "복용"]),
    ("이어폰·헤드셋", ["이어폰", "헤드셋", "블루투스", "에어팟", "버즈"],
     "귀에 꽂아 소리를 듣는 기기", "음악·통화할 때", ["먹", "마시", "복용", "세탁"]),
    ("보조배터리·충전", ["보조배터리", "충전기", "케이블", "무선충전"],
     "기기를 충전하는 물건", "배터리 부족할 때", ["먹", "마시", "복용", "세탁"]),
    ("거치대·홀더", ["거치대", "holder", "스탠드", "마운트"],
     "기기를 받쳐 고정하는 물건", "영상 볼 때·운전할 때", ["먹", "마시", "복용"]),
    ("수납·정리", ["수납", "정리함", "선반", "옷걸이", "행거", "리빙박스"],
     "물건을 정리해 보관하는 물건", "정리할 때", ["먹", "마시", "복용"]),
    ("청소기", ["청소기", "물걸레", "스팀청소", "밀대"],
     "먼지·물때를 빨아들이거나 닦는 청소 도구", "청소할 때", ["먹", "마시", "복용"]),
    ("주방가전", ["에어프라이어", "전기밥솥", "인덕션", "믹서", "블렌더", "토스터"],
     "음식을 조리하는 가전", "요리할 때", ["바르", "세탁", "충전"]),
    ("밀폐용기·주방", ["밀폐용기", "반찬통", "도시락", "보관용기", "지퍼백"],
     "음식을 담아 보관하는 그릇", "음식 보관할 때", ["복용", "충전"]),
    ("침구·이불", ["이불", "차렵", "베개커버", "침대커버", "패드"],
     "덮고 자는 침구", "잘 때", ["먹", "마시", "복용", "충전"]),
    ("커튼·블라인드", ["커튼", "블라인드", "암막", "차양"],
     "빛을 가리는 창 가리개", "햇빛 들 때", ["먹", "마시", "복용", "세탁"]),
    ("선크림·자외선", ["선크림", "선블록", "자외선차단", "선스틱"],
     "피부에 발라 자외선을 막는 화장품", "외출 전", ["먹", "마시", "원샷", "복용"]),
    ("마스크팩·기초", ["마스크팩", "앰플", "essence", "에센스", "패드"],
     "피부에 올리거나 바르는 기초 화장품", "세안 후", ["먹", "마시", "원샷", "복용"]),
    ("색조화장", ["립스틱", "틴트", "쿠션", "파운데이션", "아이섀도", "마스카라"],
     "얼굴에 바르는 색조 화장품", "화장할 때", ["먹", "마시", "원샷", "복용"]),
    ("건강기능식품", ["콜라겐", "루테인", "밀크씨슬", "가르시니아", "효소", "차전자피"],
     "몸을 위해 먹는 건강기능식품", "챙겨 먹을 때", ["바르", "세탁", "청소"]),
    ("운동용품", ["요가매트", "폼롤러", "아령", "덤벨", "밴드", "짐볼"],
     "운동할 때 쓰는 도구", "운동할 때", ["먹", "마시", "복용"]),
    ("캠핑·아웃도어", ["텐트", "타프", "캠핑", "랜턴", "코펠", "화로대", "폴딩"],
     "야외 활동에 쓰는 장비", "캠핑·야외에서", ["먹", "마시", "복용"]),
    ("우산·우비", ["우산", "우비", "레인코트", "장화"],
     "비를 막는 물건", "비 올 때", ["먹", "마시", "복용", "충전"]),
    ("모니터·pc", ["모니터", "키보드", "마우스", "노트북", "받침대"],
     "컴퓨터로 일할 때 쓰는 기기", "작업할 때", ["먹", "마시", "복용", "세탁"]),
    ("완구·유아", ["장난감", "블록", "인형", "퍼즐", "교구"],
     "아이가 가지고 노는 물건", "아이가 놀 때", ["원샷", "술"]),
    ("기저귀·육아", ["기저귀", "물티슈", "분유", "젖병", "이유식", "쪽쪽이"],
     "아기를 돌볼 때 쓰는 물건", "육아할 때", ["원샷", "술"]),
]


def _rule_brief(cleaned, raw):
    hay = f"{cleaned} {raw}"
    for cat, keys, what, when, forbid in _RULE_BRIEF:
        if any(k.strip() in hay for k in keys):
            return {"category": cat, "what": what, "when": when,
                    "who": "", "problem": "", "forbid": forbid}
    return None



def product_brief(api_key, raw_name, price=None):
    """이 물건이 무엇인지 먼저 확정한다. 글은 그 다음이다.
    반환: {category, what, when, who, problem, forbid}"""
    key = (raw_name or "")[:80]
    if key in _BRIEF_CACHE:
        return _BRIEF_CACHE[key]

    cleaned = clean_product_name(raw_name)

    # ★규칙으로 먼저 판별한다. 대부분 여기서 끝난다 = LLM 호출 1회 절약.
    #  (글 한 번 쓰는 데 brief + 초안 + 수정 = 최대 4콜이던 게 속도의 주범이었다)
    rule = _rule_brief(cleaned, raw_name)
    if rule:
        _BRIEF_CACHE[key] = rule
        return rule

    sys_p = (
        "너는 쿠팡 상품명을 읽고 '이게 무슨 물건인지'를 정확히 판별하는 분석가다.\n"
        "★가장 중요: 상품명에 들어있는 마케팅 수식어를 문자 그대로 해석하지 마라.\n"
        "  - '원샷 세탁세제'의 '원샷'은 술이 아니라 '한 번에'라는 뜻의 광고 수식어다.\n"
        "  - '끝판왕', '한방', '역대급', '초강력'도 마찬가지로 뜻이 없는 장식이다.\n"
        "  - 수식어를 빼고 남는 ★명사★가 이 물건의 정체다.\n"
        "판별 결과를 JSON으로만 출력한다.\n"
        '{"category":"물건의 종류(예: 세탁세제)",'
        '"what":"이 물건이 실제로 하는 일 한 문장",'
        '"when":"언제 쓰나(구체적 상황)",'
        '"who":"누가 사나",'
        '"problem":"이 물건이 해결하는 불편 한 문장",'
        '"forbid":["이 상품과 무관해서 글에 절대 나오면 안 되는 소재 3개"]}'
    )
    user_p = f"원본 상품명: {raw_name}\n수식어 제거 후: {cleaned}\n" + (f"가격: {int(price):,}원" if price else "")
    r = llm_chat(api_key, sys_p, user_p, max_tokens=800)
    brief = {"category": cleaned, "what": "", "when": "", "who": "", "problem": "", "forbid": []}
    if r.get("ok"):
        try:
            d = _parse_json_out(r["text"])
            if isinstance(d, dict) and d.get("category"):
                brief.update({k: d.get(k, brief[k]) for k in brief})
                if not isinstance(brief["forbid"], list):
                    brief["forbid"] = []
        except Exception:
            pass
    _BRIEF_CACHE[key] = brief
    return brief


def product_mismatch(posts, brief):
    """글이 이 상품과 무관한 소리를 하고 있는지 기계로 검사."""
    joined = " ".join(str(p) for p in posts)
    fails = []
    cat = (brief.get("category") or "").strip()
    # '세탁세제'라고 썼는데 글엔 '세제'만 있어도 통과시켜야 한다 → 부분일치(n-gram)로 본다
    core_words = []
    for w in re.split(r"\s+", cat):
        if len(w) >= 2:
            core_words.append(w)
            for n in (3, 2):
                core_words += [w[i:i+n] for i in range(len(w) - n + 1)]
    core_words = [w for w in dict.fromkeys(core_words) if len(w) >= 2]
    if core_words and not any(w in joined for w in core_words):
        fails.append(f"이 글에 '{cat}'가 무슨 물건인지 드러나는 대목이 없다. "
                     f"'{brief.get('problem') or cat}' 상황이 글에 보여야 한다.")
    for bad in (brief.get("forbid") or [])[:3]:
        b = str(bad).strip()
        if b and len(b) >= 2 and b in joined:
            fails.append(f"'{b}'는 이 상품과 무관한 소재다. 전부 빼라.")
    return fails


def claude_write_thread(api_key, product_name, deeplink, tone="friendly", price=None, extra="", fast=False):
    """쓰레드 6분할 작성. ★사람다움 최우선: few-shot + 휴머나이즈 규칙 + AI티 검출 재작성."""
    if not api_key:
        return {"ok": False, "error": "no_key"}
    tone_desc = TONE_GUIDE.get(tone, TONE_GUIDE["friendly"])
    price_line = f"가격: {int(price):,}원\n" if price else ""
    prov = detect_llm_provider(api_key)
    is_top = prov in TOP_TIER

    # ★글을 쓰기 전에 "이게 무슨 물건인지"부터 확정한다.
    brief = product_brief(api_key, product_name, price)
    brief_block = (
        "\n■ 이 상품이 무엇인지 (반드시 이 이해 위에서 써라):\n"
        f"- 종류: {brief.get('category')}\n"
        f"- 하는 일: {brief.get('what')}\n"
        f"- 쓰는 상황: {brief.get('when')}\n"
        f"- 사는 사람: {brief.get('who')}\n"
        f"- 해결하는 불편: {brief.get('problem')}\n"
        + (f"- 이 글에 나오면 안 되는 소재: {', '.join(brief.get('forbid') or [])}\n" if brief.get('forbid') else "")
        + "★상품명 속 '초강력·원샷·끝판왕·한방·역대급' 같은 말은 광고 수식어다. "
          "뜻이 없다. 문자 그대로 해석해서 글감으로 쓰면 그 글은 실패다.\n"
          "  (실제 사고: '원샷 세탁세제'를 보고 술 마시는 원샷 이야기를 썼다. 절대 이러지 마라.)\n"
    )

    base = (
        "너는 쿠팡 파트너스 쓰레드(Threads) 글을 쓰는 한국인이다. 마케터가 아니라 그냥 사람이다.\n"
        "★1순위: 사람이 쓴 글처럼. AI 티가 나면 그 글은 실패다.\n"
        "구조: 본글 1개 + 답글 5개. 본글에는 링크 절대 넣지 마라.\n"
        "답글1~3: 공감 → 원인/발견 → 변화(링크 없음). 답글4: 링크+고지문구. 답글5: 마무리+링크+해시태그 3개.\n"
        "답글4에 '(광고) 쿠팡파트너스 활동으로 수수료를 받습니다' 포함.\n"
        "각 글 2~3줄, 400자 이내.\n"
        "★★반드시 순수한 한국어로만 써라. 러시아어·중국어·일본어·라틴 특수문자를 "
        "한글 사이에 절대 섞지 마라(예: '창문이 уже 말라'❌). "
        "영어는 제품 고유명(KF94, SPF50)만 허용. 그 외 외국 문자가 하나라도 섞이면 완전 실패다.\n\n"
    )
    # ★Claude는 지시 없이도 한다. 무료 모델에는 사고 과정을 문자로 깔아준다.
    sys_prompt = (
        base
        + brief_block + "\n"
        + hook_block() + "\n"                        # ★첫 줄 훅 과학 (조회수의 핵심)
        + diversity_block() + "\n"                   # ★매번 다른 골격·화자·훅 (틀 복제 차단·모든 모델)
        + ("" if is_top else SCAFFOLD + "\n" + quirk_block(prov) + "\n")
        + HUMANIZE_RULES + "\n" + FEWSHOT + "\n" + QUALITY_RULES +
        '\n출력은 JSON만: {"posts":["본글","답글1","답글2","답글3","답글4","답글5"]}'
    )
    user_msg = (
        f"상품: {product_name}\n{price_line}링크: {deeplink}\n"
        f"말투/심리기제: {tone_desc}\n"
        f"{('추가 요청: '+extra) if extra else ''}\n\n"
        "예시들의 결(담백함·구체성·사람다움)을 그대로 따라 이 상품 글을 써라."
    )
    # ★초안 생성. 약한 모델이 프롬프트 예시를 그대로 뱉으면(플레이스홀더) 다시 시킨다.
    posts = []
    for _attempt in range(3):
        r = llm_chat(api_key, sys_prompt, user_msg
                     + ("\n\n※주의: '본글','답글1' 같은 자리표시자를 그대로 쓰지 말고 실제 글을 써라."
                        if _attempt else ""),
                     max_tokens=3000)
        if not r.get("ok"):
            if _attempt == 0:
                return r
            break
        try:
            cand = _parse_json_out(r["text"]).get("posts", [])
        except Exception:
            cand = []
        # 플레이스홀더 검사
        chk = quality_gate(cand, product_name)
        if chk == ["__PLACEHOLDER__"] or len(cand) < 4:
            continue     # 다시 시도
        posts = cand
        break
    if len(posts) < 4:
        return {"ok": False, "error": "bad_format",
                "detail": "모델이 실제 글 대신 예시를 반복했어요. 다른 AI로 시도해 주세요."}

    # ── 품질 루프 ────────────────────────────────────────────
    # Claude(유료)는 초안이 이미 좋다 → 패스를 아낀다.
    # 무료 모델은 초안이 약하지만 빠르다 → 그 속도를 패스에 쓴다.
    #   기계 검사(quality_gate) → 걸린 항목만 콕 집어 재작성(_fix_pass) → 반복
    if is_top:
        budget = 0 if fast else 1
    elif prov in FAST_FREE:
        budget = 1 if fast else 3        # ★기본은 1회만. 깊은 다듬기는 '품질 다듬기' 버튼에서.
    else:
        # 느린·약한 무료 모델(OpenRouter/LLM7/NVIDIA)은 초안이 부실하다.
        # fast여도 게이트 통과할 때까지 2회, 일반 모드는 3회까지 고친다.
        budget = 2 if fast else 3

    posts = repair_structure(posts, deeplink, product_name)   # ★먼저 구조를 못 박는다

    for _ in range(budget):
        fails = quality_gate(posts, product_name)
        if fails == ["__PLACEHOLDER__"]:
            # 재작성이 또 플레이스홀더면 그만 (구조 복구가 뒤에서 채운다)
            break
        fails = fails + product_mismatch(posts, brief)
        if not fails:
            break
        fixed = _fix_pass(api_key, product_name, tone_desc, posts, fails)
        if not fixed:
            break
        posts = fixed

    # 마지막 한 번은 항상 다듬기 (Claude 포함, fast일 땐 생략)
    if not fast:
        polished = _polish_pass(api_key, product_name, tone_desc, posts)
        if polished:
            posts = polished

    posts = repair_structure(posts, deeplink, product_name)   # 재작성 뒤 구조 재확정
    posts = [scrub_ai_artifacts(str(p)) for p in posts]
    posts = _strip_leading_product(posts, product_name)       # 본글 첫 문장 제품명 규칙 제거
    posts = _strip_weak_opener(posts)                         # 약한 오프너 도입부 규칙 제거
    remaining = quality_gate(posts, product_name) + product_mismatch(posts, brief)
    return {"ok": True, "content": "\n===THREAD===\n".join(posts),
            "provider": prov, "brief": brief, "quality_fails": remaining}


def _polish_pass(api_key, product_name, tone_desc, posts):
    """3패스: 마지막 다듬기 — 구체성·리듬·훅 강도를 한 단계 올린다."""
    sys_p = (
        "너는 최고의 한국어 카피 에디터다. 아래 쓰레드 글을 '한 단계 더' 끌어올려라.\n"
        "할 일:\n"
        "1) 본글 첫 문장을 더 구체적인 장면으로 (숫자·시간·행동이 보이게).\n"
        "2) 뻔한 문장을 하나 골라 그 사람만의 디테일로 교체.\n"
        "3) 문장 리듬을 다양하게 (짧은 문장 하나는 반드시).\n"
        "4) 답글5는 여운을 남기며 끝내라. 설명하지 마라.\n"
        "절대 하지 말 것: 광고 문구 추가, 과장, 이모지 늘리기, 문장 길이 균일화.\n"
        "구조(본글+답글5)와 링크·고지문구는 그대로.\n"
        + HUMANIZE_RULES +
        '\n출력은 JSON만: {"posts":["본글","답글1","답글2","답글3","답글4","답글5"]}'
    )
    user_p = f"상품: {product_name}\n말투: {tone_desc}\n\n원문:\n{json.dumps({'posts': posts}, ensure_ascii=False)}"
    r = llm_chat(api_key, sys_p, user_p, max_tokens=3000)
    if not r.get("ok"):
        return None
    try:
        out = _parse_json_out(r["text"]).get("posts", [])
        return out if len(out) >= 4 else None
    except Exception:
        return None


# ── 무료 LLM 지원: 키 접두어로 제공자 자동 감지 ──
# Gemini(AIza...) = 무료 티어 / OpenRouter(sk-or-...) = 무료 모델 / Anthropic(sk-ant-...) = 유료
def detect_llm_provider(api_key):
    k = (api_key or "").strip()
    if k.startswith("AIza"): return "gemini"
    if k.startswith("sk-or-"): return "openrouter"
    if k.startswith("gsk_"): return "groq"            # Groq — 무료·초고속(LPU)
    if k.startswith("csk-"): return "cerebras"        # Cerebras — 무료·최고속(웨이퍼)
    if k.startswith("nvapi-"): return "nvidia"        # NVIDIA NIM — 무료·일일한도 없음
    if k.startswith("ghp_") or k.startswith("github_pat_"): return "github"  # GitHub Models — 무료
    if k.startswith("sk-ant-"): return "anthropic"
    if k == "__free__": return "llm7"                 # 키 없이 쓰는 무료 AI
    if re.match(r"^[0-9a-f]{32}\.[A-Za-z0-9]{16}$", k): return "zai"        # Z.AI (GLM) — 무료
    return "unknown"


# ── OpenAI 호환 엔드포인트 공용 호출기 (Groq/Cerebras/NVIDIA/GitHub/OpenRouter/LLM7/Z.AI) ──
def _llm_openai_compat(name, url, api_key, models, sys_prompt, user_msg,
                       max_tokens, timeout=25, extra_headers=None, json_mode=True):
    _PROV = name
    models = _order(name, models)
    last = {}
    for m in models:
        payload = {"model": m, "max_tokens": max_tokens, "temperature": 1.0,
                   "messages": [{"role": "system", "content": sys_prompt},
                                {"role": "user", "content": user_msg}]}
        if json_mode and "JSON" in sys_prompt:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            headers.update(extra_headers)
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                         headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
                data = json.loads(r.read().decode())
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if text and text.strip():
                _sticky_ok(name, m)
                return {"ok": True, "text": text.strip(), "model": m}
            last = {"ok": False, "error": "empty"}
        except urllib.error.HTTPError as e:
            detail = ""
            try: detail = e.read().decode()[:200]
            except Exception: pass
            last = {"ok": False, "error": f"http_{e.code}", "detail": detail}
            if e.code in (401, 403): return last
            if e.code in RETRYABLE: _sticky_drop(_PROV)   # 과부하 → 기억한 모델 폐기
            continue
        except Exception as e:
            last = {"ok": False, "error": str(e)[:120]}
            continue
    return last or {"ok": False, "error": "no_response",
                    "detail": f"{name}: 모델이 응답하지 않았어요"}


def _llm_cerebras(api_key, sys_prompt, user_msg, max_tokens=3000):
    """Cerebras — 무료·초고속(~2,600 tok/s). 무료 티어는 컨텍스트 8K 상한."""
    return _llm_openai_compat(
        "cerebras", "https://api.cerebras.ai/v1/chat/completions", api_key,
        ["llama-3.3-70b", "gpt-oss-120b", "qwen-3-32b"],
        sys_prompt, user_msg, min(max_tokens, 6000), timeout=25)


def _llm_nvidia(api_key, sys_prompt, user_msg, max_tokens=3000):
    """NVIDIA NIM — 무료(개발자 프로그램), 일일 토큰 상한 없음."""
    return _llm_openai_compat(
        "nvidia", "https://integrate.api.nvidia.com/v1/chat/completions", api_key,
        ["meta/llama-3.3-70b-instruct", "qwen/qwen2.5-72b-instruct",
         "nvidia/nemotron-3-nano-30b-a3b"],
        sys_prompt, user_msg, max_tokens, timeout=30, json_mode=False)


def _llm_github(api_key, sys_prompt, user_msg, max_tokens=3000):
    """GitHub Models — GitHub 계정만 있으면 무료. gpt-4.1-mini 등."""
    return _llm_openai_compat(
        "github", "https://models.github.ai/inference/chat/completions", api_key,
        ["openai/gpt-4.1-mini", "meta/Meta-Llama-3.3-70B-Instruct", "openai/gpt-4o-mini"],
        sys_prompt, user_msg, min(max_tokens, 4000), timeout=30,
        extra_headers={"X-GitHub-Api-Version": "2022-11-28"})


def _llm_zai(api_key, sys_prompt, user_msg, max_tokens=3000):
    """Z.AI (Zhipu) — GLM-4.x Flash 영구 무료."""
    return _llm_openai_compat(
        "zai", "https://open.bigmodel.cn/api/paas/v4/chat/completions", api_key,
        ["glm-4.5-flash", "glm-4-flash"],
        sys_prompt, user_msg, max_tokens, timeout=30, json_mode=False)


def _llm_llm7(api_key, sys_prompt, user_msg, max_tokens=3000):
    """LLM7.io — ★키 없이 익명으로 쓰는 무료 AI. 회원가입도 필요 없다.
    (2026-07-13 실측: minimax-m2.7 익명 호출 1.5초, 한국어 정상. 익명 30 RPM)"""
    # 최후 보루다. 익명이라 rate limit이 빡세다(429/403) → 백오프하며 3회 재시도.
    import time as _t
    r = {}
    for _try in range(3):
        r = _llm_openai_compat(
            "llm7", "https://api.llm7.io/v1/chat/completions", None,
            ["codestral-latest", "minimax-m2.7", "deepseek-v4-flash"],  # 익명 열린 것 우선
            sys_prompt, user_msg, min(max_tokens, 4000), timeout=75, json_mode=False)
        if r.get("ok"):
            return r
        err = str(r.get("error", ""))
        if "429" in err or "403" in err:
            _t.sleep(1.5 * (_try + 1))    # 1.5s, 3s 백오프
            continue
        break
    return r


def _llm_groq(api_key, sys_prompt, user_msg, max_tokens=3000):
    """Groq — 무료 티어 (console.groq.com). Llama 4 / Qwen 등 고성능."""
    _PROV = "groq"
    models = _order("groq", ["llama-3.3-70b-versatile", "qwen/qwen3-32b", "llama-3.1-8b-instant"])
    last = {}
    for m in models:
        payload = {"model": m, "max_tokens": max_tokens, "temperature": 1.0,
                   "messages": [{"role": "system", "content": sys_prompt},
                                {"role": "user", "content": user_msg}],
                   "response_format": {"type": "json_object"}}
        try:
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(req, timeout=25, context=_ctx) as r:
                data = json.loads(r.read().decode())
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if text and text.strip():
                _sticky_ok("groq", m)
                return {"ok": True, "text": text.strip(), "model": m}
            last = {"ok": False, "error": "empty"}
        except urllib.error.HTTPError as e:
            detail = ""
            try: detail = e.read().decode()[:200]
            except Exception: pass
            last = {"ok": False, "error": f"http_{e.code}", "detail": detail}
            if e.code in (401, 403): return last
            if e.code in RETRYABLE: _sticky_drop(_PROV)   # 과부하 → 기억한 모델 폐기
            continue
        except Exception as e:
            last = {"ok": False, "error": str(e)[:120]}; continue
    return last


def _llm_gemini(api_key, sys_prompt, user_msg, max_tokens=1200):
    """Google Gemini — 무료 티어 (aistudio.google.com에서 키 발급)."""
    _PROV = "gemini"
    models = _order("gemini", ["gemini-2.5-flash", "gemini-2.0-flash",
                               "gemini-2.5-flash-lite", "gemini-flash-latest"])
    last = {}
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": sys_prompt}]},
            "contents": [{"parts": [{"text": user_msg}]}],
            "generationConfig": {"temperature": 1.0, "maxOutputTokens": min(max(max_tokens, 1500), 6144),
                                 "responseMimeType": "application/json",
                                 "thinkingConfig": {"thinkingBudget": 0}},
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30, context=_ctx) as r:
                data = json.loads(r.read().decode())
            cands = data.get("candidates", [])
            if not cands:
                last = {"ok": False, "error": "no_candidates"}; continue
            text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))
            _sticky_ok("gemini", m)
            return {"ok": True, "text": text.strip(), "model": m}
        except urllib.error.HTTPError as e:
            detail = ""
            try: detail = e.read().decode()[:200]
            except Exception: pass
            last = {"ok": False, "error": f"http_{e.code}", "detail": detail}
            if e.code in (401, 403): return last
            if e.code in RETRYABLE: _sticky_drop(_PROV)   # 과부하 → 기억한 모델 폐기
            continue
        except Exception as e:
            last = {"ok": False, "error": str(e)[:120]}; continue
    return last


_OR_CACHE = {"models": [], "at": 0}

def _openrouter_free_models():
    """살아있는 무료 모델을 실시간 조회 (모델 ID가 바뀌어도 안 깨지게). 1시간 캐시."""
    now = time.time()
    if _OR_CACHE["models"] and now - _OR_CACHE["at"] < 3600:
        return _OR_CACHE["models"]
    # 선호 순서 (한국어·창작 강한 대형 우선)
    PREFER = ["llama-3.3-70b", "gpt-oss-120b", "qwen3-next-80b", "gemma-4-31b",
              "nemotron-3-super", "gemma-4-26b", "nemotron-3-nano-30b", "hy3"]
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/models")
        data = json.loads(urllib.request.urlopen(req, timeout=8, context=_ctx).read())
        free = []
        for m in data.get("data", []):
            mid = m.get("id", "")
            pricing = m.get("pricing", {})
            if str(pricing.get("prompt")) not in ("0", "0.0"):
                continue
            if any(k in mid for k in ["coder", "lyria", "vision", "embed", "safety", "-vl"]):
                continue
            free.append(mid)
        # 선호 순서로 정렬
        def rank(mid):
            for i, p in enumerate(PREFER):
                if p in mid:
                    return i
            return 99
        free.sort(key=rank)
        if free:
            _OR_CACHE["models"] = free[:6]
            _OR_CACHE["at"] = now
            return _OR_CACHE["models"]
    except Exception:
        pass
    # 조회 실패 시 하드코딩 폴백
    return ["meta-llama/llama-3.3-70b-instruct:free", "openai/gpt-oss-120b:free",
            "qwen/qwen3-next-80b-a3b-instruct:free", "google/gemma-4-31b-it:free"]


def _llm_openrouter(api_key, sys_prompt, user_msg, max_tokens=3000):
    """OpenRouter — :free 모델만 사용 (0원). 살아있는 모델 실시간 조회."""
    _PROV = "openrouter"
    # ★무료 모델은 큐 대기가 붙어 느리다. 실측상 빠른 축부터 태운다.
    FAST = ["meta-llama/llama-3.3-70b-instruct:free", "openai/gpt-oss-120b:free",
            "google/gemma-4-31b-it:free", "minimax/minimax-m2.5:free"]
    avail = _openrouter_free_models()
    ranked = [m for m in FAST if m in avail] + [m for m in avail if m not in FAST]
    models = _order("openrouter", ranked)[:4]      # 4개까지만 시도(폴백 지옥 방지)
    last = {}
    for m in models:
        payload = {"model": m, "max_tokens": max_tokens, "temperature": 1.0,
                   "messages": [{"role": "system", "content": sys_prompt},
                                {"role": "user", "content": user_msg}]}
        try:
            req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                         "HTTP-Referer": "https://linklynk.onrender.com", "X-Title": "LinkLynk"},
                method="POST")
            with urllib.request.urlopen(req, timeout=20, context=_ctx) as r:
                data = json.loads(r.read().decode())
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if text and text.strip():
                _sticky_ok("openrouter", m)
                return {"ok": True, "text": text.strip(), "model": m}
            last = {"ok": False, "error": "empty"}
        except urllib.error.HTTPError as e:
            detail = ""
            try: detail = e.read().decode()[:200]
            except Exception: pass
            last = {"ok": False, "error": f"http_{e.code}", "detail": detail}
            if e.code in (401, 403): return last
            if e.code in RETRYABLE: _sticky_drop(_PROV)   # 과부하 → 기억한 모델 폐기
            continue
        except Exception as e:
            last = {"ok": False, "error": str(e)[:120]}; continue
    return last


def _llm_anthropic(api_key, sys_prompt, user_msg, max_tokens=1200):
    """Anthropic Claude — 유료(크레딧 필요)."""
    _PROV = "anthropic"
    models = ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-sonnet-5"]
    last = {}
    for m in models:
        payload = {"model": m, "max_tokens": max_tokens, "temperature": 1.0,
                   "system": sys_prompt, "messages": [{"role": "user", "content": user_msg}]}
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode(),
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60, context=_ctx) as r:
                data = json.loads(r.read().decode())
            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            return {"ok": True, "text": text.strip()}
        except urllib.error.HTTPError as e:
            detail = ""
            try: detail = e.read().decode()[:200]
            except Exception: pass
            last = {"ok": False, "error": f"http_{e.code}", "detail": detail}
            if e.code in (401, 403): return last
            if e.code in RETRYABLE: _sticky_drop(_PROV)   # 과부하 → 기억한 모델 폐기
            continue
        except Exception as e:
            last = {"ok": False, "error": str(e)[:120]}; continue
    return last


def llm_chat(api_key, sys_prompt, user_msg, max_tokens=1200):
    """어떤 키든 자동 라우팅 (Gemini 무료 / OpenRouter 무료 / Claude 유료)."""
    p = detect_llm_provider(api_key)
    if p == "gemini": return _llm_gemini(api_key, sys_prompt, user_msg, max_tokens)
    if p == "openrouter": return _llm_openrouter(api_key, sys_prompt, user_msg, max_tokens)
    if p == "groq": return _llm_groq(api_key, sys_prompt, user_msg, max_tokens)
    if p == "cerebras": return _llm_cerebras(api_key, sys_prompt, user_msg, max_tokens)
    if p == "nvidia": return _llm_nvidia(api_key, sys_prompt, user_msg, max_tokens)
    if p == "github": return _llm_github(api_key, sys_prompt, user_msg, max_tokens)
    if p == "zai": return _llm_zai(api_key, sys_prompt, user_msg, max_tokens)
    if p == "llm7": return _llm_llm7(api_key, sys_prompt, user_msg, max_tokens)
    if p == "anthropic": return _llm_anthropic(api_key, sys_prompt, user_msg, max_tokens)
    return {"ok": False, "error": "unknown_key",
            "detail": "키 형식을 알 수 없어요 (AIza… / gsk_… / csk-… / nvapi-… / ghp_… / sk-or-… / sk-ant-…)"}


def _parse_json_out(text):
    """LLM JSON 파싱. 잘린 응답(Unterminated string)도 최대한 복구."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t).strip()
    # 1) 정상 파싱
    try:
        return json.loads(t)
    except Exception:
        pass
    # 2) 앞뒤 잡음 제거 후 재시도 ({ ... } 만 추출)
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # 3) 잘린 JSON 복구: 문자열 배열 항목만 뽑아내기
    #    "posts":["...","...", ... 형태에서 완성된 문자열만 수집
    items = re.findall(r'"((?:[^"\\]|\\.)*)"', t)
    # key 이름(posts/topics 등) 제거하고 실제 값만
    KEYS = {"posts", "topics", "title", "time_context", "sample", "angle", "hook", "keywords"}
    vals = [json.loads('"%s"' % i) for i in items if i not in KEYS]
    if "posts" in t and len(vals) >= 4:
        return {"posts": vals[:6]}
    if "topics" in t:
        raise ValueError("topics 복구 불가")
    raise ValueError("JSON 복구 실패")


# ── 퀄리티 핵심: 실제 잘 쓴 글을 few-shot 예시로 (사용자 검증 샘플) ──
import random as _random

# ── 골격(뼈대) 12종 — 본글이 시작되는 방식이 매번 달라진다 ──
_SKELETONS = [
    "계산형: 낭비한 돈/시간을 실제로 계산해보는 데서 시작. ('작년에 이거 사느라 쓴 돈 계산해봤다')",
    "발견형: 원인이 딴 데 있었다는 걸 뒤늦게 안 순간. ('이게 사실 X 때문이 아니더라')",
    "장면형: 특정 시각·장소의 구체적 한 컷. ('새벽 3시, 냉장고 문 앞에서')",
    "고백형: 남들은 별거 아니라는데 나만 신경 쓰이던 것. ('나만 이런가 싶었는데')",
    "대조형: 전에는 이랬는데 지금은 이렇다. ('한 달 전만 해도 매일 이랬다')",
    "질문형: 누가 던진 질문에서 시작. ('친구가 이거 왜 샀냐고 묻길래')",
    "실패담형: 엉뚱한 걸 먼저 사봤다가 실패한 얘기. ('처음엔 싼 거 샀다가')",
    "습관형: 무의식적으로 반복하던 행동을 자각. ('매번 자기 전에 이걸 확인하던 버릇')",
    "숫자충격형: 의외의 수치 하나를 던지고 시작. ('하루 8시간을 이 자세로 있더라')",
    "후회형: 진작 할 걸 그랬다는 자조. ('3년을 엉뚱한 데서 찾았다')",
    "비교견적형: 남의 것과 비교하다 깨달음. ('옆자리 사람 건 왜 다르지 했더니')",
    "계절체감형: 계절이 바뀌며 몸으로 느낀 변화. ('올해 여름은 유독')",
    "타인관찰형: 남을 보다가 나를 돌아본 순간. ('옆자리 동료가 매번')",
    "루틴붕괴형: 당연하던 일상이 어긋난 지점. ('매일 하던 건데 어느 날')",
    "물음표형: 스스로도 이상하다 여긴 것. ('이게 왜 이러지 싶었다')",
    "before만형: 힘들었던 과거만 담담히. ('그때는 몰랐다')",
    "영수증형: 구체적 지출 내역을 나열. ('영수증 보니까')",
    "새벽형: 잠 못 드는 밤의 독백. ('다들 자는데 나만')",
    "지적당함형: 남이 내 문제를 먼저 짚어준 순간. ('엄마가 너 왜 자꾸 그러냐고')",
    "포기직전형: 이제 그냥 포기하려던 참이었다. ('그냥 이렇게 사나 했는데')",
    "우연발견형: 원래 목적과 다른 걸 하다 얻어걸림. ('딴 거 사러 갔다가')",
    "비용충격형: 예상보다 훨씬 큰 대가를 뒤늦게 인지. ('청구서 보고 알았다')",
    "타이밍형: 하필 그때 벌어진 일. ('하필 중요한 날 아침에')",
    "무의식반복형: 나도 모르게 계속 하던 것. ('생각해보니 하루에 몇 번씩')",
    "남탓하다가형: 딴 걸 탓하다 진짜 원인 발견. ('날씨 탓인 줄 알았는데')",
    "귀찮음극복형: 미루다 미루다 결국. ('귀찮아서 안 하다가')",
    "작은승리형: 사소하지만 확실한 개선. ('별거 아닌데 이게 그렇게')",
    "관성깨짐형: 늘 그러려니 하던 걸 의심. ('원래 이런 건 줄 알았지')",
    "몸이먼저형: 머리보다 몸이 먼저 안 것. ('아침에 일어나는데 어깨가')",
    "비교당함형: 남과 비교되어 자각. ('친구 집 갔다가')",
    "돈세는형: 통장·가계부를 들여다보다. ('한 달 쓴 거 정리하다가')",
    "계기사건형: 딱 하나의 사건이 방아쇠. ('그날 그 일 이후로')",
    "습관교정형: 나쁜 습관을 바꾸려던 시도. ('안 하려고 했는데')",
    "체념후반전형: 포기했다가 뜻밖에 해결. ('안 될 줄 알았는데')",
    "관찰기록형: 며칠간 지켜본 변화. ('일주일 지켜봤더니')",
    "충동구매반성형: 홧김에 샀는데 결과는. ('홧김에 질렀는데')",
    "루틴자랑형: 요즘 생긴 소소한 루틴. ('요즘 아침마다')",
    "실수담형: 잘못 알고 있던 걸 정정. ('완전 반대로 알고 있었다')",
    "환절기형: 계절 바뀔 때마다 겪는 것. ('환절기만 되면')",
    "가족언급형: 가족 때문에/덕분에. ('와이프가 하도 그래서')",
]

# ── 화자 페르소나 8종 — 말투·문장 길이·종결이 매번 달라진다 ──
_VOICES = [
    "20대 후반 자취 남성 / 반말 / 건조하고 짧게 / '~함' '~더라' 종결 / 감정 절제",
    "30대 워킹맘 / 존댓말 / 문장 길고 정서적 / '~더라고요' / 공감 유도",
    "40대 가장 / 반존대 섞임 / 계산적·현실적 / 돈 얘기 자주 / 담백",
    "대학생 / 반말 / 툭툭 던지는 구어체 / 리듬 가볍게",
    "꼼꼼한 30대 남성 / 존댓말 / 디테일 집착 / 숫자·스펙 대신 체감 위주",
    "육아 3년차 / 반말 / 지친 톤 / 짧은 한숨 같은 문장 / 현실 육아",
    "직장인 여성 / 존댓말 / 효율 중시 / '결국' '어차피' 자주 / 실용",
    "느긋한 자영업자 / 반말 / 여유로운 만연체 / 경험담 위주",
    "1인가구 30대 남 / 반말 / 무심한 듯 디테일 챙김 / '그냥' 자주",
    "복학생 / 존댓말~반말 오감 / 솔직 담백 / 허세 없음",
    "맞벌이 40대 / 존댓말 / 시간 없음 강조 / 효율·실용 극대",
    "예민한 20대 / 반말 / 감각 묘사 섬세 / 작은 차이 잘 느낌",
    "50대 주부 / 존댓말 / 살림 노하우 톤 / 알뜰함 / 경험 신뢰",
    "20대 대학원생 / 반말 / 분석적 / '따져보니' '결론은' / 논리 위주",
    "프리랜서 30대 / 반말 / 자유로운 톤 / 불규칙한 생활 언급",
    "신혼 30대 / 존댓말 / 둘이 사는 얘기 / '우리집' 자주 / 다정",
    "운동하는 20대 / 반말 / 몸 상태 민감 / 컨디션 언급 잦음",
    "출퇴근 2시간 직장인 / 반말 / 피곤 강조 / 이동 중 상황 자주",
    "집순이 20대 / 반말 / 집 안에서의 디테일 / 나른한 톤",
    "예산 빠듯한 사회초년생 / 존댓말 / 가성비 예민 / 후회·다짐 자주",
    "반려동물 키우는 30대 / 반말 / 아이(반려동물) 중심 서술 / 다정",
    "야근 잦은 직장인 / 반말 / 늦은 밤 톤 / 피로 누적 언급",
    "정리 좋아하는 40대 / 존댓말 / 깔끔함 추구 / 전후 비교 선명",
    "감성 20대 / 반말 / 분위기·기분 묘사 / 단 빈 감성은 아님(구체 동반)",
    "실속파 50대 남성 / 반존대 / 무뚝뚝 / 핵심만 / 결과 중시",
    "재택근무 30대 / 반말 / 집=사무실 상황 / 작은 불편에 민감",
    "장거리 운전 잦은 40대 / 반말 / 차 안 상황 자주 / 현실적",
    "미니멀 지향 30대 / 존댓말 / 물건 늘리기 싫어함 / 신중한 구매",
]

# ── 훅 전략 10종 — 첫 문장이 스크롤을 멈추게 하는 방식 ──
_HOOKS = [
    "통념 반박: 다들 A라고 아는데 사실 B다",
    "손실 강조: 이거 모르면 계속 돈/시간 새는 중",
    "공범 의식: 나만 그런 거 아니지? 하는 은근한 동의 요청",
    "반전 고백: 인정하기 싫지만 사실은 이랬다",
    "구체 수치: 검증 가능한 숫자 하나를 대뜸 던짐",
    "결핍 자극: 남들 다 아는데 나만 몰랐던 것",
    "즉시성: 바로 지금 이 순간의 문제로 훅",
    "죄책감 반전: 내 탓인 줄 알았는데 구조 탓이었다",
    "호기심 갭: 원인을 말하기 직전에 멈춤",
    "역설: 비싼 게 오히려 쌌다 / 편한 게 오히려 불편했다",
    "권위 부정: 다들 하라는 대로 했는데 틀렸더라",
    "시간 압축: 몇 년을 고생한 게 하루아침에",
    "사소함 강조: 아무것도 아닌 것 같은데 이게 컸다",
    "비밀 폭로: 아무도 안 알려주던 걸 말하듯",
    "자기 부정: 나 같은 사람도 됐으니",
    "숫자 대비: 3만원 아끼려다 30만원 날린 얘기",
    "감각 훅: 그 축축함/뻐근함을 아는 사람은 안다",
    "타이밍 훅: 하필 그 순간에",
    "반복 강조: 매일, 하루도 빠짐없이 겪던 것",
    "결과 선공개: 결론부터 말하면 이렇게 됐다",
    "질문 던지기: 왜 아무도 이걸 말 안 해줬지?",
    "후회 훅: 진작 알았으면 좋았을 걸",
    "대비 훅: 남들은 편한데 나만 이러고 있었다",
    "발견의 순간: 어느 날 문득 알아버린 것",
]


# 감각 디테일 은행 — 모델이 '구체'를 못 떠올릴 때 이 층위에서 하나 고르게
_DETAIL_AXES = [
    "촉각(축축함/뽀송함/뻐근함/미끈거림/서늘함)",
    "시간(새벽 몇 시/며칠째/몇 분 만에/일주일 뒤)",
    "돈(얼마 썼다/얼마 아꼈다/몇 번 사서 버렸다)",
    "비교(전에 쓰던 것과의 차이/옆사람 것과의 차이)",
    "타인의 반응(가족·친구가 뭐라고 했는지)",
    "실패 경험(엉뚱한 걸 먼저 사봤다가)",
    "몸의 신호(어깨·목·눈·피부가 보낸 신호)",
    "공간(방/침대/현관/차 안에서의 구체적 위치)",
    "소리(윙윙거림/조용해짐/삐걱임/알림음)",
    "냄새(쉰내/비누향/퀴퀴함/새것 냄새)",
    "온도(미지근함/서늘함/후끈함/체온)",
    "무게·부피(묵직함/가벼움/한 손에 잡힘/자리 차지)",
    "횟수(하루 몇 번/한 주에 몇 번 반복)",
    "지속(며칠째/몇 주 지나도/처음 그대로)",
    "색·시각(누레짐/맑아짐/뿌옇던 게/선명해짐)",
    "습관 변화(안 하게 된 행동/새로 생긴 루틴)",
    "돌발 상황(하필 그때 벌어진 일)",
    "계절·날씨(장마철/한겨울/환절기 특유의)",
    "가족·동거인(같이 사는 사람이 겪은 변화)",
    "이전 제품과의 대비(그거 쓸 때는 이랬는데)",
]

# ── 첫 줄(본글 오프너) 과학 ──────────────────────────────
# Threads 조회수는 첫 1~2줄에서 결정된다. "스크롤을 멈추게 하는" 오프너 유형 15종.
# 각 유형은 '왜 멈추는가'의 심리 기제가 다르다.
_OPENER_TYPES = [
    ("자기지목", "읽는 사람이 '어 내 얘긴데' 하게. 특정 상황을 콕 집어서. 예: '자기 전에 폰 충전기 못 찾아서 더듬는 사람'"),
    ("반전선언", "당연한 통념을 첫 줄에서 뒤집어. 예: '비싼 게 답이 아니었다'"),
    ("숫자충격", "예상 밖 수치를 대뜸. 예: '한 달에 이걸로 만원 넘게 버리고 있었다'"),
    ("미완성문장", "말하다 만 것처럼 끊어서 다음이 궁금하게. 예: '이거 알기 전까지는 진짜…'"),
    ("금기고백", "남들 잘 안 하는 솔직한 인정. 예: '사실 3년 동안 잘못 쓰고 있었음'"),
    ("질문직격", "읽는 사람에게 바로 묻기. 예: '다들 이거 어떻게 참고 살았어요?'"),
    ("장면던지기", "설명 없이 한 장면부터. 예: '새벽 2시. 또 깼다.'"),
    ("손실경고", "지금 손해 보는 중임을 알려. 예: '이거 모르면 계속 돈 나감'"),
    ("비교충격", "남과 나의 격차. 예: '옆자리 사람은 왜 안 더워 보이지 했는데'"),
    ("시간대비", "긴 고생이 짧게 해결. 예: '3년 고생한 게 3일 만에'"),
    ("역설훅", "모순처럼 들리는 진실. 예: '더 싼데 더 오래 씀'"),
    ("공범호출", "'나만 그런 거 아니지?' 예: '이거 나만 불편한 거 아니죠?'"),
    ("전후분절", "before를 한 줄로 강렬하게. 예: '작년 여름을 어떻게 버텼나 싶다'"),
    ("의외원인", "진짜 원인이 딴 데. 예: '더위 탓인 줄 알았는데 아니었다'"),
    ("사소한위화감", "작은데 계속 거슬리던 것. 예: '별거 아닌데 매일 신경 쓰이던 게 있었다'"),
]

# 첫 줄이 '약한 오프너'인지 검사 (조회수 죽이는 시작들)
_WEAK_OPENERS = [
    "안녕", "오늘은", "여러분", "요즘", "최근", "이번에", "제가", "저는",
    "소개할", "추천할", "리뷰", "후기를", "구매한", "써보니",
]


def _opener_is_weak(first_line):
    """첫 줄이 스크롤을 못 멈추는 약한 시작인가?"""
    fl = (first_line or "").strip()
    if len(fl) < 6:
        return True   # 너무 짧아 맥락 없음
    if len(fl) > 45:
        return True   # 첫 줄이 너무 길면 안 읽힘
    for w in _WEAK_OPENERS:
        if fl.startswith(w):
            return True
    # 제품 소개형 시작
    if any(x in fl[:12] for x in ["소개", "추천", "리뷰", "후기"]):
        return True
    return False


def hook_block():
    ot = _random.choice(_OPENER_TYPES)
    return (
        "■ 첫 줄(본글 오프너) — 이게 조회수를 결정한다. 사활을 걸어라:\n"
        f"  · 이번 오프너 유형: [{ot[0]}] {ot[1]}\n"
        "  · 첫 줄은 6~40자. 너무 길면 안 읽히고 너무 짧으면 맥락이 없다.\n"
        "  · 첫 줄에 절대 넣지 마라: 인사('안녕'), '오늘은/요즘/제가', 제품 소개('추천할게요').\n"
        "  · 첫 줄만 읽고도 '다음이 궁금'하거나 '내 얘기네' 싶어야 한다.\n"
        "  · 둘째 줄에서 첫 줄의 긴장을 이어받아라. 바로 설명으로 풀지 마라.\n"
    )


def diversity_block():
    """매 호출마다 골격·화자·훅·디테일축을 랜덤 지정 → 같은 틀 복제 차단."""
    sk = _random.choice(_SKELETONS)
    vc = _random.choice(_VOICES)
    hk = _random.choice(_HOOKS)
    dt = _random.sample(_DETAIL_AXES, 2)
    return (
        "■ 이번 글의 지정 설정 (반드시 이대로. 예시 문장은 절대 베끼지 마라):\n"
        f"  · 본글 골격: {sk}\n"
        f"  · 화자 페르소나: {vc}\n"
        f"  · 훅 전략: {hk}\n"
        f"  · 이 글에 반드시 녹일 감각 디테일 2축: {dt[0]} + {dt[1]}\n"
        "  · 답글 5개는 서로 다른 리듬: 하나는 한 줄(단, 내용 있는 한 줄), 하나는 길게, "
        "하나는 자문자답, 하나는 숫자 포함. 다섯 개가 비슷하면 실패.\n"
        "  · ★가장 중요: 감정을 '이름 붙이지' 말고(편안하다/위로된다 금지) "
        "그 감정이 나온 '장면'을 보여줘라. 짧아도 손에 잡히는 구체가 있어야 한다.\n"
    )


FEWSHOT = '''다음은 실제로 반응이 좋았던 글들이다. 이 결의 담백함·구체성을 그대로 따라라.

[예시1 — 정보격차 / 반말 건조 / 경추베개]
본글: 아침에 목 뻐근한 거, 사실 베개 때문 아닐 수도 있음.
답글1: 진짜 원인은 따로 있는데 대부분 이걸 모름.\\n나도 3년을 엉뚱한 데서 찾았고.
답글2: 목이 자는 동안 15도만 꺾여도 아침에 결린다더라.\\n그래서 높이 아니라 '각도' 잡아주는 베개로 바꿈.
답글3: 바꾸고 일주일 만에 목 돌릴 때 뚝뚝 나던 게 없어짐.
답글4: 밑에 링크.\\n{링크}\\n\\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다.
답글5: 원인 알고 나니까 허무하더라. 진작 바꿀걸.\\n{링크}\\n\\n#꿀잠 #목통증 #경추베개

[예시2 — 정밀 오버셰어링 / 존댓말 / 홈캠]
본글: 아기 재워놓고 문 닫고 나오는데, 문틈으로 3초를 더 쳐다보고 있는 나를 발견함.
답글1: 혹시 자다가 이불 얼굴 덮으면 어쩌지, 그 생각 하나로요.\\n이 마음, 부모면 다 아실 거예요.
답글2: 홈캠 달고부터는 그 3초를 폰으로 대신하게 됐어요.\\n어디 있든 실시간으로 보이고 소리도 감지되니까요.
답글3: 별거 아닌 것 같아도 그 3초의 불안이 사라진 게 컸어요.
답글4: 혹시 저 같은 분 계실까 봐 남겨둘게요.\\n{링크}\\n\\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다.
답글5: 그 작은 불안들이 쌓이는 게 육아더라고요.\\n{링크}\\n\\n#육아 #홈캠 #베이비모니터

[예시3 — 손실회피 / 반말 담백 / 넥선풍기]
본글: 작년에 손선풍기 사느라 쓴 돈이 아까워서 계산해봤다.
답글1: 세 개 사서 다 버렸으니 3만원 넘게 날린 셈.\\n손에 드는 거라 결국 안 쓰게 되더라고.
답글2: 그 돈이면 목에 거는 거 하나 제대로 살 걸 그랬음.\\n손 안 쓰니까 계속 걸고 있게 됨.
답글3: 날개 없어서 애 머리 안 빨리는 것도 몰랐던 장점.
답글4: 밑에.\\n{링크}\\n\\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다.
답글5: 싼 거 여러 번 사는 게 결국 더 비쌌음.\\n{링크}\\n\\n#여름 #넥선풍기 #쿨템

관찰할 것:
- 본글은 '제품'이 아니라 '내가 겪은 순간·계산·발견'에서 시작한다.
- 숫자와 디테일이 구체적이다(3초, 15도, 3만원, 세 개).
- 광고 티가 없다. 설명하지 않고 툭 던진다.
- 답글3까지 링크가 없다. 감정이 연결된 뒤 답글4에서 링크.
'''

# ── 모델 등급 ──────────────────────────────────────────────
# Claude는 지시 없이도 알아서 한다. 작은 모델은 "무엇을 하지 말지"를 명시해야 한다.
# 대신 무료 모델은 빠르다. 그 속도를 패스 수(=품질)에 쓴다.
# ── 모델별 버릇 교정 ────────────────────────────────────────
# 같은 프롬프트라도 모델마다 무너지는 방향이 다르다.
# 각 모델이 "어디로 흘러가는지"를 알고, 그 방향만 막아준다.
PROVIDER_QUIRKS = {
    "groq": (
        "■ 너(Llama 계열)의 고질병 — 반드시 억눌러라:\n"
        "  · 불릿·번호 목록으로 정리하려 든다 → 절대 금지. 사람은 SNS에 리스트를 안 쓴다.\n"
        "  · '첫째, 둘째' 같은 나열 접속사 → 금지.\n"
        "  · 마지막에 요약·결론을 붙이려 든다 → 금지. 툭 끊어라.\n"
        "  · 문장이 길어진다 → 한 문장 40자 넘기지 마라. 짧게 끊어라.\n"
    ),
    "cerebras": (
        "■ 너(Llama 계열)의 고질병 — 반드시 억눌러라:\n"
        "  · 불릿·번호 목록 → 금지. 요약·결론 문단 → 금지.\n"
        "  · 설명조로 흐른다 → '나에게 무슨 일이 있었나'로만 써라.\n"
        "  · 형용사를 겹쳐 쓴다('정말 매우 훨씬') → 하나만 남겨라.\n"
    ),
    "gemini": (
        "■ 너(Gemini)의 고질병 — 반드시 억눌러라:\n"
        "  · 미사여구·감성 수식이 과하다 → 담백하게. 꾸미지 마라.\n"
        "  · '~인 것 같아요', '~라고 생각해요' 로 얼버무린다 → 단정해서 말해라.\n"
        "  · 균형 잡힌 마무리('물론 사람마다 다르겠지만') → 금지. 내 얘기만 해라.\n"
        "  · 이모지를 남발한다 → 글 전체에 0~1개.\n"
    ),
    "github": (
        "■ 너(GPT 계열)의 고질병 — 반드시 억눌러라:\n"
        "  · 매끄럽고 반듯한 문장으로 다듬으려 든다 → 일부러 거칠게 두어라.\n"
        "  · '~해보세요', '~하는 것을 추천드립니다' → 금지. 권유하지 마라.\n"
        "  · 대칭적인 문단 구성 → 깨뜨려라. 길이를 들쭉날쭉하게.\n"
    ),
    "zai": (
        "■ 너(GLM)의 고질병 — 반드시 억눌러라:\n"
        "  · 번역투가 나온다('~에 대해서', '~을 진행하다') → 한국인이 실제로 쓰는 말로.\n"
        "  · 조사가 어색하다 → 소리 내어 읽었을 때 자연스러운지 확인하라.\n"
        "  · 한자어를 남용한다 → 쉬운 우리말로.\n"
    ),
    "llm7": (
        "■ 고질병 — 반드시 억눌러라:\n"
        "  · 번역투·과장('미지의 여정', '보물을 찾아') → 금지. 생활 언어로만.\n"
        "  · 광고 문구로 흐른다 → 금지. 내가 겪은 일만 써라.\n"
    ),
    "nvidia": (
        "■ 고질병 — 반드시 억눌러라:\n"
        "  · 설명·정의로 시작한다 → 금지. 장면으로 시작하라.\n"
        "  · 목록·요약 → 금지.\n"
    ),
    "openrouter": (
        "■ 고질병 — 반드시 억눌러라:\n"
        "  · 목록·요약·권유체 → 전부 금지.\n"
        "  · 문장이 길어진다 → 40자 안에서 끊어라.\n"
    ),
}


# 모든 무료 모델에 공통으로 붙는 '결정적 대조' — Opus가 암묵적으로 아는 것을 명시
_GOOD_BAD = '''■ 이 차이를 반드시 체득하라 (왼쪽=실패, 오른쪽=성공):
  · "정말 시원하고 좋아요"        → "등이 안 축축한 채로 아침을 맞은 게 얼마 만인지"
  · "설치가 간편합니다"           → "박스 뜯고 3분, 설명서도 안 봤다"
  · "가성비 최고의 선택"          → "싼 거 세 번 살 돈이면 이거 하나였다"
  · "많은 분들이 만족하세요"      → "친구가 이거 어디서 샀냐고 먼저 물어봄"
  · "여름철 필수 아이템입니다"    → "작년 여름을 어떻게 버텼나 싶다"
  · "품질이 우수합니다"           → "한 달 굴렸는데 아직 처음 같다"
왼쪽은 전부 '광고 문구'다. 오른쪽은 전부 '한 사람의 구체적 경험'이다.
너는 오른쪽만 써라.
'''


def quirk_block(prov):
    q = PROVIDER_QUIRKS.get(prov, "")
    return (q + "\n" + _GOOD_BAD) if q else _GOOD_BAD


TOP_TIER = {"anthropic"}
FAST_FREE = {"cerebras", "groq", "github", "zai", "gemini"}   # 3패스 감당 가능
SLOW_FREE = {"openrouter", "llm7", "nvidia"}                  # 2패스까지


# ── 무료 모델 전용 스캐폴드 ─────────────────────────────────
# Claude가 암묵적으로 하는 사고 과정을 문자로 강제한다.
SCAFFOLD = '''쓰기 전에 머릿속으로 이 순서를 반드시 밟아라(출력하지는 마라):
1) 이 제품을 쓰는 사람이 겪는 "구체적인 한 장면"을 하나 고른다.
   → 시간대·장소·행동이 보여야 한다. ("여름밤"❌ / "새벽 3시에 깨서 베개를 뒤집는 순간"⭕)
2) 그 장면에서 나온 "숫자" 하나를 정한다. (3초, 15도, 3만원, 세 번, 일주일)
3) 사람들이 "원인이라고 착각하는 것"과 "진짜 원인"을 나눈다.
4) 답글마다 문장 골격을 다르게 잡는다. (하소연 / 계산 / 발견 / 고백 / 자조)
5) 마지막에 아래 자가검사를 통과하는지 스스로 확인한 뒤 출력한다.

자가검사(하나라도 걸리면 그 문장을 고쳐 써라):
□ 본글 첫 문장에 제품명이 있는가? → 있으면 삭제하고 장면으로 시작
□ 숫자·시간·구체적 행동이 하나도 없는가? → 넣어라
□ 이 글을 다른 제품에 붙여도 말이 되는가? → 되면 실패. 이 제품에만 맞는 디테일로 교체
□ 모든 문장이 비슷한 길이인가? → 한 줄짜리 짧은 문장을 반드시 섞어라
□ 스펙을 나열했는가? → 스펙 대신 "그래서 뭐가 달라졌는지"로 바꿔라
□ 금지어가 하나라도 있는가? → 전부 제거
□ 마지막 답글이 깔끔하게 요약·결론으로 끝나는가? → 여운을 남기고 툭 끊어라

아래는 흔한 실패와 그 교정이다. 이 차이를 반드시 체득해라.

[실패] "이 쿨매트 정말 좋아요! 시원하고 촉감도 부드러워서 강추합니다."
[교정] "새벽 세 시에 깨서 이불을 걷어차는 게 습관이 됐었다. 지금은 안 깬다."
  → 이유: 형용사 나열 대신 '언제·무엇이 달라졌는지'로.

[실패] "쿨매트는 냉감 소재를 사용하여 체온을 낮춰주는 제품입니다."
[교정] "매트가 시원한 게 아니라, 열이 안 갇히는 거더라. 그걸 몰랐음."
  → 이유: 사전 설명 대신 '내가 알게 된 것'으로.

[실패] "결론적으로 여름철 필수템이라고 할 수 있습니다."
[교정] "싼 거 세 번 사는 게 결국 더 비쌌음."
  → 이유: 결론 선언 대신 관찰·자조로 끝낸다.
'''


QUALITY_RULES = '''품질 기준(반드시 지킬 것 — 이걸 다 지키면 사람이 쓴 글이 된다):
1) 첫 문장에 제품명을 넣지 마라. '내가 겪은 장면'부터 시작해라.
2) 구체적 숫자·시간·장면을 최소 1개. 단 ★앞뒤 숫자가 맞아야 한다★.
   (세 개 샀다면 세 개 이야기로 끝까지 가라. 중간에 다섯 개로 바뀌면 실패.)
3) '~해요 좋아요' 식 뭉뚱그린 칭찬 금지. 무엇이 '어떻게' 달라졌는지 한 장면으로.
4) '강추·대박·필수템·후회없는선택·인생템·갓성비' 같은 광고 클리셰 전부 금지.
5) 단점이나 의외의 점을 한 줄. (완벽하다고만 하면 광고 티가 난다.)
6) 이 글을 다른 제품에 붙여도 말이 되면 실패. 이 제품에만 맞는 디테일을 써라.
7) 문장 길이를 일부러 들쭉날쭉하게. 긴 문장 뒤에 세 글자 문장을 붙여라.
8) 감정을 '설명'하지 말고 '행동'으로 보여줘라.
   ("불안했다"❌ / "문틈으로 3초를 더 쳐다봤다"⭕)
9) 마지막 답글은 결론·요약으로 닫지 마라. 여운을 남기고 툭 끊어라.
10) 제품이 무슨 물건인지 글만 읽고도 알 수 있어야 한다. 단, 스펙 나열은 금지.
'''


def _quality_critique(api_key, product_name, tone_desc, draft_json_text):
    """2패스: 생성된 글을 기준에 맞춰 자체 검수·재작성 (무료 모델도 퀄 상승)."""
    sys_p = (
        "너는 한국어 카피 에디터다. 아래 쓰레드 초안을 품질 기준에 맞춰 고쳐 써라.\n"
        "AI 티, 광고 클리셰, 뭉뚱그린 칭찬을 제거하고 구체적 장면·숫자로 바꿔라.\n"
        "구조(본글+답글5)와 링크·고지문구 위치는 유지해라.\n"
        + QUALITY_RULES +
        '\n출력은 JSON만: {"posts":["본글","답글1","답글2","답글3","답글4","답글5"]}'
    )
    user_p = f"상품: {product_name}\n말투: {tone_desc}\n\n초안:\n{draft_json_text}\n\n위 기준으로 다시 써라."
    r = llm_chat(api_key, sys_p, user_p, max_tokens=3000)
    if not r.get("ok"):
        return None
    try:
        posts = _parse_json_out(r["text"]).get("posts", [])
        return posts if len(posts) >= 4 else None
    except Exception:
        return None


# ── 휴머나이저: AI 티 탐지 → 강제 재작성 → 기계적 정리 ──
AI_TELLS = [
    # 광고·AI 클리셰
    "강추", "필수템", "후회 없는", "후회없는", "인생템", "갓성비", "가성비 갑",
    "정말 좋아요", "너무 좋아요", "완전 만족", "대만족", "적극 추천", "추천드립니다",
    "고민하지 마세요", "후회하지 않으실", "선택이었습니다", "탁월한 선택",
    "여러분", "많은 분들", "다양한", "뛰어난", "우수한", "최고의", "완벽한",
    "혁신적", "놀라운", "특별한 경험", "새로운 경험",
    # AI 특유 접속·마무리
    "결론적으로", "종합적으로", "마지막으로", "무엇보다", "특히나",
    "~에 대해 알아보았습니다", "도움이 되셨길", "참고하시기 바랍니다",
    "라고 할 수 있습니다", "라고 볼 수 있습니다",
    # 과장
    "혁명", "게임 체인저", "인생이 바뀌", "삶의 질이 수직",
]
# AI가 즐겨쓰는 문장부호·패턴
AI_PATTERNS = [
    (r"—", " "),            # em dash (한국인 잘 안 씀)
    (r"–", " "),
    (r"…{2,}", "…"),
    (r"!{2,}", "!"),
    (r"\?{2,}", "?"),
    (r"\s{2,}", " "),
]

HUMANIZE_RULES = '''사람이 쓴 글처럼(가장 중요):
★ 짧게 쓰되 '텅 비지' 마라. 이게 제일 중요하다.
  나쁜 예: "작은 것 하나로 위로받는 느낌이에요" (아무 정보 없음 = 실패)
  나쁜 예: "비밀은 여기 있었어요" (뭘 말하는지 없음 = 실패)
  좋은 예: "선풍기 끄고 자도 등이 안 축축한 게, 그게 그렇게 클 줄 몰랐음"
  → 짧아도 '무엇이 어떻게 달라졌는지' 손에 잡히는 게 반드시 하나 있어야 한다.
- 답글마다 최소 한 개의 '구체'를 박아라: 숫자·시간·감각(축축함/뻐근함)·행동·비교 중 하나.
- 감정을 이름 붙이지 마라('위로받는다','편안하다'). 그 감정이 나온 '장면'을 보여줘라.
- 문장 길이를 들쭉날쭉하게. 한 줄짜리 짧은 문장을 섞되, 그 한 줄도 내용이 있어야 한다.
- 완결된 결론·요약으로 끝내지 마라. 말하다 만 것처럼 툭 끊어도 된다.
- 자기 확신을 낮춰라. "~인 것 같다", "~더라", "~였음" 같은 관찰조.
- 과장·감탄사·이모지 최소(0~1개). 느낌표 남발 금지.
- 브랜드명을 반복하지 마라. 대명사나 '이거'로 받아라.
- 문장을 병렬로 예쁘게 맞추지 마라(AI 티의 대표).
- 사전 같은 설명 금지. 겪은 것만 써라.
- 상품명에 붙은 광고 수식어(초강력·원샷·끝판꽝·프리미엄·대용량)를 소재로 삼지 마라.
- ★모르는 사실을 지어내지 마라. 특히 인증(KC·FDA·특허)·성분·수치·효능은 확실하지 않으면 아예 쓰지 마라.
  글에 없어도 되는 정보다. '이런 게 있대서' 같은 추측성 인증 언급 금지. 겪은 것·느낀 것만 써라.
- ★마무리 답글(5번)에 '오늘도 좋은 하루 되세요' 같은 상투적 인사 금지. 여운만 남겨라.
금지어(절대 쓰지 마라): 강추, 필수템, 인생템, 갓성비, 적극 추천, 후회 없는 선택,
정말 좋아요, 대만족, 여러분, 다양한, 뛰어난, 최고의, 완벽한, 결론적으로, 종합적으로,
도움이 되셨길, 참고하시기 바랍니다, 좋은 하루 되세요, 위로받는, 그런 존재.
'''


DISCLOSURE = "(광고) 쿠팡파트너스 활동으로 수수료를 받습니다."


def repair_structure(posts, deeplink, product_name=""):
    """★구조는 모델에게 맡기지 않는다. 코드가 강제한다.
    작은 모델은 '6개를 써라'를 자주 어긴다(5개·7개). 목소리는 모델이,
    개수·링크 위치·고지문구·해시태그는 기계가 책임진다."""
    posts = [str(p).strip() for p in (posts or []) if str(p).strip()]
    # 모델이 프롬프트의 {링크} 플레이스홀더를 그대로 뱉는 경우가 있다 → 제거
    posts = [re.sub(r"\{\s*(링크|link|url|deeplink)\s*\}", "", p).strip() for p in posts]
    posts = [p for p in posts if p]
    if not posts:
        return posts

    def has_link(t):  return "http" in t
    def has_disc(t):  return "수수료" in t
    def has_tags(t):  return "#" in t

    # 고지문구/해시태그가 붙은 글을 찾아 뒤로 뺀다
    disc = next((p for p in posts if has_disc(p)), None)
    tags = next((p for p in posts if has_tags(p) and p is not disc), None)
    rest = [p for p in posts if p is not disc and p is not tags]

    # 본글·답글1~3 = 링크 없는 글 4개
    rest = [re.sub(r"https?://\S+", "", p).strip() for p in rest]
    rest = [p for p in rest if p]

    while len(rest) < 4:
        # 모자라면 가장 긴 글을 두 문장으로 쪼개서 채운다 (억지 생성 금지)
        idx = max(range(len(rest)), key=lambda i: len(rest[i])) if rest else None
        if idx is None:
            rest.append("…")
            continue
        parts = re.split(r"(?<=[.!?…])\s+|\n+", rest[idx])
        parts = [x.strip() for x in parts if x.strip()]
        if len(parts) < 2:
            rest.append(rest[idx])
            break
        half = max(1, len(parts) // 2)
        rest[idx] = " ".join(parts[:half])
        rest.insert(idx + 1, " ".join(parts[half:]))
    rest = rest[:4]

    # 답글4: 링크 + 고지문구 (모델이 쓴 한 줄 안내는 살린다)
    lead = ""
    if disc:
        lead = re.sub(r"https?://\S+", "", disc).replace(DISCLOSURE, "")
        lead = re.sub(r"\(광고\)[^\n]*", "", lead).strip()
    if not lead:
        lead = "밑에."
    r4 = f"{lead}\n{deeplink}\n\n{DISCLOSURE}"

    # 답글5: 마무리 + 링크 + 해시태그 3개
    tail, hashtags = "", ""
    if tags:
        hashtags = " ".join(re.findall(r"#\S+", tags)[:3])
        tail = re.sub(r"#\S+", "", tags)
        tail = re.sub(r"https?://\S+", "", tail).strip()
    if not tail or tail == lead:
        # 답글4와 답글5가 같은 말이면 안 된다
        cands = [x for x in rest if x and x != lead and x != tail]
        tail = cands[-1] if cands else (rest[-1] if rest else "그냥 그렇다고.")
    if not hashtags:
        base = re.sub(r"[^가-힣A-Za-z ]", " ", product_name or "").split()
        hashtags = " ".join("#" + w for w in base[:3]) or "#추천"
    r5 = f"{tail}\n{deeplink}\n\n{hashtags}"

    return rest + [r4, r5]


def quality_gate(posts, product_name):
    """모델을 믿지 않고 기계가 직접 검사한다. 실패 항목을 문장으로 돌려준다.
    이 목록을 그대로 재작성 프롬프트에 먹여서 '무엇을 고쳐야 하는지'를 못 박는다."""
    fails = []
    if not posts:
        return ["글이 비었다."]

    # 0) ★모델이 프롬프트 예시(플레이스홀더)를 그대로 뱉은 경우 — NVIDIA 등 약한 모델이 자주.
    #  정확히 자리표시자 단어와 일치하는 것만 센다(짧은 실제 답글 '밑에','끝'은 오판 금지).
    PLACEHOLDER = {"본글", "답글1", "답글2", "답글3", "답글4", "답글5",
                   "ans글4", "ans답글5", "ans 글4", "ans 답글5"}
    stripped = [re.sub(r"[\s]", "", str(x)) for x in posts]
    ph_hits = sum(1 for x in stripped if x in PLACEHOLDER)
    # 본글이 JSON 통째로거나, 자리표시자가 2개 이상이면 플레이스홀더
    if ph_hits >= 2 or (posts and "{" in str(posts[0]) and "posts" in str(posts[0])):
        return ["__PLACEHOLDER__"]
    # 개수·링크위치·고지문구는 repair_structure()가 코드로 보장한다 → 모델에게 시키지 않는다.
    body = str(posts[0])
    joined = "\n".join(str(p) for p in posts)

    # 1) 본글 첫 문장에 제품명
    head = body.split("\n")[0]
    for tok in re.split(r"[\s,/·]+", product_name or ""):
        if len(tok) >= 2 and tok in head:
            fails.append(f"본글 첫 문장에 제품명('{tok}')이 들어있다. 제품명을 빼고 '내가 겪은 장면'으로 시작하라.")
            break

    # 1.5) ★첫 줄 훅 검사 — 조회수를 죽이는 약한 오프너
    if _opener_is_weak(head):
        fails.append("첫 줄이 약하다(스크롤을 못 멈춘다). '안녕/오늘은/제가/추천' 같은 시작이거나 "
                     "너무 길다. 첫 줄을 6~40자로, '내 얘긴데?' 또는 '이게 뭐지?' 싶게 다시 써라.")

    # 2) 구체적 숫자·시간 (★한글 수사도 숫자다. "새벽 두 시", "사흘째"를 놓치면 안 된다)
    KOR_NUM = r"(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무|서너|대여섯)\s?(시|번|개|달|주|명|살|번째|시간|분)"
    KOR_DAY = r"(하루|이틀|사흘|나흘|닷새|열흘|보름|한달|일주일|이주일|반년)"
    if not (re.search(r"\d", joined) or re.search(KOR_NUM, joined) or re.search(KOR_DAY, joined)):
        fails.append("숫자가 하나도 없다. 시간·개수·금액·각도 같은 구체적 숫자를 최소 1개 넣어라 (예: 새벽 3시, 세 번, 3만원).")

    # 3) 문장 길이 단조로움
    lines = [l.strip() for l in re.split(r"[\n.!?]", joined) if len(l.strip()) > 3]
    if lines:
        L = [len(l) for l in lines]
        avg = sum(L) / len(L)
        var = sum((x - avg) ** 2 for x in L) / len(L)
        if var < 60:
            fails.append("문장 길이가 다 비슷하다(AI 티의 대표). 아주 짧은 한 줄짜리 문장을 최소 하나 섞어라.")
        if min(L) > 14:
            fails.append("짧은 문장이 하나도 없다. 10자 이내의 툭 던지는 문장을 넣어라.")

    # 4) 금지어
    tells = detect_ai_tells(joined)
    if tells:
        fails.append(f"금지어가 들어있다: {', '.join(tells[:6])}. 전부 다른 표현으로 바꿔라.")

    # 6.5) ★깨진 문자 — äku°C, 데enska, уже(러시아어) 류. 최우선 검출.
    if has_garbled(joined):
        fails.insert(0, "한글 사이에 외국 문자(러시아어 уже, 라틴 äku, 한자, 일본어 등)가 섞였다. "
                        "그 부분을 전부 자연스러운 한국어로 다시 써라. KF94·SPF 같은 제품명 외 외국문자 금지.")

    # 6.8) ★숫자 모순 — "세 개 샀다"더니 "다섯 개 버렸다" 류
    #  같은 대상을 세는 수가 글 안에서 어긋나면 잡는다.
    nums_kor = {"한":1,"하나":1,"두":2,"둘":2,"세":3,"셋":3,"네":4,"넷":4,"다섯":5,"여섯":6,"일곱":7}
    counts = []
    for m in re.finditer(r"(\d+)\s*(개|번|년|달|주|시간|만원|원)", joined):
        counts.append((m.group(2), int(m.group(1))))
    # 본글에서 산 개수 vs 답글에서 버린/쓴 개수가 정면 충돌하는 흔한 케이스만 본다
    buy = re.search(r"(\d+)\s*개.{0,10}(샀|구매|주문)", joined)
    trash = re.search(r"(\d+)\s*개.{0,10}(버렸|버림|버리)", joined)
    if buy and trash and int(buy.group(1)) < int(trash.group(1)):
        fails.append(f"숫자가 안 맞는다. {buy.group(1)}개 샀다면서 {trash.group(1)}개를 버렸다고 한다. 앞뒤 숫자를 맞춰라.")

    # 6.9) ★지어낸 인증·효능 — 모기팔찌인데 'KC인증' 물고늘어지는 류
    FABRICATED = ["KC인증", "KC 인증", "FDA", "특허", "인증받", "인증을 받",
                  "임상", "식약처", "성분 함량", "99.9%", "99.99%", "효능이 입증"]
    fab_hits = [w for w in FABRICATED if w in joined]
    if fab_hits:
        fails.append(f"'{fab_hits[0]}' 같은 인증·효능을 언급했다. 확인 안 된 사실을 지어내면 안 된다"
                     "(허위광고 위험). 그 부분을 빼고 '실제로 써보니 어땠는지'로만 써라.")

    # 7) 스펙 나열
    if re.search(r"(스펙|사양|용량|무게|사이즈|재질)\s*[:은는]", joined):
        fails.append("스펙을 나열했다. 스펙 대신 '그래서 무엇이 달라졌는지'로 바꿔라.")

    # 7.7) 답글 중복 (약한 모델이 같은 문장을 답3·답5에 반복)
    bodies = [re.sub(r"https?://\S+|#\S+|\s", "", str(x)) for x in posts]
    seen = {}
    for i, bd in enumerate(bodies):
        if len(bd) > 8:
            if bd in seen:
                fails.append(f"답글 내용이 반복된다({seen[bd]+1}번째와 {i+1}번째가 같다). 서로 다른 얘기를 써라.")
                break
            seen[bd] = i

    # 7.9) ★빈 감성 답글 — "위로받는 느낌" "비밀은 여기" 처럼 구체가 하나도 없는 것
    EMPTY_PATTERNS = ["위로받", "그런 존재", "비밀은 여기", "답이 나왔", "뭘 하는지",
                      "느낌이에요", "느낌이었", "좋은 하루", "행복", "소중한", "특별한"]
    VAGUE_ENDINGS = ["되길", "될까요", "느낌이에요", "느낌이죠"]
    # 링크·해시태그·고지 없는 순수 답글(1~3번)만 검사
    content_posts = []
    for i, pp in enumerate(posts):
        t = str(pp)
        if "http" in t or "수수료" in t or t.strip().startswith("#"):
            continue
        content_posts.append((i, t))
    empty_count = 0
    for i, t in content_posts:
        bare = re.sub(r"[#\s]", "", t)
        # 숫자·감각어·구체명사가 하나도 없고 20자 미만이면 '빈 문장' 의심
        has_concrete = bool(re.search(r"\d", t)) or any(
            w in t for w in ["축축", "뻐근", "시원", "따뜻", "무겁", "가볍", "냄새", "소리",
                             "각도", "온도", "분", "초", "번", "개", "원", "도 ", "주일", "달"])
        if len(bare) < 22 and not has_concrete:
            empty_count += 1
        if any(p in t for p in EMPTY_PATTERNS):
            fails.append(f"'{t.strip()[:20]}...' 같은 빈 감성 문장이다. 구체적인 장면·변화·숫자로 바꿔라.")
            break
    if empty_count >= 2:
        fails.append("내용 없는 짧은 답글이 여러 개다(감정만 있고 구체가 없음). "
                     "각 답글에 숫자·감각·행동 중 하나를 반드시 넣어라.")

    # 8) 링크 클리셰
    for cliche in ("궁금할까봐 남겨둠", "궁금하실까봐", "필요하신 분들"):
        if cliche in joined:
            fails.append(f"링크 클리셰('{cliche}')를 썼다. 다른 방식으로 링크를 던져라.")
            break
    return fails


def _strip_weak_opener(posts):
    """모델이 끝내 약한 오프너('써보니까','제가')로 시작하면 그 도입부만 규칙으로 제거."""
    if not posts:
        return posts
    lines = str(posts[0]).split("\n")
    lines[0] = re.sub(r"^[\s.,·…!?]+", "", lines[0])   # 앞 기호 잔재 제거
    head = lines[0].strip()
    # '써보니까/사서/제가 ... ,' 같은 군더더기 도입부를 잘라 뒷문장을 첫 줄로
    m = re.match(r"^(써보니까|사서 쓰다가|제가|저는|이번에|요즘|최근에)\s*[^,.。]*[,，]\s*(.+)", head)
    if m and len(m.group(2)) >= 6:
        lines[0] = m.group(2).strip()
        posts = ["\n".join(lines)] + list(posts[1:])
    return posts


def _strip_leading_product(posts, product_name):
    """모델이 끝내 본글 첫 문장에 제품명을 넣으면 규칙으로 걷어낸다."""
    if not posts:
        return posts
    body = str(posts[0])
    lines = body.split("\n")
    head = lines[0]
    toks = [t for t in re.split(r"[\s,/·]+", clean_product_name(product_name)) if len(t) >= 2]
    changed = False
    # ★첫 어절이 정확히 제품명일 때만 제거. 조사가 붙어 단어 중간을 자르지 않게.
    #  '모기에게 물린' 에서 '모기'만 지우면 '에게 물린'이 되어버리므로,
    #  제품명+조사가 '완결된 첫 토막'일 때만 잘라낸다.
    for tok in toks:
        # 제품명 뒤에 조사/공백이 오고 그 다음 실제 문장이 이어질 때만
        m = re.match(r"^" + re.escape(tok) + r"(은|는|이|가|을|를|도|만|의|와|과|,)?\s+(.+)", head)
        if m and len(m.group(2)) >= 8:
            head = m.group(2).strip()
            changed = True
            break
    if changed and head and len(head) >= 6:
        lines[0] = head
        posts = [("\n".join(lines))] + list(posts[1:])
    return posts


def _fix_pass(api_key, product_name, tone_desc, posts, fails, max_tokens=3000):
    """기계가 잡아낸 실패 항목만 콕 집어 재작성시킨다.
    ★'더 잘 써봐'는 작은 모델에 안 통한다. '이 항목을 이렇게 고쳐라'는 통한다."""
    sys_p = (
        "너는 한국어 카피 에디터다. 아래 쓰레드 글에서 지적된 문제만 정확히 고쳐라.\n"
        "지적되지 않은 부분은 절대 건드리지 마라. 구조(본글+답글5)와 링크·고지문구는 그대로 유지.\n\n"
        "■ 고치는 법 예시:\n"
        "  문제 '빈 감성 문장' → '작은 것 하나로 위로받는 느낌' 을 "
        "'선풍기 끄고 자도 등이 안 축축한 게 그렇게 클 줄 몰랐음' 으로.\n"
        "  문제 '첫 문장에 제품명' → '선리커버 좋아요'를 "
        "'거울 앞에서 매일 한숨 쉬던 게 한 달 전인데' 로.\n"
        "  문제 '숫자 없음' → 시간·개수·금액·기간 중 하나를 실제로 박아라.\n\n"
        + HUMANIZE_RULES +
        '\n출력은 JSON만: {"posts":["본글","답글1","답글2","답글3","답글4","답글5"]}'
    )
    user_p = (
        f"상품: {product_name}\n말투: {tone_desc}\n\n"
        "■ 반드시 고쳐야 할 것:\n" + "\n".join(f"{i+1}. {f}" for i, f in enumerate(fails)) +
        "\n\n■ 원문:\n" + json.dumps({"posts": posts}, ensure_ascii=False)
    )
    r = llm_chat(api_key, sys_p, user_p, max_tokens=max_tokens)
    if not r.get("ok"):
        return None
    try:
        out = _parse_json_out(r["text"]).get("posts", [])
        return out if len(out) >= 4 else None
    except Exception:
        return None


def detect_ai_tells(text):
    """AI 티 나는 표현 검출 → 리스트 반환."""
    found = []
    t = text or ""
    for w in AI_TELLS:
        if w in t:
            found.append(w)
    return found


def scrub_garbled(t):
    """★무료 모델이 한글 사이에 섞는 깨진 문자/외국어 제거.
    'aku°C', '데enska', '물놀이equipment', '탈수기付き', '창문이 уже' 류."""
    if not t:
        return t
    t = re.sub(r"[\u00C0-\u024F\u1E00-\u1EFF]", "", t)          # 라틴 확장
    t = re.sub(r"[°±×÷¤¦§¨©ª«¬®¯²³´µ¶¸¹º»¼½¾¿]", "", t)
    t = re.sub(r"[\u3040-\u30FF]", "", t)                        # 일본어 가나
    t = re.sub(r"[\u0400-\u04FF]", "", t)                        # ★키릴(러시아어 уже 등)
    t = re.sub(r"[\u0370-\u03FF]", "", t)                        # 그리스
    t = re.sub(r"[\u0600-\u06FF\u0590-\u05FF]", "", t)          # 아랍·히브리
    t = re.sub(r"[\u0E00-\u0E7F]", "", t)                        # 태국
    t = re.sub(r"(?<=[가-힣])[a-zA-Z]+", "", t)                   # 한글+영문 → 제거
    t = re.sub(r"[a-zA-Z]+(?=[가-힣])", "", t)                    # 영문+한글 → 제거
    t = re.sub(r"[가-힣]*[\u4E00-\u9FFF]+[가-힣]*", lambda m: re.sub(r"[\u4E00-\u9FFF]", "", m.group()), t)  # 한글 사이 한자
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def has_garbled(t):
    if not t:
        return False
    # 한글 텍스트에 섞이면 안 되는 외국문자 (키릴·그리스·아랍·히브리·태국·가나·한자)
    if re.search(r"[\u00C0-\u024F\u1E00-\u1EFF\u0400-\u04FF\u0370-\u03FF"
                 r"\u0600-\u06FF\u0590-\u05FF\u0E00-\u0E7F\u3040-\u30FF°±×÷]", t):
        return True
    if re.search(r"[가-힣][a-zA-Z]", t) or re.search(r"[a-zA-Z][가-힣]", t):
        return True
    # 한글 문장 안에 낀 한자
    if re.search(r"[가-힣][\u4E00-\u9FFF]|[\u4E00-\u9FFF][가-힣]", t):
        return True
    return False


def scrub_ai_artifacts(text):
    """기계적 정리: 깨진 문자 + AI 특유 문장부호·공백."""
    t = scrub_garbled(text or "")
    for pat, rep in AI_PATTERNS:
        t = re.sub(pat, rep, t)
    return t.strip()


def _humanize_pass(api_key, product_name, tone_desc, posts, tells):
    """AI 티가 검출되면 → 그 부분을 사람 말투로 강제 재작성."""
    sys_p = (
        "너는 한국어 문장을 '사람이 쓴 것처럼' 고치는 에디터다.\n"
        "아래 글에서 AI 티 나는 표현을 전부 제거하고, 실제 사람이 쓴 것처럼 다시 써라.\n"
        + HUMANIZE_RULES +
        f"\n검출된 금지 표현: {', '.join(tells)}\n"
        "이 표현들을 반드시 없애고, 구체적 장면·관찰로 바꿔라.\n"
        "구조(본글+답글5)와 링크·고지문구 위치는 그대로 유지.\n"
        '출력은 JSON만: {"posts":["본글","답글1","답글2","답글3","답글4","답글5"]}'
    )
    user_p = f"상품: {product_name}\n말투: {tone_desc}\n\n원문:\n{json.dumps({'posts': posts}, ensure_ascii=False)}"
    r = llm_chat(api_key, sys_p, user_p, max_tokens=3000)
    if not r.get("ok"):
        return None
    try:
        out = _parse_json_out(r["text"]).get("posts", [])
        return out if len(out) >= 4 else None
    except Exception:
        return None


# ── 지금 뜨는 주제 레이더 (Google Trends + 계절 신호, 무료·키 불필요) ──
_TRENDS_CACHE = {"at": 0, "items": []}
_TRENDS_BUSY = threading.Lock()

# 소비·생활 관련 신호만 통과 (연예·정치·스포츠·증시 제외).
# 카테고리별 사전 = 필터이자 분류기. 새 카테고리를 추가하려면 여기에 한 줄 추가하면 된다.
_CAT_KW = {
    "날씨":   ["더위","폭염","열대야","장마","호우","비","태풍","습도","미세먼지","황사","한파","추위",
              "꽃가루","건조","결로","눈","빙판","자외선","일교차","환절기"],
    "건강":   ["감기","독감","코로나","알레르기","비염","두통","수면","불면","숙면","다이어트","운동",
              "스트레칭","홈트","단백질","영양제","비타민","유산균","혈압","혈당","면역","눈피로",
              "거북목","허리","무릎","족저근막","금연","금주","해장","보양식","삼계탕","초복","중복","말복"],
    "육아":   ["육아","아기","신생아","유아","기저귀","분유","이유식","어린이집","유치원","등원","하원",
              "방학","개학","수유","젖병","카시트","유모차","아기띠","돌잔치","임산부","출산","산후조리",
              "아이방","학용품","초등","돌봄"],
    "생활":   ["청소","빨래","세탁","곰팡이","냄새","벌레","모기","바퀴","진드기","좀벌레","정리","수납",
              "이사","자취","원룸","분리수거","환기","제습","가습","살균","소독","방충망","배수구","하수구"],
    "주방":   ["주방","설거지","식기","도마","프라이팬","냄비","에어프라이어","전자레인지","밥솥","커피",
              "원두","텀블러","보온병","도시락","밀프렙","반찬","김치","냉장고","정수기","식중독"],
    "가전":   ["에어컨","선풍기","서큘레이터","제습기","가습기","공기청정기","보일러","난방","전기요금",
              "온수매트","전기장판","건조기","로봇청소기","무선청소기","스타일러","TV","모니터"],
    "뷰티":   ["화장품","스킨케어","선크림","자외선차단","보습","각질","여드름","트러블","모공","기미",
              "탈모","두피","샴푸","염색","네일","향수","제모","면도","바디로션","핸드크림","립밤"],
    "패션":   ["옷","코디","패션","운동화","샌들","슬리퍼","레인부츠","우산","양산","모자","선글라스",
              "가방","지갑","시계","린넨","기능성","냉감","발열내의","패딩"],
    "반려동물": ["강아지","고양이","반려견","반려묘","펫","사료","간식","산책","배변","화장실","털빠짐",
              "슬개골","심장사상충","진드기","펫케어","캣타워","하네스"],
    "자동차": ["자동차","차량","운전","주차","타이어","엔진오일","와이퍼","블랙박스","썬팅","차박",
              "장마철운전","김서림","성에","배터리방전","연비","전기차","충전"],
    "아웃도어": ["캠핑","차박","등산","백패킹","낚시","물놀이","계곡","해변","바다","수영","서핑","자전거",
              "러닝","트레킹","피크닉","텐트","타프","화로대","쿨러","아이스박스"],
    "여행":   ["여행","휴가","연휴","항공","호텔","숙소","캐리어","여권","환전","로밍","면세","기차",
              "고속도로","정체","성수기","해외여행","국내여행"],
    "인테리어": ["인테리어","조명","커튼","블라인드","러그","침구","매트리스","베개","소파","책상","의자",
              "선반","수납장","페인트","셀프시공","단열","방음"],
    "홈오피스": ["재택","홈오피스","노트북","키보드","마우스","모니터암","웹캠","헤드셋","의자","모니터받침",
              "충전기","보조배터리","공유기","와이파이","백업","클라우드"],
    "취미":   ["취미","독서","캘리그라피","뜨개","자수","베이킹","홈카페","와인","위스키","맥주","보드게임",
              "레고","프라모델","드로잉","사진","기타","피아노","식물","화분","가드닝","텃밭"],
    "학습":   ["공부","자격증","토익","시험","인강","독학","영어","코딩","자기계발","스터디","필기","다이어리"],
    "쇼핑":   ["할인","특가","세일","블랙프라이데이","쿠폰","최저가","가성비","리뷰","추천템","득템","직구"],
}
_TREND_ALLOW = [w for ws in _CAT_KW.values() for w in ws]

def _cat_of(title):
    """제목이 어느 카테고리인지. 못 찾으면 None(=관련 없음).
    ★사전 순서에 끌려가면 '강아지 산책 더위'가 날씨로 분류된다.
      매칭 개수 → 매칭된 키워드 길이(구체성) 순으로 점수를 매겨 고른다."""
    best, best_score = None, (0, 0)
    for cat, ws in _CAT_KW.items():
        hits = [w for w in ws if w in title]
        if not hits:
            continue
        score = (len(hits), max(len(w) for w in hits))
        if score > best_score:
            best, best_score = cat, score
    return best

_TREND_BLOCK = ["주가","증시","코스피","선거","의원","연예","배우","가수","드라마","아이돌",
                "야구","축구","골프","경기","사망","사고","화재","재판","검찰","부고"]

_SEASON_TOPICS = {
    1: [("한파", "날씨", "보일러를 돌려도 발끝이 시린 집의 공통점", ["온수매트", "발난로", "문풍지"]),
        ("건조", "건강", "겨울마다 아침에 목이 칼칼한 진짜 이유", ["가습기", "무드등", "립밤"]),
        ("새해 다짐", "학습", "1월에 산 운동기구가 3월에 옷걸이가 되는 이유", ["홈트기구", "다이어리", "체중계"]),
        ("설 연휴", "여행", "연휴 고속도로에서 덜 지치는 사람들의 준비물", ["차량용 방석", "보조배터리", "차량 정리함"])],
    2: [("환절기", "건강", "2월에 유독 감기가 안 떨어지는 이유", ["가습기", "비타민", "온열 목베개"]),
        ("졸업·입학", "육아", "입학 전에 미리 사두면 덜 허둥대는 것들", ["책가방", "학용품", "책상"]),
        ("미세먼지", "날씨", "창문을 닫아도 집 안 공기가 나빠지는 이유", ["공기청정기", "필터", "마스크"])],
    3: [("꽃가루", "건강", "봄만 되면 눈이 가렵고 코가 막히는 사람들", ["공기청정기", "코세척기", "알레르기 안약"]),
        ("황사", "날씨", "봄 황사에 빨래를 밖에 널면 안 되는 이유", ["건조기", "실내 건조대", "제습기"]),
        ("새 학기", "육아", "새 학기에 아이가 유독 피곤해하는 이유", ["수면등", "책상 조명", "영양제"])],
    4: [("봄나들이", "아웃도어", "돗자리 하나 차이로 소풍이 달라진다", ["피크닉 매트", "보냉백", "폴딩 박스"]),
        ("자외선", "뷰티", "4월 자외선이 한여름보다 무서운 이유", ["선크림", "모자", "선글라스"]),
        ("환기·청소", "생활", "봄 대청소에서 다들 빼먹는 곳", ["창틀 청소솔", "곰팡이 제거제", "먼지 필터"])],
    5: [("가정의 달", "쇼핑", "선물 고르다 시간만 보내는 사람들을 위한 정리", ["카네이션", "안마기", "기프트 세트"]),
        ("일교차", "건강", "낮엔 덥고 밤엔 추운 5월의 감기", ["얇은 이불", "가디건", "비타민"]),
        ("캠핑 시즌", "아웃도어", "첫 캠핑에서 꼭 후회하는 세 가지", ["폴딩 체어", "랜턴", "화로대"])],
    6: [("장마 시작", "날씨", "장마 전에 미리 해두면 편한 것들", ["제습기", "방수 스프레이", "우산"]),
        ("초여름 벌레", "생활", "6월부터 벌레가 갑자기 늘어나는 이유", ["방충망", "모기퇴치기", "트랩"]),
        ("여름 준비", "가전", "에어컨을 켜기 전에 반드시 해야 하는 것", ["에어컨 청소", "필터", "서큘레이터"])],
    7: [("열대야", "날씨", "열대야에 에어컨을 켜도 자꾸 잠에서 깨는 이유", ["냉감 이불", "쿨매트", "서큘레이터"]),
        ("장마 습도", "생활", "장마철 빨래를 바로 널어도 냄새가 나는 이유", ["제습기", "빨래건조대", "탈취제"]),
        ("여름 세균", "건강", "여름철 행주를 매일 삶아도 냄새가 남는 이유", ["행주", "식기건조대", "살균기"]),
        ("모기", "생활", "밤에 모기 한 마리 때문에 잠 못 자는 집", ["모기퇴치기", "방충망", "모기향"]),
        ("초복 보양", "건강", "복날 지나고 더 지치는 사람들의 공통점", ["홍삼", "비타민", "단백질"]),
        ("차량 실내온도", "자동차", "여름 차 안이 60도까지 오르는 걸 막는 법", ["차량용 햇빛가리개", "썬팅 필름", "차량용 선풍기"]),
        ("반려동물 더위", "반려동물", "말 못 하는 아이가 더위를 먹는 신호", ["펫 쿨매트", "펫 급수기", "쿨 밴드"]),
        ("물놀이", "아웃도어", "계곡·바다에서 짐 때문에 고생하는 사람들", ["방수팩", "아이스박스", "래시가드"])],
    8: [("늦더위", "날씨", "8월 늦더위가 더 지치는 이유", ["넥쿨러", "쿨토시", "선풍기"]),
        ("개학 준비", "육아", "개학 전 아이 생활 리듬 되돌리기", ["학용품", "책상", "수면등"]),
        ("휴가 후유증", "건강", "휴가 다녀와서 더 피곤한 사람들", ["마사지건", "족욕기", "비타민"]),
        ("에어컨 전기요금", "가전", "8월 전기요금 고지서가 무서운 이유", ["절전 멀티탭", "서큘레이터", "전력 측정기"])],
    9: [("환절기 비염", "건강", "9월만 되면 코가 막히는 사람들", ["공기청정기", "코세척기", "가습기"]),
        ("추석 준비", "쇼핑", "명절 전에 미리 사두면 편한 것들", ["선물세트", "보냉백", "일회용기"]),
        ("가을 캠핑", "아웃도어", "가을 캠핑에서 밤에 추워 잠 못 자는 이유", ["침낭", "난로", "핫팩"])],
    10: [("일교차", "건강", "10월 아침저녁 기침이 늘어나는 이유", ["온열 목베개", "가습기", "비타민"]),
         ("가을 건조", "뷰티", "가을만 되면 얼굴이 당기는 사람들", ["보습 크림", "미스트", "핸드크림"]),
         ("난방 준비", "가전", "보일러 켜기 전에 해야 할 점검", ["보일러 청소", "문풍지", "단열 필름"])],
    11: [("첫추위", "날씨", "첫 한파에 유독 손발이 시린 이유", ["전기장판", "온수매트", "수면양말"]),
         ("결로·곰팡이", "생활", "겨울 창문에 물이 맺히는 집의 문제", ["제습제", "결로 방지 테이프", "곰팡이 제거제"]),
         ("블랙프라이데이", "쇼핑", "할인에 홀려 결국 안 쓰게 되는 물건들", ["가성비템", "직구", "쿠폰"])],
    12: [("한파·난방", "가전", "난방비를 아끼면서 따뜻하게 지내는 법", ["전기요", "온풍기", "단열 커튼"]),
         ("연말 모임", "패션", "연말 모임에서 덜 추운 옷차림", ["발열내의", "코트", "머플러"]),
         ("독감", "건강", "12월 독감이 유독 오래가는 이유", ["가습기", "비타민", "손소독제"]),
         ("새해 준비", "학습", "연말에 사두면 1월이 편한 것들", ["다이어리", "플래너", "달력"])],
}

def _season_topics():
    import datetime
    m = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).month
    out = []
    for name, cat, hook, kws in _SEASON_TOPICS.get(m, []):
        out.append({"title": name, "cat": cat, "hook": hook, "keywords": kws,
                    "source": "계절 신호", "kind": "season"})
    return out


def fetch_trend_radar(force=False):
    """Google Trends 실시간 급상승 + 계절 신호 → 생활·육아·건강 관련만."""
    now = time.time()
    if not force and _TRENDS_CACHE["items"]:
        # 캐시가 있으면 무조건 즉시 반환. 오래됐으면 뒤에서 조용히 갱신한다.
        if now - _TRENDS_CACHE["at"] > 1800:
            _spawn_radar_refresh()
        return _TRENDS_CACHE["items"]
    items = []
    try:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
        req = urllib.request.Request("https://trends.google.com/trending/rss?geo=KR",
                                     headers={"User-Agent": ua})
        body = urllib.request.urlopen(req, timeout=6, context=_ctx).read().decode("utf-8", "ignore")
        blocks = re.findall(r"<item>(.*?)</item>", body, re.S)
        for b in blocks:
            t = re.search(r"<title>(.*?)</title>", b, re.S)
            if not t: continue
            title = re.sub(r"<!\[CDATA\[|\]\]>", "", t.group(1)).strip()
            if any(x in title for x in _TREND_BLOCK):
                continue
            cat = _cat_of(title)
            hit = cat is not None
            traffic = re.search(r"<ht:approx_traffic>(.*?)</ht:approx_traffic>", b)
            link = re.search(r"<link>(.*?)</link>", b)
            items.append({
                "title": title, "cat": cat or "생활",
                "hook": f"{title}, 지금 검색이 몰리는 이유",
                "keywords": [], "source": "Google Trends",
                "traffic": (traffic.group(1) if traffic else ""),
                "url": (link.group(1).strip() if link else ""),
                "kind": "trend", "related": bool(hit),
            })
    except Exception:
        pass
    # 관련 신호 우선, 그다음 계절 신호
    related = [i for i in items if i.get("related")]
    others = [i for i in items if not i.get("related")]
    merged = _season_topics() + related + others[:5]
    _TRENDS_CACHE["items"] = merged
    _TRENDS_CACHE["at"] = now
    return merged


def _spawn_radar_refresh():
    """만료된 캐시를 백그라운드에서 갱신. 사용자는 절대 기다리지 않는다."""
    if _TRENDS_BUSY.locked():
        return
    def run():
        with _TRENDS_BUSY:
            try:
                fetch_trend_radar(force=True)
            except Exception:
                pass
    threading.Thread(target=run, daemon=True).start()


def warm_radar():
    """서버 부팅 직후 미리 채워둔다 → 첫 사용자도 즉시."""
    threading.Thread(target=lambda: fetch_trend_radar(force=True), daemon=True).start()


# ── 네이버 검색 리서치 (상품 특징 후보 추출) ──
def naver_research(product_name, limit=6):
    """네이버 검색에서 그 상품의 특징·후기 스니펫을 뽑아 '특징 후보'로 제시."""
    import urllib.parse
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    q = urllib.parse.quote(product_name[:60])
    out = []
    # DuckDuckGo HTML(네이버 차단 회피) — site:naver 우선
    for url in (f"https://html.duckduckgo.com/html/?q={q}+%EB%A6%AC%EB%B7%B0",
                f"https://html.duckduckgo.com/html/?q={q}"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            body = urllib.request.urlopen(req, timeout=7, context=_ctx).read().decode("utf-8", "ignore")
            blocks = re.findall(r'result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?result__snippet"[^>]*>(.*?)</a>',
                                body, re.S)
            for href, title, snip in blocks:
                t = re.sub(r"<[^>]+>", "", title).strip()
                sn = re.sub(r"<[^>]+>", "", snip).strip()
                sn = re.sub(r"\s+", " ", sn)
                if len(sn) < 25:
                    continue
                out.append({"title": t[:70], "snippet": sn[:180], "url": href})
                if len(out) >= limit:
                    break
        except Exception:
            pass
        if out:
            break
    return out
