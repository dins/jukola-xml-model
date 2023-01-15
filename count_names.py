import csv
import logging

import pandas as pd
import shared
# time poetry run python count_names.py

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


def _append_names(year, ve_or_ju, all_names):
    in_file_name = f'data/results_with_dist_j{year}_{ve_or_ju}.tsv'
    with open(in_file_name) as csvfile:
        csvreader = csv.reader(csvfile, delimiter="\t")
        next(csvreader, None)  # skip the headers
        for row in csvreader:
            name = row[8].lower().strip()
            if len(name) > 4:
                all_names.append(name)


def analyze_names():
    all_years = shared.all_years
    logging.info(f"All years {all_years}")

    all_names = []
    for year in all_years:
        _append_names(year, "ve", all_names)
        _append_names(year, "ju", all_names)

    all_names
    runs = pd.DataFrame(all_names, columns=["name"])

    runs = runs[runs.name.str.count(" ") >= 1]
    names = runs["name"].str.split(" ", n=1, expand=True)
    runs["firstname"] = names[0]
    runs["lastname"] = names[1]
    logging.info(runs)

    fn_counts = runs.groupby("firstname").count().reset_index()[["firstname", "name"]].rename(
        columns={"name": "fn_count"})
    ln_counts = runs.groupby("lastname").count().reset_index()[["lastname", "name"]].rename(
        columns={"name": "ln_count"})
    counts = fn_counts.set_index('firstname').join(ln_counts.set_index('lastname'), how="outer").fillna(0)
    logging.info(counts)

    counts["is_firstname"] = counts["fn_count"] > counts["ln_count"]

    to_file = counts.reset_index().rename(columns={"index": "name"})
    to_file.to_json(f'data/name_counts.json', orient="records", date_format="iso")


if __name__ == '__main__':
    analyze_names()
