import json
import logging

import numpy as np
import pandas as pd
import joblib

import log_utils
import shared


# time RACE_TYPE=ve FORECAST_YEAR=2022 poetry run python prepare_run_features.py

# os.environ['FORECAST_YEAR'] = "2019"

def read_persisted_dummy_column_values():
    with open(f"data/top_countries_{shared.race_id_str()}.json") as json_file:
        top_countries = json.load(json_file)

    return top_countries


def preprocess_features_v2(runs_df, top_countries, include_history_paces):
    log_utils.log_dataframe_info(runs_df)
    logging.info(f"runs_df {len(runs_df)} rows")
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
    log_utils.log_dataframe_info(name_pace_classes)
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
    features["leg_distance"] = runs["leg_dist"]

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
    logging.info(f"missing_cols after fn_pace_class_ check: {missing_cols}")

    pace_std_class_cols = [f"fn_pace_std_class_{float(i)}" for i in range(4)]
    missing_cols.extend([col for col in pace_std_class_cols if not col in features.columns])
    logging.info(f"missing_cols after fn_pace_std_class_ check: {missing_cols}")

    missing_country_cols_df = pd.DataFrame({col: 0 for col in missing_cols}, index=features.index)
    features = pd.concat([features, missing_country_cols_df], sort=False, axis=1)

    features.insert(0, "team_id", runs["team_id"])
    features = features.reindex(sorted(features.columns), axis=1)

    log_utils.log_dataframe_info(features)
    logging.info(f"features columns {len(features.columns)} {features.columns}")

    return features


def prepare_run_features(include_history_paces):
    runs = pd.read_csv(f'data/long_runs_and_running_order_{shared.race_id_str()}.tsv', delimiter='\t')
    runs = runs.dropna(subset=['pace'])
    runs["log_pace"] = np.log(runs["pace"])
    # TODO use median_pace
    runner_means = runs[["unique_name", "log_pace"]].groupby(["unique_name"]).agg("mean")

    runs["pace_mean"] = runner_means["log_pace"][runs["unique_name"]].values
    logging.info(f"Runs: \n{runs.head(5).round(3)}")

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
    _write_features_report(features, include_history_paces, "training")
    return x, y, features


def _predict_for_unknown_runners(features, unknown_or_known):
    logging.info(f"{unknown_or_known.upper()} runners, features: {features.shape}")
    log_utils.log_dataframe_info(features)
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


# def _PYMC5_combine_estimates_with_running_order():
def combine_estimates_with_running_order():
    # running_order_with_history = _find_history_values_for_running_order_names()
    running_order_with_estimates = _load_pymc_history_values_for_running_order_names()

    estimates = running_order_with_estimates.rename(columns={"ro_orig_name": "name", "leg_dist": "dist"})


    path = f"data/running_order_with_estimates_{shared.race_id_str()}.tsv"
    estimates.to_csv(path, sep="\t", index=False)
    logging.info(f'Wrote: {path}')

    shared.log_df(estimates[['num_runs', "log_std", "log_mean"]].groupby('num_runs').agg(["mean"]).round(2))


# def combine_estimates_with_running_order():
def _OLD_combine_estimates_with_running_order():
    # running_order_with_history = _find_history_values_for_running_order_names()
    running_order_with_history = _load_history_values_for_running_order_names()

    running_order = _choose_final_estimates_from_various_models(running_order_with_history)
    running_order = running_order[
        ["team_id", "team", "leg", "leg_dist", "ro_orig_name", "final_pace_mean", "final_pace_std", "num_runs"]]
    running_order = running_order.rename(
        columns={"ro_orig_name": "name", "leg_dist": "dist", "final_pace_mean": "log_mean",
                 "final_pace_std": "log_std"})

    running_order.to_csv(f"data/running_order_with_estimates_{shared.race_id_str()}.tsv", sep="\t", index=False)

    shared.log_df(running_order[['num_runs', "log_std", "log_mean"]].groupby('num_runs').agg(["mean"]).round(2))


