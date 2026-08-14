# -*- coding: utf-8 -*-
"""
보임(BOIM) — AI 검색 노출 진단 엔진
"챗GPT가 당신 상품을 팔아주고 있습니까?"

스토어명 + 업종 키워드를 받아, 실제 쇼핑 질문을 AI들에게 던지고
답변에 그 스토어(또는 경쟁사)가 등장하는지 파싱해 점수화한다.
LinkLynk의 LLM 라우팅(core.llm_chat)을 재활용한다.
"""
import re
import json
import time

from core import llm_chat, scrub_garbled

# ── 업종별 쇼핑 질문 시나리오 (사람이 AI에게 실제로 묻는 방식) ──
_SCENARIO_TPL = {
    "generic": [
        "{kw} 추천해줘",
        "{kw} 어디서 사는 게 좋아?",
        "{kw} 살 만한 온라인 스토어 알려줘",
        "{kw} 선물하려는데 괜찮은 곳 있어?",
        "한국에서 {kw} 파는 좋은 쇼핑몰 알려줘",
        "{kw} 믿을 만한 판매처 추천",
    ],
    "니치": [
        "남들 잘 모르는 {kw} 브랜드 추천해줘",
        "{kw} 매니아들이 가는 스토어 알려줘",
    ],
}


def build_queries(keywords, store_name):
    """키워드당 질문 4~6개 생성 (총 12개 이내)."""
    out = []
    for kw in keywords[:3]:
        for t in _SCENARIO_TPL["generic"][:4]:
            out.append(t.format(kw=kw))
    return out[:12]


def _ask_ai(api_key, query):
    """쇼핑 질문 하나를 AI에게 물어본다 — 실제 소비자처럼."""
    r = llm_chat(
        api_key,
        "너는 한국 소비자의 쇼핑 질문에 답하는 AI 어시스턴트다. "
        "구체적인 브랜드·스토어·상품명을 들어 실용적으로 답해라.",
        query, max_tokens=700)
    if not r.get("ok"):
        return None
    return r.get("text") or ""


def _find_mentions(text, store_name, aliases):
    """답변에 스토어가 언급됐는지 + 어떤 경쟁 이름들이 나왔는지."""
    if not text:
        return False, []
    t = text.lower()
    hit = any(a.lower() in t for a in [store_name] + aliases if a)
    # 경쟁사 후보: 답변에 나온 고유명 패턴 (한글 2~10자 + 스토어/샵/몰/마켓 등, 또는 영문 브랜드)
    comps = set()
    for m in re.finditer(r"([가-힣A-Za-z0-9&.\-]{2,16})", text):
        w = m.group(1).strip(".-&")
        # 꼬리 조사 제거 (와/과/도/은/는/이/가/을/를/의/에/로/랑)
        w = re.sub(r"(와|과|도|은|는|이|가|을|를|의|에|로|랑)$", "", w) if len(w) > 2 else w
        if len(w) < 2 or w.isdigit():
            continue
        comps.add(w)
    # 일반명사 대충 걸러내기 (조사·서술어가 붙기 쉬운 흔한 단어)
    NOISE = {"추천", "온라인", "쇼핑몰", "스토어", "브랜드", "제품", "상품", "구매",
             "가격", "판매", "한국", "네이버", "쿠팡", "지마켓", "옥션", "믿을",
             "괜찮", "좋은", "이런", "다양", "인기", "대표", "유명", "그리고", "하지만",
             "같은", "니치", "향수", "편집샵", "선물", "정도", "경우", "이후", "또한",
             "가장", "특히", "먼저", "추천드", "구입", "이용", "주문", "배송",
             "구매할", "특징", "장점", "단점", "종류", "관련", "위주", "기준",
             "백화점", "면세점", "공식몰", "공식홈", "매장", "오프라인",
             "https", "http", "www", "com", "co.kr", "공식", "있는", "맞는",
             "평가", "리뷰", "후기", "가능", "무료", "할인", "특가", "세일"}

    def _looks_like_name(w):
        # 조사·서술어 꼬리가 붙은 일반 단어 걸러내기
        BAD_TAIL = ("니다", "세요", "라면", "이라", "하고", "부터", "까지", "에서",
                    "이고", "예요", "어요", "라서", "지만", "든지", "네요", "고요",
                    "시면", "하면", "으로", "스러운", "적인", "스럽", "다면", "려면")
        if any(w.endswith(t) for t in BAD_TAIL):
            return False
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9&.\-]{1,15}", w):
            # URL 조각(도메인 파편)은 제외
            return w.lower() not in ("https", "http", "www", "com", "net", "org", "kr")
        # 한글 이름: 2~8자, 받침 있는 서술형 아닌 것
        return 2 <= len(w) <= 8

    comps = [c for c in comps if c not in NOISE and _looks_like_name(c)][:12]
    return hit, comps


