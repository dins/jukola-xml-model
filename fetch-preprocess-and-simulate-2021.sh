#!/usr/bin/env bash
set -euf -o pipefail

# time ./fetch-preprocess-and-simulate-2021.sh

wc data/running_order_final_ju_fy_2022.tsv && wc data/running_order_final_ve_fy_2022.tsv
sleep 3
time pipenv run python fetch_running_order.py 2022
wc data/running_order_final_ju_fy_2022.tsv && wc data/running_order_final_ve_fy_2022.tsv
sleep 5

BEFORE_RACE="true" RACE_TYPE=ve FORECAST_YEAR=2022 time ./process-one-race.sh
BEFORE_RACE="true" RACE_TYPE=ju FORECAST_YEAR=2022 time ./process-one-race.sh

