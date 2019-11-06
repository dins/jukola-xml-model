import json
import pandas as pd
import numpy as np
import shared
import json

import collections
import csv
import logging
import sys
from collections import defaultdict

# time pipenv run python normalize_names.py

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

def read_first_names():
    with open(f'data/name_counts.json') as json_file:
        name_counts = json.load(json_file)
        first_names = [count["name"] for count in name_counts if count["is_firstname"]]
        return first_names

first_names = read_first_names()

def is_firstname(name):
    return name.lower() in first_names

def normalize_name(orig_name):
    name = orig_name.strip()
    if " - " in name:
        logging.info(f"Trimming spaces around DASH '{orig_name}'")
        name = name.replace(" - ", "-")

    if "  " in name:
        logging.info(f"Trimming DOUBLE or multiple spaces '{orig_name}'")
        name = ' '.join(name.split())

    if "|" in name:
        logging.info(f"Trimming pipes '{orig_name}'")
        name = name.replace("|", "")

    splits = name.split()
    if len(splits) <= 1:
        if len(name) > 0:
            logging.info(f"Ignoring possibly invalid name '{orig_name}'")
        return name

    if len(splits) == 2:
        if not is_firstname(splits[0]) and not is_firstname(splits[1]):
            logging.info(f"NOT swithcing name '{orig_name}'")
        if not is_firstname(splits[0]) and is_firstname(splits[1]):
            swithced_name = f"{splits[1]} {splits[0]}"
            logging.info(f"swithced name '{orig_name}' TO '{swithced_name}'")
            return swithced_name

    return name


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
    num_all_years = 27
    all_years = [i for i in range(1992, 1992 + num_all_years)]
    logging.info(f"All years {all_years}")

    all_names = []
    for year in all_years:
        _append_names(year, "ve", all_names)
        _append_names(year, "ju", all_names)

    all_names
    runs = pd.DataFrame(all_names, columns=["name"])

    runs = runs[runs.name.str.count(" ") >= 1]
    names = runs["name"].str.split(" ", n= 1, expand = True)
    runs["firstname"] = names[0]
    runs["lastname"] = names[1]
    logging.info(runs)

    fn_counts = runs.groupby("firstname").count().reset_index()[["firstname", "name"]].rename(columns={"name": "fn_count"})
    ln_counts = runs.groupby("lastname").count().reset_index()[["lastname", "name"]].rename(columns={"name": "ln_count"})
    counts = fn_counts.set_index('firstname').join(ln_counts.set_index('lastname'), how="outer").fillna(0)
    logging.info(counts)

    counts["is_firstname"] = counts["fn_count"] > counts["ln_count"]

    to_file = counts.reset_index().rename(columns={"index": "name"})
    to_file.to_json(f'data/name_counts.json', orient="records", date_format="iso")


if __name__ == '__main__':
    analyze_names()
