# radar_api_v1.py — 미국 재산업화 수요 레이더 (Flask Blueprint)
# app.py: from radar_api_v1 import radar_bp; app.register_blueprint(radar_bp)
import os
from flask import Blueprint, jsonify, request
import psycopg2, psycopg2.extras

DB_URL = os.environ["DATABASE_URL"]
radar_bp = Blueprint("radar", __name__)

def _db():
    return psycopg2.connect(DB_URL)

@radar_bp.get("/api/radar/brief")
def radar_brief():
    with _db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""select name, state, sector, status, confidence, phase, days_to_start,
                                  construction_start::text, commercial_ops::text, workers_peak
                           from radar.active_window""")
            projects = [dict(r) for r in cur.fetchall()]
            cur.execute("""select item, category, season,
                                  sum(units_per_month) units_per_month, sum(usd_per_month) usd_per_month
                           from radar.consumables_demand
                           where not cert_required
                           group by 1,2,3 order by 5 desc""")
            demand = [dict(r) for r in cur.fetchall()]
    upcoming = [p for p in projects if p["phase"] == "pre" and p["days_to_start"] is not None and p["days_to_start"] <= 365]
    active = [p for p in projects if p["phase"] == "active"]
    actions = []
    for p in upcoming:
        actions.append(f"{p['name']} ({p['state']}) 착공 D-{p['days_to_start']} — 인력 유입 전 상품 리스팅·재고 배치 [[런북 레이더 대응]]")
    est = [p for p in projects if p["confidence"] == "estimated" and p["status"] != "operating"]
    if est:
        actions.append(f"검증 필요 {len(est)}건 — 추정치로 들어간 프로젝트 확인: " + ", ".join(p["name"] for p in est[:3]))
    if not actions:
        actions.append("이번 달 임박 프로젝트 없음 — 신규 발표 스캔 [[런북 레이더 스캔]]")
    return jsonify(projects=projects, active_count=len(active), upcoming_12m=len(upcoming),
                   demand_top=demand[:5], actions=actions)

@radar_bp.get("/api/radar/health")
def radar_health():
    return jsonify(ok=True, service="radar", version="v1")
