#!/usr/bin/env bash
set -ef -o pipefail

# time BEFORE_RACE="true" RACE_TYPE=ve FORECAST_YEAR=2023 ./process-one-race.sh
# time RACE_TYPE=ve FORECAST_YEAR=2023 ./process-one-race.sh

# BEFORE_RACE="true"
echo $(date -u +"%F %T") "RACE_TYPE: ${RACE_TYPE}, FORECAST_YEAR: ${FORECAST_YEAR}, RUN_TS: ${RUN_TS}"
time poetry run python group_csv.py
echo $(date -u +"%F %T") "group_csv ${RACE_TYPE} ${FORECAST_YEAR} DONE"
time poetry run python cluster_names.py
echo $(date -u +"%F %T") "cluster_names ${RACE_TYPE} ${FORECAST_YEAR} DONE"
time poetry run python estimate_personal_coefficients.py
echo $(date -u +"%F %T") "personal_coefficients ${RACE_TYPE} ${FORECAST_YEAR} DONE"

UNKNOWN_OR_KNOWN=unknown time poetry run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=600 --execute individual-estimates.ipynb
echo $(date -u +"%F %T") "UNKNOWN individual-estimates.ipynb ${RACE_TYPE} ${FORECAST_YEAR} DONE"

UNKNOWN_OR_KNOWN=known time poetry run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=600 --execute individual-estimates.ipynb
echo $(date -u +"%F %T") "KNOWN individual-estimates.ipynb ${RACE_TYPE} ${FORECAST_YEAR} DONE"

time poetry run python prepare_run_features.py
echo $(date -u +"%F %T") "combine_estimates_with_running_order ${RACE_TYPE} ${FORECAST_YEAR} DONE"

time poetry run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=1200 --execute 2019-relay-simulation.ipynb
echo $(date -u +"%F %T") "2019-relay-simulation ${RACE_TYPE} ${FORECAST_YEAR} DONE"

if [[ -z "${BEFORE_RACE}"  ]]; then
  time poetry run jupyter nbconvert --to notebook --inplace --execute post-race-analysis.ipynb
  echo $(date -u +"%F %T") "post-race-analysis ${RACE_TYPE} ${FORECAST_YEAR} DONE"
else
  echo $(date -u +"%F %T") "SKIPPING post-race-analysis ${RACE_TYPE} ${FORECAST_YEAR}"
fi

