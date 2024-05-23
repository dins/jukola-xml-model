import logging
from sklearn.cluster import KMeans
import numpy as np
import pandas as pd
import shared
import json

# time RACE_TYPE=ve FORECAST_YEAR=2022 poetry run python cluster_names.py

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s [%(threadName)s] %(funcName)s [%(levelname)s] %(message)s')


def cluster_names():
    logging.info(f"computing name clusters for {shared.race_id_str()}")
    runs = pd.read_csv(f'data/long_runs_and_running_order_{shared.race_id_str()}.tsv', delimiter='\t')
    runs = runs.dropna(subset=['pace'])
    history = runs.groupby('name').agg(
        num_valid_times=('pace', 'count'),
        mean_pace=('pace', 'mean'),
    ).reset_index()

    # preprocess
    history["first_name"] = history.name.str.split(" ", expand=True).iloc[:, 0]
    # logging.info(history.head())
    with_history = history[history["num_valid_times"] >= 1]
    names = with_history[['first_name', "mean_pace"]].groupby('first_name').agg(
        ["median", "mean", "std", "count"]).dropna()
    names.columns = ['_'.join(col).strip() for col in names.columns.values]
    logging.info(names)

    X = names[["mean_pace_median", "mean_pace_mean"]].values
    pace_kmeans = KMeans(n_clusters=10, random_state=2019).fit(X)
    X_std = names[["mean_pace_std"]].values
    pace_std_kmeans = KMeans(n_clusters=4, random_state=2019).fit(X_std)

    names = names.assign(fn_pace_class=pace_kmeans.labels_)
    names = names.assign(fn_pace_std_class=pace_std_kmeans.labels_)
    logging.info(names.head(10))

    logging.info(names.sort_values(by=["mean_pace_median"]))
    names.columns = names.columns.get_level_values(0)
    sorted = names.sort_values(by=["mean_pace_count"], ascending=False)[
        ["mean_pace_count", "fn_pace_class", "fn_pace_std_class"]]
    logging.info(sorted)
    output_path = f"data/name_pace_classes_{shared.race_id_str()}.tsv"
    sorted.to_csv(output_path, sep="\t")
    logging.info(f'Wrote: {output_path}')

cluster_names()
