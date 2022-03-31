import json
import logging

import joblib
import numpy as np
import pandas as pd

import shared

# time pipenv run python static_individual_estimates.py

logging.basicConfig(level=shared.log_df, format='%(asctime)s %(message)s')


def read_persisted_dummy_column_values():
    with open(f"data/top_countries_{shared.race_id_str()}.json") as json_file:
        top_countries = json.load(json_file)
    with open(f"data/top_first_names_{shared.race_id_str()}.json") as json_file:
        top_first_names = json.load(json_file)

    return (top_countries, top_first_names)


# TODO this takes most time in simulation
def get_matching_history_row_for_runner(running_order_row, history_df, no_history_row):
    # no_history_row = pd.DataFrame([[0, 0]], columns=["log_means", "log_stdevs"])
    name = running_order_row["name"].lower()
    # Remove double spaces
    name = " ".join(name.split())

    by_name = history_df[history_df['name'] == name]
    by_name_and_colon = history_df[history_df['name'].str.contains(name + ":", regex=False)]

    runners = by_name.append(by_name_and_colon)

    if (len(runners) == 0) and " " in name:
        names = name.split()
        names.insert(0, names.pop())
        switched_name = " ".join(names)
        # print(f"No history for {name}, trying switched name {switched_name}")
        by_name = history_df[history_df['name'] == switched_name]
        by_name_and_colon = history_df[history_df['name'].str.contains(switched_name + ":", regex=False)]
        runners = by_name.append(by_name_and_colon)
        # if (len(runners) > 0):
          #  print(f"Found {len(runners)} history with switched name {switched_name} ")

    if (len(runners) == 1):
        # Only one runner with this name
        return runners
    # Try to match runner with team name
    team_name = running_order_row["team_base_name"].upper()
    runners = runners[runners['teams'].str.contains(team_name, regex=False)]
    if (len(runners) == 1):
        return runners
    if (len(runners) == 0):
        # No history found
        return no_history_row
    print(f"name '{name}' team_name '{team_name}'")
    print(f"by_name {len(by_name)} by_name_and_colon {len(by_name_and_colon)} runners {len(runners)}")
    print(f"Duplicate runner {runners}")
    # print(f"TEAMS by_name_and_colon {by_name_and_colon['teams']}")
    return runners.sort_values("num_runs", ascending=False).head(1)


def predict_without_history(features):
    gbr = joblib.load(f'models/gbr_{shared.race_id_str()}.sav')
    gbr_q_low = joblib.load(f'models/gbr_q_low_{shared.race_id_str()}.sav')
    gbr_q_high = joblib.load(f'models/gbr_q_high_{shared.race_id_str()}.sav')

    gbr_preds = gbr.predict(features)
    gbr_q_low_preds = gbr_q_low.predict(features)
    gbr_q_high_preds = gbr_q_high.predict(features)

    gbr_sd_estimate = pd.DataFrame({
        'log_q_low': gbr_q_low_preds,
        'predicted': np.exp(gbr_preds),
        'log_q_high': gbr_q_high_preds,
    })

    # Propably unjustified way to estimate standard deviation
    gbr_sd_estimate["log_std"] = (gbr_sd_estimate.log_q_high - gbr_sd_estimate.log_q_low) / 2

    logging.info(gbr_sd_estimate.head(15).round(3))
    logging.info(gbr_sd_estimate["log_std"].mean())
    return gbr_sd_estimate


def preprocess_countries_names_and_features():
    grouped = pd.read_csv(f'data/grouped_paces_{shared.race_id_str()}.tsv', delimiter="\t")
    grouped["leg"] = grouped["most_common_leg"]
    grouped["team_id"] = grouped["mean_team_id"]

    # top_countries
    grouped["team_country"] = grouped["most_common_country"]
    country_counts = grouped["team_country"].value_counts()
    top_country_counts = country_counts[country_counts > 30]
    top_countries = top_country_counts.keys().tolist()
    logging.info(f"top_countries: {len(top_countries)}: {top_countries}")

    with open(f"data/top_countries_{shared.race_id_str()}.json", 'w') as outfile:
        json.dump(top_countries, outfile)

    # TODO do this before top_countries ?
    grouped = grouped[grouped["mean_pace"].notna()]

    # top_first_names
    grouped["first_name"] = grouped.name.str.split(" ", expand=True).iloc[:, 0]
    fn_counts = grouped["first_name"].value_counts()
    top_fn_counts = fn_counts[fn_counts > 10]
    top_first_names = top_fn_counts.keys().tolist()

    with open(f"data/top_first_names_{shared.race_id_str()}.json", 'w') as outfile:
        json.dump(top_first_names, outfile)

    features = preprocess_features(grouped, top_countries)
    x = features.values
    y = np.log(grouped.mean_pace.values)
    y = y.reshape(len(y), 1).ravel()

    logging.info(f"x: {x.shape}, y: {y.shape}, features: {features.shape}, ")

    return (x, y, features)


