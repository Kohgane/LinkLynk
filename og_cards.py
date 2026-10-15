# -*- coding: utf-8 -*-
"""공유 카드(1200x630)를 요청 시점에 그린다.

★왜 PNG 를 커밋하지 않고 런타임에 그리나
  카드 13장이면 1.1MB 다. 레포에 바이너리를 넣는 대신 글씨와 기존
  아트로 그 자리에서 만든다. 필요한 건 전부 이미 레포에 있다 —
  Pillow(requirements.txt), static/fonts/NotoKR-Bold.ttf, 각 앱 아이콘.

★비용
  한 장 그리는 데 0.3~1초. 처음 한 번만이고 그 뒤로는 메모리와
  디스크에 남는다. 카드를 긁는 건 크롤러와 메신저 미리보기뿐이라
  사람 트래픽에는 영향이 없다.

★실패하면 404 를 낸다. 카드가 안 떠도 페이지는 떠야 한다.
"""
import io
import os
import threading

W, H = 1200, 630
HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "static", "fonts", "NotoKR-Bold.ttf")
# ★컨테이너 디스크는 재배포마다 날아간다. 그래서 캐시지 저장소가 아니다.
CACHE_DIR = os.path.join("/tmp", "ogcards")

_MEM = {}
_LOCK = threading.Lock()

# name: (큰줄, 작은줄, 배경색1, 배경색2, 강조색, 아트경로(레포 기준, 없으면 None))
CARDS = {
    "home": ("LinkLynk", "쿠팡 링크, 딸깍 한 번에",
             (12, 12, 16), (28, 26, 40), (255, 200, 60),
             "static/meta/app_icon_1024.png"),
    "aiknows": ("AI는 이 가게를\n알고 있을까요?", "가게 이름만 넣으면 10초 · 회원가입 없음",
                (10, 14, 24), (18, 34, 58), (96, 186, 255), None),
    "boim": ("SPECULA", "사람들이 AI에게 물으면 어느 가게 이름이 나올까",
             (10, 10, 12), (26, 20, 34), (176, 140, 255), None),
    "boimguide": ("내 상품이 AI 답변에\n안 나오는 이유", "스마트스토어·쿠팡 셀러를 위한 정리",
                  (12, 12, 14), (30, 24, 36), (176, 140, 255), None),
    "duty": ("이거 직구하면\n얼마 뜯기나", "관세청 간이세율 기준 · 5초 계산",
             (14, 12, 10), (44, 30, 16), (255, 170, 60), None),
    "eats": ("Local Bites", "3,900 spots across 18 cities — picked by travellers",
             (10, 16, 12), (20, 42, 28), (120, 224, 150), None),
    "fly": ("EARTHFLIGHT", "지구 전체가 활주로다 — 브라우저에서 바로 비행",
            (6, 10, 20), (14, 30, 60), (110, 200, 255), "static/fly/icon-512.png"),
    "gift": ("선물레이더", "어떻게 알았지, 싶은 선물",
             (18, 10, 16), (48, 20, 40), (255, 130, 170), "giftradar-og.png"),
    "gottago": ("GottaGo", "Nearest public restroom in 20 cities — free & accessible",
                (10, 14, 20), (18, 36, 54), (120, 200, 255), "static/gottago/icon-512.png"),
    "gov": ("과태료레이더", "자동차검사·면허갱신·건강검진·여권 — 30초 전수 확인",
            (18, 10, 10), (50, 18, 18), (255, 110, 90), "penaltyradar-og.png"),
    "hwatu": ("저승화투", "같은 달 패를 맞추면, 차사가 오늘의 화투점을 읊는다",
              (14, 8, 8), (42, 16, 14), (240, 180, 90), "static/hwatu/icon-512.png"),
    "majak": ("저승마작", "화투 문양 마작 솔리테어 — 글자는 없다, 문양만 본다",
              (10, 8, 10), (34, 18, 22), (230, 170, 110), "static/majak/icon-512.png"),
    "rx": ("이 약,\n가져가도 되나요", "성분으로 찾아 국가별 반입 규정을 판정",
           (8, 12, 16), (16, 34, 44), (110, 220, 210), None),
}
DOMAIN = "linklynk.onrender.com"


