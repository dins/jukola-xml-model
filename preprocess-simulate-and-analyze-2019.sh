#!/usr/bin/env bash

# ./preprocess-simulate-and-analyze-2019.sh ve
# time ./preprocess-simulate-and-analyze-2019.sh ve && time ./preprocess-simulate-and-analyze-2019.sh ju
VE_OR_JU=$1

echo $(date -u +"%F %T") "RACE_TYPE: ${VE_OR_JU}"
RACE_TYPE=${VE_OR_JU} time pipenv run jupyter nbconvert --to notebook --inplace --execute preprocess-priors-grouped.ipynb
echo $(date -u +"%F %T") "preprocess-priors ${VE_OR_JU} DONE"
RACE_TYPE=${VE_OR_JU} time pipenv run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=1200 --execute 2019-relay-simulation.ipynb
echo $(date -u +"%F %T") "2019-relay-simulation ${VE_OR_JU} DONE"
RACE_TYPE=${VE_OR_JU} time pipenv run jupyter nbconvert --to notebook --inplace --execute post-race-analysis.ipynb
echo $(date -u +"%F %T") "post-race-analysis ${VE_OR_JU} DONE"
