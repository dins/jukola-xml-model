import json

import joblib
import numpy as np
import pandas as pd


def read_persisted_dummy_column_values(ve_or_ju):
    with open(f"data/top_countries_{ve_or_ju}.json") as json_file:
        top_countries = json.load(json_file)
    with open(f"data/top_first_names_{ve_or_ju}.json") as json_file:
        top_first_names = json.load(json_file)

    return (top_countries, top_first_names)


def get_matching_history_row_for_runner(running_order_row, history_df, no_history_row):
    # no_history_row = pd.DataFrame([[0, 0]], columns=["log_means", "log_stdevs"])
    name = running_order_row["name"].lower()

    by_name = history_df[history_df['name'] == name]
    by_name_and_colon = history_df[history_df['name'].str.contains(name + ":", regex=False)]

    runners = by_name.append(by_name_and_colon)
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
    gbr = joblib.load('gbr.sav')
    gbr_q_low = joblib.load('gbr_q_low.sav')
    gbr_q_high = joblib.load('gbr_q_high.sav')

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

    display(gbr_sd_estimate.head(15).round(3))
    display(gbr_sd_estimate["log_std"].mean())
    return gbr_sd_estimate


def preprocess_features(runs_df, top_countries, ve_or_ju):
    display(runs_df.info())
    # convert some int columns to labels
    runs = runs_df.assign(leg=runs_df.leg_nro.astype(str))
    runs["runs"] = np.clip(runs.num_runs, 0, 8).astype(str)

    def truncate_to_top_values(value, top_values):
        if value in top_values:
            return value
        else:
            return "OTHER"

    # First name based pace category
    runs["first_name"] = runs.name.str.split(" ", expand=True).iloc[:, 0]
    name_pace_classes = pd.read_csv(f"data/name_pace_classes_{ve_or_ju}.tsv", delimiter="\t")
    display(name_pace_classes.info())
    runs = runs.join(name_pace_classes.set_index('first_name'), on="first_name")
    runs["fn_pace_class"] = runs["fn_pace_class"].astype(str)
    runs["fn_pace_std_class"] = runs["fn_pace_std_class"].astype(str)

    # Add column for most popular countries
    runs["c"] = runs.apply(lambda run: truncate_to_top_values(run["team_country"], top_countries), axis=1)

    # Explode categories to dummy columns
    features = pd.get_dummies(runs[["leg", "c", "runs", "fn_pace_class", "fn_pace_std_class"]], sparse=True)

    # allow linear regression to fit non-linear terms
    # features["team_id_log2"] = np.log2(runs.team_id)
    # features["team_id_log10"] = np.log10(runs.team_id)
    # features["team_id_log100"] = np.log(runs.team_id) / np.log(100)
    # features["team_id_square"] = np.square(runs.team_id)

    features.insert(0, "team_id_square", np.square(runs.team_id))
    features.insert(0, "team_id_log10", np.log10(runs.team_id))
    features.insert(0, "team_id", runs["team_id"])

    return features


def preprocess_and_make_np_pd_frames(runs_df, list_of_features):
    def truncate_to_top_values(value, top_values):
        if value in top_values:
            return value
        else:
            return "OTHER"

    features = runs_df.assign(leg=runs_df.leg_nro.astype(str))
    # truncate runs
    features["runs"] = np.clip(features.num_runs, 0, 8)
    # first name split
    features["first_name"] = features.name.str.split(" ", expand=True).iloc[:, 0]

    # set country to one of the top countries or other
    country_counts = runs_df["team_country"].value_counts()
    top_country_counts = country_counts[country_counts > 100]
    top_countries = top_country_counts.keys().tolist()
    features["c"] = features.apply(lambda run: truncate_to_top_values(run["team_country"], top_countries), axis=1)

    # hierarchical group from full name
    labels, uniques = pd.factorize(features.name.values)

    # ID transforms
    features["team_id_log10"] = np.log10(features.team_id)
    features["team_id_log100"] = np.log(features.team_id) / np.log(100)
    features["team_id_square"] = np.square(features.team_id)

    # make df with names from Venlat
    ve_data = pd.read_csv(f'data/runs_ve.tsv', delimiter="\t")
    ve_data["first_name"] = ve_data.name.str.split(" ", expand=True).iloc[:, 0]
    features["ve_name"] = runs_df.first_name.isin(set(ve_data.first_name))
    features['ve_name'] = features['ve_name'] * 1

    # select only the named features
    features = features[list_of_features]
    # explode leg and country
    numpy_frame_x = pd.get_dummies(data=features, columns=["leg", "c"], drop_first=True, sparse=True).drop(
        columns=["pace"]).values
    numpy_y = features["pace"].values
    return numpy_frame_x, numpy_y, features, labels
