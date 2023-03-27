#!/usr/bin/env bash
set -ef -o pipefail

# BEFORE_RACE="true" RACE_TYPE=ve FORECAST_YEAR=2022 time ./process-one-race.sh
# RACE_TYPE=ve FORECAST_YEAR=2022 TUNE_HYPERPARAMS="true" time ./process-one-race.sh

# TUNE_HYPERPARAMS="true"
# BEFORE_RACE="true"
echo $(date -u +"%F %T") "RACE_TYPE: ${RACE_TYPE}, FORECAST_YEAR: ${FORECAST_YEAR}, RUN_TS: ${RUN_TS}"
time poetry run python group_csv.py
echo $(date -u +"%F %T") "group_csv ${RACE_TYPE} ${FORECAST_YEAR} DONE"
time poetry run python cluster_names.py
echo $(date -u +"%F %T") "cluster_names ${RACE_TYPE} ${FORECAST_YEAR} DONE"
time poetry run python estimate_personal_coefficients.py
echo $(date -u +"%F %T") "personal_coefficients ${RACE_TYPE} ${FORECAST_YEAR} DONE"
if [[ -z "${TUNE_HYPERPARAMS}"  ]]; then
  echo $(date -u +"%F %T") "SKIPPING hyperparameter-tuning ${RACE_TYPE} ${FORECAST_YEAR}"
else
  time poetry run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=10000 --execute preprocess-priors-hyperparameter-tuning.ipynb
  echo $(date -u +"%F %T") "hyperparameter-tuning ${RACE_TYPE} ${FORECAST_YEAR} DONE"
fi
time poetry run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=180 --execute preprocess-priors-grouped.ipynb
echo $(date -u +"%F %T") "preprocess-priors ${RACE_TYPE} ${FORECAST_YEAR} DONE"
time poetry run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=1200 --execute 2019-relay-simulation.ipynb
echo $(date -u +"%F %T") "2019-relay-simulation ${RACE_TYPE} ${FORECAST_YEAR} DONE"

if [[ -z "${BEFORE_RACE}"  ]]; then
  time poetry run jupyter nbconvert --to notebook --inplace --execute post-race-analysis.ipynb
  echo $(date -u +"%F %T") "post-race-analysis ${RACE_TYPE} ${FORECAST_YEAR} DONE"
else
  echo $(date -u +"%F %T") "SKIPPING post-race-analysis ${RACE_TYPE} ${FORECAST_YEAR}"
fi

