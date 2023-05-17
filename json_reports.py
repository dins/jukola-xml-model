import json
import logging
import os

import pandas as pd
import numpy as np

import shared

# time poetry run python json_reports.py && wc data/all_json_reports.tsv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s [%(process)d] %(funcName)s [%(levelname)s] %(message)s')


def list_files_in_folder(folder_name):
    files = []
    for file in os.listdir(folder_name):
        if file.endswith(".json"):
            files.append(file)
    return files


def read_all_json_files_from_folder_to_df():
    folder_name = "json_reports"
    # read .json files in parallel to pandas dataframes
    dfs = []
    for file_name in list_files_in_folder(folder_name):
        #logging.info(f"Reading {file_name}")
        with open(f"{folder_name}/{file_name}", "r") as f:
            reports_dict = json.load(f)
            execution_timestamp = reports_dict.pop("execution_timestamp")["value"]
            if execution_timestamp == "unknown":
                logging.warning(f"Skipping {file_name} with unknown execution_timestamp")
                continue
            race_id = reports_dict.pop("race_id")["value"]
            num_runners = reports_dict.pop("num_runners")["value"]

            # convert dict items to flat records
            def _to_record(k, v):
                return {"name": k, "value": v["value"], "desc": v["desc"]}

            records = [_to_record(k, v) for k, v in reports_dict.items()]
            df = pd.DataFrame(records)
            df["execution_timestamp"] = execution_timestamp
            df["race_id"] = race_id
            df["num_runners"] = num_runners
            dfs.append(df)

    # concatenate all dataframes
    all_df = pd.concat(dfs, ignore_index=True).sort_values(by=["execution_timestamp", "race_id", "name"])
    # move execution_timestamp to the first column
    cols = all_df.columns.tolist()
    cols = cols[-2:] + cols[:-2]
    all_df = all_df[cols]

    all_reports_path = "reports/all_json_reports.tsv"
    all_df.to_csv(all_reports_path, sep="\t", index=False)
    logging.info(f"Saved {len(all_df)} rows to {all_reports_path}")

    # Should we distinguish ve and ju here?
    key_values_df = all_df[all_df["desc"].isin(
        ["Viestin aikaväliennuste väärin", "Yksilöennusteen keskivirhe", "Yksilön aikaväliennuste väärin"])]
    # Weighted by number of participants which is roughly legs * teams,
    # so Venlas with less legs have less influence
    averages_df = key_values_df.groupby(["execution_timestamp", "desc"]).apply(
        lambda x: np.average(x.value, weights=x.num_runners)).reset_index()
    averages_df.columns = ["execution_timestamp", "kpi", "value"]
    # convert long format to wide format
    wide_averages_df = averages_df.pivot(index="execution_timestamp", columns="kpi", values="value")
    shared.log_df(wide_averages_df.round(3))

    summary_path = "reports/reports_summary.tsv"
    averages_df.round(3).to_csv(summary_path, sep="\t", index=False)
    logging.info(f"Saved {len(averages_df)} rows to {summary_path}")


if __name__ == '__main__':
    read_all_json_files_from_folder_to_df()
    os.getenv("RUN_TS", "unknown")
