#!/usr/bin/env bash
set -euf -o pipefail

# RACE_TYPE=ve FORECAST_YEAR=2021 time ./preprocess-simulate-and-analyze-2019.sh

echo $(date -u +"%F %T") "RACE_TYPE: ${RACE_TYPE}, FORECAST_YEAR: ${FORECAST_YEAR}"
time pipenv run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=180 --execute preprocess-priors-grouped.ipynb
echo $(date -u +"%F %T") "preprocess-priors ${RACE_TYPE} ${FORECAST_YEAR} DONE"
time pipenv run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=1200 --execute 2019-relay-simulation.ipynb
echo $(date -u +"%F %T") "2019-relay-simulation ${RACE_TYPE} ${FORECAST_YEAR} DONE"
#time pipenv run jupyter nbconvert --to notebook --inplace --execute post-race-analysis.ipynb
#echo $(date -u +"%F %T") "post-race-analysis ${RACE_TYPE} ${FORECAST_YEAR} DONE"