def run_scan(api_key, store_name, keywords, aliases=None, progress_cb=None, store_url=None):
    """진단 실행. api_key는 LinkLynk LLM 키(무엇이든) — '__free__' 가능."""
    aliases = aliases or []
    queries = build_queries(keywords, store_name)
    results = []
    comp_count = {}
    hits = 0

    for i, q in enumerate(queries):
        ans = _ask_ai(api_key, q)
        if ans is None:
            results.append({"query": q, "ok": False})
            continue
        ans = scrub_garbled(ans)
        hit, comps = _find_mentions(ans, store_name, aliases)
        if hit:
            hits += 1
        for c in comps:
            comp_count[c] = comp_count.get(c, 0) + 1
        results.append({
            "query": q, "ok": True, "mentioned": hit,
            "answer_head": ans[:280],
        })
        if progress_cb:
            progress_cb(i + 1, len(queries))
        time.sleep(0.4)          # 무료 한도 배려

    asked = sum(1 for r in results if r.get("ok"))
    # ── 4층 채점 ────────────────────────────────────
    #  1~3층은 중소 스토어면 대부분 0이 나온다. 4층(인용 가능성)이
    #  실제로 움직이는 축이고, 처방이 나오는 자리다.
    mention_score = int(round(70 * hits / asked)) if asked else 0   # 1~2층 합산 70점
    page = None
    try:
        import boim_page_v1 as _bp
        page = _bp.diagnose_v2(store_url, store_name) if store_url else None
    except Exception:
        page = None
    page_score = (page or {}).get("score", 0) * 3        # 10점 만점 → 30점
    score = min(100, mention_score + page_score)
    top_comps = sorted(((k, v) for k, v in comp_count.items() if v >= 2),
                       key=lambda x: -x[1])[:8]

    # 진단 소견
    if asked == 0:
        verdict = "AI 응답을 받지 못했어요. 잠시 후 다시 시도해주세요."
        grade = "?"
    elif score == 0:
        _blk = (page or {}).get("blocked")
        verdict = ("AI가 인용할 소스 자체가 없습니다. "
                   + ("스토어 페이지가 AI 크롤러에 막혀 있고, 밖에도 참조할 글이 없습니다."
                      if _blk else
                      "쇼핑 질문 어디에도 등장하지 않았고, 페이지도 인용될 형태가 아닙니다."))
        grade = "F"
    elif score < 20:
        verdict = "일부 질문에서만 등장합니다. 노출 기반은 있지만 매우 약합니다."
        grade = "D"
    elif score < 45:
        verdict = "절반 이하의 질문에서 등장합니다. 구조화를 강화하면 올라갈 여지가 큽니다."
        grade = "C"
    elif score < 70:
        verdict = "양호합니다. 경쟁 스토어보다 자주 언급되는지 비교해보세요."
        grade = "B"
    else:
        verdict = "훌륭합니다. AI가 이미 당신 스토어를 추천하고 있습니다."
        grade = "A"

    # ★선택 대행: 등급별로 '지금 딱 하나' 단 하나의 액션만 준다.
    #  10개를 주면 0개를 한다. 하나를 주면 한다.
    # ★액션은 등급이 아니라 '무엇이 비었는지'로 고른다.
    #  언급 0인데 "이미 불리는 질문을 찾아라"는 말이 안 된다.
    _pg = page or {}
    _det = _pg.get("detail") or {}
    _blocked = _pg.get("blocked")
    if grade == "?":
        next_one = ""
        risk = ""
    elif _blocked:
        next_one = ("스토어 밖에 글 하나를 만드세요. 블로그든 어디든, "
                    "대표 상품을 설명하는 텍스트가 검색되는 곳에 있어야 합니다.")
        risk = ("이 플랫폼은 AI 크롤러 접근이 막혀 있습니다. "
                "안에서 아무리 잘 써도 AI는 그 글을 볼 수 없습니다.")
    elif _det.get("text_len", 0) < 800:
        next_one = ("대표 상품 하나의 설명을 이미지에서 꺼내 텍스트로 옮기세요. "
                    "성분·크기·사용법을 문장으로 적으면 됩니다.")
        risk = ("상세가 이미지뿐이면 AI에게는 빈 페이지입니다. "
                "상품이 좋아도 인용할 문장 자체가 없습니다.")
    elif _det.get("questions", 0) < 5:
        next_one = ("사람들이 실제로 묻는 질문 3개와 답을 상품 설명에 그대로 넣으세요. "
                    "\"세탁기에 써도 되나요?\" 같은 문장 그대로요.")
        risk = ("AI는 질문-답변 형식을 우선 인용합니다. "
                "설명문만 있으면 읽어도 인용 단위를 못 만듭니다.")
    elif not _det.get("jsonld"):
        next_one = ("상품명·가격·브랜드를 구조화 데이터(JSON-LD)로 넣으세요. "
                    "쇼핑몰 솔루션이면 대부분 설정 한 번으로 됩니다.")
        risk = "기계가 읽을 형태가 없으면 AI는 페이지를 추측으로 해석합니다."
    elif hits == 0:
        next_one = ("좁은 질문 하나를 정하고 그 답을 페이지에 명시하세요. "
                    "\"입문용 OO 추천\" 같은 조건이 붙은 질문이 뚫기 쉽습니다.")
        risk = "넓은 질문은 대형 브랜드가 가져갑니다. 좁은 질문에서 먼저 자리를 잡아야 합니다."
    elif grade == "?":
        next_one = ""
        risk = ""
    elif grade == "F":
        next_one = "대표 상품 하나만 골라, 사람들이 물어볼 질문 3개와 답을 상품 설명에 텍스트로 넣으세요."
        risk = "상세페이지가 이미지 한 장이면 AI는 그 안의 글자를 전혀 읽지 못합니다. 상품이 좋아도 인용할 문장이 없으면 영영 불리지 않습니다."
    elif grade == "D":
        next_one = "이미 불리는 그 질문 하나를 찾아, 같은 형식으로 상품을 두 개 더 정리하세요."
        risk = "지금 불리는 것이 우연일 수 있습니다. 형식이 없으면 다음 모델 업데이트에서 사라집니다."
    elif grade == "C":
        next_one = "경쟁사가 불리는 질문 하나를 골라, 그 질문에 당신이 더 정확히 답하는 문장을 만드세요."
        risk = "절반은 이미 왔습니다. 여기서 멈추면 먼저 형식을 갖춘 쪽이 그 자리를 굳힙니다."
    elif grade == "B":
        next_one = "가장 좁은 질문(가격대·용도·입문용)에서 확실히 1등이 되도록 그 조건을 명시하세요."
        risk = "넓은 질문은 대형 브랜드가 가져갑니다. 좁은 질문을 놓치면 남는 자리가 없습니다."
    else:
        next_one = "지금 상태를 기록으로 남기고, 매주 같은 질문으로 변화를 추적하세요."
        risk = "AI 응답은 모델이 바뀌면 함께 바뀝니다. 오늘의 결과가 내일을 보장하지 않습니다."

    return {
        "next_one": next_one,
        "risk": risk,
        "ok": True,
        "store": store_name,
        "keywords": keywords,
        "asked": asked,
        "mentioned": hits,
        "score": score,
        "grade": grade,
        "verdict": verdict,
        "competitors": [{"name": k, "count": v} for k, v in top_comps],
        # ★4층: 페이지 인용 가능성 — 이게 실제 처방이 나오는 자리다
        "page": page,
        "mention_score": mention_score,
        "page_score": page_score,
        "results": results,
    }


