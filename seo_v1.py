# -*- coding: utf-8 -*-
"""
페이지 메타 중앙 주입 (og / twitter / description / canonical / 내부링크)

★왜 핸들러마다 안 고치고 여기서 하나
  페이지가 13개인데 어떤 건 send_static_file, 어떤 건 문자열 f-string,
  어떤 건 모듈이 돌려준다. 13군데를 각각 고치면 13번 깨질 수 있다.
  태그는 </head> 앞에 한 번만 끼우면 되므로 출구 한 곳에서 처리한다.

★원칙 — before_request 사고의 재발 방지
  1. 아는 경로만 건드린다. META 에 없으면 응답을 그대로 돌려준다.
  2. 이미 그 태그가 있으면 덮어쓰지 않는다. 페이지가 제 og 를 들고 있으면
     그쪽이 맞다 (예: /dwaeji, /sky 는 자기 카드가 이미 있다).
  3. 예외는 전부 삼킨다. 메타가 안 붙는 건 아쉬운 일이고,
     페이지가 안 뜨는 건 장사가 멈추는 일이다.

★왜 og:image 가 비어 있었나 (2026-10-14 실측)
  /gottago-og.png, /giftradar-og.png, /penaltyradar-og.png 는 200 으로
  살아 있는데 정작 페이지가 그걸 가리키지 않았다. 이미지는 만들어 두고
  배선만 빠져 있었다. 카카오톡·X 에 링크를 붙이면 카드 없이 맨 주소만
  떴다는 뜻이다. static/og/*.png 는 그 공백을 1200x630 으로 새로 채운 것.
"""

APP_HOST = "linklynk.onrender.com"

_B = "https://" + APP_HOST


def _og(name):
    # ★/static/og/ 가 아니다. 이 앱은 static_folder="." 라서 /static/x 가
    #   레포 루트의 x 를 가리킨다. 전용 라우트 /og/<name>.png 를 쓴다.
    return "%s/og/%s.png" % (_B, name)


# ★이 호스트에서 200 으로 사는 페이지. 사이트맵이 이걸로 다시 만들어진다.
#   canibringmeds 로 301 되는 경로(/next, /can-i-bring, /ko, /about,
#   /parking)는 넣지 않는다 — 넣으면 "리다이렉트됨" 경고만 쌓인다.
SITEMAP_PATHS = ["/", "/boim", "/boim/guide", "/gottago", "/eats", "/majak",
                 "/hwatu", "/gov", "/duty", "/gift", "/dwaeji", "/rx",
                 "/aiknows", "/fly", "/sky"]


