import csv
import json
import logging
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

import shared

# time pipenv run python estimate_personal_coefficients.py

race_type = shared.race_type()
year = shared.forecast_year()
startTime = time.time()

ideal_paces = pd.read_csv(f'Jukola-terrain/ideal-paces-{race_type}.tsv', delimiter='\t')

logging.info(f"{ideal_paces.head().round(3)}")

runs = pd.read_csv(f'data/runs_{shared.race_id_str()}.tsv', delimiter='\t')
runs["leg"] = runs["leg_nro"]
runs["log_pace"] = np.log(runs["pace"])
runs = runs.query("num_runs > 1")

# TODO use median or other means to reduce outliers
runner_means = runs[["name", "log_pace"]].groupby(["name"]).agg("mean")

runs["pace_mean"] = runner_means["log_pace"][runs["name"]].values
runs["personal_coefficient"] = runs["log_pace"] / runs["pace_mean"]

runs = pd.merge(runs, ideal_paces[["year", "leg", "terrain_coefficient"]], how="left", on=["year", "leg"])
logging.info(f"{runs.sample(10).round(3)}")

X = np.array(runs["terrain_coefficient"]).reshape(-1, 1)
y = np.array(runs["personal_coefficient"]).reshape(-1, 1)
lr = LinearRegression().fit(X, y)
defaults = {
    "default_intercept": lr.intercept_[0],
    "default_coef": lr.coef_[0][0],
    "score": lr.score(X, y)
}
logging.info(f"defaults: {defaults}")
with open(f"data/default_personal_coefficients_{shared.race_id_str()}.json", 'w') as fp:
    json.dump(defaults, fp)

subset = runs
by_name = pd.DataFrame(data=subset.groupby("name")["terrain_coefficient"].apply(list).items(),
                       columns=["name", "terrain_coefficients"])
personal = pd.DataFrame(data=subset.groupby("name")["personal_coefficient"].apply(list).items(),
                        columns=["name", "personal_coefficients"])
by_name["personal_coefficients"] = personal["personal_coefficients"]
by_name["num_runs"] = by_name["terrain_coefficients"].apply(len)
by_name = by_name[by_name["num_runs"] > 2]


def fit_model_for_runner(row):
    name = row["name"]
    terrain_coefficients = row["terrain_coefficients"]
    X = np.array(terrain_coefficients).reshape(len(terrain_coefficients), 1)
    y = np.array(row["personal_coefficients"]).reshape(len(terrain_coefficients), 1)
    lr = LinearRegression().fit(X, y)
    score = lr.score(X, y)
    # logging.info(f"{name} intercept_: {lr.intercept_}, coef_: {lr.coef_[0][0]}")
    return [lr.coef_[0][0], lr.intercept_[0], score]


by_name[["coef", "intercept", "score"]] = by_name.apply(fit_model_for_runner, axis=1, result_type="expand")

logging.info(f"{by_name.sample(10).round(3)}")

by_name["bad_prediction"] = (by_name["coef"] <= 0) | (by_name["score"] <= 0)
logging.info(f'bad_prediction mean: {by_name["bad_prediction"].mean()}')

bad_prediction_summary = by_name[["bad_prediction", "num_runs", "score"]].groupby(['num_runs']).agg(["mean", "count"])
logging.info(bad_prediction_summary)

by_name = by_name[by_name["bad_prediction"] == False]
by_name = by_name[["name", "coef", "intercept", "score"]]
by_name.round(5).to_csv(f"data/personal_coefficients_{shared.race_id_str()}.tsv", "\t", quoting=csv.QUOTE_ALL,
                        index=False)
