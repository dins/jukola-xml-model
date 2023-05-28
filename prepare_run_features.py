import json
import logging

import numpy as np
import pandas as pd
import joblib

import shared


# time RACE_TYPE=ve FORECAST_YEAR=2022 poetry run python prepare_run_features.py

# os.environ['FORECAST_YEAR'] = "2019"

def read_persisted_dummy_column_values():
    with open(f"data/top_countries_{shared.race_id_str()}.json") as json_file:
        top_countries = json.load(json_file)
    with open(f"data/top_first_names_{shared.race_id_str()}.json") as json_file:
        top_first_names = json.load(json_file)

    return (top_countries, top_first_names)


def preprocess_features_v2(runs_df, top_countries, include_history_paces):
    # log column names and types
    logging.info("runs_df")
    logging.info(runs_df.info())
    # convert some int columns to labels
    runs = runs_df.assign(leg=runs_df.leg.astype(str))
    # cliping 0 to 1 is a hack for when predicting for unknown runners
    runs["runs"] = np.clip(runs.num_runs, 1, shared.num_pace_years + 1).astype(int)

    def truncate_to_top_values(value, top_values):
        if value in top_values:
            return value
        else:
            return "OTHER"

    # First name based pace category
    runs["first_name"] = runs.name.str.split(" ", expand=True).iloc[:, 0]
    name_pace_classes = pd.read_csv(f"data/name_pace_classes_{shared.race_id_str()}.tsv", delimiter="\t")
    logging.info(name_pace_classes.info())
    runs = runs.join(name_pace_classes.set_index('first_name'), on="first_name")
    runs["fn_pace_class"] = runs["fn_pace_class"].astype(str)
    runs["fn_pace_std_class"] = runs["fn_pace_std_class"].astype(str)

    # Add column for most popular countries
    runs["c"] = runs.apply(lambda run: truncate_to_top_values(run["team_country"], top_countries), axis=1)

    # Explode categories to dummy columns
    features = pd.get_dummies(runs[["leg", "c", "fn_pace_class", "fn_pace_std_class"]], sparse=True)
    features["runs"] = runs["runs"]
    features["terrain_coefficient"] = runs["terrain_coefficient"]
    features["vertical_per_km"] = runs["vertical_per_km"]
    # features["marking_per_km"] = runs["marking_per_km"]
    features["leg_distance"] = runs["leg_distance"]

    if include_history_paces:
        # replace "NA" string with nan and convert to float
        features["median_pace"] = runs["median_pace"].replace("NA", np.nan).astype(float)
        features["log_stdev"] = runs["log_stdev"].replace("NA", np.nan).astype(float)

        logging.info(f"median_pace and log_stdev per runs")
        shared.log_df(features[["median_pace", "log_stdev"]].groupby(features["runs"]).agg(["mean", "count"]))

    # Ensure that a column exists for each top country + OTHER, despite none being in data
    country_cols = [f"c_{country}" for country in top_countries]
    country_cols.append("c_OTHER")
    missing_cols = [col for col in country_cols if not col in features.columns]
    logging.info(f"missing_cols: {missing_cols}")

    pace_class_cols = [f"fn_pace_class_{float(i)}" for i in range(10)]
    missing_cols.extend([col for col in pace_class_cols if not col in features.columns])
    logging.info(f"missing_cols: {missing_cols}")

    missing_country_cols_df = pd.DataFrame({col: 0 for col in missing_cols}, index=features.index)
    features = pd.concat([features, missing_country_cols_df], sort=False, axis=1)

    features.insert(0, "team_id", runs["team_id"])
    features = features.reindex(sorted(features.columns), axis=1)

    logging.info(f"features: {features.info()}")
    logging.info(f"features columns {features.columns}")

    return features


