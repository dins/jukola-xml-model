#!/usr/bin/env bash
set -euf -o pipefail

# time ./fetch-preprocess-and-simulate-2021.sh

wc data/running_order_j2021_ju.tsv && wc data/running_order_j2021_ve.tsv
# They are in 2020 in 2021
time pipenv run python fetch_running_order.py 2020
wc data/running_order_j2020_ju.tsv && wc data/running_order_j2020_ve.tsv
sleep 5
cp data/running_order_j2020_ve.tsv data/running_order_j2021_ve.tsv && cp data/running_order_j2020_ju.tsv data/running_order_j2021_ju.tsv
RACE_TYPE=ve FORECAST_YEAR=2021 time pipenv run python group_csv.py && RACE_TYPE=ju FORECAST_YEAR=2021 time pipenv run python group_csv.py
RACE_TYPE=ve FORECAST_YEAR=2021 time pipenv run python cluster_names.py && RACE_TYPE=ju FORECAST_YEAR=2021 time pipenv run python cluster_names.py

RACE_TYPE=ve FORECAST_YEAR=2021 time ./preprocess-simulate-and-analyze-2019.sh && RACE_TYPE=ju FORECAST_YEAR=2021 time ./preprocess-simulate-and-analyze-2019.sh

