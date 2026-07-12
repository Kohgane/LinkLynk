"""
LinkLynk — 코어 모듈
쿠팡 파트너스 딥링크 생성 + 고지문구 삽입 + 블로그 초안 생성
서버(app.py)에서 import해서 사용.
"""
import hmac, hashlib, time, urllib.request, json, ssl, re, random

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
            res = json.loads(urllib.request.urlopen(req, context=_ctx, timeout=15).read())
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
            res = json.loads(urllib.request.urlopen(req, context=_ctx, timeout=25).read())
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
def claude_generate_topics(api_key, user_topic="", now_str="", n=3):
    """주제 생성 (무료 Gemini/OpenRouter 또는 Claude). 상품이 아니라 '주제'가 먼저."""
    if not api_key:
        return {"ok": False, "error": "no_key"}
    sys_prompt = (
        "당신은 쿠팡 파트너스 쓰레드 마케팅 전략가입니다. "
        "상품이 아니라 '주제'가 먼저입니다. 사람들이 공감할 상황·고민을 주제로 잡고, "
        "거기서 자연스럽게 필요한 상품으로 연결합니다. "
        "각 주제마다: 현재 시각/계절 맥락, 타겟 표본(누구), 반전 앵글, 훅 문장, "
        "그리고 그 주제에 맞는 쿠팡 검색 키워드 2~3개를 제시하세요. "
        "죄책감 반전('내 탓이 아니라 구조 탓'), 상황 공감, 의외의 사실 같은 훅을 활용하세요. "
        "반드시 JSON만 출력. 형식: "
        '{"topics":[{"title":"...","time_context":"...","sample":"...","angle":"...","hook":"...","keywords":["...","..."]}]}'
    )
    user_msg = f"현재: {now_str}\n"
    if user_topic.strip():
        user_msg += f"요청 주제/방향: {user_topic}\n{n}개의 세부 주제를 뽑아주세요."
    else:
        user_msg += f"지금 시각·계절에 맞는 주제 {n}개를 제안해주세요. 표본이 넓은 걸로."

    r = llm_chat(api_key, sys_prompt, user_msg, max_tokens=1500)
    if not r.get("ok"):
        return r
    try:
        parsed = _parse_json_out(r["text"])
        return {"ok": True, "topics": parsed.get("topics", [])}
    except Exception as e:
        return {"ok": False, "error": "parse_error", "detail": str(e)[:100]}


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

def claude_write_thread(api_key, product_name, deeplink, tone="friendly", price=None, extra=""):
    """쓰레드 6분할 작성. ★사람다움 최우선: few-shot + 휴머나이즈 규칙 + AI티 검출 재작성."""
    if not api_key:
        return {"ok": False, "error": "no_key"}
    tone_desc = TONE_GUIDE.get(tone, TONE_GUIDE["friendly"])
    price_line = f"가격: {int(price):,}원\n" if price else ""
    sys_prompt = (
        "너는 쿠팡 파트너스 쓰레드(Threads) 글을 쓰는 한국인이다. 마케터가 아니라 그냥 사람이다.\n"
        "★1순위: 사람이 쓴 글처럼. AI 티가 나면 그 글은 실패다.\n"
        "구조: 본글 1개 + 답글 5개. 본글에는 링크 절대 넣지 마라.\n"
        "답글1~3: 공감 → 원인/발견 → 변화(링크 없음). 답글4: 링크+고지문구. 답글5: 마무리+링크+해시태그 3개.\n"
        "답글4에 '(광고) 쿠팡파트너스 활동으로 수수료를 받습니다' 포함.\n"
        "각 글 2~3줄, 400자 이내.\n\n"
        + HUMANIZE_RULES + "\n" + FEWSHOT + "\n" + QUALITY_RULES +
        '\n출력은 JSON만: {"posts":["본글","답글1","답글2","답글3","답글4","답글5"]}'
    )
    user_msg = (
        f"상품: {product_name}\n{price_line}링크: {deeplink}\n"
        f"말투/심리기제: {tone_desc}\n"
        f"{('추가 요청: '+extra) if extra else ''}\n\n"
        "예시들의 결(담백함·구체성·사람다움)을 그대로 따라 이 상품 글을 써라."
    )
    r = llm_chat(api_key, sys_prompt, user_msg, max_tokens=1400)
    if not r.get("ok"):
        return r
    try:
        posts = _parse_json_out(r["text"]).get("posts", [])
    except Exception as e:
        return {"ok": False, "error": "parse_error", "detail": str(e)[:100]}
    if len(posts) < 4:
        return {"ok": False, "error": "bad_format"}

    # ★사람다움 검증 루프: AI 티 검출되면 최대 2회까지 강제 재작성
    for _ in range(2):
        joined = "\n".join(str(p) for p in posts)
        tells = detect_ai_tells(joined)
        if not tells:
            break
        fixed = _humanize_pass(api_key, product_name, tone_desc, posts, tells)
        if not fixed:
            break
        posts = fixed

    # 남은 AI 티는 기계적으로 정리
    posts = [scrub_ai_artifacts(str(p)) for p in posts]
    return {"ok": True, "content": "\n===THREAD===\n".join(posts)}


