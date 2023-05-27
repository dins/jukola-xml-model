#!/usr/bin/env bash
set -eu -o pipefail

# time ./unknown-runners-hyperparameter-tuning.sh

function run_tuning_notebook {
  echo $(date -u +"%F %T") "Starting tuning for ${RACE_TYPE} ${FORECAST_YEAR} ${UNKNOWN_OR_KNOWN}"
  time poetry run jupyter nbconvert --to notebook --inplace --ExecutePreprocessor.timeout=1200 --execute unknown-runners-estimates-hyperparams.ipynb
  echo $(date -u +"%F %T") "DONE tuning for ${RACE_TYPE} ${FORECAST_YEAR} ${UNKNOWN_OR_KNOWN}"
}

for file in $(ls models/best_params_unknown_runs_hgbr_*.json); do echo "$file $(cat $file)"; done

UNKNOWN_OR_KNOWN=unknown RACE_TYPE=ve FORECAST_YEAR=2017 run_tuning_notebook
UNKNOWN_OR_KNOWN=unknown RACE_TYPE=ju FORECAST_YEAR=2017 run_tuning_notebook
UNKNOWN_OR_KNOWN=unknown RACE_TYPE=ve FORECAST_YEAR=2018 run_tuning_notebook
UNKNOWN_OR_KNOWN=unknown RACE_TYPE=ju FORECAST_YEAR=2018 run_tuning_notebook
UNKNOWN_OR_KNOWN=unknown RACE_TYPE=ve FORECAST_YEAR=2019 run_tuning_notebook
UNKNOWN_OR_KNOWN=unknown RACE_TYPE=ju FORECAST_YEAR=2019 run_tuning_notebook
UNKNOWN_OR_KNOWN=unknown RACE_TYPE=ve FORECAST_YEAR=2021 run_tuning_notebook
UNKNOWN_OR_KNOWN=unknown RACE_TYPE=ju FORECAST_YEAR=2021 run_tuning_notebook
UNKNOWN_OR_KNOWN=unknown RACE_TYPE=ve FORECAST_YEAR=2022 run_tuning_notebook
UNKNOWN_OR_KNOWN=unknown RACE_TYPE=ju FORECAST_YEAR=2022 run_tuning_notebook

for file in $(ls models/best_params_unknown_runs_hgbr_*.json); do echo "$file $(cat $file)"; done

UNKNOWN_OR_KNOWN=known RACE_TYPE=ve FORECAST_YEAR=2017 run_tuning_notebook
UNKNOWN_OR_KNOWN=known RACE_TYPE=ju FORECAST_YEAR=2017 run_tuning_notebook
UNKNOWN_OR_KNOWN=known RACE_TYPE=ve FORECAST_YEAR=2018 run_tuning_notebook
UNKNOWN_OR_KNOWN=known RACE_TYPE=ju FORECAST_YEAR=2018 run_tuning_notebook
UNKNOWN_OR_KNOWN=known RACE_TYPE=ve FORECAST_YEAR=2019 run_tuning_notebook
UNKNOWN_OR_KNOWN=known RACE_TYPE=ju FORECAST_YEAR=2019 run_tuning_notebook
UNKNOWN_OR_KNOWN=known RACE_TYPE=ve FORECAST_YEAR=2021 run_tuning_notebook
UNKNOWN_OR_KNOWN=known RACE_TYPE=ju FORECAST_YEAR=2021 run_tuning_notebook
UNKNOWN_OR_KNOWN=known RACE_TYPE=ve FORECAST_YEAR=2022 run_tuning_notebook
UNKNOWN_OR_KNOWN=known RACE_TYPE=ju FORECAST_YEAR=2022 run_tuning_notebook


for file in $(ls models/best_params_known_runs_hgbr_*.json); do echo "$file $(cat $file)"; done

