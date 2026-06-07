"""Drop-in adapter that converts current project files into runner_linking.Run objects."""

from __future__ import annotations

import csv
import logging
from collections import defaultdict
from typing import Any, Iterable

import numpy as np
import pandas as pd

import normalize_names
import runner_linking
import shared

# time RACE_TYPE=ju FORECAST_YEAR=2024 uv run python group_names.py
# To get all years use next year:
# time RACE_TYPE=ju FORECAST_YEAR=2026 uv run python group_names.py


def _group_runs_to_runners() -> None:
    """Read result/running-order rows, link them, and write the current long output file."""
    race_type = shared.race_type()
    result_runs = _read_result_runs(race_type)
    running_order_runs = _read_running_order_runs(race_type)

    linked_runners = runner_linking.link_runs(
        runs=result_runs + running_order_runs,
    )

    grouped_runs_by_unique_name = _to_grouped_runs_by_unique_name(linked_runners)
    _write_individual_runs_file(grouped_runs_by_unique_name)


def _read_result_runs(race_type: str) -> list[runner_linking.Run]:
    """Read historical result rows and convert them into canonical Run objects."""
    runs: list[runner_linking.Run] = []

    for year in shared.history_years():
        result_year = int(year)
        country_by_team_id = shared.read_team_countries(result_year, race_type)
        in_file_name = f"data/results_with_dist_j{result_year}_{race_type}.tsv"

        with open(in_file_name) as csvfile:
            csvreader = csv.reader(csvfile, delimiter="\t")
            next(csvreader, None)

            for row in csvreader:
                team_id = int(row[0])
                team_base_name = row[3].upper()
                raw_name = row[8].lower()
                normalized_name = normalize_names.normalize_name(raw_name)
                leg = int(row[5])
                emit_id = _optional_value(row[6])
                leg_time_str = row[7]

                if leg_time_str == "NA":
                    leg_pace = None
                else:
                    leg_distance = shared.leg_distance(race_type, result_year, leg)
                    leg_pace = round((int(leg_time_str) / 60) / leg_distance, 3)

                if len(normalized_name) <= 5:
                    if leg_pace is not None:
                        print(
                            f"Ignoring too short name '{normalized_name}' with leg_pace {leg_pace} "
                            f"from {result_year}/{race_type} {team_id}/{leg}"
                        )
                    continue

                runs.append(
                    runner_linking.Run(
                        run_id=_make_run_id(result_year, race_type, team_id, leg),
                        year=result_year,
                        race_type=race_type,
                        team_id=team_id,
                        team_name=team_base_name,
                        team_country=country_by_team_id.get(team_id, "NA"),
                        leg=leg,
                        normalized_name=normalized_name,
                        emit_id=emit_id,
                        pace=leg_pace,
                        source=runner_linking.RunSource.RESULT,
                    )
                )

    return runs


def _read_running_order_runs(race_type: str) -> list[runner_linking.Run]:
    """Read forecast-year running order rows and convert them into Run objects."""
    running_order = pd.read_csv(
        f"data/running_order_final_{shared.race_id_str()}.tsv", delimiter="\t"
    )
    running_order["ro_orig_name"] = running_order["name"]

    running_order["name"] = (
        running_order["name"]
        .str.lower()
        .str.strip()
        .str.replace(r" +", " ", regex=True)
    )
    running_order["name"] = (
        running_order["name"].astype(str).apply(normalize_names.normalize_name)
    )

    running_order.replace("", pd.NA, inplace=True)
    running_order.replace("nan", pd.NA, inplace=True)

    logging.info(f"Name missing in {sum(running_order.name.isna())} rows")

    running_order = running_order.dropna(subset="name")
    shared.log_df(running_order)
    logging.info(f"running_order: {running_order.head(1).T}")
    logging.info(f"running_order: {running_order.info()}")

    running_order["team"] = running_order["team_base_name"].str.upper()
    running_order["year"] = shared.forecast_year()
    running_order["pace"] = "NA"
    running_order["emit"] = "NA"

    running_order = running_order[
        [
            "name",
            "ro_orig_name",
            "team_id",
            "team",
            "team_country",
            "year",
            "pace",
            "emit",
            "leg",
        ]
    ]

    runs: list[runner_linking.Run] = []

    for running_order_rec in running_order.to_dict(orient="records"):
        logging.info(running_order_rec)

        forecast_year = int(running_order_rec["year"])
        team_id = int(running_order_rec["team_id"])
        leg = int(running_order_rec["leg"])

        runs.append(
            runner_linking.Run(
                run_id=_make_run_id(forecast_year, race_type, team_id, leg),
                year=forecast_year,
                race_type=race_type,
                team_id=team_id,
                team_name=str(running_order_rec["team"]),
                team_country=str(running_order_rec.get("team_country", "NA")),
                leg=leg,
                normalized_name=str(running_order_rec["name"]),
                emit_id=None,
                pace=None,
                source=runner_linking.RunSource.RUNNING_ORDER,
                original_name=_optional_value(running_order_rec.get("ro_orig_name")),
            )
        )

    return runs


def _to_grouped_runs_by_unique_name(
    linked_runners: Iterable[runner_linking.LinkedRunner],
) -> dict[str, list[dict[str, Any]]]:
    """Convert LinkedRunner objects back to the dict shape used by the old writer."""
    grouped_runs_by_unique_name: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for linked_runner in linked_runners:
        for run in linked_runner.runs:
            run_record: dict[str, Any] = {
                "run_id": run.run_id,
                "linked_runner_id": linked_runner.linked_runner_id,
                "name": run.normalized_name,
                "team_id": run.team_id,
                "team": run.team_name,
                "team_country": run.team_country,
                "year": run.year,
                "pace": "NA" if run.pace is None else run.pace,
                "emit": "NA" if run.emit_id is None else run.emit_id,
                "leg": run.leg,
            }

            if run.original_name is not None:
                run_record["ro_orig_name"] = run.original_name

            grouped_runs_by_unique_name[linked_runner.unique_name].append(run_record)

    return dict(grouped_runs_by_unique_name)