def prepare_run_features(include_history_paces):
    year = shared.forecast_year()

    ideals = pd.read_csv(f'Jukola-terrain/ideal-paces-{shared.race_type()}.tsv', delimiter='\t')
    ideals["marking_per_km"] = ideals["marking"] / ideals["leg_distance"]
    logging.info(f"Ideals:\n{ideals.head(5).round(3)}")
    logging.info(f"Loaded ideals for {len(ideals)} legs")

    runs = pd.read_csv(f'data/runs_{shared.race_id_str()}.tsv', delimiter='\t')
    runs["log_pace"] = np.log(runs["pace"])
    # TODO use median or other means to reduce outliers
    runner_means = runs[["name", "log_pace"]].groupby(["name"]).agg("mean")

    runs["pace_mean"] = runner_means["log_pace"][runs["name"]].values
    logging.info(f"Runs: \n{runs.head(5).round(3)}")

    runs = pd.merge(runs,
                    ideals[["year", "leg", "leg_distance", "terrain_coefficient", "vertical_per_km", "marking_per_km"]],
                    how="left", on=["year", "leg"])
    runs.sample(10).round(3)
    country_counts = runs["team_country"].value_counts()
    top_country_counts = country_counts[country_counts > 30]
    top_countries = top_country_counts.keys().tolist()
    logging.info(f"top_countries: {len(top_countries)}: {top_countries}")
    # save top countries to file for later use
    with open(f"data/top_countries_{shared.race_id_str()}.json", 'w') as outfile:
        json.dump(top_countries, outfile)

    features = preprocess_features_v2(runs, top_countries, include_history_paces)

    y = runs["log_pace"].values
    x = features.values
    logging.info(f"Shapes y: {y.shape}, x: {x.shape}")
    return x, y, features


def _load_history_and_calculate_log_paces():
    history = pd.read_csv(f'data/grouped_paces_{shared.race_id_str()}.tsv', delimiter="\t")

    # CHEAP TRICK: Use median instead of mean to filter out one time accidents,
    # the std will still carry the uncertainty caused by those
    history["predicted_log_pace_mean"] = np.nanmedian(np.log(history[shared.pace_columns]), axis=1)
    history["predicted_log_pace_std"] = np.nanstd(np.log(history[shared.pace_columns]), axis=1)

    return history[["num_valid_times", "predicted_log_pace_mean", "predicted_log_pace_std", "name", "teams"]]


def switch_first_and_last_name(name):
    names = name.split()
    names.insert(0, names.pop())
    switched_name = " ".join(names)
    return switched_name


def _predict_for_unknown_runners(features, unknown_or_known):
    hgbr = joblib.load(f'models/{unknown_or_known}_runs_hgbr_{shared.race_id_str()}.sav')
    hgbr_q_low = joblib.load(f'models/{unknown_or_known}_runs_hgbr_q_low_{shared.race_id_str()}.sav')
    hgbr_q_high = joblib.load(f'models/{unknown_or_known}_runs_hgbr_q_high_{shared.race_id_str()}.sav')

    hgbr_preds = hgbr.predict(features)
    hgbr_q_low_preds = hgbr_q_low.predict(features)
    hgbr_q_high_preds = hgbr_q_high.predict(features)

    hgbr_sd_estimate = pd.DataFrame({
        'log_q_low': hgbr_q_low_preds,
        'predicted': np.exp(hgbr_preds),
        'log_q_high': hgbr_q_high_preds,
    })

    # Probably unjustified way to estimate standard deviation
    hgbr_sd_estimate["log_std"] = (hgbr_sd_estimate.log_q_high - hgbr_sd_estimate.log_q_low) / 2

    logging.info(hgbr_sd_estimate.head(15).round(3))
    logging.info(hgbr_sd_estimate["log_std"].mean())
    logging.info(f"hgbr_sd_estimate shape: {hgbr_sd_estimate.shape}")
    return hgbr_sd_estimate


def combine_estimates_with_running_order():
    running_order_with_history = _find_history_values_for_running_order_names()

    running_order = _choose_final_estimates_from_various_models(running_order_with_history)

    running_order.to_csv(f"data/running_order_with_estimates_{shared.race_id_str()}.tsv", "\t")

    shared.log_df(running_order[['num_runs', 'pred_log_mean', "pred_log_std", "predicted", "log_std", "final_pace_mean",
                                 "final_pace_std", "weighted_leg_factor"]].groupby('num_runs').agg(["mean"]).round(2))


