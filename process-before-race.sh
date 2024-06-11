#!/usr/bin/env bash
set -euf -o pipefail

# time FORECAST_YEAR=2024 ./process-before-race.sh

RUN_TS="br-$(date -u '+%Y%m%d_%H%M%S')"
SECONDS=0



RO_LOG_PATH="logs/running-order-${FORECAST_YEAR}-${RUN_TS}.log"
echo $(date -u +"%F %T") "Starting BEFORE_RACE ${RUN_TS}, logs: ${RO_LOG_PATH}"

poetry run python fetch_running_order.py 2024  &> ${RO_LOG_PATH}
tail -n 10 ${RO_LOG_PATH}

#ORO_LOG_PATH="logs/running-order-online-${FORECAST_YEAR}-${RUN_TS}.log"
#echo $(date -u +"%F %T") "Starting ${ORO_LOG_PATH}"
#poetry run python process_online_running_order.py 2024  &> ${ORO_LOG_PATH}
#tail -n 10 ${ORO_LOG_PATH}

wc data/running_order_final_ju_fy_${FORECAST_YEAR}.tsv

time RACE_TYPE=ve poetry run python group_names.py
echo $(date -u +"%F %T") "group_names ve ${FORECAST_YEAR} DONE"

time RACE_TYPE=ju poetry run python group_names.py
echo $(date -u +"%F %T") "group_names ju ${FORECAST_YEAR} DONE"

# cannot do more before running Pymc models

echo "DONE ${RUN_TS} in $SECONDS secs"

# time poetry run python json_reports.py