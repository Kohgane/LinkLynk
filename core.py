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


def make_blog_draft(product_name: str, deeplink: str, tone: str = "friendly", channel: str = "blog", info: dict = None) -> str:
    """플랫폼별 맞춤 초안. ★매번 다른 글 + ★상품 카테고리 반영(휴머나이저)."""
    name = product_name
    first = name.split()[0] if name else "이거"
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
        # 본글: 훅 유형 랜덤 (하소연/질문/정보/실패담/TMI)
        posts = [
            f"{first} 이런 거 찾다가 시간 다 씀…\n다들 어떻게 고르는지 궁금",
            f"{first} 이거 하나 사려다 3시간 검색함ㅋㅋ 현타옴",
            f"솔직히 {first} 이런 거 다 거기서 거기 아님? 했는데",
            f"{first} 잘못 사서 돈 날린 적 있어서 이번엔 신중하게 골랐음",
            f"요즘 {first} 뭐 쓰냐고 물어보는 사람 많아서 그냥 여기 적음",
            f"{first} 없을 때랑 있을 때랑 삶의 질이 다름 진짜",
        ]
        r1s = [
            f"며칠 고민하다 그냥 질렀는데\n{cat_line} 생각보다 만족",
            f"처음엔 별 기대 안 했는데\n{cat_line} 의외로 계속 손이 감",
            "리뷰 엄청 뒤지다가 결국 이거 골랐음",
            f"반신반의하면서 샀는데\n{cat_line} 웬걸",
        ]
        r2s = [
            f"{'가격도 '+price_txt+'이라 부담 없었고' if price_txt else '가격도 생각보다 착했고'}\n써보니 확실히 다름",
            f"{'가격 '+price_txt+' 정도였는데' if price_txt else '가격도 적당했는데'}\n이 값이면 만족",
            "비싼 거랑 비교해봤는데\n이걸로도 충분하더라",
        ]
        r3s = [
            "처음엔 반신반의했는데\n이젠 없으면 아쉬울 듯",
            "지금은 주변에도 추천하고 다님ㅋㅋ",
            "재구매 의사 100%임",
            "괜히 고민했나 싶을 정도",
        ]
        # 링크 안내: 로테이션 (클리셰 피하기)
        link_intros = [
            "찾기 귀찮을까 봐 밑에 링크 둠 👇",
            "궁금한 사람 있을까 봐 걸어둠",
            "광고 맞음ㅋㅋ 그래도 쓰는 건 진짜",
            "밑에 링크.",
            "혹시 몰라 남겨둠 👇",
        ]
        r4 = f"{R(link_intros)}\n{deeplink}\n\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다"
        endings = [
            f"암튼 나만 알기 아까워서 공유함ㅋㅋ\n{deeplink}",
            f"도움 됐으면 좋겠음\n{deeplink}",
            f"다들 뭐 쓰는지 댓글로 알려줘요\n{deeplink}",
            f"필요한 사람 참고하셈\n{deeplink}",
        ]
        r5 = f"{R(endings)}\n\n#{first} " + R(["#추천템", "#내돈내산", "#꿀템"])
        parts = [R(posts), R(r1s), R(r2s), R(r3s), r4, r5]
        return "\n===THREAD===\n".join(parts)

    # ── 인스타: 감성, 매번 다른 캡션·해시태그 ──
    if channel == "insta":
        opens = [
            f"✨ {name} ✨", f"🤍 {first} 기록 🤍", f"📌 요즘 최애템 : {first}",
            f"⭐ {name} ⭐", f"💫 데일리 {first} 💫",
        ]
        bodies = [
            "요즘 데일리로 챙기는 아이템 🤍",
            "몇 번을 재구매하는지 모르겠어요",
            "한번 쓰면 계속 찾게 되는 그런 거 있잖아요",
            "친구들이 자꾸 물어봐서 공유해요",
            "고민하다 샀는데 완전 만족 중이에요",
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


def zernio_publish(api_key, platforms, content, media_urls=None, account_ids=None):
    """Zernio API로 SNS 즉시 게시. platforms=['threads','instagram','x'...].
    account_ids: {platform: accountId} 지정 시 그 계정으로 게시 (4개 중 선택).
    실제 API 형식: platforms=[{platform,accountId}], mediaItems=[{type,url}], publishNow=true.
    x는 Zernio에서 'twitter'로 매핑."""
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
        # 지정된 계정 우선, 없으면 해당 플랫폼 첫 계정
        aid = account_ids.get(p) or account_ids.get(zp) or accounts.get(zp)
        if aid:
            targets.append({"platform": zp, "accountId": aid})
    if not targets:
        connected = ", ".join(accounts.keys()) or "없음"
        return {"ok": False, "error": "platform_not_connected",
                "detail": f"해당 플랫폼이 연결 안 됨 (연결된 것: {connected})"}
    payload = {"content": content, "platforms": targets, "publishNow": True}
    if media_urls:
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
