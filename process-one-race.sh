#!/usr/bin/env bash
set -euf -o pipefail

# RACE_TYPE=ve FORECAST_YEAR=2021 time ./process-one-race.sh

echo $(date -u +"%F %T") "RACE_TYPE: ${RACE_TYPE}, FORECAST_YEAR: ${FORECAST_YEAR}"
time pipenv run python group_csv.py
echo $(date -u +"%F %T") "group_csv ${RACE_TYPE} ${FORECAST_YEAR}"
time pipenv run python cluster_names.py
echo $(date -u +"%F %T") "cluster_names ${RACE_TYPE} ${FORECAST_YEAR}"
time pipenv run python estimate_personal_coefficients.py
echo $(date -u +"%F %T") "personal_coefficients ${RACE_TYPE} ${FORECAST_YEAR}"
time pipenv run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=180 --execute preprocess-priors-grouped.ipynb
echo $(date -u +"%F %T") "preprocess-priors ${RACE_TYPE} ${FORECAST_YEAR} DONE"
time pipenv run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=1200 --execute 2019-relay-simulation.ipynb
echo $(date -u +"%F %T") "2019-relay-simulation ${RACE_TYPE} ${FORECAST_YEAR} DONE"
time pipenv run jupyter nbconvert --to notebook --inplace --execute post-race-analysis.ipynb
echo $(date -u +"%F %T") "post-race-analysis ${RACE_TYPE} ${FORECAST_YEAR} DONE"