import json

import joblib
import numpy as np
import pandas as pd

# time for year in $(seq 1992 2019); do ./parse-leg-distances.sh $year ve; done
distances = {
    "ve": {
        1992: [6.8, 6.7, 5.7, 8.6],
        1993: [6.2, 6.7, 5.6, 8.5],
        1994: [7.4, 7.4, 5.7, 8.6],
        1995: [5.8, 5.7, 7.9, 8.3],
        1996: [7.9, 7.9, 6.1, 9.1],
        1997: [6.8, 4.7, 4.7, 7.3],
        1998: [6.8, 4.7, 4.7, 7.3],
        1999: [7.0, 7.0, 6.2, 8.8],
        2000: [6.3, 6.3, 7.3, 7.7],
        2001: [6.9, 6.2, 7.1, 8.1],
        2002: [5.6, 5.3, 6.2, 8.0],
        2003: [5.0, 4.9, 5.1, 6.5],
        2004: [7.8, 4.5, 7.7, 4.4],
        2005: [5.1, 5.2, 6.1, 7.8],
        2006: [5.4, 5.9, 5.2, 7.8],
        2007: [5.7, 5.7, 6.2, 7.7],
        2008: [7.1, 7.1, 5.6, 8.1],
        2009: [7.1, 6.6, 6.0, 8.9],
        2010: [5.1, 4.4, 6.2, 7.5],
        2011: [6.9, 6.2, 5.1, 8.5],
        2012: [5.7, 5.8, 7.2, 8.4],
        2013: [8.2, 6.2, 6.2, 8.7],
        2014: [5.1, 5.0, 6.7, 7.4],
        2015: [8.0, 6.0, 6.2, 8.8],
        2016: [7.1, 6.7, 6.0, 9.1],
        2017: [6.7, 6.6, 5.8, 8.0],
        2018: [6.2, 6.2, 5.4, 7.9],
        2019: [6.0, 5.7, 7.3, 7.9]
    },
    "ju": {
        1992: [12.2, 12.7, 14.4, 8.4, 8.3, 10.4, 13.7],
        1993: [12.2, 14.3, 10.0, 8.3, 12.6, 8.3, 14.8],
        1994: [12.2, 12.3, 9.0, 16.4, 9.3, 8.9, 14.0],
        1995: [10.0, 11.9, 13.0, 8.3, 8.3, 10.4, 14.1],
        1996: [13.1, 13.5, 10.7, 8.9, 8.9, 12.2, 16.6],
        1997: [12.1, 11.1, 13.0, 7.3, 11.9, 6.4, 14.6],
        1998: [10.0, 10.0, 12.8, 6.8, 6.8, 11.0, 13.1],
        1999: [13.4, 13.4, 15.7, 8.8, 8.8, 11.0, 14.5],
        2000: [13.0, 13.0, 14.2, 8.4, 8.4, 11.9, 16.2],
        2001: [12.1, 12.2, 13.2, 7.4, 7.4, 9.7, 14.7],
        2002: [10.7, 10.7, 12.8, 6.3, 6.4, 10.3, 14.2],
        2003: [11.4, 11.9, 13.3, 6.6, 6.6, 10.2, 14.4],
        2004: [13.8, 13.7, 14.9, 8.5, 8.5, 12.0, 15.7],
        2005: [13.2, 11.3, 14.2, 7.5, 7.6, 9.8, 15.1],
        2006: [11.3, 11.1, 13.0, 7.7, 7.7, 9.3, 14.3],
        2007: [10.7, 10.7, 13.8, 7.6, 7.6, 10.0, 15.0],
        2008: [11.5, 12.3, 13.1, 7.8, 7.9, 9.8, 13.8],
        2009: [12.5, 12.7, 14.7, 9.5, 9.6, 11.3, 16.6],
        2010: [9.8, 10.0, 11.3, 6.9, 6.8, 9.2, 13.4],
        2011: [11.5, 11.4, 13.6, 8.3, 8.5, 10.5, 15.6],
        2012: [12.7, 12.7, 14.1, 7.7, 8.1, 10.2, 15.1],
        2013: [12.2, 13.0, 14.4, 7.8, 7.7, 11.7, 15.1],
        2014: [10.1, 11.5, 10.2, 7.6, 7.7, 10.7, 14.0],
        2015: [13.8, 12.3, 15.8, 8.1, 8.6, 12.6, 14.6],
        2016: [10.7, 12.8, 14.1, 8.6, 8.7, 12.4, 16.5],
        2017: [12.8, 14.3, 12.3, 7.7, 7.8, 11.1, 13.8],
        2018: [11.0, 11.9, 12.7, 8.8, 8.7, 10.8, 15.1],
        2019: [10.9, 10.5, 13.2, 7.3, 7.8, 11.1, 12.9]
    }
}


def leg_distance(ve_or_ju, year, leg):
    dist = distances[ve_or_ju][year]
    return dist[leg - 1]


start_timestamp = {
    "ve": {
        2018: pd.Timestamp(year=2018, month=6, day=16, hour=14),
        2019: pd.Timestamp(year=2019, month=6, day=15, hour=14)
    },
    "ju": {
        2018: pd.Timestamp(year=2018, month=6, day=16, hour=23),
        2019: pd.Timestamp(year=2019, month=6, day=15, hour=23)
    }
}

changeover_closing = {
    "ve": {
        2018: pd.Timestamp(year=2018, month=6, day=16, hour=18, minute=30),
        2019: pd.Timestamp(year=2019, month=6, day=15, hour=18, minute=30)
    },
    "ju": {
        2018: pd.Timestamp(year=2018, month=6, day=17, hour=8, minute=45),
        2019: pd.Timestamp(year=2019, month=6, day=16, hour=8, minute=45)
    }
}

dark_period = {
    2019: {
        "start": pd.Timestamp(year=2019, month=6, day=15, hour=23, minute=4),
        "end": pd.Timestamp(year=2019, month=6, day=16, hour=3, minute=41)
    }
}

num_legs = {
    "ve": 4,
    "ju": 7
}


def read_persisted_dummy_column_values(ve_or_ju):
    with open(f"data/top_countries_{ve_or_ju}.json") as json_file:
        top_countries = json.load(json_file)
    with open(f"data/top_first_names_{ve_or_ju}.json") as json_file:
        top_first_names = json.load(json_file)

    return (top_countries, top_first_names)


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
        if (len(runners) > 0):
            print(f"Found {len(runners)} history with switched name {switched_name} ")

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


def predict_without_history(features, ve_or_ju):
    gbr = joblib.load(f'gbr_{ve_or_ju}.sav')
    gbr_q_low = joblib.load(f'gbr_q_low_{ve_or_ju}.sav')
    gbr_q_high = joblib.load(f'gbr_q_high_{ve_or_ju}.sav')

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
    # cliping 0 to 1 is a hack for when predicting for unknown runners
    runs["runs"] = np.clip(runs.num_runs, 1, 8).astype(str)

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

    # Ensure that a column exists for each to country, despite none being in data
    country_cols = [f"c_{country}" for country in top_countries]
    missing_country_cols = [col for col in country_cols if not col in features.columns]
    display(missing_country_cols)
    missing_country_cols_df = pd.DataFrame({col: 0 for col in missing_country_cols}, index=features.index)
    features = pd.concat([features, missing_country_cols_df], sort=False, axis=1)

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