# ══════════ 부스트 실행 키트 — FAQ·텍스트 설명 생성 ══════════
from core import _parse_json_out

_KIT_SYS = (
    "너는 한국 이커머스 셀러의 상세페이지를 돕는 카피 에디터다.\n"
    "★절대 규칙: 사실을 지어내지 마라. 배송일·원산지·인증·수치처럼 가게마다 다른 정보는 "
    "반드시 [대괄호]로 비워둬라. 예: '결제 후 [1~2일] 내 출고됩니다.'\n"
    "구매자가 실제로 묻는 것(정품·배송·반품·사용법·선물포장·차이점)에 미리 답하는 FAQ를 쓴다.\n"
    "말투는 정중하되 딱딱하지 않게. 과장 광고 문구(최고·완벽·강추) 금지.\n"
    "출력은 JSON만."
)


def build_kit_product(api_key, store_name, product_name, keywords):
    """상품 1개의 FAQ 10문답 + 텍스트 설명 블록."""
    user = (
        f"스토어: {store_name}\n상품: {product_name}\n업종: {', '.join(keywords)}\n\n"
        "1) 이 상품 구매자가 결제 전에 실제로 궁금해할 질문 10개와 답변.\n"
        "   - 정품/출처, 배송, 반품/교환, 사용법·보관, 선물 관련, 비슷한 상품과의 차이 등을 섞어라.\n"
        "   - 가게마다 다른 사실은 [대괄호]로 비워둬라.\n"
        "2) 검색과 AI가 읽을 수 있는 텍스트 상품 설명 400~600자.\n"
        "   - 이미지 없이 글만으로 상품이 그려지게. 상품명·용도·특징·어울리는 사람.\n"
        '출력 JSON: {"faq":[{"q":"...","a":"..."}x10], "desc":"..."}'
    )
    r = llm_chat(api_key, _KIT_SYS, user, max_tokens=2600)
    if not r.get("ok"):
        return None
    try:
        d = _parse_json_out(r["text"])
        faq = [x for x in (d.get("faq") or []) if x.get("q") and x.get("a")][:10]
        desc = scrub_garbled(str(d.get("desc") or ""))[:1200]
        if len(faq) < 5 or len(desc) < 100:
            return None
        return {"faq": [{"q": scrub_garbled(x["q"])[:120],
                         "a": scrub_garbled(x["a"])[:400]} for x in faq],
                "desc": desc}
    except Exception:
        return None


