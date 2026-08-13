# -*- coding: utf-8 -*-
"""4층: 인용 가능성 — AI 응답이 아니라 스토어 페이지 자체를 본다.
1~3층은 대부분 0이 나오지만 이 층은 항상 점수가 움직이고, 처방이 구체적이다."""
import re, json, urllib.request, urllib.error

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

def fetch(url, timeout=15):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA,
            "Accept-Language": "ko-KR,ko;q=0.9"})
        raw = urllib.request.urlopen(r, timeout=timeout).read()
        for enc in ("utf-8", "euc-kr", "cp949"):
            try: return raw.decode(enc)
            except Exception: pass
        return raw.decode("utf-8", "ignore")
    except Exception as e:
        return None

def analyze(html, store_name=""):
    """AI가 읽을 수 있는 형태인지 점수화(0~10)와 구체 지적."""
    if not html:
        return {"score": 0, "ok": False,
                "issues": ["페이지를 불러올 수 없었습니다(봇 차단 또는 주소 오류)."],
                "detail": {}}
    body = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text).strip()

    imgs = len(re.findall(r"<img[^>]*>", html, re.I))
    # 지표
    txt_len = len(text)
    q_marks = text.count("?") + len(re.findall(r"(요\?|나요|까요|무엇|어떻게|왜)", text))
    has_ld = bool(re.search(r'application/ld\+json', html, re.I))
    has_h = len(re.findall(r"<h[1-3][^>]*>", html, re.I))
    has_meta = bool(re.search(r'name=["\']description["\']', html, re.I))
    has_faq = bool(re.search(r'(FAQ|자주\s*묻는|Q&A|자주하는질문)', text, re.I))
    tbl = len(re.findall(r"<t[hd][^>]*>", html, re.I))

    score, issues, good = 0, [], []
    if txt_len >= 1200: score += 3; good.append("본문 텍스트가 충분합니다")
    elif txt_len >= 500: score += 2; issues.append("본문 텍스트가 짧습니다(%d자). AI는 이미지 속 글자를 읽지 못합니다." % txt_len)
    else: issues.append("본문 텍스트가 %d자뿐입니다. 상품 설명이 이미지에만 있으면 AI에게는 빈 페이지입니다." % txt_len)

    if has_ld: score += 2; good.append("구조화 데이터(JSON-LD)가 있습니다")
    else: issues.append("구조화 데이터(JSON-LD)가 없습니다. 상품명·가격·브랜드를 기계가 읽을 형태로 넣으세요.")

    if q_marks >= 5: score += 2; good.append("질문형 문장이 있습니다")
    else: issues.append("질문형 문장이 거의 없습니다(%d개). AI는 질문-답변 형식을 우선 인용합니다." % q_marks)

    if has_faq: score += 1; good.append("FAQ 영역이 있습니다")
    else: issues.append("FAQ 영역이 없습니다. 손님이 실제로 묻는 3가지를 텍스트로 넣으세요.")

    if has_h >= 3: score += 1; good.append("제목 구조(H1~H3)가 있습니다")
    else: issues.append("제목 태그가 %d개뿐입니다. 소제목으로 내용을 나누면 인용 단위가 생깁니다." % has_h)

    if tbl >= 4 or has_meta: score += 1
    if imgs > 20 and txt_len < 800:
        issues.append("이미지 %d장 대비 텍스트가 %d자입니다. 정보가 이미지에 갇혀 있습니다." % (imgs, txt_len))

    return {"score": min(score, 10), "ok": True, "issues": issues[:5], "good": good[:3],
            "detail": {"text_len": txt_len, "images": imgs, "questions": q_marks,
                       "jsonld": has_ld, "headings": has_h, "faq": has_faq}}

def diagnose(url, store_name=""):
    if not url: return None
    if not url.startswith("http"): url = "https://" + url
    return analyze(fetch(url), store_name)

# ── 플랫폼 판별 및 구조적 진단 ──────────────────────
PLATFORMS = {
    "smartstore.naver.com": ("네이버 스마트스토어", "blocked",
        "AI 크롤러 접근이 차단돼 있습니다. 상품 정보가 AI에게 도달할 경로가 사실상 없습니다."),
    "coupang.com": ("쿠팡", "thin",
        "상세 정보가 대부분 이미지로 들어가 AI가 읽을 텍스트가 거의 없습니다."),
    "shopping.naver.com": ("네이버쇼핑", "blocked",
        "AI 크롤러 접근이 제한적입니다."),
    "11st.co.kr": ("11번가", "thin", "상세가 이미지 중심이라 AI가 읽을 텍스트가 적습니다."),
    "gmarket.co.kr": ("G마켓", "thin", "상세가 이미지 중심입니다."),
}

def platform_of(url):
    u = (url or "").lower()
    for host, info in PLATFORMS.items():
        if host in u:
            return info
    return ("자사몰/기타", "open", "")

def diagnose_v2(url, store_name=""):
    """플랫폼 구조까지 반영한 4층 진단."""
    if not url:
        return {"score": 0, "ok": False, "platform": None,
                "issues": ["스토어 주소가 없어 페이지 진단을 건너뜁니다."]}
    if not url.startswith("http"):
        url = "https://" + url
    name, kind, note = platform_of(url)
    if kind == "blocked":
        return {"score": 0, "ok": True, "platform": name, "blocked": True,
                "issues": [
                    "%s는 %s" % (name, note),
                    "AI가 인용할 수 있는 건 스토어 밖의 글입니다 — 블로그·리뷰·커뮤니티 언급.",
                    "같은 상품이라도 자사몰이나 블로그가 있는 쪽이 AI에 먼저 불립니다.",
                ],
                "good": [], "detail": {"platform_blocked": True}}
    r = analyze(fetch(url), store_name)
    r["platform"] = name
    if kind == "thin" and r.get("ok"):
        r["issues"] = ([note] + r.get("issues", []))[:5]
        r["score"] = min(r.get("score", 0), 4)
    return r

if __name__ == "__main__":
    import sys
    print(json.dumps(diagnose_v2(sys.argv[1]), ensure_ascii=False, indent=1))