def _choose_final_estimates_from_various_models(running_order_with_history):
    running_order = running_order_with_history[
        ['team_id', 'team', 'team_country', 'leg', 'leg_dist',
         'name', 'ro_orig_name',
         'num_runs', 'pred_log_mean', 'pred_log_std', 'terrain_coefficient',
         'vertical_per_km']
    ]
    running_order = running_order.reset_index()
    # List of runners with na team_id
    missing_team_ids = running_order[running_order["team_id"].isna()]
    shared.log_df(missing_team_ids)
    assert len(missing_team_ids) == 0, "Missing team ids"

    running_order["year"] = shared.forecast_year()
    top_countries = read_persisted_dummy_column_values()
    running_order["median_pace"] = np.exp(running_order["pred_log_mean"])
    running_order["log_stdev"] = running_order["pred_log_std"]

    # In the training data the minimum is 1, for unknown runners
    running_order["num_runs"] = running_order["num_runs"] + 1
    assert len(running_order) > 0, "Empty running_order"
    unknown_runners_features = preprocess_features_v2(running_order, top_countries, False)
    known_runners_features = preprocess_features_v2(running_order, top_countries, True)
    running_order["num_runs"] = running_order["num_runs"] - 1

    _write_features_report(unknown_runners_features, False, "prediction")
    _write_features_report(known_runners_features, True, "prediction")

    hgbr_unknown_runners_est = _predict_for_unknown_runners(unknown_runners_features, "unknown")
    hgbr_known_runners_est = _predict_for_unknown_runners(known_runners_features, "known")
    running_order["predicted"] = hgbr_unknown_runners_est["predicted"]
    running_order["log_std"] = hgbr_unknown_runners_est["log_std"]
    logging.info(f"hgbr_unknown_runners_est:")
    shared.log_df(
        running_order[["predicted", "log_std"]].groupby(running_order["num_runs"]).agg(["mean", "median", "count"]))

    # overwrite where num_runs is greater than 1
    known_runners = running_order["num_runs"] > 1
    logging.info(f"{running_order.shape=}, {known_runners.shape=}, {hgbr_known_runners_est.shape=}, ")
    # Ensure indices match
    assert running_order.index.equals(hgbr_known_runners_est.index), "Indices do not match"

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

    log_utils.log_dataframe_info(running_order)
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

    # List of runners with na team_id
    missing_team_ids = running_order[running_order["team_id"].isna()]
    shared.log_df(missing_team_ids)
    assert len(missing_team_ids) == 0, "Missing team ids"

    rows_with_na = running_order[running_order['final_pace_mean'].isna() | running_order['final_pace_std'].isna()]
    shared.log_df(rows_with_na, 'NA values')

    assert not running_order['final_pace_mean'].isna().any(), "final_pace_mean column contains NaN values"
    assert not running_order['final_pace_std'].isna().any(), "final_pace_std column contains NaN values"

    return running_order


def _write_features_report(features: pd.DataFrame, include_history: bool, train_or_predict: str) -> None:
    known_or_unknown = "UNKNOWN" if not include_history else "KNOWN"
    cols_str = log_utils.column_names_and_types_to_str(features)
    shared.write_simple_text_report([cols_str, log_utils.dataframe_info_to_str(features)],
                                    f'features/hgbr-{train_or_predict}-{known_or_unknown}-{shared.race_id_str()}.txt')