def build_brand_intro(api_key, store_name, keywords):
    """프로필·공지·상세 공통으로 쓸 브랜드 소개 표준 문안."""
    user = (
        f"스토어: {store_name}\n업종: {', '.join(keywords)}\n\n"
        "이 스토어의 표준 소개문을 만들어라.\n"
        "- 3~4문장, 250자 이내. 프로필·공지·상세 하단 어디든 똑같이 붙일 문안.\n"
        "- 스토어 이름을 정확히 한 번 포함(표기 통일용).\n"
        "- 가게마다 다른 사실([운영 연차], [주력 산지] 등)은 대괄호로 비워둬라.\n"
        '출력 JSON: {"intro":"..."}'
    )
    r = llm_chat(api_key, _KIT_SYS, user, max_tokens=600)
    if not r.get("ok"):
        return None
    try:
        t = scrub_garbled(str(_parse_json_out(r["text"]).get("intro") or ""))[:400]
        return t if len(t) > 50 else None
    except Exception:
        return None


def build_jsonld(store_name, product_name, desc, faq):
    """진단에서 'JSON-LD 없음'이 잡힌 경우 — 그대로 붙여넣는 구조화 데이터.
    기계가 읽을 형태가 없으면 AI는 페이지를 추측으로 해석한다."""
    import json as _j
    prod = {
        "@context": "https://schema.org", "@type": "Product",
        "name": product_name,
        "description": (desc or "")[:500],
        "brand": {"@type": "Brand", "name": store_name},
        "offers": {"@type": "Offer", "priceCurrency": "KRW",
                   "price": "[판매가]", "availability": "https://schema.org/InStock"},
    }
    faqp = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": x["q"],
                        "acceptedAnswer": {"@type": "Answer", "text": x["a"]}}
                       for x in (faq or [])[:6]],
    }
    def _tag(o):
        return ('<script type="application/ld+json">\n'
                + _j.dumps(o, ensure_ascii=False, indent=1) + "\n</script>")
    return {"product": _tag(prod), "faq": _tag(faqp),
            "howto": ("상세페이지 HTML 편집 모드에서 </body> 앞이나 "
                      "본문 맨 아래에 그대로 붙여넣으세요. "
                      "[판매가]는 실제 숫자로 바꾸세요.")}


def run_kit(api_key, store_name, keywords, products):
    """실행 키트 전체 생성. 상품 최대 3개."""
    out = {"ok": True, "store": store_name, "products": []}
    for pn in products[:3]:
        item = None
        for _ in range(2):                      # 약한 모델 대비 재시도
            item = build_kit_product(api_key, store_name, pn, keywords)
            if item:
                break
        _it = item or {"faq": [], "desc": ""}
        # ★진단 'JSON-LD 없음'에 대한 결과물 — 그대로 붙여넣는 구조화 데이터
        if _it.get("faq"):
            try:
                _it["jsonld"] = build_jsonld(store_name, pn, _it.get("desc"), _it.get("faq"))
            except Exception:
                pass
        out["products"].append({"name": pn, **_it})
        time.sleep(0.3)
    out["brand_intro"] = build_brand_intro(api_key, store_name, keywords) or ""
    made = sum(1 for p in out["products"] if p.get("faq"))
    if made == 0:
        return {"ok": False, "error": "생성에 실패했어요. 잠시 후 다시 시도해주세요."}
    return out


def build_teaser(api_key, store_name, product_name, keywords):
    """무료 맛보기 — FAQ 3문답만. 나머지는 잠금 표시용 질문 제목만."""
    full = build_kit_product(api_key, store_name, product_name, keywords)
    if not full or not full.get("faq"):
        return None
    faq = full["faq"]
    return {
        "product": product_name,
        "free": faq[:10],                                   # ★전량 무료 공개 (미끼)
        "locked": [],                                        # 잠금 없음 — 추적이 유료
        "desc_preview": (full.get("desc") or "")[:120],
    }