# ── 무료 LLM 지원: 키 접두어로 제공자 자동 감지 ──
# Gemini(AIza...) = 무료 티어 / OpenRouter(sk-or-...) = 무료 모델 / Anthropic(sk-ant-...) = 유료
def detect_llm_provider(api_key):
    k = (api_key or "").strip()
    if k.startswith("AIza"): return "gemini"
    if k.startswith("sk-or-"): return "openrouter"
    if k.startswith("sk-ant-"): return "anthropic"
    return "unknown"


def _llm_gemini(api_key, sys_prompt, user_msg, max_tokens=1200):
    """Google Gemini — 무료 티어 (aistudio.google.com에서 키 발급)."""
    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro", "gemini-flash-latest"]
    last = {}
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": sys_prompt}]},
            "contents": [{"parts": [{"text": user_msg}]}],
            "generationConfig": {"temperature": 1.0, "maxOutputTokens": max_tokens,
                                 "responseMimeType": "application/json"},
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60, context=_ctx) as r:
                data = json.loads(r.read().decode())
            cands = data.get("candidates", [])
            if not cands:
                last = {"ok": False, "error": "no_candidates"}; continue
            text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))
            return {"ok": True, "text": text.strip()}
        except urllib.error.HTTPError as e:
            detail = ""
            try: detail = e.read().decode()[:200]
            except Exception: pass
            last = {"ok": False, "error": f"http_{e.code}", "detail": detail}
            if e.code in (401, 403): return last
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
    PREFER = ["nemotron-3-ultra", "nemotron-3-super", "qwen3-next-80b", "gpt-oss-120b",
              "llama-3.3-70b", "gemma-4-31b", "gemma-4-26b", "hy3", "nemotron-3-nano-30b"]
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/models")
        data = json.loads(urllib.request.urlopen(req, timeout=15, context=_ctx).read())
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


def _llm_openrouter(api_key, sys_prompt, user_msg, max_tokens=1200):
    """OpenRouter — :free 모델만 사용 (0원). 살아있는 모델 실시간 조회."""
    models = _openrouter_free_models()
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
            with urllib.request.urlopen(req, timeout=90, context=_ctx) as r:
                data = json.loads(r.read().decode())
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if text and text.strip():
                return {"ok": True, "text": text.strip(), "model": m}
            last = {"ok": False, "error": "empty"}
        except urllib.error.HTTPError as e:
            detail = ""
            try: detail = e.read().decode()[:200]
            except Exception: pass
            last = {"ok": False, "error": f"http_{e.code}", "detail": detail}
            if e.code in (401, 403): return last
            continue
        except Exception as e:
            last = {"ok": False, "error": str(e)[:120]}; continue
    return last


