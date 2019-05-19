import numpy as np
import pandas as pd


def preprocess_features(runs_df, top_countries, top_first_names):
    display(runs_df.info())
    # convert some int columns to labels
    runs = runs_df.assign(leg=runs_df.leg_nro.astype(str))
    runs["runs"] = np.clip(runs.num_runs, 0, 8).astype(str)
    runs = runs.drop(["leg_nro", "year", "team"], axis=1)

    def truncate_to_top_values(value, top_values):
        if value in top_values:
            return value
        else:
            return "OTHER"

    # A columns that contains most poular first names
    runs["first_name"] = runs.name.str.split(" ", expand=True).iloc[:, 0]
    runs["fn"] = runs.apply(lambda run: truncate_to_top_values(run["first_name"], top_first_names), axis=1)

    # Add column for most popular countries
    runs["c"] = runs.apply(lambda run: truncate_to_top_values(run["team_country"], top_countries), axis=1)

    # Explode categories to dummy columns
    features = pd.get_dummies(runs[["leg", "c", "runs", "fn"]], sparse=True)
    # allow linear regression to fit non-linear terms
    # features["team_id_log2"] = np.log2(runs.team_id)
    features["team_id_log10"] = np.log10(runs.team_id)
    features["team_id_log100"] = np.log(runs.team_id) / np.log(100)
    features["team_id_square"] = np.square(runs.team_id)

    features.insert(0, "team_id", runs["team_id"])

    return features