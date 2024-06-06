#!/usr/bin/env bash
set -euf -o pipefail

# time ./process-recent-years.sh

RUN_TS=$(date -u '+%Y%m%d_%H%M%S')
SECONDS=0

time poetry run python count_names.py
echo $(date -u +"%F %T") "count_names.py DONE"

function process_one_race {
  LOG_PATH="logs/parallel-${RACE_TYPE}-${FORECAST_YEAR}-${RUN_TS}.log"
  start_secs=$SECONDS
  echo $(date -u +"%F %T") "Starting at ${start_secs} secs, ${LOG_PATH}"
  RUN_TS=${RUN_TS} ./process-one-race.sh &> ${LOG_PATH} || echo $(date -u +"%F %T") "FAILED ${LOG_PATH}"
  duration=$((SECONDS - start_secs))
  echo $(date -u +"%F %T") "DONE ${LOG_PATH} in $duration secs"
}

RACE_TYPE=ju FORECAST_YEAR=2023 process_one_race &
RACE_TYPE=ve FORECAST_YEAR=2023 process_one_race &
RACE_TYPE=ju FORECAST_YEAR=2017 process_one_race &
sleep 2
RACE_TYPE=ve FORECAST_YEAR=2017 process_one_race &
sleep 2
RACE_TYPE=ju FORECAST_YEAR=2018 process_one_race &
sleep 2
RACE_TYPE=ve FORECAST_YEAR=2018 process_one_race &
sleep 2
RACE_TYPE=ju FORECAST_YEAR=2019 process_one_race &
sleep 2
RACE_TYPE=ve FORECAST_YEAR=2019 process_one_race &

wait

RACE_TYPE=ju FORECAST_YEAR=2021 process_one_race &
RACE_TYPE=ve FORECAST_YEAR=2021 process_one_race &
RACE_TYPE=ju FORECAST_YEAR=2022 process_one_race &
RACE_TYPE=ve FORECAST_YEAR=2022 process_one_race &

wait

BEFORE_RACE="true" RACE_TYPE=ve FORECAST_YEAR=2024 process_one_race
BEFORE_RACE="true" RACE_TYPE=ju FORECAST_YEAR=2024 process_one_race

echo "DONE ${RUN_TS}"

time poetry run python json_reports.py