def _load_history_values_for_running_order_names():
    # unique_name	num_runs	name	team_id	team	team_country	year	pace	emit	leg	median_pace	log_stdev
    runs = pd.read_csv(f'data/long_runs_and_running_order_{shared.race_id_str()}.tsv', delimiter='\t')
    # runs = runs.dropna(subset=['pace'])
    # runs["log_pace"] = np.log(runs["pace"])
    runs = runs[runs['year'] == shared.forecast_year()]
    running_order_with_history = runs.rename(columns={
        'median_log_pace': 'pred_log_mean',
        'log_stdev': 'pred_log_std',
    })
    # TODO team is currently, team_base_name
    shared.log_df(running_order_with_history[['name', 'num_runs', 'pred_log_mean']])
    running_order_with_history = running_order_with_history[[
        'team_id', 'team', 'team_country', 'leg', 'leg_dist', 'name', 'ro_orig_name',
        'num_runs', 'pred_log_mean', 'pred_log_std', 'terrain_coefficient', 'vertical_per_km']
    ]
    logging.info(
        f"running_order_with_history {len(running_order_with_history)} rows, columns: {running_order_with_history.columns}")

    return running_order_with_history


def _load_pymc_history_values_for_running_order_names():
    # unique_name	num_runs	name	team_id	team	team_country	year	pace	emit	leg	median_pace	log_stdev
    runs = pd.read_csv(f'data/long_runs_and_running_order_{shared.race_id_str()}.tsv', delimiter='\t')
    # runs = runs.dropna(subset=['pace'])
    # runs["log_pace"] = np.log(runs["pace"])
    running_order = runs[runs['year'] == shared.forecast_year()]

    results_dir = '~/koodi/Statistical-Rethinking/pymc5-stats-rethink/results/fulldata-jax-v4'
    # results_dir = '~/koodi/Statistical-Rethinking/pymc5-stats-rethink/results/jax-dev'
    path = f'{results_dir}/pymc5_v3_estimates_{shared.race_id_str()}.tsv'

    history_estimates = pd.read_csv(path, delimiter='\t')
    history_estimates.info()
    history_estimates = history_estimates.drop(columns=['num_runs', 'median_pace'])

    missing_estimate_0 = history_estimates[history_estimates['log_mean'].isna()]
    logging.info(f'Found {len(missing_estimate_0)} runners without history estimate:\n{missing_estimate_0.to_string(index=False)}')
    assert len(missing_estimate_0) == 0, "All should have estiamte pace"

    running_order_with_estimates = pd.merge(running_order, history_estimates, on='unique_name', how='left',
                                            suffixes=['_ro', '_history']).reset_index()

    shared.log_df(running_order_with_estimates[['unique_name', 'num_runs', 'log_mean']])

    debug_df = running_order_with_estimates[running_order_with_estimates['unique_name'].str.contains('jonna virtanen')]
    shared.log_df(debug_df[['unique_name', 'num_runs', 'log_mean', 'log_std']])

    # TODO team is currently, team_base_name
    running_order_with_estimates = running_order_with_estimates[[
        'team_id', 'team', 'team_country', 'leg', 'leg_dist', 'unique_name', 'ro_orig_name',
        'num_runs', 'log_mean', 'log_std',
        'personal_start_95', 'personal_end_95', 'pace_samples',
    ]]
    logging.info(
        f"running_order_with_estimates {len(running_order_with_estimates)} rows, columns: {running_order_with_estimates.columns}")

    missing_estimate = running_order_with_estimates[running_order_with_estimates['log_mean'].isna()]
    logging.info(f'Found {len(missing_estimate)} runners without estimate:\n{missing_estimate.to_string(index=False)}')

    # TODO HACK: just add the median for all unknown runners
    fresh_runners = running_order_with_estimates['num_runs'] <= 2
    log_pace_median = running_order_with_estimates[fresh_runners]['log_mean'].dropna().median()
    running_order_with_estimates['log_mean'] = running_order_with_estimates['log_mean'].fillna(log_pace_median)
    log_pace_std_median = running_order_with_estimates[fresh_runners]['log_std'].dropna().median()
    running_order_with_estimates['log_std'] = running_order_with_estimates['log_std'].fillna(log_pace_std_median)

    running_order_with_estimates.info()

    return running_order_with_estimates


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s [%(threadName)s] %(funcName)s [%(levelname)s] %(message)s')
    logging.info("Creating static individual estimates for running order")
    combine_estimates_with_running_order()
