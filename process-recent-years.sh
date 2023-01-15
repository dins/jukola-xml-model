#!/usr/bin/env bash
set -euf -o pipefail

# time ./process-recent-years.sh

RUN_TS=$(date -u '+%Y%m%d_%H%M%S')
SECONDS=0

function process_one_race {
  LOG_PATH="logs/parallel-${RACE_TYPE}-${FORECAST_YEAR}-${RUN_TS}.log"
  echo $(date -u +"%F %T") "Starting ${LOG_PATH}"
  ./process-one-race.sh &> ${LOG_PATH} || echo $(date -u +"%F %T") "FAILED ${LOG_PATH}"
  duration=$SECONDS
  echo $(date -u +"%F %T") "DONE ${LOG_PATH} in $duration secs"
}

RACE_TYPE=ve FORECAST_YEAR=2017 process_one_race &
RACE_TYPE=ju FORECAST_YEAR=2017 process_one_race &
RACE_TYPE=ve FORECAST_YEAR=2018 process_one_race &
RACE_TYPE=ju FORECAST_YEAR=2018 process_one_race &
RACE_TYPE=ve FORECAST_YEAR=2019 process_one_race &
RACE_TYPE=ju FORECAST_YEAR=2019 process_one_race &
RACE_TYPE=ve FORECAST_YEAR=2021 process_one_race &
RACE_TYPE=ju FORECAST_YEAR=2021 process_one_race &
RACE_TYPE=ve FORECAST_YEAR=2022 process_one_race &
RACE_TYPE=ju FORECAST_YEAR=2022 process_one_race &

wait
echo "DONE ${RUN_TS}"

git diff --color=always --word-diff=color -U0 reports/ | grep -E "aikaväliennuste väärin|keskivirhe"
grep learning_rate ./models/best_params_gbr_*
