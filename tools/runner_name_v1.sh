#!/bin/bash
# 이름 보강 감시 래퍼 — 죽으면 되살린다. near 필드가 있으면 건너뛰므로 이어받기가 공짜.
# 사용: setsid nohup bash runner_name_v1.sh < /dev/null > runner_name.log 2>&1 & disown
cd "$(dirname "$0")" || exit 1
for i in $(seq 1 200); do
  # 다른 OSM 작업이 돌면 대기 (Overpass 슬롯 2개 보호)
  while [ "$(ps aux | grep -c '[o]sm_toilet')" -gt 0 ]; do sleep 30; done
  echo "===== 라운드 $i $(date '+%F %T')"
  python3 osm_toilet_name_v3.py
  echo "----- 종료 $(date '+%F %T')"
  pct=$(python3 osm_toilet_name_v3.py --stat | tail -n 1 | grep -o '([0-9]*%)' | tr -d '(%)')
  echo "----- 현재 식별가능 ${pct}%"
  [ -n "$pct" ] && [ "$pct" -ge 60 ] && { echo "목표 도달"; break; }
  sleep 45
done