# path -> (제목, 설명, og이미지, 타입)
#   제목/설명은 페이지에 실제로 적힌 문장에서 가져왔다. 새로 지어내지 않는다.
META = {
    "/": (
        "LinkLynk — 쿠팡 링크, 딸깍 한 번에",
        "상품을 찾아 제휴 링크를 자동으로 만들고, 고지문구까지 주소에 맞춰 붙여주는 도구.",
        _og("home"), "website"),
    "/aiknows": (
        "AI는 이 가게를 알까? — 브랜드 AI 노출 확인",
        "단골 카페, 동네 맛집, 사려던 브랜드. 챗GPT에게 물으면 뭐라고 답하는지 대신 확인합니다. 약 10초, 회원가입 없음.",
        _og("aiknows"), "website"),
    "/boim": (
        "SPECULA — 챗GPT가 당신 상품을 팔아주고 있습니까?",
        "AI 검색 시대, 당신의 스토어가 AI 답변에 등장하는지 무료로 진단합니다. 의견이 아니라 기록입니다.",
        _og("boim"), "website"),
    "/boim/guide": (
        None,  # 이 페이지는 제 title 이 이미 길고 정확하다. 건드리지 않는다
        "검색창 대신 AI에게 묻는 시대에, 스마트스토어·쿠팡 상품이 AI 답변에서 빠지는 이유를 정리했습니다.",
        _og("boimguide"), "article"),
    "/duty": (
        None,
        "해외직구 예상 세액을 5초 만에. 관세청 간이세율·목록통관 면세한도 기준.",
        _og("duty"), "website"),
    "/eats": (
        None,
        "Places to eat and drink picked by travellers, not by ads. 3,900 spots across 18 cities.",
        _og("eats"), "website"),
    "/fly": (
        "Earthflight — 지구비행",
        "지구 전체가 활주로다. 설치 없이 브라우저에서 바로 뜨는 지형 비행.",
        _og("fly"), "website"),
    "/gift": (
        "선물레이더 — 어떻게 알았지, 싶은 선물",
        "받는 사람과 예산만 넣으면 어울리는 선물을 골라줍니다.",
        _og("gift"), "website"),
    "/gottago": (
        None,
        "Find the nearest public restroom in 20 cities worldwide. Free, wheelchair-accessible filters and a map.",
        _og("gottago"), "website"),
    "/gov": (
        "과태료레이더 — 내 행정 기한 30초 전수 확인",
        "자동차검사·면허갱신·건강검진·여권. 30초 입력으로 놓치고 있는 기한을 한 번에 확인합니다. 입력 정보는 저장하지 않습니다.",
        _og("gov"), "website"),
    "/hwatu": (
        None,
        "같은 달의 패를 맞추면 차사가 오늘의 화투점을 읊는다. 자체 도안, 매일 자정 새 판.",
        _og("hwatu"), "website"),
    "/majak": (
        None,
        "화투 문양 마작 솔리테어. 글자는 없다, 문양만 본다. 5층까지 광고 없음.",
        _og("majak"), "website"),
    "/rx": (
        None,
        "약 이름을 넣으면 성분을 찾아 국가별 반입 규정을 판정합니다. UN INCB 통제물질 목록과 각국 공개 규정 기준.",
        _og("rx"), "website"),
    # 아래 둘은 제 og 카드가 이미 1200x630 으로 제대로 있다(실측).
    #   설명문과 canonical 만 없어서 그것만 채운다. 이미지는 건드리지 않는다.
    "/dwaeji": (
        None,
        "프랜차이즈·관광 호객집 빼고 현지인 단골 노포만. 주문 공식부터 솔직한 단점까지.",
        None, "website"),
    "/sky": (
        None,
        "Catch today's colors. One photo a day fills your calendar — and finds your sky twin on Earth.",
        None, "website"),
}

# ★이미 og:image 가 있지만 교체해야 하는 곳.
#   /majak 은 512x512 정사각 아이콘을 카드로 쓰고 있었다. 카카오·X 는
#   정사각을 작게 잘라 붙이므로 글자가 안 보인다. 1200x630 으로 바꾼다.
_FORCE_IMG = {"/majak": _og("majak")}

# ★웹 → 플레이스토어 설치 경로.
#
#   2026-10-14 실측: 플레이 등록은 5개 다 살아 있는데(각각 200),
#   웹 페이지에서 스토어를 가리키는 건 /sky 한 장뿐이었다.
#   /majak, /hwatu, /fly, /gottago 로 들어온 사람은 설치할 방법이 없었다.
#   설치수 0~1 의 가장 직접적인 원인이 이것이다.
#
#   방식은 /sky 가 이미 쓰던 것을 그대로 쓴다(static/sky/index.html:166):
#   기본 숨김 → 설치된 앱(standalone) 안이 아닐 때만 보인다.
#   여기에 안드로이드일 때만, 을 더한다. iOS·데스크톱에선 눌러도 못 깐다.
_PLAY = {
    "/majak": "app.jeoseungmajak.twa",
    "/hwatu": "app.jeoseunghwatu.twa",
    "/fly": "com.kohgane.earthflight",
    "/gottago": "com.kohgane.gottago",
}
_PLAY_LABEL = {
    "/majak": "저승마작 설치", "/hwatu": "저승화투 설치",
    "/fly": "Earthflight 설치", "/gottago": "Get it on Google Play",
}


