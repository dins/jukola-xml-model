import csv
import logging
import os
import re

import pandas as pd

import logging_config
import shared

logger = logging.getLogger(__name__)

# time uv run python count_names.py
# time RACE_TYPE=ve FORECAST_YEAR=2024 uv run python count_names.py


def _correct_hyphen_spacing_in_names(name: str) -> str:
    # Remove extra spaces around hyphens
    corrected_name = re.sub(r"\s*-\s*", "-", name)
    # Ensure only one space between words
    corrected_name = re.sub(r"\s+", " ", corrected_name)
    return corrected_name


def cleanup_name(orig_name: str) -> str:
    name = orig_name.strip()
    name = _correct_hyphen_spacing_in_names(name)
    if "  " in name:
        # logging.info(f"Trimming DOUBLE or multiple spaces '{orig_name}'")
        name = " ".join(name.split())
    if "|" in name:
        # logging.info(f"Trimming pipes '{orig_name}'")
        name = name.replace("|", "")
    return name


def _append_names(year: int, ve_or_ju: str, all_names: list[str]) -> None:
    in_file_name = f"data/results_with_dist_j{year}_{ve_or_ju}.tsv"
    with open(in_file_name) as csvfile:
        csvreader = csv.reader(csvfile, delimiter="\t")
        next(csvreader, None)  # skip the headers
        for row in csvreader:
            name = row[8].lower().strip()
            if len(name) > 4:
                all_names.append(name)


def _years_for_stats() -> list[int]:
    """Only years strictly before the forecast year: name statistics must not be
    influenced by results of the forecast year or later (temporal leakage)."""
    fy = shared.forecast_year()
    return [y for y in shared.all_years if y < fy]


def _stats_output_path() -> str:
    return f"data/name-counts/name-stats-{shared.forecast_year()}.json"


def analyze_names() -> None:
    all_years_list = _years_for_stats()
    logger.info(f"Years used for name stats (forecast_year={shared.forecast_year()}): {all_years_list}")

    all_names: list[str] = []
    for year in all_years_list:
        _append_names(year, "ve", all_names)
        _append_names(year, "ju", all_names)

    all_names = [cleanup_name(name) for name in all_names]
    runs = pd.DataFrame(all_names, columns=["name"])

    runs = runs[runs.name.str.count(" ") >= 1]
    names = runs["name"].str.split(" ", n=1, expand=True)
    runs["firstname"] = names[0]
    runs["lastname"] = names[1]
    logger.info(runs)

    fn_counts = (
        runs.groupby("firstname")
        .count()
        .reset_index()[["firstname", "name"]]
        .rename(columns={"name": "fn_count"})
    )
    ln_counts = (
        runs.groupby("lastname")
        .count()
        .reset_index()[["lastname", "name"]]
        .rename(columns={"name": "ln_count"})
    )
    counts = (
        fn_counts.set_index("firstname")
        .join(ln_counts.set_index("lastname"), how="outer")
        .fillna(0)
    )
    logger.info(counts)

    counts["is_firstname"] = counts["fn_count"] > counts["ln_count"]

    to_file = counts.reset_index().rename(columns={"firstname": "name"})
    out_path = _stats_output_path()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    to_file.to_json(out_path, orient="records", date_format="iso")
    logger.info(f"Wrote name stats to {out_path}")


if __name__ == "__main__":
    logging_config.configure_logging()
    analyze_names()
