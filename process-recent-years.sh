#!/usr/bin/env bash
set -euf -o pipefail

# time ./process-recent-years.sh

RACE_TYPE=ve FORECAST_YEAR=2018 time ./process-one-race.sh
RACE_TYPE=ju FORECAST_YEAR=2018 time ./process-one-race.sh
RACE_TYPE=ve FORECAST_YEAR=2019 time ./process-one-race.sh
RACE_TYPE=ju FORECAST_YEAR=2019 time ./process-one-race.sh
RACE_TYPE=ve FORECAST_YEAR=2021 time ./process-one-race.sh
RACE_TYPE=ju FORECAST_YEAR=2021 time ./process-one-race.sh

git diff --color=always --word-diff=color -U0 reports/ | grep -E "aikaväliennuste väärin|keskivirhe"