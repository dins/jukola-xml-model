"""Drop-in adapter that converts current project files into runner_linking.Run objects."""

from __future__ import annotations

import logging
from collections import defaultdict
import numpy as np
import pandas as pd
from typing import Any, Iterable

import polars as pl

import normalize_names
import runner_linking
import shared

# time RACE_TYPE=ju FORECAST_YEAR=2024 uv run python group_names.py
# To get all years use next year:
# time RACE_TYPE=ju FORECAST_YEAR=2026 uv run python group_names.py




def _group_runs_to_runners() -> None:
    """Read result/running-order rows, link them, and write the current long output file."""
    race_type = shared.race_type()

    result_df = _read_result_runs_df(race_type)
    running_order_df = _read_running_order_runs_df(race_type)

    runs_df = pl.concat([result_df, running_order_df], how="vertical")
    logging.info(
        "Built canonical runs_df: %d rows (%d result, %d running order)",
        runs_df.height,
        result_df.height,
        running_order_df.height,
    )

    linked_runners = runner_linking.link_runs(runs=_runs_from_df(runs_df))

    grouped_runs_by_unique_name = _to_grouped_runs_by_unique_name(linked_runners)
    _write_individual_runs_file(grouped_runs_by_unique_name)


def _read_result_runs_df(race_type: str) -> pl.DataFrame:
    """Read historical result rows into one cleaned canonical runs DataFrame."""
    year_frames: list[pl.DataFrame] = []

    for year_str in shared.history_years():
        result_year = int(year_str)
        in_file_name = f"data/results_with_dist_j{result_year}_{race_type}.tsv"

        raw_df = pl.read_csv(
            in_file_name,
            separator="\t",
            schema_overrides={
                "team-id": pl.Int64,
                "team-name": pl.String,
                "competitor-name": pl.String,
                "leg-nro": pl.Int64,
                "emit": pl.String,
                "leg-time": pl.String,
            },
            infer_schema_length=0,
        )

        year_df = raw_df.select(
            team_id=pl.col("team-id").cast(pl.Int64),
            team_name=pl.col("team-name").cast(pl.String).str.to_uppercase(),
            raw_name=pl.col("competitor-name").cast(pl.String).str.to_lowercase(),
            leg=pl.col("leg-nro").cast(pl.Int64),
            emit=pl.col("emit").cast(pl.String),
            leg_time=pl.col("leg-time").cast(pl.String),
        ).with_columns(
            year=pl.lit(result_year, dtype=pl.Int64),
            race_type=pl.lit(race_type),
        )

        year_df = _attach_team_countries(year_df, result_year, race_type)
        year_frames.append(year_df)

    df = pl.concat(year_frames, how="vertical")
    df = _attach_leg_distance(df, race_type)

    df = df.with_columns(
        normalized_name=pl.col("raw_name").map_elements(
            normalize_names.normalize_name, return_dtype=pl.String
        ),
        emit_id=_normalize_optional_expr(pl.col("emit")),
        pace=pl.when(pl.col("leg_time") == "NA")
        .then(None)
        .otherwise(
            # NOTE: polars rounds by float-scaling, so ~0.1% of paces differ by
            # 0.001 min/km from the legacy Python round(x, 3). The drift is well
            # below measurement resolution and is accepted to keep this fully
            # vectorized (no per-row Python callback just for rounding).
            (pl.col("leg_time").cast(pl.Int64, strict=False) / 60 / pl.col("leg_distance")).round(3)
        )
        .cast(pl.Float64),
    )

    # Diagnostic: surface implausibly short names that still carry a pace.
    short_with_pace = df.filter(
        (pl.col("normalized_name").str.len_chars() <= 5) & pl.col("pace").is_not_null()
    )
    if short_with_pace.height:
        logging.warning(
            "Ignoring %d too short names that still have a pace:\n%s",
            short_with_pace.height,
            short_with_pace.select("normalized_name", "pace", "year", "team_id", "leg"),
        )

    df = df.filter(pl.col("normalized_name").str.len_chars() > 5)

    df = df.with_columns(
        run_id=_run_id_expr(race_type),
        source=pl.lit(runner_linking.RunSource.RESULT.value),
        original_name=pl.lit(None, dtype=pl.String),
    )

    return _select_standard_run_columns(df)


