#!/usr/bin/env bash
set -ef -o pipefail

# time BEFORE_RACE="true" RACE_TYPE=ve FORECAST_YEAR=2025 ./process-one-race.sh
# time RACE_TYPE=ve FORECAST_YEAR=2024 ./process-one-race.sh

# BEFORE_RACE="true"
echo $(date -u +"%F %T") "RACE_TYPE: ${RACE_TYPE}, FORECAST_YEAR: ${FORECAST_YEAR}, RUN_TS: ${RUN_TS}"
time uv run python group_names.py
echo $(date -u +"%F %T") "group_names ${RACE_TYPE} ${FORECAST_YEAR} DONE"

echo $(date -u +"%F %T") "Starting ngboost  ${RACE_TYPE} ${FORECAST_YEAR} "
# Run in subshell
#(cd ~/koodi/jukola-ngboost; time RACE_TYPE=${RACE_TYPE} FORECAST_YEAR=${FORECAST_YEAR} BATCH_RUN_TS=${RUN_TS} PROCESSING_BATCH_ID=ngboost-student-t uv run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=36000  --execute ngboost-norm-tuned.ipynb)
#(cd ~/koodi/jukola-ngboost; time RACE_TYPE=${RACE_TYPE} FORECAST_YEAR=${FORECAST_YEAR} BATCH_RUN_TS=${RUN_TS} PROCESSING_BATCH_ID=ngboost-norm-tuned-reviewed uv run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=36000  --execute ngboost-norm-tuned-reviewed.ipynb)
#(cd ~/koodi/jukola-ngboost; time RACE_TYPE=${RACE_TYPE} FORECAST_YEAR=${FORECAST_YEAR} PROCESSING_BATCH_ID=ngboost-student-t uv run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=36000  --execute ngboost-skwenorm.ipynb)

time RACE_TYPE=${RACE_TYPE} FORECAST_YEAR=${FORECAST_YEAR} BATCH_RUN_TS=${RUN_TS} PROCESSING_BATCH_ID=ngboost-norm-tuned-reviewed NGB_EXTRA_ITERATIONS=0 NGB_METRICS_JSON=data/ngb-metrics.json uv run jupyter nbconvert --to notebook --inplace  --ExecutePreprocessor.timeout=36000  --execute ngboost-norm-tuned-reviewed.ipynb

echo $(date -u +"%F %T") "ngboost ${RACE_TYPE} ${FORECAST_YEAR} DONE"


time uv run python prepare_run_features.py
echo $(date -u +"%F %T") "prepare_run_features.py ${RACE_TYPE} ${FORECAST_YEAR} DONE"

time uv run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=1200 --execute relay-simulation-2024.ipynb
echo $(date -u +"%F %T") "relay-simulation-2024.ipynb ${RACE_TYPE} ${FORECAST_YEAR} DONE"

if [[ -z "${BEFORE_RACE}" ]]; then
  time uv run jupyter nbconvert --to notebook --inplace --execute post-race-analysis-crps-nll.ipynb
  echo $(date -u +"%F %T") "post-race-analysis ${RACE_TYPE} ${FORECAST_YEAR} DONE"
else
  echo $(date -u +"%F %T") "SKIPPING post-race-analysis ${RACE_TYPE} ${FORECAST_YEAR}"
fi
