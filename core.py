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
        "food":    (["과자","커피","차","간식","라면","음료","견과","초콜릿","젤리"],
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
    """상품명에서 핵심 키워드 추출 → 글에 자연스럽게 녹임.
    예: '슈어홈 BLDC 차일드락 14단 가정용 선풍기' → 핵심='선풍기', 특징=['BLDC','차일드락','14단','가정용']"""
    if not name:
        return {"core": "이거", "brand": "", "features": []}
    words = name.replace(",", " ").split()
    # 브랜드 = 보통 첫 단어 (한글/영문 고유명사)
    brand = words[0] if words else ""
    # 핵심 명사 = 보통 마지막 단어 (제품 종류)
    core = words[-1] if len(words) > 1 else (words[0] if words else "이거")
    # 특징 = 중간 단어들 (숫자+단위, 기능 키워드)
    features = []
    for w in words[1:-1] if len(words) > 2 else []:
        # 너무 짧거나 순수 숫자만은 제외, 의미있는 특징만
        if len(w) >= 2 and not w.isdigit():
            features.append(w)
    # 핵심에서 흔한 카테고리 명사 뽑기 (마지막 단어가 복합어면)
    return {"core": core, "brand": brand, "features": features[:3]}


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
            f"요즘 {first} 이거 하나로 버팀",
            f"{name} 진작 살걸 후회 중",
            f"별 기대 안 했는데 {first} 이거 의외로 대박",
            f"{name} 3주째 쓰는 중인데 만족도 높음",
            f"솔직히 {first} 이 가격이면 안 살 이유가 없음",
        ]
        tails = [
            f"{'지금 '+price_txt+' ' if price_txt else ''}👉 {deeplink}",
            f"필요한 사람 링크 👉 {deeplink}",
            f"밑에 링크 둠 {deeplink}",
            f"{'가격 '+price_txt+' ' if price_txt else ''}{deeplink}",
        ]
        tags = R([f"#쿠팡추천 #{first}", f"#{first} #추천템", f"#내돈내산 #{first}"])
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
                    f"{first} {core} 써보신 분 있으신가요? 후기 남겨봐요",
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
                    f"{first} {core} 실측 후기입니다",
                ],
                "r1": [f"핵심은 실사용 만족도인데\n{cat_line} 합격점이었습니다", "스펙보다 실제 사용감이 중요합니다", f"{feat+' 성능은 기대 이상이었습니다' if feat else '기본기가 탄탄합니다'}"],
                "r2": [f"{'가격 대비 성능이 '+price_txt+' 기준 우수합니다' if price_txt else '가성비가 뛰어납니다'}", "동급 대비 경쟁력 있습니다"],
                "r3": ["종합적으로 추천할 만합니다", "재구매 가치 있다고 판단됩니다"],
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
                "r3": ["이젠 없으면 아쉬울 듯", "재구매 의사 100%임", "주변에 다 영업하고 다니는 중ㅋㅋ"],
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
                    f"{first} {core} 써보고 있는데 만족 중이에요",
                    f"{core} 살까 말까 고민 많이 했는데 잘 산 것 같아요",
                ],
                "r1": [f"며칠 고민하다 샀는데\n{cat_line} 만족해요", f"처음엔 반신반의했는데\n{cat_line} 웬걸요ㅎㅎ", f"{feat+' 기능 은근 잘 써요' if feat else '생각보다 손이 자주 가요'}"],
                "r2": [f"{'가격도 '+price_txt+'이라 부담 없었어요' if price_txt else '가격도 착했어요'}\n써보니 좋더라고요", "이 값이면 충분한 것 같아요"],
                "r3": ["지금은 주변에도 추천 중이에요ㅎㅎ", "재구매 의사 100%예요"],
                "link": ["찾기 귀찮을까 봐 링크 둘게요 👇", "궁금한 분 있을까 봐 걸어둬요~"],
                "end": [f"도움 됐으면 좋겠어요\n{deeplink}", f"필요한 분 참고하세요~\n{deeplink}"],
            },
            "excited": {
                "posts": [f"{core} 이거 진짜 대박이에요!!! 🔥\n왜 이제 샀지 싶음", f"{core} 사고 완전 신세계 열림ㅠㅠ 미쳤다", f"{feat+' ' if feat else ''}{core} 이건 진짜 사야 함!! 강추!!"],
                "r1": [f"{cat_line} 첫날부터 감동;;;", "기대 이상이라 소리 질렀어요 진짜"],
                "r2": [f"{'가격 '+price_txt+'에 이 퀄?! 말도 안 됨' if price_txt else '이 가격에 이 퀄리티 실화?!'}", "가성비 미쳤어요 완전 이득!!"],
                "r3": ["벌써 하나 더 사려고요ㅋㅋㅋ", "주변에 다 사라고 영업 중!!"],
                "link": ["빨리 봐요 이거 👇🔥", "링크 여기!! 놓치지 마세요"],
                "end": [f"진짜 강추합니다!!!\n{deeplink}", f"안 사면 손해예요ㅠㅠ\n{deeplink}"],
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
        }
        P = POOLS.get(TONE, POOLS["friendly"])
        r4 = f"{R(P['link'])}\n{deeplink}\n\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다"
        r5 = f"{R(P['end'])}\n\n#{first} " + R(["#추천템", "#내돈내산", "#꿀템", f"#{core}"])
        parts = [R(P["posts"]), R(P["r1"]), R(P["r2"]), R(P["r3"]), r4, r5]
        return "\n===THREAD===\n".join(parts)

    # ── 인스타: 감성, 매번 다른 캡션·해시태그 ──
    if channel == "insta":
        opens = [
            f"✨ {name} ✨", f"🤍 {first} 기록 🤍", f"📌 요즘 최애템 : {first}",
            f"⭐ {name} ⭐", f"💫 데일리 {first} 💫",
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
        tags = f"#{first} " + " ".join(random.sample(base_tags, 4))
        body = (f"{R(opens)}\n\n{R(bodies)}\n"
                f"{'가격 '+price_txt+' / ' if price_txt else ''}{R(guides)}\n\n"
                f"👉 {deeplink}\n\n{tags}")
        return append_disclosure(body)

    # ── 유튜브: 설명란, 매번 다른 인트로 ──
    if channel == "youtube":
        intros = [
            f"📌 {name} 상세정보",
            f"📌 오늘 영상에서 소개한 {first}",
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
        f"[추천] {first} 고민이라면 {name} 어때요?",
        f"{name} 써보고 정리한 장단점",
        f"요즘 뜨는 {name}, 진짜 괜찮을까?",
        f"{first} 뭐 살지 고민이라면 (feat. {name})",
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
            f"{first} 살까 말까 고민했는데 그냥 질렀다. 후기 시작.",
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


def zernio_publish(api_key, platforms, content, media_urls=None, account_ids=None, thread_items=None, as_draft=False):
    """Zernio API로 SNS 게시. as_draft=True면 발행 안 하고 Zernio에 초안 저장.
    platforms=['threads','instagram','x'...]. account_ids: {platform: accountId} 지정.
    thread_items: 쓰레드/X 답글 체인. x→'twitter' 매핑."""
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
    # ★as_draft=True면 publishNow/scheduledFor 둘 다 생략 → Zernio 초안으로 저장
    if not as_draft:
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
