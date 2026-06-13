#!/usr/bin/env bash
set -euf -o pipefail

# time FORECAST_YEAR=2026 ./process-before-race.sh

RUN_TS="br-$(date -u '+%Y%m%d_%H%M%S')"
SECONDS=0

# Registration dats BEFORE race

# RO_LOG_PATH="logs/running-order-${FORECAST_YEAR}-${RUN_TS}.log"
# echo $(date -u +"%F %T") "Starting BEFORE_RACE ${RUN_TS}, logs: ${RO_LOG_PATH}"

# uv run python fetch_running_order.py 2026  &> ${RO_LOG_PATH}
# tail -n 10 ${RO_LOG_PATH}


# --- START Online data during Saturday and Sunday race

ORO_LOG_PATH="logs/running-order-online-${FORECAST_YEAR}-${RUN_TS}.log"
echo $(date -u +"%F %T") "Starting ${ORO_LOG_PATH}"
time RACE_TYPE=ve FORECAST_YEAR=2026 uv run python process_online_running_order.py  &> ${ORO_LOG_PATH}
echo $(date -u +"%F %T") "DONE VE process_online_running_order.py"
time RACE_TYPE=ju FORECAST_YEAR=2026 uv run python process_online_running_order.py  &> ${ORO_LOG_PATH}
echo $(date -u +"%F %T") "DONE JU process_online_running_order.py"
tail -n 10 ${ORO_LOG_PATH}
#cp data/online_running_order_ke_fy_2026.tsv data/running_order_final_ke_fy_2026.tsv
cp data/online_running_order_ve_fy_2026.tsv data/running_order_final_ve_fy_2026.tsv
cp data/online_running_order_ju_fy_2026.tsv data/running_order_final_ju_fy_2026.tsv

# --- END Online data during Saturday and Sunday race



wc data/running_order_final_ju_fy_${FORECAST_YEAR}.tsv

# wc data/running_order_final_ke_fy_${FORECAST_YEAR}.tsv

#time RACE_TYPE=ve uv run python group_names.py
#echo $(date -u +"%F %T") "group_names ve ${FORECAST_YEAR} DONE"

#time RACE_TYPE=ju uv run python group_names.py
#echo $(date -u +"%F %T") "group_names ju ${FORECAST_YEAR} DONE"

time uv run python count_names.py
echo $(date -u +"%F %T") "count_names.py DONE"

# tail -n 10 ${RO_LOG_PATH}
tail -n 10 ${ORO_LOG_PATH}

function process_one_race {
  LOG_PATH="logs/parallel-${RACE_TYPE}-${FORECAST_YEAR}-${RUN_TS}.log"
  start_secs=$SECONDS
  echo $(date -u +"%F %T") "Starting at ${start_secs} secs, ${LOG_PATH}"
  BEFORE_RACE="true" RUN_TS=${RUN_TS} ./process-one-race.sh &>${LOG_PATH} || echo $(date -u +"%F %T") "FAILED ${LOG_PATH}"
  duration=$((SECONDS - start_secs))
  echo $(date -u +"%F %T") "DONE ${LOG_PATH} in $duration secs"
}

# RACE_TYPE=ke process_one_race &
RACE_TYPE=ju process_one_race &
RACE_TYPE=ve process_one_race &

wait

#tail -n 10 ${ORO_LOG_PATH}

echo "DONE ${RUN_TS} in $SECONDS secs"

# time uv run python json_reports.py