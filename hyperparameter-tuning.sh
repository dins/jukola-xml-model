#!/usr/bin/env bash
set -efu -o pipefail

# time ./hyperparameter-tuning.sh

function run_tuning_notebook {
  echo $(date -u +"%F %T") "Starting tuning for ${RACE_TYPE} ${FORECAST_YEAR}"
  time poetry run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=10000 --execute individual-estimates-hyperparams.ipynb
  echo $(date -u +"%F %T") "DONE tuning for ${RACE_TYPE} ${FORECAST_YEAR}"
}

RACE_TYPE=ve FORECAST_YEAR=2017 run_tuning_notebook
RACE_TYPE=ju FORECAST_YEAR=2017 run_tuning_notebook
RACE_TYPE=ve FORECAST_YEAR=2018 run_tuning_notebook
RACE_TYPE=ju FORECAST_YEAR=2018 run_tuning_notebook
RACE_TYPE=ve FORECAST_YEAR=2019 run_tuning_notebook
RACE_TYPE=ju FORECAST_YEAR=2019 run_tuning_notebook
RACE_TYPE=ve FORECAST_YEAR=2021 run_tuning_notebook
RACE_TYPE=ju FORECAST_YEAR=2021 run_tuning_notebook
RACE_TYPE=ve FORECAST_YEAR=2022 run_tuning_notebook
RACE_TYPE=ju FORECAST_YEAR=2022 run_tuning_notebook

# loop over models/best_params_v2_gbr_*.json files
for file in $(ls models/best_params_v2_gbr_*.json); do echo "$file $(cat $file)"; done
