# -*- coding: utf-8 -*-
"""선물레이더 — 앱인토스 미니앱용 선물 큐레이션 엔진.
받는 사람+예산+취향 -> LLM이 '뻔하지 않은' 선물 방향 3개 -> 쿠팡 실상품+딥링크 매핑."""
import os
import json
import time

from core import llm_chat, scrub_garbled, _parse_json_out, CoupangPartners

_SYS = (
    "너는 니치하고 감각적인 선물을 잘 고르는 큐레이터다.\n"
    "뻔한 것(기프티콘·현금·양말)은 피하고, 받는 사람이 '어떻게 알았지' 싶을 물건을 고른다.\n"
    "각 추천은 (1)쿠팡에서 검색 가능한 구체적 상품 키워드 (2)왜 이 사람에게 맞는지 한 줄 이유.\n"
    "이유는 광고 문구가 아니라 친구가 귀띔하는 말투. 과장 금지.\n"
    "출력은 JSON만."
)


def recommend(api_key, who, budget, taste):
    user = (
        f"받는 사람: {who}\n예산: {budget}\n취향 힌트: {taste or '없음'}\n\n"
        "선물 방향 3개. 서로 다른 계열로(예: 감각적 소품 / 실용 업그레이드 / 경험·취미).\n"
        'JSON: {"picks":[{"keyword":"쿠팡 검색어(2~4단어)","reason":"한 줄 이유","angle":"계열 이름"}x3]}'
    )
    r = llm_chat(api_key, _SYS, user, max_tokens=900)
    if not r.get("ok"):
        return {"ok": False, "error": "추천 생성 실패"}
    try:
        picks = _parse_json_out(r["text"]).get("picks", [])[:3]
    except Exception:
        return {"ok": False, "error": "추천 형식 오류"}
    if not picks:
        return {"ok": False, "error": "추천이 비었어요"}

    # 쿠팡 실상품 매핑 (서버 파트너스 키)
    ck = os.environ.get("COUPANG_ACCESS", "")
    cs = os.environ.get("COUPANG_SECRET", "")
    cp = CoupangPartners(ck, cs) if ck and cs else None
    out = []
    for p in picks:
        kw = scrub_garbled(str(p.get("keyword") or ""))[:40]
        item = {"keyword": kw,
                "reason": scrub_garbled(str(p.get("reason") or ""))[:160],
                "angle": scrub_garbled(str(p.get("angle") or ""))[:20],
                "products": []}
        if cp and kw:
            try:
                found = cp.search_products(kw, limit=3) or []
                item["products"] = [{
                    "name": f.get("name", "")[:60],
                    "price": f.get("price"),
                    "image": f.get("image"),
                    "link": f.get("url"),   # 파트너스 검색 결과 URL은 이미 수익 트래킹 링크
                } for f in found[:3]]
            except Exception:
                pass
        out.append(item)
        time.sleep(0.2)
    return {"ok": True, "picks": out}