def _choose_final_estimates_from_various_models(running_order_with_history):
    running_order = running_order_with_history[['team_id', 'team', 'team_base_name', 'team_country', 'leg', 'leg_dist',
                                                'name', 'orig_name',
                                                'num_runs', 'pred_log_mean', 'pred_log_std']]
    ideals = pd.read_csv(f'Jukola-terrain/ideal-paces-{shared.race_type()}.tsv', delimiter='\t')
    ideals["marking_per_km"] = ideals["marking"] / ideals["leg_distance"]
    logging.info(f"Ideals:\n{ideals.head(5).round(3)}")
    logging.info(f"Loaded ideals for {len(ideals)} legs")
    running_order["year"] = shared.forecast_year()
    running_order = pd.merge(running_order,
                             ideals[["year", "leg", "leg_distance", "terrain_coefficient", "vertical_per_km",
                                     "marking_per_km"]],
                             how="left", on=["year", "leg"])
    (top_countries, top_first_names) = read_persisted_dummy_column_values()
    running_order["median_pace"] = np.exp(running_order["pred_log_mean"])
    running_order["log_stdev"] = running_order["pred_log_std"]

    # In the training data the minimum is 1, for unknown runners
    running_order["num_runs"] = running_order["num_runs"] + 1
    unknown_runners_features = preprocess_features_v2(running_order, top_countries, False)
    known_runners_features = preprocess_features_v2(running_order, top_countries, True)
    running_order["num_runs"] = running_order["num_runs"] - 1

    hgbr_unknown_runners_est = _predict_for_unknown_runners(unknown_runners_features, "unknown")
    hgbr_known_runners_est = _predict_for_unknown_runners(known_runners_features, "known")
    running_order["predicted"] = hgbr_unknown_runners_est["predicted"]
    running_order["log_std"] = hgbr_unknown_runners_est["log_std"]
    logging.info(f"hgbr_unknown_runners_est:")
    shared.log_df(
        running_order[["predicted", "log_std"]].groupby(running_order["num_runs"]).agg(["mean", "median", "count"]))

    # overwrite where num_runs is greater than 1
    known_runners = running_order["num_runs"] > 1
    running_order.loc[known_runners, "predicted"] = hgbr_known_runners_est.loc[known_runners, "predicted"]

    # Do not use historical std from known runners as its quite narrow

    shared.log_df(running_order[["predicted", "log_std"]].groupby(running_order["num_runs"]).agg(["mean", "count"]))
    # Remove extremes and negative log_std values that should not be possible
    running_order.loc[running_order["log_std"] < np.log(1.07), "log_std"] = np.log(1.07)
    shared.log_df(running_order["log_std"].describe(percentiles=[0.01, 0.05, .25, .5, .75, .95, .99]))

    unknown_paces = running_order["num_runs"] < 1
    running_order.loc[unknown_paces, "pred_log_mean"] = 0
    running_order.loc[unknown_paces, "pred_log_std"] = 0

    shared.log_df(running_order[["pred_log_mean", "pred_log_std"]].groupby(running_order["num_runs"]).agg(
        ["mean", "median", "count"]))
    shared.log_df(running_order[["predicted", "log_std"]].describe(percentiles=[0.01, 0.05, .25, .5, .75, .95, .99]))
    shared.log_df(running_order[["predicted", "log_std"]].groupby(running_order["num_runs"]).agg(["mean", "count"]))

    # Trick to combine values from different models
    # Use 100% of HGBR estimates for unknown and slide to runners personal historical values as num_run increase
    # unfortunately this loses terrain scaling for larger num_runs
    running_order["final_pace_mean"] = (np.log(running_order["predicted"]) / (running_order["num_runs"] + 1)) + (
            running_order["pred_log_mean"] * (running_order["num_runs"] / (running_order["num_runs"] + 1)))
    extra_std_weight = 3
    running_order["final_pace_std"] = (extra_std_weight * running_order["log_std"] / (
            running_order["num_runs"] + extra_std_weight)) + (running_order["pred_log_std"] * (
            running_order["num_runs"] / (running_order["num_runs"] + extra_std_weight)))
    # for num_runs 2 and 3 the std is too low, because low number of data point (runs)
    unknown_stds = running_order["num_runs"] < 4
    running_order.loc[unknown_stds, "final_pace_std"] = running_order.loc[unknown_stds, "log_std"]

    logging.info(f"final_pace_std na count: {running_order['final_pace_std'].isna().sum()}")
    shared.log_df(running_order["final_pace_std"].describe(percentiles=[0.01, 0.05, .25, .5, .75, .95, .99]))
    shared.log_df(
        running_order[["final_pace_mean", "final_pace_std"]].groupby(running_order["num_runs"]).agg(["mean", "count"]))

    logging.info(running_order.info())
    logging.info(f"running_order sample:\n{running_order.sample(5)}")

    # remove extremes from unknown runners predictions
    unknown_pace = running_order["num_runs"] < 1
    unknown_std = running_order["num_runs"] < 2
    # TODO Try with more realistic lower bound?
    running_order["final_pace_mean"].values[unknown_pace] = np.clip(
        running_order["final_pace_mean"].values[unknown_pace], np.log(7), np.log(15))
    running_order["final_pace_std"].values[unknown_std] = np.clip(
        running_order["final_pace_std"].values[unknown_std], np.log(1.2), np.log(1.5))

    # remove extremes from all runners
    running_order["final_pace_mean"] = np.clip(running_order["final_pace_mean"].values, np.log(5.6), np.log(19))
    # TODO 1.6 is prob too high
    running_order["final_pace_std"] = np.clip(running_order["final_pace_std"], np.log(1.07), np.log(1.6))
    shared.log_df(running_order.head().round(3))
    shared.log_df(np.exp(running_order[["final_pace_mean", "final_pace_std"]]).describe(
        percentiles=[0.01, 0.02, 0.05, 0.1, .25, .5, .75, .9, .95, .99]))

    # Multiply by default terrain coefficients
    with open(f"data/default_personal_coefficients_{shared.race_id_str()}.json") as json_file:
        defaults = json.load(json_file)
    ideal_paces = pd.read_csv(f'Jukola-terrain/ideal-paces-{shared.race_type()}.tsv', delimiter='\t')
    ideal_paces = ideal_paces[ideal_paces["year"] == shared.forecast_year()]
    ideal_paces["leg_factor"] = defaults["default_intercept"] + defaults["default_coef"] * ideal_paces[
        "terrain_coefficient"]
    shared.log_df(ideal_paces)
    running_order = pd.merge(running_order, ideal_paces[["leg", "leg_factor"]], how="left", on=["leg"])
    # bring in some terrain scaling for larger num_runs
    running_order["weighted_leg_factor"] = (1 / (running_order["num_runs"] + 1)) + (
            running_order["leg_factor"] * (running_order["num_runs"] / (running_order["num_runs"] + 1)))
    # log scale addition equals multiplication in linear scale
    running_order["final_pace_mean"] = running_order["final_pace_mean"] + np.log(running_order["weighted_leg_factor"])

    return running_order


