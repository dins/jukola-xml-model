#!/usr/bin/env bash
set -euf -o pipefail

# time FORECAST_YEAR=2023 ./process-before-race.sh

RUN_TS="br-$(date -u '+%Y%m%d_%H%M%S')"
SECONDS=0

echo $(date -u +"%F %T") "Starting BEFORE_RACE ${RUN_TS}"

function process_one_race {
  LOG_PATH="logs/parallel-${RACE_TYPE}-${FORECAST_YEAR}-${RUN_TS}.log"
  echo $(date -u +"%F %T") "Starting ${LOG_PATH}"
  RUN_TS=${RUN_TS} ./process-one-race.sh &> ${LOG_PATH} || echo $(date -u +"%F %T") "FAILED ${LOG_PATH}"
  duration=$SECONDS
  echo $(date -u +"%F %T") "DONE ${LOG_PATH} in $duration secs"
}

RO_LOG_PATH="logs/running-order-${FORECAST_YEAR}-${RUN_TS}.log"
poetry run python fetch_running_order.py 2023  &> ${RO_LOG_PATH} && tail -n 10 ${RO_LOG_PATH} && wc data/running_order_final_ju_fy_${FORECAST_YEAR}.tsv
echo $(date -u +"%F %T") "DONE ${RO_LOG_PATH} in $SECONDS secs"


BEFORE_RACE="true" RACE_TYPE=ve process_one_race &
BEFORE_RACE="true" RACE_TYPE=ju process_one_race &

wait

echo "DONE ${RUN_TS} in $SECONDS secs"

# time poetry run python json_reports.py