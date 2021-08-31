#!/usr/bin/env bash
set -euf -o pipefail

# time ./preprocess-simulate-and-analyze.sh

RACE_TYPE=ve FORECAST_YEAR=2018 time ./preprocess-simulate-and-analyze-2019.sh
RACE_TYPE=ju FORECAST_YEAR=2018 time ./preprocess-simulate-and-analyze-2019.sh
RACE_TYPE=ve FORECAST_YEAR=2019 time ./preprocess-simulate-and-analyze-2019.sh
RACE_TYPE=ju FORECAST_YEAR=2019 time ./preprocess-simulate-and-analyze-2019.sh
RACE_TYPE=ve FORECAST_YEAR=2021 time ./preprocess-simulate-and-analyze-2019.sh
RACE_TYPE=ju FORECAST_YEAR=2021 time ./preprocess-simulate-and-analyze-2019.sh