def _font(sz):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        # ★레포 폰트가 없으면 시스템 CJK 로 떨어진다. 한글이 두부가 되는 것보단 낫다.
        for p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
                  "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"):
            if os.path.exists(p):
                return ImageFont.truetype(p, sz)
        return ImageFont.load_default()


def _wrap(d, text, f, maxw):
    out = []
    for para in text.split("\n"):
        line = ""
        for w in para.split(" "):
            t = (line + " " + w).strip()
            if d.textlength(t, font=f) <= maxw or not line:
                line = t
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


def _render(name):
    from PIL import Image, ImageDraw, ImageFilter
    big, small, c1, c2, accent, art = CARDS[name]

    im = Image.new("RGB", (W, H), c1)
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)],
               fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))

    has_art = False
    if art:
        p = os.path.join(HERE, art)
        if os.path.exists(p):
            try:
                a = Image.open(p).convert("RGBA")
                a.thumbnail((330, 330), Image.LANCZOS)
                gx, gy = W - 110 - a.width, (H - a.height) // 2
                glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
                glow.paste(a, (gx, gy), a)
                glow = glow.filter(ImageFilter.GaussianBlur(28))
                im = Image.alpha_composite(im.convert("RGBA"), glow).convert("RGB")
                im.paste(a, (gx, gy), a)
                d = ImageDraw.Draw(im)
                has_art = True
            except Exception:
                pass

    if not has_art:
        gl = Image.new("RGBA", im.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(gl)
        gd.ellipse([W - 470, H // 2 - 230, W - 10, H // 2 + 230], fill=accent + (46,))
        gd.ellipse([W - 390, H // 2 - 150, W - 90, H // 2 + 150], fill=accent + (34,))
        gl = gl.filter(ImageFilter.GaussianBlur(60))
        im = Image.alpha_composite(im.convert("RGBA"), gl).convert("RGB")
        d = ImageDraw.Draw(im)

    textw = (W - 200 - 360) if has_art else (W - 260 - 300)
    sz = 86
    while sz > 40:
        f = _font(sz)
        if len(_wrap(d, big, f, textw)) * (sz + 14) <= 300:
            break
        sz -= 4
    f = _font(sz)
    lines = _wrap(d, big, f, textw)
    fs = _font(32)
    slines = _wrap(d, small, fs, textw)

    blockh = len(lines) * (sz + 14) + 34 + len(slines) * 46
    y = (H - blockh) // 2
    d.rounded_rectangle([100, y + 8, 108, y + blockh - 8], radius=4, fill=accent)
    for ln in lines:
        d.text((136, y), ln, font=f, fill=(255, 255, 255))
        y += sz + 14
    y += 26
    for ln in slines:
        d.text((138, y), ln, font=fs, fill=(194, 198, 208))
        y += 46
    d.text((138, H - 72), DOMAIN, font=_font(24), fill=accent)

    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def get(name):
    """카드 PNG 바이트. 없는 이름이면 None."""
    if name not in CARDS:
        return None
    hit = _MEM.get(name)
    if hit:
        return hit
    fp = os.path.join(CACHE_DIR, name + ".png")
    try:
        if os.path.exists(fp):
            with open(fp, "rb") as fh:
                b = fh.read()
            if b[:8] == b"\x89PNG\r\n\x1a\n":
                _MEM[name] = b
                return b
    except Exception:
        pass
    # ★같은 카드를 동시에 두 번 그리지 않게. 워커가 여럿이라 의미가 있다.
    with _LOCK:
        if name in _MEM:
            return _MEM[name]
        try:
            b = _render(name)
        except Exception:
            return None
        _MEM[name] = b
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            tmp = fp + ".tmp%d" % os.getpid()
            with open(tmp, "wb") as fh:
                fh.write(b)
            os.replace(tmp, fp)
        except Exception:
            pass
        return b
