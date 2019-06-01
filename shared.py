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
    #features["team_id_log10"] = np.log10(runs.team_id)
    #features["team_id_log100"] = np.log(runs.team_id) / np.log(100)
    #features["team_id_square"] = np.square(runs.team_id)

    #features.insert(0, "team_id_square", np.square(runs.team_id))
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
    #truncate runs
    features["runs"] = np.clip(features.num_runs, 0, 8 )
    #first name split
    features["first_name"] = features.name.str.split(" ", expand=True).iloc[:, 0]

    #set country to one of the top countries or other
    country_counts = runs_df["team_country"].value_counts()
    top_country_counts = country_counts[country_counts > 100]
    top_countries = top_country_counts.keys().tolist()
    features["c"] = features.apply(lambda run: truncate_to_top_values(run["team_country"], top_countries), axis=1)

    #hierarchical group from full name
    labels, uniques = pd.factorize(features.name.values)

    #ID transforms
    features["team_id_log10"] = np.log10(features.team_id)
    features["team_id_log100"] = np.log(features.team_id) / np.log(100)
    features["team_id_square"] = np.square(features.team_id)


    #make df with names from Venlat
    ve_data = pd.read_csv(f'data/runs_ve.tsv', delimiter="\t")
    ve_data["first_name"] = ve_data.name.str.split(" ", expand=True).iloc[:, 0]
    features["ve_name"]=runs_df.first_name.isin(set(ve_data.first_name))
    features['ve_name']=features['ve_name']*1

    #select only the named features
    features = features[list_of_features]
    #explode leg and country
    numpy_frame_x = pd.get_dummies(data=features, columns=["leg","c"], drop_first=True, sparse=True).drop(columns=["pace"]).values
    numpy_y = features["pace"].values
    return numpy_frame_x, numpy_y, features, labels