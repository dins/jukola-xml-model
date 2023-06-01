#!/usr/bin/env bash
set -eu -o pipefail

# time ./individual-estimates-hyperparameter-tuning.sh

time FORECAST_YEAR=2017 ./single-year-hyperparameter-tuning.sh
time FORECAST_YEAR=2018 ./single-year-hyperparameter-tuning.sh
time FORECAST_YEAR=2019 ./single-year-hyperparameter-tuning.sh
time FORECAST_YEAR=2021 ./single-year-hyperparameter-tuning.sh
time FORECAST_YEAR=2022 ./single-year-hyperparameter-tuning.sh
time FORECAST_YEAR=2023 ./single-year-hyperparameter-tuning.sh

for file in $(ls models/best_params_unknown_runs_hgbr_*.json); do echo "$file $(cat $file)"; done
for file in $(ls models/best_params_known_runs_hgbr_*.json); do echo "$file $(cat $file)"; done