def _write_individual_runs_file(
    grouped_runs_by_unique_name: dict[str, list[dict[str, Any]]],
) -> None:
    """Write the same long run-history TSV format as the current group_names.py path."""
    records = [
        {"unique_name": unique_name, **run}
        for unique_name, runs in grouped_runs_by_unique_name.items()
        for run in runs
    ]

    df = pd.json_normalize(records)
    df["pace"] = pd.to_numeric(df["pace"], errors="coerce")
    df["year"] = df["year"].astype(int)
    df = df.sort_values(by=["unique_name", "year", "leg", "team_id"])
    df["run_num"] = df.groupby("unique_name").cumcount() + 1

    df["log_pace"] = np.log(df["pace"])

    runner_stats_df = (
        df.groupby("unique_name")
        .agg(
            median_pace=("pace", "median"),
            median_log_pace=("log_pace", "median"),
            log_stdev=("log_pace", "std"),
            num_runs=("pace", "count"),
        )
        .reset_index()
    )

    df = df.merge(runner_stats_df, on="unique_name")
    df.drop(columns=["log_pace"], inplace=True)

    ideals = pd.read_csv(
        f"Jukola-terrain/ideal-paces-{shared.race_type()}.tsv", delimiter="\t"
    )
    ideals = ideals.rename(columns={"leg_distance": "leg_dist"})
    ideals["marking_per_km"] = ideals["marking"] / ideals["leg_dist"]

    logging.info(f"Ideals:\n{ideals.head(5).round(3)}")
    logging.info(f"Loaded ideals for {len(ideals)} legs")

    ideals = ideals[
        [
            "year",
            "leg",
            "leg_dist",
            "terrain_coefficient",
            "vertical_per_km",
            "marking_per_km",
        ]
    ]

    ideals.info()
    df.info()

    df = pd.merge(df, ideals, how="left", on=["year", "leg"]).reset_index()

    df.info()

    df = _first_name_stats(df)

    output_file_path = f"data/long_runs_and_running_order_{shared.race_id_str()}.tsv"
    df.to_csv(output_file_path, sep="\t", index=False)
    logging.info(f"Wrote: {output_file_path}")

    duplicates = df[df.duplicated(subset=["year", "team_id", "leg"], keep=False)]
    logging.info(
        f"Duplicate legs {len(duplicates)} in running order:\n{duplicates.to_string(index=False)}"
    )
    assert len(duplicates) == 0, "Duplicate legs"


def _first_name_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Add first-name-based fallback pace features used by the existing forecast path."""
    df["first_name"] = df["unique_name"].str.split().str[0]

    leg_medians_df = (
        df.dropna(subset=["pace"])
        .groupby(["year", "leg"])
        .agg(
            leg_median_pace=("pace", "median"),
        )
        .reset_index()
    )

    df = pd.merge(df, leg_medians_df, how="left", on=["year", "leg"])
    df["scaled_pace"] = df["pace"] / df["leg_median_pace"]

    fn_counts_df = (
        df[df["year"] >= 2014]
        .groupby("first_name")
        .agg(
            fn_nunique_runners=("unique_name", "nunique"),
        )
        .sort_values("fn_nunique_runners")
        .reset_index()
    )

    logging.info(fn_counts_df)

    df = pd.merge(df, fn_counts_df, how="left", on=["first_name"])
    df["fn_nunique_runners"] = df["fn_nunique_runners"].fillna(-1)

    unqualified_first_name_mask = df["fn_nunique_runners"] < 5
    df.loc[unqualified_first_name_mask, "first_name"] = "OTHER"
    logging.info(f"{np.mean(unqualified_first_name_mask)=}")

    fn_stats_df = (
        df[df["year"] >= 2014]
        .groupby("first_name")
        .agg(
            fn_median_scaled_pace=("scaled_pace", "median"),
            fn_stats_runners=("unique_name", "nunique"),
        )
        .sort_values("fn_median_scaled_pace")
        .reset_index()
    )

    logging.info(fn_stats_df)

    df = pd.merge(df, fn_stats_df, how="left", on=["first_name"])
    logging.info(df)

    default_scaled_pace = (
        fn_stats_df[fn_stats_df["first_name"] == "OTHER"]
        .head(1)["fn_median_scaled_pace"]
        .item()
    )
    logging.info(f"{default_scaled_pace=}")

    df["fn_scaled_pace"] = df["fn_median_scaled_pace"].fillna(default_scaled_pace)
    logging.info(
        df[
            [
                "unique_name",
                "first_name",
                "pace",
                "fn_scaled_pace",
                "fn_median_scaled_pace",
            ]
        ]
    )

    df.info()

    df = df.drop(
        columns=[
            "first_name",
            "fn_median_scaled_pace",
            "leg_median_pace",
            "scaled_pace",
            "fn_nunique_runners",
        ]
    )

    df.info()

    return df


def _make_run_id(year: int, race_type: str, team_id: int, leg: int) -> str:
    """Build the stable run id used as the linking graph node id."""
    return f"{year}-{race_type}-{team_id}-{leg}"


def _optional_value(value: Any) -> str | None:
    """Normalize project NA-like values to None."""
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass

    text = str(value).strip()

    if text == "" or text.upper() == "NA" or text.lower() == "nan":
        return None

    return text


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s [%(threadName)s] %(funcName)s [%(levelname)s] %(message)s",
    )
    _group_runs_to_runners()