def _play_html(path):
    pkg = _PLAY.get(path)
    if not pkg:
        return ""
    url = "https://play.google.com/store/apps/details?id=" + pkg
    label = _PLAY_LABEL.get(path, "Google Play")
    return (
        '<a id="llPlay" href="%s" target="_blank" rel="noopener" '
        'style="display:none;position:fixed;left:50%%;transform:translateX(-50%%);'
        'bottom:calc(14px + env(safe-area-inset-bottom));z-index:2147483000;'
        'padding:10px 18px;border-radius:22px;background:rgba(18,20,26,.93);'
        'border:1px solid rgba(255,255,255,.22);color:#fff;text-decoration:none;'
        'font:600 13px/1 system-ui,-apple-system,sans-serif;'
        'box-shadow:0 6px 20px rgba(0,0,0,.35)">▶ %s'
        '<span id="llPlayX" style="margin-left:10px;opacity:.5;padding:0 4px">✕</span></a>'
        '<script>(function(){try{'
        'if(matchMedia("(display-mode: standalone)").matches)return;'
        'if(!/Android/i.test(navigator.userAgent))return;'
        'if(sessionStorage.getItem("llPlayHid"))return;'
        'var a=document.getElementById("llPlay");if(!a)return;'
        'a.style.display="block";'
        'var x=document.getElementById("llPlayX");'
        'if(x)x.addEventListener("click",function(e){e.preventDefault();e.stopPropagation();'
        'a.style.display="none";try{sessionStorage.setItem("llPlayHid","1")}catch(_){}'
        '});}catch(e){}})();</script>' % (url, label))


# ★h1 이 아예 없는 페이지. 전부 캔버스/앱 셸이라 화면에 제목 블록이 없다.
#   화면에 보이는 워드마크와 같은 문구만 쓴다 — 다른 말을 숨기면 클로킹이다.
_HIDDEN_H1 = {
    "/": "LinkLynk — 쿠팡 링크, 딸깍 한 번에",
    "/fly": "Earthflight — 지구비행",
    "/majak": "저승마작 — 차사의 패방",
}

# ★막다른 페이지: 들어온 사람이 다음 갈 곳이 없다.
#   크롤러도 여기서 끊기고(/dwaeji, /gift, /gov, /majak, /rx 는 내부링크 0개),
#   사람도 한 번 쓰고 나간다. 앱끼리 서로를 가리키게 한다.
_SIBLINGS = [
    ("/gov", "과태료레이더", "행정 기한 30초 확인"),
    ("/duty", "관세 계산기", "직구 세금 5초 계산"),
    ("/gift", "선물레이더", "예산 맞춤 선물"),
    ("/dwaeji", "돼지레이다", "현지인 노포 탐지"),
    ("/rx", "약 반입 판정", "국가별 의약품 규정"),
    ("/hwatu", "저승화투", "차사와 한 판"),
    ("/majak", "저승마작", "문양 마작 솔리테어"),
    ("/fly", "Earthflight", "브라우저 지구비행"),
    ("/boim", "SPECULA", "AI 노출 진단"),
]

# 어느 페이지에 footer 를 붙일지. 정적 도구 페이지만.
#   게임(/majak,/hwatu,/fly)은 전체화면 캔버스라 DOM 끝에 붙이면 레이아웃이
#   깨질 수 있다 — 넣지 않는다. 먼저 안전한 곳부터.
_FOOTER_ON = ("/gov", "/gift", "/rx", "/duty", "/aiknows", "/dwaeji")


