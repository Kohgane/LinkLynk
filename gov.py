# -*- coding: utf-8 -*-
"""과태료레이더 — 법정 주기 기반 행정 기한 계산 엔진.
정부 API 불필요: 도로교통법·자동차관리법·건강검진 규정의 주기를 코드로.
[근거 2026-07 확인] 자동차 정기검사: 비사업용 승용 최초 4년(2024+ 등록 5년) 후 2년 주기,
 검사기간=만료일 전후 31일, 지연 과태료 4만 시작/3일당+2만/최대 60만.
 운전면허: 10년 주기(65세+ 5년), 1종 적성검사/2종 갱신. 미필 과태료 1종 3만·2종 2만.
 국가건강검진: 출생연도 짝홀=검진연도 짝홀(비사무직 매년), 해 넘기면 무료 검진 소멸."""
import datetime


def _d(y, m, d=1):
    try:
        return datetime.date(int(y), int(m), min(int(d), 28))
    except Exception:
        return None


def plan(birth_year=None, license_type=None, license_year=None,
         car_reg=None, last_insp_year=None, worker=None, passport_exp=None):
    today = datetime.date.today()
    items = []

    def add(icon, title, due, risk, action, note=""):
        dd = (due - today).days if due else None
        items.append({"icon": icon, "title": title,
                      "due": due.isoformat() if due else None, "dday": dd,
                      "risk": risk, "action": action, "note": note})

    # ── 자동차 정기검사 ──
    if car_reg:
        try:
            ry, rm = int(str(car_reg)[:4]), int(str(car_reg)[5:7] or str(car_reg)[4:6])
        except Exception:
            ry = rm = None
        if ry:
            first_gap = 5 if ry >= 2024 else 4
            if last_insp_year:
                ny = int(last_insp_year) + 2
            else:
                ny = ry + first_gap
                # 이미 지난 주기는 검사받았다고 가정하고 다음 주기로 (날짜 기준 비교)
                while (_d(ny, rm or 1) or today) < today:
                    ny += 2
            due = _d(ny, rm or 1)
            if due:
                add("🚗", "자동차 정기검사",
                    due,
                    "만료 후 31일 넘기면 과태료 4만원 시작, 3일마다 +2만원, 최대 60만원",
                    "TS한국교통안전공단 사이버검사소에서 예약",
                    f"검사 가능 기간: 만료일 앞뒤 31일 (등록 {ry}년 기준 추정 — 자동차365에서 정확 조회)")

    # ── 운전면허 ──
    if license_type and license_year:
        age = today.year - int(birth_year) if birth_year else 40
        cycle = 5 if age >= 65 else 10
        ny = int(license_year) + cycle
        due = _d(ny, 12, 31)
        if due:
            what = "적성검사" if str(license_type).startswith("1") else "면허 갱신"
            fine = "3만원" if str(license_type).startswith("1") else "2만원"
            add("🪪", f"운전면허 {what}",
                due,
                f"기간 내 미필 시 과태료 {fine} + 장기 방치 시 면허 취소까지",
                "안전운전 통합민원(온라인) 또는 운전면허시험장",
                f"주기 {cycle}년 — 정확한 만료일은 면허증 하단에 표기")

    # ── 국가건강검진 ──
    if birth_year:
        by = int(birth_year)
        every_year = (worker == "비사무직")
        this_year_target = every_year or (by % 2 == today.year % 2)
        if this_year_target:
            due = datetime.date(today.year, 12, 31)
            add("🩺", "국가건강검진 (올해 대상)",
                due,
                "12월 31일 지나면 올해 무료 검진 소멸 — 직장인은 미수검 시 회사에 과태료",
                "국민건강보험 홈페이지·앱에서 대상 확인 후 검진기관 예약",
                "연말엔 검진기관 예약 폭주 — 10월 전 예약 권장")
        else:
            due = datetime.date(today.year + 1, 12, 31)
            add("🩺", "국가건강검진", due,
                "내년이 검진 해 — 올해는 대상 아님",
                "국민건강보험에서 대상 연도 확인", "")

    # ── 여권 ──
    if passport_exp:
        try:
            py, pm = int(str(passport_exp)[:4]), int(str(passport_exp)[5:7])
            exp = _d(py, pm, 28)
            warn = exp - datetime.timedelta(days=182)
            add("🛂", "여권 갱신 준비",
                warn,
                "잔여 유효기간 6개월 미만이면 입국 거부하는 국가 다수 — 항공권 끊고 낭패 보는 1순위",
                "정부24 온라인 재발급 또는 구청 여권과",
                f"여권 만료: {exp.isoformat()}")
        except Exception:
            pass

    # ── 세금 캘린더 (전국 공통 법정 기한 — 벤치마킹: 세금 시즌에 정부24류 급등) ──
    def _next(m, d, m2=None, d2=None):
        """매년 반복 기한의 다음 도래일 (m2/d2 주면 연2회 중 가까운 것)"""
        cands = [datetime.date(today.year + dy, mm, dd)
                 for dy in (0, 1) for mm, dd in ([(m, d)] + ([(m2, d2)] if m2 else []))]
        return min(c for c in cands if c >= today)

    add("🏠", "재산세 납부", _next(7, 31, 9, 30),
        "기한 넘기면 가산금 3% + 매달 중가산", "위택스·서울은 이택스, 토스 고지서 납부도 가능",
        "1기분 7/31 · 2기분 9/30 (주택·토지)")
    add("🧾", "주민세(개인분) 납부", _next(8, 31),
        "기한 넘기면 가산금 3%", "위택스 또는 고지서 — 8월 한 달이 납부기간",
        "매년 8/16~8/31")
    if car_reg:
        add("🚙", "자동차세 납부", _next(6, 30, 12, 31),
            "기한 넘기면 가산금 3%", "위택스 납부 — 1월 연납 신청하면 할인",
            "1기분 6/30 · 2기분 12/31")
        jan = datetime.date(today.year + (1 if today.month > 1 else 0), 1, 31)
        add("💸", "자동차세 연납 신청", jan,
            "놓치면 할인 없이 연 2회 납부", "위택스 > 자동차세 연납 신청 (1월 한 달)",
            "1월 신청 시 연세액 할인")
    add("📊", "종합소득세 신고", _next(5, 31),
        "무신고 가산세 20% — 프리랜서·부업·임대소득 해당", "홈택스 5/1~5/31 (해당자만)",
        "근로소득만 있으면 연말정산으로 갈음")
    add("🧮", "부가가치세 신고", _next(1, 25, 7, 25),
        "무신고 가산세 — 사업자만 해당", "홈택스 1/25·7/25 (간이과세는 1/25 연 1회)",
        "사업자등록 있는 경우만")

    # 긴급도 정렬: 이미 지난 것 -> 임박 -> 먼 것
    items.sort(key=lambda x: (x["dday"] is None, x["dday"] if x["dday"] is not None else 9999))
    # 상태 태그
    for it in items:
        dd = it["dday"]
        if dd is None:
            it["level"] = "info"
        elif dd < 0:
            it["level"] = "danger"
        elif dd <= 45:
            it["level"] = "warn"
        else:
            it["level"] = "ok"
    return {"ok": True, "items": items, "today": today.isoformat()}