def preprocess_features(runs_df, top_countries):
    logging.info(runs_df.info())
    logging.info(f"top_countries: {len(top_countries)}: {top_countries}")
    # convert some int columns to labels
    runs = runs_df.assign(leg=runs_df.leg.astype(str))
    # cliping 0 to 1 is a hack for when predicting for unknown runners
    runs["runs"] = np.clip(runs.num_runs, 1, shared.num_pace_years + 1).astype(str)

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
    features = pd.get_dummies(runs[["leg", "c", "runs", "fn_pace_class", "fn_pace_std_class"]], sparse=True)

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

    # allow linear regression to fit non-linear terms
    # features["team_id_log2"] = np.log2(runs.team_id)
    # features["team_id_log10"] = np.log10(runs.team_id)
    # features["team_id_log100"] = np.log(runs.team_id) / np.log(100)
    # features["team_id_square"] = np.square(runs.team_id)

    # TODO remove and maybe replace with log 100
    features.insert(0, "team_id_square", np.square(runs.team_id))
    features.insert(0, "team_id_log10", np.log10(runs.team_id))
    features.insert(0, "team_id", runs["team_id"])

    # TODO Test the effect of this
    features = features.reindex(sorted(features.columns), axis=1)

    logging.info(f"features: {features.info()}")
    logging.info(f"features columns {features.columns}")

    return features


def _load_history_and_calculate_log_paces():
    history = pd.read_csv(f'data/grouped_paces_{shared.race_id_str()}.tsv', delimiter="\t")

    history["predicted_log_pace_mean"] = np.nanmean(np.log(history[shared.pace_columns]), axis=1)
    history["predicted_log_pace_std"] = np.nanstd(np.log(history[shared.pace_columns]), axis=1)

    return history[["num_valid_times", "predicted_log_pace_mean", "predicted_log_pace_std", "name", "teams"]]