def _footer_html(cur):
    items = [s for s in _SIBLINGS if s[0] != cur][:6]
    li = "".join(
        # ★테두리는 중립 회색이다. 흰 페이지(/gov,/gift,/aiknows)와
        #   어두운 페이지(/duty,/rx,/dwaeji)가 섞여 있어 흰색 반투명은
        #   한쪽에서 아예 안 보인다. 실측하고 바꿨다.
        '<a href="%s" style="display:block;padding:11px 13px;border:1px solid rgba(127,127,127,.32);'
        'border-radius:11px;text-decoration:none;color:inherit">'
        '<b style="display:block;font-size:14px">%s</b>'
        '<span style="font-size:12px;opacity:.62">%s</span></a>' % (p, n, d)
        for p, n, d in items)
    return (
        '<nav style="max-width:760px;margin:44px auto 28px;padding:0 16px;'
        'font-family:system-ui,-apple-system,sans-serif">'
        '<div style="font-size:12px;letter-spacing:.08em;opacity:.45;margin-bottom:11px">'
        '같이 쓰는 도구</div>'
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:9px">'
        '%s</div></nav>' % li)


def _has(html, needle):
    return needle in html


def build_tags(path, html):
    """이 페이지에 아직 없는 태그만 만들어 돌려준다."""
    m = META.get(path)
    if not m:
        return ""
    title, desc, img, otype = m
    low = html.lower()
    out = []

    if 'name="description"' not in low and "name='description'" not in low:
        out.append('<meta name="description" content="%s">' % desc)

    if 'property="og:' not in low and "property='og:" not in low:
        t = title or ""
        if not t:
            i, j = low.find("<title"), low.find("</title>")
            if i >= 0 < j:
                t = html[html.find(">", i) + 1:j].strip()
        out += ['<meta property="og:type" content="%s">' % otype,
                '<meta property="og:site_name" content="LinkLynk">',
                '<meta property="og:locale" content="ko_KR">',
                '<meta property="og:title" content="%s">' % t,
                '<meta property="og:description" content="%s">' % desc,
                '<meta property="og:url" content="%s%s">' % (_B, path)]

    # og:image 는 따로 센다. og:title 만 있고 이미지가 없던 페이지가 있다
    #   (/duty, /hwatu, /boim/guide) — 카드가 글자만 뜬다
    if img and "og:image" not in low:
        out += ['<meta property="og:image" content="%s">' % img,
                '<meta property="og:image:width" content="1200">',
                '<meta property="og:image:height" content="630">']

    tw_img = img or _FORCE_IMG.get(path)
    if 'name="twitter:' not in low and "name='twitter:" not in low:
        out.append('<meta name="twitter:card" content="summary_large_image">')
        if tw_img:
            out.append('<meta name="twitter:image" content="%s">' % tw_img)
    elif tw_img and "twitter:image" not in low:
        out.append('<meta name="twitter:image" content="%s">' % tw_img)

    if "rel=\"canonical\"" not in low and "rel='canonical'" not in low:
        out.append('<link rel="canonical" href="%s%s">' % (_B, path))

    return "".join(out)


