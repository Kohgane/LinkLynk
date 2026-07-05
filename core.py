"""
LinkLynk — 코어 모듈
쿠팡 파트너스 딥링크 생성 + 고지문구 삽입 + 블로그 초안 생성
서버(app.py)에서 import해서 사용.
"""
import hmac, hashlib, time, urllib.request, json, ssl, re

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


def is_valid_coupang_url(url: str) -> bool:
    """쿠팡 상품/카테고리 URL인지 확인."""
    return bool(re.match(r'https?://(www\.)?coupang\.com/', url.strip()))


def append_disclosure(text: str) -> str:
    """블로그 초안 하단에 고지문구 자동 삽입 (없으면)."""
    if COUPANG_DISCLOSURE[:20] in text:
        return text
    return text.rstrip() + "\n\n---\n" + COUPANG_DISCLOSURE


def make_blog_draft(product_name: str, deeplink: str, tone: str = "friendly", channel: str = "blog") -> str:
    """채널별 맞춤 초안. 블로그=길게, SNS(쓰레드/X/인스타)=짧게."""
    # 짧은 SNS 채널
    if channel in ("x", "threads"):
        body = (
            "{name} 이거 진짜 괜찮아요 👀\n\n"
            "고민되면 한번 보세요\n"
            "👉 {link}\n"
        ).format(name=product_name, link=deeplink)
        return append_disclosure(body)
    if channel == "insta":
        body = (
            "{name} ✨\n\n"
            "요즘 제가 잘 쓰고 있는 거예요!\n"
            "자세한 건 프로필 링크에서 확인하세요 👆\n\n"
            "👉 {link}\n"
        ).format(name=product_name, link=deeplink)
        return append_disclosure(body)
    # 블로그/유튜브 = 긴 형식 (톤 선택)
    templates = {
        "friendly": (
            "요즘 {name} 찾는 분들 많으시죠?\n\n"
            "직접 써보고 괜찮아서 소개해드려요. "
            "고민되셨다면 아래 링크에서 한 번 확인해보세요!\n\n"
            "👉 {name} 보러가기: {link}\n"
        ),
        "review": (
            "[{name} 솔직 후기]\n\n"
            "장점과 단점을 정리해봤어요. "
            "구매 전에 참고하시면 좋을 것 같습니다.\n\n"
            "👉 최저가 확인: {link}\n"
        ),
        "clean": (
            "{name}\n\n"
            "제품 정보와 구매처를 안내드립니다.\n\n"
            "👉 상품 보기: {link}\n"
        ),
    }
    body = templates.get(tone, templates["friendly"]).format(name=product_name, link=deeplink)
    return append_disclosure(body)