def _read_running_order_runs_df(race_type: str) -> pl.DataFrame:
    """Read forecast-year running order rows into one cleaned canonical runs DataFrame."""
    in_file_name = f"data/running_order_final_{shared.race_id_str()}.tsv"
    forecast_year = shared.forecast_year()

    df = pl.read_csv(in_file_name, separator="\t", infer_schema_length=0)

    # Keep the untouched original name for later linking diagnostics, then apply
    # the same lower/strip/collapse + normalize_name cleanup the pandas path used.
    df = df.with_columns(original_name=pl.col("name").cast(pl.String))
    df = df.with_columns(
        normalized_name=pl.col("name")
        .cast(pl.String)
        .str.to_lowercase()
        .str.strip_chars()
        .str.replace_all(r" +", " ")
    )
    df = df.with_columns(
        normalized_name=pl.col("normalized_name").map_elements(
            lambda x: normalize_names.normalize_name(str(x)) if x is not None else None,
            return_dtype=pl.String,
        )
    )
    df = df.with_columns(pl.col("normalized_name").replace(["", "nan"], [None, None]))

    missing_names = df.filter(pl.col("normalized_name").is_null()).height
    logging.info(f"Name missing in {missing_names} rows")
    df = df.drop_nulls(subset=["normalized_name"])

    if "team_country" not in df.columns:
        df = df.with_columns(team_country=pl.lit("NA"))

    df = df.with_columns(
        team_id=pl.col("team_id").cast(pl.Int64),
        leg=pl.col("leg").cast(pl.Int64),
        year=pl.lit(forecast_year, dtype=pl.Int64),
        race_type=pl.lit(race_type),
        team_name=pl.col("team_base_name").cast(pl.String).str.to_uppercase(),
        team_country=pl.col("team_country").cast(pl.String).fill_null("NA"),
        emit_id=pl.lit(None, dtype=pl.String),
        pace=pl.lit(None, dtype=pl.Float64),
        source=pl.lit(runner_linking.RunSource.RUNNING_ORDER.value),
        original_name=_normalize_optional_expr(pl.col("original_name")),
    )
    df = df.with_columns(run_id=_run_id_expr(race_type))

    return _select_standard_run_columns(df)


def _runs_from_df(runs_df: pl.DataFrame) -> list[runner_linking.Run]:
    """Materialize Run objects from a canonical runs DataFrame (one row per run)."""
    runs: list[runner_linking.Run] = []

    for row in runs_df.iter_rows(named=True):
        runs.append(
            runner_linking.Run(
                run_id=row["run_id"],
                year=int(row["year"]),
                race_type=row["race_type"],
                team_id=int(row["team_id"]),
                team_name=row["team_name"],
                team_country=row["team_country"],
                leg=int(row["leg"]),
                normalized_name=row["normalized_name"],
                emit_id=row["emit_id"],
                pace=row["pace"],
                source=runner_linking.RunSource(row["source"]),
                original_name=row["original_name"],
            )
        )

    return runs


def _attach_team_countries(
    df: pl.DataFrame, year: int, race_type: str
) -> pl.DataFrame:
    """Left-join team -> country, defaulting missing teams to 'NA'."""
    country_by_team_id = shared.read_team_countries(year, race_type)
    country_df = pl.DataFrame(
        {
            "team_id": list(country_by_team_id.keys()),
            "team_country": list(country_by_team_id.values()),
        },
        schema={"team_id": pl.Int64, "team_country": pl.String},
    )
    return df.join(country_df, on="team_id", how="left").with_columns(
        pl.col("team_country").fill_null("NA")
    )


def _attach_leg_distance(df: pl.DataFrame, race_type: str) -> pl.DataFrame:
    """Left-join leg distance, resolved once per distinct (year, leg) pair."""
    leg_distance_df = (
        df.select("year", "leg")
        .unique()
        .with_columns(
            leg_distance=pl.struct("year", "leg").map_elements(
                lambda s: float(shared.leg_distance(race_type, s["year"], s["leg"])),
                return_dtype=pl.Float64,
            )
        )
    )
    return df.join(leg_distance_df, on=["year", "leg"], how="left")


def _run_id_expr(race_type: str) -> pl.Expr:
    """Vectorized equivalent of ``{year}-{race_type}-{team_id}-{leg}``."""
    return pl.concat_str(
        [
            pl.col("year").cast(pl.String),
            pl.lit(race_type),
            pl.col("team_id").cast(pl.String),
            pl.col("leg").cast(pl.String),
        ],
        separator="-",
    ).alias("run_id")


def _normalize_optional_expr(col: pl.Expr) -> pl.Expr:
    """Vectorized equivalent of ``_optional_value``: NA-like values become null."""
    text = col.cast(pl.String).str.strip_chars()
    is_na_like = (
        text.is_null()
        | (text.str.len_chars() == 0)
        | (text.str.to_uppercase() == "NA")
        | (text.str.to_lowercase() == "nan")
    )
    return pl.when(is_na_like).then(None).otherwise(text)


def _select_standard_run_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Project onto the canonical column set with stable order and dtypes."""

    schema_common_to_history_and_running_order = pl.Schema(
        {
            "run_id": pl.String,
            "year": pl.Int64,
            "race_type": pl.String,
            "team_id": pl.Int64,
            "team_name": pl.String,
            "team_country": pl.String,
            "leg": pl.Int64,
            "normalized_name": pl.String,
            "emit_id": pl.String,
            "pace": pl.Float64,
            "source": pl.String,
            "original_name": pl.String,
        }
    )

    return df.select(
        [pl.col(name).cast(dtype) for name, dtype in schema_common_to_history_and_running_order.items()]
    )


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

    output_file_path = f"data/long_runs_and_running_order_{shared.race_id_str()}.tsv"
    df.to_csv(output_file_path, sep="\t", index=False)
    logging.info(f"Wrote: {output_file_path}")

    duplicates = df[df.duplicated(subset=["year", "team_id", "leg"], keep=False)]
    logging.info(
        f"Duplicate legs {len(duplicates)} in running order:\n{duplicates.to_string(index=False)}"
    )
    assert len(duplicates) == 0, "Duplicate legs"


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s [%(threadName)s] %(funcName)s [%(levelname)s] %(message)s",
    )
    _group_runs_to_runners()