def apply(html, path):
    # 정사각 아이콘을 카드로 쓰던 곳은 1200x630 으로 갈아끼운다
    force = _FORCE_IMG.get(path)
    if force:
        import re as _re
        html = _re.sub(
            r'(<meta[^>]+property=["\']og:image["\'][^>]*content=["\'])[^"\']*(["\'][^>]*>)',
            lambda m: m.group(1) + force + m.group(2) +
            '<meta property="og:image:width" content="1200">'
            '<meta property="og:image:height" content="630">',
            html, count=1, flags=_re.I)

    tags = build_tags(path, html)
    i = html.lower().find("</head>")
    if tags and i >= 0:
        html = html[:i] + tags + html[i:]

    # ★h1 이 없는 캔버스 페이지에 접근성용 제목을 넣는다.
    #   화면에 보이는 워드마크와 같은 문구다. 스크린리더에도 도움이 된다.
    h1 = _HIDDEN_H1.get(path)
    if h1 and "<h1" not in html.lower():
        k = html.lower().find("<body")
        if k >= 0:
            k = html.find(">", k)
            if k >= 0:
                html = (html[:k + 1] +
                        '<h1 style="position:absolute;width:1px;height:1px;'
                        'overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap">'
                        '%s</h1>' % h1 + html[k + 1:])

    j = html.lower().rfind("</body>")

    # ★검색 질의에 답하는 본문. 도구 UI 아래, 앱 간 링크 위에 들어간다.
    #   도구 페이지는 입력 폼뿐이라 구글에 보여줄 글이 없었다 — 그래서
    #   크롤은 되는데 색인이 안 됐다. 숫자는 전부 계산 엔진에서 가져온다.
    if j >= 0:
        try:
            import seo_content
            art, mark = seo_content.html_for(path)
            if art and mark and mark not in html:
                html = html[:j] + art + html[j:]
                j = html.lower().rfind("</body>")
        except Exception:
            pass

    if path in _FOOTER_ON and "같이 쓰는 도구" not in html:
        if j >= 0:
            html = html[:j] + _footer_html(path) + html[j:]
            j = html.lower().rfind("</body>")

    # ★설치 배지. 이미 제 배지를 들고 있으면(= /sky) 건드리지 않는다
    if path in _PLAY and "play.google.com" not in html and j >= 0:
        html = html[:j] + _play_html(path) + html[j:]
    return html


def register(app):
    """wsgi.py 에서 한 번 부른다. app.py 는 건드리지 않는다.

    ★왜 app.py 를 안 고치나
      app.py 는 3800줄이다. 한 줄 넣자고 그 파일을 통째로 다시 올리는 건
      사고가 나기 좋은 방식이다. 라우트 추가도 사이트맵 교체도
      Flask 객체에 밖에서 붙일 수 있다.
    """
    from flask import request, Response, send_file
    import io

    # ── 공유 카드 라우트 ────────────────────────────────────────
    def _og_card(name):
        import og_cards
        b = og_cards.get(name)
        if not b:
            return Response("nope", status=404)
        r = send_file(io.BytesIO(b), mimetype="image/png")
        r.headers["Cache-Control"] = "public, max-age=86400"
        return r

    if "_seo_og_card" not in app.view_functions:
        app.add_url_rule("/og/<name>.png", "_seo_og_card", _og_card)

    # ── 사이트맵 교체 ──────────────────────────────────────────
    # ★2026-10-14 실측: 6장뿐이었다. 200 으로 사는 페이지가 15장인데
    #   9장은 어느 사이트맵에도 없어 구글이 존재 자체를 몰랐다.
    #   라우트를 새로 만들지 않고 기존 뷰 함수만 갈아끼운다.
    def _sitemap_full():
        x = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for p in SITEMAP_PATHS:
            x.append("<url><loc>%s%s</loc><changefreq>weekly</changefreq></url>"
                     % (_B, p))
        x.append("</urlset>")
        return Response("\n".join(x), mimetype="application/xml")

    for vf, fn in list(app.view_functions.items()):
        if getattr(fn, "__name__", "") == "_sitemap":
            app.view_functions[vf] = _sitemap_full
            break

    @app.after_request
    def _seo(resp):
        try:
            p = request.path
            if p not in META and p not in _FOOTER_ON and p not in _PLAY:
                return resp
            if resp.status_code != 200:
                return resp
            if "text/html" not in (resp.content_type or ""):
                return resp
            h = (request.host or "").split(":")[0].lower()
            if h not in (APP_HOST, "127.0.0.1", "localhost"):
                return resp
            # send_static_file 은 파일 래퍼라 그냥 읽으면 터진다
            if getattr(resp, "direct_passthrough", False):
                resp.direct_passthrough = False
            body = resp.get_data(as_text=True)
            new = apply(body, p)
            if new != body:
                resp.set_data(new)
                # 본문을 바꿨으니 파일 기준 ETag 는 더 이상 맞지 않는다
                resp.headers.pop("ETag", None)
                resp.headers.pop("Last-Modified", None)
        except Exception:
            pass
        return resp

    return app
