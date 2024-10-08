#!/usr/bin/env bash
set -ef -o pipefail

# time BEFORE_RACE="true" RACE_TYPE=ve FORECAST_YEAR=2023 ./process-one-race.sh
# time RACE_TYPE=ve FORECAST_YEAR=2023 ./process-one-race.sh

# BEFORE_RACE="true"
echo $(date -u +"%F %T") "RACE_TYPE: ${RACE_TYPE}, FORECAST_YEAR: ${FORECAST_YEAR}, RUN_TS: ${RUN_TS}"
time poetry run python group_names.py
echo $(date -u +"%F %T") "group_names ${RACE_TYPE} ${FORECAST_YEAR} DONE"

time poetry run python prepare_run_features.py
echo $(date -u +"%F %T") "prepare_run_features.py ${RACE_TYPE} ${FORECAST_YEAR} DONE"

#time poetry run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=1200 --execute 2019-relay-simulation.ipynb
#echo $(date -u +"%F %T") "2019-relay-simulation ${RACE_TYPE} ${FORECAST_YEAR} DONE"

time poetry run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=1200 --execute relay-simulation-2024.ipynb
echo $(date -u +"%F %T") "relay-simulation-2024.ipynb ${RACE_TYPE} ${FORECAST_YEAR} DONE"

if [[ -z "${BEFORE_RACE}" ]]; then
  time poetry run jupyter nbconvert --to notebook --inplace --execute post-race-analysis.ipynb
  echo $(date -u +"%F %T") "post-race-analysis ${RACE_TYPE} ${FORECAST_YEAR} DONE"
else
  echo $(date -u +"%F %T") "SKIPPING post-race-analysis ${RACE_TYPE} ${FORECAST_YEAR}"
fi
