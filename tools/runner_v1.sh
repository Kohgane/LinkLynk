#!/bin/bash
# OSM 수집 감시 래퍼 — 죽으면 되살린다. 부분저장이 있어 이어받기가 공짜.
# 사용: setsid nohup bash runner_v1.sh 도시 도시 ... < /dev/null > runner.log 2>&1 & disown
cd "$(dirname "$0")"
CITIES="$*"
[ -z "$CITIES" ] && { echo "도시를 지정하라"; exit 1; }
for i in $(seq 1 60); do
  # 이미 도는 게 있으면 대기 (슬롯 2개 보호)
  while [ "$(ps aux | grep -c '[o]sm_toilet_collect')" -gt 0 ]; do sleep 30; done
  echo "===== 라운드 $i $(date '+%F %T') : $CITIES"
  python3 osm_toilet_collect_v2.py $CITIES
  rc=$?
  echo "----- 종료코드 $rc $(date '+%F %T')"
  # 지정 도시가 전부 meta 생성되면 완료
  done_all=1
  for c in $CITIES; do
    [ -f "toilets_world/$c.meta.json" ] || done_all=0
  done
  [ "$done_all" = "1" ] && { echo "전 도시 완료"; break; }
  sleep 60
done