def _llm_anthropic(api_key, sys_prompt, user_msg, max_tokens=1200):
    """Anthropic Claude — 유료(크레딧 필요)."""
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
            continue
        except Exception as e:
            last = {"ok": False, "error": str(e)[:120]}; continue
    return last


def llm_chat(api_key, sys_prompt, user_msg, max_tokens=1200):
    """어떤 키든 자동 라우팅 (Gemini 무료 / OpenRouter 무료 / Claude 유료)."""
    p = detect_llm_provider(api_key)
    if p == "gemini": return _llm_gemini(api_key, sys_prompt, user_msg, max_tokens)
    if p == "openrouter": return _llm_openrouter(api_key, sys_prompt, user_msg, max_tokens)
    if p == "anthropic": return _llm_anthropic(api_key, sys_prompt, user_msg, max_tokens)
    return {"ok": False, "error": "unknown_key", "detail": "키 형식을 알 수 없어요 (AIza… / sk-or-… / sk-ant-…)"}


def _parse_json_out(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t).strip()
    return json.loads(t)


# ── 퀄리티 핵심: 실제 잘 쓴 글을 few-shot 예시로 (사용자 검증 샘플) ──
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

QUALITY_RULES = '''품질 기준(반드시 지킬 것):
1) 첫 문장에 제품명을 넣지 마라. 상황부터 시작해라.
2) 구체적 숫자·시간·장면을 최소 1개 넣어라(며칠, 몇 시, 몇 원, 몇 번).
3) '~해요 좋아요' 식 뭉뚱그린 칭찬 금지. 무엇이 어떻게 달라졌는지 써라.
4) '강추', '대박', '필수템', '후회 없는 선택' 같은 광고 클리셰 금지.
5) 단점이나 의외의 점을 한 줄 넣으면 신뢰도가 올라간다.
6) 이 글을 다른 제품에 그대로 붙여도 말이 되면 실패다. 이 제품에만 맞는 디테일을 써라.
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
    r = llm_chat(api_key, sys_p, user_p, max_tokens=1300)
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
- 문장 길이를 들쭉날쭉하게. 한 줄짜리 짧은 문장을 섞어라.
- 완결된 결론·요약으로 끝내지 마라. 말하다 만 것처럼 툭 끊어도 된다.
- 사소한 곁가지를 하나 넣어라(관련 없어 보이는 개인적 디테일).
- 자기 확신을 낮춰라. "~인 것 같다", "~더라", "~였음" 같은 관찰조.
- 과장·감탄사·이모지 최소(0~1개). 느낌표 남발 금지.
- 브랜드명을 반복하지 마라. 대명사나 '이거'로 받아라.
- 문장을 병렬로 예쁘게 맞추지 마라(AI 티의 대표).
- 사전 같은 설명 금지. 겪은 것만 써라.
금지어(절대 쓰지 마라): 강추, 필수템, 인생템, 갓성비, 적극 추천, 후회 없는 선택,
정말 좋아요, 대만족, 여러분, 다양한, 뛰어난, 최고의, 완벽한, 결론적으로, 종합적으로,
도움이 되셨길, 참고하시기 바랍니다.
'''


def detect_ai_tells(text):
    """AI 티 나는 표현 검출 → 리스트 반환."""
    found = []
    t = text or ""
    for w in AI_TELLS:
        if w in t:
            found.append(w)
    return found


def scrub_ai_artifacts(text):
    """기계적 정리: AI 특유 문장부호·공백 정리."""
    t = text or ""
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
    r = llm_chat(api_key, sys_p, user_p, max_tokens=1300)
    if not r.get("ok"):
        return None
    try:
        out = _parse_json_out(r["text"]).get("posts", [])
        return out if len(out) >= 4 else None
    except Exception:
        return None