def combine_estimates_with_running_order():
    # running_order = pd.read_csv(f'data/running_order_j{shared.forecast_year()}_{shared.race_type()}.tsv', delimiter="\t")
    running_order = pd.read_csv(f"data/running_order_final_{shared.race_id_str()}.tsv", delimiter="\t")
    shared.log_df(running_order.shape)

    running_order["orig_name"] = running_order["name"]
    running_order["name"] = running_order["name"].str.lower()

    historical_log_paces = _load_history_and_calculate_log_paces()
    shared.log_df(historical_log_paces.shape)

    historical_log_paces["num_runs"] = historical_log_paces["num_valid_times"]
    no_history_row = pd.DataFrame([[0, 0, 0]],
                                  columns=["predicted_log_pace_mean", "predicted_log_pace_std", "num_valid_times"])

    def get_history_and_preds(running_order_row):
        history_row = get_matching_history_row_for_runner(running_order_row, historical_log_paces, no_history_row)
        pred_log_mean = history_row.predicted_log_pace_mean.values[0]
        pred_log_std = history_row.predicted_log_pace_std.values[0]
        num_valid_times = history_row.num_valid_times.values[0]
        return pd.Series(
            {"pred_log_mean": pred_log_mean, "pred_log_std": pred_log_std, "num_valid_times": num_valid_times})

    history_and_preds = running_order.apply(lambda row: get_history_and_preds(row), axis=1)
    running_order = running_order.assign(num_runs=history_and_preds.num_valid_times)
    running_order = running_order.assign(pred_log_mean=history_and_preds.pred_log_mean)
    running_order = running_order.assign(pred_log_std=history_and_preds.pred_log_std)

    (top_countries, top_first_names) = read_persisted_dummy_column_values()

    features = preprocess_features(running_order, top_countries)

    shared.log_df(features.info())

    gbr_sd_estimate = predict_without_history(features)

    running_order["predicted"] = gbr_sd_estimate["predicted"]
    running_order["log_q_low"] = gbr_sd_estimate["log_q_low"]
    running_order["log_q_high"] = gbr_sd_estimate["log_q_high"]
    running_order["log_std"] = gbr_sd_estimate["log_std"]

    shared.log_df(running_order["log_std"].describe(percentiles=[0.01, 0.05, .25, .5, .75, .95, .99]))

    running_order["log_std_fixed"] = running_order["log_std"]
    # running_order["log_std_fixed"] = np.clip(running_order["log_std"], 0.1, 0.5)
    # running_order["log_std"].values[running_order["log_std"].values < 0] = 0.1

    # def select_final_ind_preds(row):
    #    return pd.Series({"pred_log_mean": pred_log_mean, "pred_log_std": pred_log_std, "num_valid_times": num_valid_times})

    # final_ind_preds = running_order.apply(lambda row: select_final_ind_preds(row), axis=1)

    running_order["final_pace_mean"] = np.log(running_order["predicted"])
    running_order["final_pace_std"] = running_order["log_std"]
    use_predicted_mean = running_order["num_runs"].values >= 1
    running_order["final_pace_mean"].values[use_predicted_mean] = running_order["pred_log_mean"].values[
        use_predicted_mean]
    use_predicted_std = running_order["num_runs"].values >= 4
    running_order["final_pace_std"].values[use_predicted_std] = running_order["pred_log_std"].values[use_predicted_std]

    # remove extremes from unknown runners predictions
    unknown_runners = running_order["num_runs"].values < 1
    # TODO Try with more realistic lower bound?
    running_order["final_pace_mean"].values[unknown_runners] = np.clip(
        running_order["final_pace_mean"].values[unknown_runners], np.log(7), np.log(15))
    running_order["final_pace_std"].values[unknown_runners] = np.clip(
        running_order["final_pace_std"].values[unknown_runners], np.log(1.2), np.log(1.5))

    # remove extremes from all runners
    # TODO for 2022 we may need to lower 5.6 ???
    running_order["final_pace_mean"] = np.clip(running_order["final_pace_mean"].values, np.log(5.6), np.log(18))
    # TODO 1.6 is prob too high
    running_order["final_pace_std"] = np.clip(running_order["final_pace_std"], np.log(1.07), np.log(1.6))

    shared.log_df(running_order.head().round(3))

    shared.log_df(np.exp(running_order[["final_pace_mean", "final_pace_std"]]).describe(
        percentiles=[0.01, 0.02, 0.05, 0.1, .25, .5, .75, .9, .95, .99]))

    # Multiply by terrain coefficients
    with open(f"data/default_personal_coefficients_{shared.race_id_str()}.json") as json_file:
        defaults = json.load(json_file)

    # default coefficients
    ideal_paces = pd.read_csv(f'Jukola-terrain/ideal-paces-{shared.race_type()}.tsv', delimiter='\t')
    ideal_paces = ideal_paces[ideal_paces["year"] == shared.forecast_year()]
    ideal_paces["leg_factor"] = defaults["default_intercept"] + defaults["default_coef"] * ideal_paces[
        "terrain_coefficient"]
    shared.log_df(ideal_paces)

    running_order = pd.merge(running_order, ideal_paces[["leg", "leg_factor"]], how="left", on=["leg"])
    # log scale multiplication equals addition on normal scale
    running_order["final_pace_mean"] = running_order["final_pace_mean"] + np.log(running_order["leg_factor"])

    running_order.to_csv(f"data/running_order_with_estimates_{shared.race_id_str()}.tsv", "\t")

    shared.log_df(running_order[
                      ['num_runs', 'pred_log_mean', "pred_log_std", "predicted", "log_std_fixed", "final_pace_mean",
                       "final_pace_std"]
                  ].groupby('num_runs').agg(["mean"]).round(2))

# combine_estimates_with_running_order()
