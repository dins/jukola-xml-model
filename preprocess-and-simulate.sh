#!/usr/bin/env bash
set -euf -o pipefail

# time ./preprocess-and-simulate.sh ju 2020
VE_OR_JU=$1
FORECAST_YEAR=$2

echo $(date -u +"%F %T") "RACE_TYPE: ${VE_OR_JU}"
RACE_TYPE=${VE_OR_JU} FORECAST_YEAR=${FORECAST_YEAR} time pipenv run jupyter nbconvert --to notebook --inplace --execute preprocess-priors-grouped.ipynb
echo $(date -u +"%F %T") "preprocess-priors ${VE_OR_JU} ${FORECAST_YEAR} DONE"
RACE_TYPE=${VE_OR_JU}  FORECAST_YEAR=${FORECAST_YEAR} time pipenv run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=1200 --execute relay-simulation.ipynb
echo $(date -u +"%F %T") "relay-simulation ${VE_OR_JU} ${FORECAST_YEAR} DONE"