def _find_history_values_for_running_order_names():
    # running_order = pd.read_csv(f'data/running_order_j{shared.forecast_year()}_{shared.race_type()}.tsv', delimiter="\t")
    running_order = pd.read_csv(f"data/running_order_final_{shared.race_id_str()}.tsv", delimiter="\t")
    logging.info(f"running_order.shape: {running_order.shape}")
    shared.log_df(running_order)
    running_order["orig_name"] = running_order["name"]
    # to lower case, trim spaces, remove double spaces
    running_order["name"] = running_order["name"].str.lower().str.strip().str.replace(' +', ' ')
    running_order["team_base_name_upper"] = running_order["team_base_name"].str.upper()
    history = _load_history_and_calculate_log_paces()
    # logging.info(f"history.shape before cleanup: {history.shape}")
    # history = history[history["num_valid_times"] >= 1].reset_index()
    logging.info(f"history.shape: {history.shape}")
    shared.log_df(history)
    history["num_runs"] = history["num_valid_times"]
    history = history.assign(name_without_colon=history['name'].str.split(":").str[0])
    switched_names = [switch_first_and_last_name(name) for name in history["name_without_colon"].values]
    history = history.assign(switched_name=switched_names)
    history["duplicate_name"] = history["name_without_colon"].duplicated(keep=False)
    history["name_contains_colon"] = history['name'].str.contains(":", regex=False)
    shared.log_df(
        history[history["name_contains_colon"]][
            ["name", "duplicate_name", "switched_name", "name_without_colon", "teams"]])
    # No history defaults
    running_order["pred_log_mean"] = 0
    running_order["pred_log_std"] = 0
    running_order["num_runs"] = 0
    running_order["predicted_log_pace_mean"] = 0
    running_order["predicted_log_pace_std"] = 0
    running_order["num_valid_times"] = 0
    # switched names
    switched_names_history = history.sort_values('num_valid_times', ascending=False).drop_duplicates(['switched_name'])
    running_order_with_history = running_order.merge(switched_names_history, how="left", left_on=["name"],
                                                     right_on=["switched_name"], suffixes=("", "_switched"))
    switched = running_order_with_history["predicted_log_pace_mean_switched"].notna()
    logging.info(f"switched ratio: {switched.mean()}")
    logging.info(f"switched count: {switched.sum()}")
    assert len(running_order) == len(running_order_with_history)
    running_order_with_history.loc[switched, "pred_log_mean"] = running_order_with_history[switched][
        "predicted_log_pace_mean_switched"]
    running_order_with_history.loc[switched, "pred_log_std"] = running_order_with_history[switched][
        "predicted_log_pace_std_switched"]
    running_order_with_history.loc[switched, "num_runs"] = running_order_with_history[switched][
        "num_valid_times_switched"]
    # Multiple teams
    multi_team_history = history[history["name_contains_colon"]]
    # teams column contain only a single team name if runs are splitted to multiple teams (one history row per team)
    running_order_with_history = pd.merge(running_order_with_history, multi_team_history,
                                          how="left", left_on=["name", "team_base_name_upper"],
                                          right_on=["name_without_colon", "teams"],
                                          suffixes=("", "_multi_team"), )
    multi_team = running_order_with_history["predicted_log_pace_mean_multi_team"].notna()
    logging.info(f"multi_team ratio: {multi_team.mean()}")
    logging.info(f"multi_team count: {multi_team.sum()}")
    assert len(running_order) == len(running_order_with_history)
    running_order_with_history.loc[multi_team, "pred_log_mean"] = running_order_with_history[multi_team][
        "predicted_log_pace_mean_multi_team"]
    running_order_with_history.loc[multi_team, "pred_log_std"] = running_order_with_history[multi_team][
        "predicted_log_pace_std_multi_team"]
    running_order_with_history.loc[multi_team, "num_runs"] = running_order_with_history[multi_team][
        "num_valid_times_multi_team"]
    # By just name, no special tricks (plain name)
    running_order_with_history = pd.merge(running_order_with_history, history[history["duplicate_name"] == False],
                                          how="left", left_on=["name"], right_on=["name"],
                                          suffixes=("", "_plain_name"), )
    shared.log_df(running_order_with_history[['name', "pred_log_mean", 'predicted_log_pace_mean_plain_name']])
    plain_name = running_order_with_history["predicted_log_pace_mean_plain_name"].notna()
    logging.info(f"plain_name ratio: {plain_name.mean()}")
    logging.info(f"plain_name count: {plain_name.sum()}")
    logging.info(f"running_order.shape: {running_order.shape}")
    logging.info(f"running_order_with_history.shape: {running_order_with_history.shape}")
    assert len(running_order) == len(running_order_with_history)
    running_order_with_history.loc[plain_name, "pred_log_mean"] = running_order_with_history[plain_name][
        "predicted_log_pace_mean_plain_name"]
    running_order_with_history.loc[plain_name, "pred_log_std"] = running_order_with_history[plain_name][
        "predicted_log_pace_std_plain_name"]
    running_order_with_history.loc[plain_name, "num_runs"] = running_order_with_history[plain_name][
        "num_valid_times_plain_name"]
    shared.log_df(running_order_with_history[['name', 'num_runs', 'pred_log_mean']])
    logging.info(f"running_order_with_history.columns: {running_order_with_history.columns}")
    return running_order_with_history


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s [%(process)d] %(funcName)s [%(levelname)s] %(message)s')
    logging.info("Creating static individual estimates for running order")
    combine_estimates_with_running_order()
