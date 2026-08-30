#!/bin/bash
cd "$(dirname "$0")" || exit 1
for i in $(seq 1 100); do
  :
  echo "===== 라운드 $i $(date '+%F %T')"
  python3 osm_toilet_addr_v4.py
  pct=$(python3 osm_toilet_addr_v4.py --stat | tail -n 1 | grep -o '([0-9]*%)' | tr -d '(%)')
  echo "----- 식별 ${pct}%  $(date '+%F %T')"
  [ -n "$pct" ] && [ "$pct" -ge 95 ] && { echo "완료"; break; }
  sleep 120
done
