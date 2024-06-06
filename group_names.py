import csv
import logging
from collections import defaultdict

import numpy as np
import pandas as pd

import normalize_names
import shared


# time RACE_TYPE=ju FORECAST_YEAR=2023 poetry run python group_names.py
# To get all years use next year:
# time RACE_TYPE=ju FORECAST_YEAR=2024 poetry run python group_names.py
def _connect_teams_by_emit(runs):
    runs_by_team = defaultdict(list)
    for run in runs:
        runs_by_team[run["team"]].append(run)
    runs_by_emit = defaultdict(list)
    for run in runs:
        if "NA" not in run["emit"]:
            runs_by_emit[run["emit"]].append(run)
    # over years emit can connect teams
    teams_connected_by_emit = defaultdict(set)
    for emit, emit_runs in runs_by_emit.items():
        for emit_run in emit_runs:
            unique_teams = set(emit_run["team"] for emit_run in emit_runs)
            unique_teams.remove(emit_run["team"])
            teams_connected_by_emit[emit_run["team"]].update(unique_teams)

    def _get_connected_teams(team, found_connections):
        found_connections.add(team)
        for connection in teams_connected_by_emit[team]:
            if connection not in found_connections:
                found_connections.update(_get_connected_teams(connection, found_connections))
        return found_connections

    connected_teams_sets = set()
    for team, connected_teams in teams_connected_by_emit.items():
        connected_teams_sets.add(frozenset(_get_connected_teams(team, connected_teams)))

    # TODO this is overly complex
    connected_teams_sets = [set(fs) for fs in connected_teams_sets]
    new_connected_teams_sets = []
    for connected_teams_set in connected_teams_sets:
        new_connected_teams_set = set()
        new_connected_teams_set.update(connected_teams_set)
        for team in connected_teams_set:
            other_sets = [o for o in connected_teams_sets if team in o and o is not connected_teams_set]
            for other_set in other_sets:
                new_connected_teams_set.update(other_set)
        new_connected_teams_sets.append(new_connected_teams_set)

    # remove duplicate sets
    connected_teams_sets = set([frozenset(s) for s in new_connected_teams_sets])

    # remove unnecessary subsets that are contained in some other
    connected_teams_sets = [connections for connections in connected_teams_sets if len(connections) > 1]
    # remove overlapping subsets
    connected_teams_sets = [s for s in connected_teams_sets if
                            not any(s.issubset(o) for o in connected_teams_sets if s is not o)]

    return connected_teams_sets


def _write_individual_runs_file(grouped_runs_by_unique_name):
    records = [
        {"unique_name": unique_name, **run}
        for unique_name, runs in grouped_runs_by_unique_name.items()
        for run in runs
    ]

    # Use json_normalize to create the DataFrame
    df = pd.json_normalize(records)
    # Convert 'pace' column to numeric, coercing errors to NaN
    df['pace'] = pd.to_numeric(df['pace'], errors='coerce')
    df['year'] = df['year'].astype(int)
    df = df.sort_values(by=['unique_name', 'year', 'leg', 'team_id'])
    df['run_num'] = df.groupby('unique_name').cumcount() + 1

    # Add a temporary 'log_pace' column
    df['log_pace'] = np.log(df['pace'])
    #fy_year = shared.forecast_year()

    runner_stats_df = df.groupby('unique_name').agg(
        # TODO which one is better?
        median_pace=('pace', 'median'),
        median_log_pace=('log_pace', 'median'),
        log_stdev=('log_pace', 'std'),
        # Does not count in NAs, so DNFs and running order entries are filtered out
        num_runs=('pace', 'count'),
    ).reset_index()

    df = df.merge(runner_stats_df, on='unique_name')

    # Drop the temporary 'log_pace' column
    df.drop(columns=['log_pace'], inplace=True)

    # ve_or_ju = shared.race_type()
    # df['leg_dist'] = df.apply(lambda row: f"{row['first_name']} {row['last_name']}", axis=1)
    # df['leg_dist'] = df.apply(lambda row: shared.leg_distance(ve_or_ju, int(row['year']), row['leg']), axis=1)

    ideals = pd.read_csv(f'Jukola-terrain/ideal-paces-{shared.race_type()}.tsv', delimiter='\t')
    ideals = ideals.rename(columns={
        'leg_distance': 'leg_dist'
    })
    ideals["marking_per_km"] = ideals["marking"] / ideals["leg_dist"]
    logging.info(f"Ideals:\n{ideals.head(5).round(3)}")
    logging.info(f"Loaded ideals for {len(ideals)} legs")

    ideals = ideals[["year", "leg", "leg_dist", "terrain_coefficient", "vertical_per_km", "marking_per_km"]]
    #ideals["year"] = ideals["year"].astype(str)
    ideals.info()
    df.info()
    df = pd.merge(df, ideals, how="left", on=["year", "leg"]).reset_index()
    df.info()

    # FIRST NAME STATS
    df = _first_name_stats(df)

    output_file_path = f'data/long_runs_and_running_order_{shared.race_id_str()}.tsv'
    df.to_csv(output_file_path, sep='\t', index=False)
    logging.info(f'Wrote: {output_file_path}')


def _first_name_stats(df):
    # df = runs[['unique_name', 'pace', 'year', 'leg']].copy()
    df['first_name'] = df['unique_name'].str.split().str[0]
    # logging.info(df.head(50).to_string(index=False) )
    leg_medians_df = df.dropna(subset=['pace']).groupby(['year', 'leg']).agg(
        # leg_num_valid_runs=('pace', 'count'),
        leg_median_pace=('pace', 'median'),
    ).reset_index()
    #logging.info(leg_medians_df.head(20).to_string(index=False))
    df = pd.merge(df, leg_medians_df, how="left", on=['year', 'leg'])
    df['scaled_pace'] = df['pace'] / df['leg_median_pace']
    #logging.info(df.head(5).to_string(index=False))

    # Count the last years
    fn_counts_df = df[df['year'] >= 2014].groupby('first_name').agg(
        fn_nunique_runners=('unique_name', 'nunique'),
    ).sort_values('fn_nunique_runners').reset_index()
    logging.info(fn_counts_df)

    #fn_counts_df = fn_counts_df[fn_counts_df['fn_nunique_runners'] >= 5]
    df = pd.merge(df, fn_counts_df, how="left", on=['first_name'])
    df['fn_nunique_runners'] = df['fn_nunique_runners'].fillna(-1)
    unqualified_first_name_mask = df['fn_nunique_runners'] < 5
    df.loc[unqualified_first_name_mask, 'first_name'] = 'OTHER'

    logging.info(f'{np.mean(unqualified_first_name_mask)=}')

    # Count fn stats only for the last years
    fn_stats_df = df[df['year'] >= 2014].groupby('first_name').agg(
        fn_median_scaled_pace=('scaled_pace', 'median'),
        fn_stats_runners=('unique_name', 'nunique'),
    ).sort_values('fn_median_scaled_pace').reset_index()
    logging.info(fn_stats_df)

    df = pd.merge(df, fn_stats_df, how="left", on=['first_name'])
    logging.info(df)

    default_scaled_pace = fn_stats_df[fn_stats_df['first_name'] == 'OTHER'].head(1)['fn_median_scaled_pace'].item()
    logging.info(f'{default_scaled_pace=}')
    df['fn_scaled_pace'] = df['fn_median_scaled_pace'].fillna(default_scaled_pace)

    logging.info(df[['unique_name', 'first_name', 'pace', 'fn_scaled_pace', 'fn_median_scaled_pace']])

    df.info()
    df = df.drop(columns=['first_name', 'fn_median_scaled_pace', 'leg_median_pace', 'scaled_pace', 'fn_nunique_runners'])
    df.info()
    return df


def _group_raw_runs_to_runners(raw_runs_by_name):
    by_unique_name = {}
    for name, raw_runs in raw_runs_by_name.items():

        years_with_multiple_teams = _find_years_with_multiple_teams(raw_runs)
        has_multiple_teams_at_least_in_one_year = len(years_with_multiple_teams) > 0
        has_multiple_teams_only_in_one_year = len(years_with_multiple_teams) == 1

        connected_teams_sets = _connect_teams_by_emit(raw_runs)

        if len(years_with_multiple_teams) > 1:
            logging.info(
                f"{name} Multiple teams, ONE: {has_multiple_teams_only_in_one_year} {years_with_multiple_teams=} {connected_teams_sets=}\n{pd.DataFrame.from_dict(raw_runs)}")

        if not has_multiple_teams_at_least_in_one_year or has_multiple_teams_only_in_one_year:
            by_unique_name[name] = raw_runs
        else:
            by_team_set = defaultdict(list)
            for run in raw_runs:
                team_name = run["team"]
                team_sets = [connected_teams_set for connected_teams_set in connected_teams_sets if
                             team_name in connected_teams_set]
                if len(team_sets) == 0:
                    key_set = frozenset([team_name])
                else:
                    key_set = frozenset(team_sets[0])
                by_team_set[key_set].append(run)
            for team_set, runs_in_teams in by_team_set.items():
                # logging.info(f"{name=}, {team_set=}, {runs_in_teams=}")
                team_names = ';'.join(sorted(team_set))
                unique_name = f"{name}:{team_names}"
                by_unique_name[unique_name] = runs_in_teams
                logging.info(f"{unique_name} SPLIT\n{pd.DataFrame.from_dict(runs_in_teams)}")
    return by_unique_name


def _find_years_with_multiple_teams(raw_runs):
    qualified_runs = [run for run in raw_runs if run["pace"] != "NA"]
    # try to distinguish different people with same name from each other
    # kaima vs tuplaaja
    # namesakes vs those individuals who run multiple legs in one race
    unique_teams_by_year = defaultdict(set)
    for run in qualified_runs:
        year = run["year"]
        unique_teams_by_year[year].add(run["team"])
    years_with_multiple_teams = [year for year, teams in unique_teams_by_year.items() if len(teams) > 1]
    return years_with_multiple_teams


def _get_raw_runs_by_runner_name(ve_or_ju):
    by_name = defaultdict(list)
    for year in shared.history_years():
        country_by_team_id = shared.read_team_countries(year, ve_or_ju)

        in_file_name = f'data/results_with_dist_j{year}_{ve_or_ju}.tsv'
        with open(in_file_name) as csvfile:
            csvreader = csv.reader(csvfile, delimiter="\t")
            next(csvreader, None)  # skip the headers
            for row in csvreader:
                team_id = int(row[0])
                team_base_name = row[3].upper()
                raw_name = row[8].lower()
                normalized_name = normalize_names.normalize_name(raw_name)
                leg = int(row[5])
                emit_str = row[6]
                leg_time_str = row[7]

                if leg_time_str == "NA":
                    leg_pace = "NA"
                else:
                    leg_distance = shared.leg_distance(ve_or_ju, int(year), leg)
                    # TODO whats the sense in rounding?
                    leg_pace = round((int(leg_time_str) / 60) / leg_distance, 3)

                if len(normalized_name) <= 5:
                    if leg_pace != "NA":
                        print(
                            f"Ignoring too short name '{normalized_name}' with leg_pace {leg_pace} from {year}/{ve_or_ju} {team_id}/{leg}")
                else:
                    run = {}
                    run["name"] = normalized_name
                    run["team_id"] = team_id
                    run["team"] = team_base_name
                    run["team_country"] = "NA"
                    if team_id in country_by_team_id:
                        run["team_country"] = country_by_team_id[team_id]
                    run["year"] = year
                    run["pace"] = leg_pace
                    run["emit"] = emit_str
                    run["leg"] = leg
                    by_name[normalized_name].append(run)
            csvfile.close()
    return by_name


def _group_runs_to_runners():
    ve_or_ju = shared.race_type()

    raw_runs_by_name = _get_raw_runs_by_runner_name(ve_or_ju)

    _add_running_order(raw_runs_by_name)

    # assert len(running_order) == 0
    grouped_runs_by_unique_name = _group_raw_runs_to_runners(raw_runs_by_name)

    _write_individual_runs_file(grouped_runs_by_unique_name)


def _add_running_order(raw_runs_by_name):
    running_order = pd.read_csv(f"data/running_order_final_{shared.race_id_str()}.tsv", delimiter="\t")
    running_order["ro_orig_name"] = running_order["name"]
    # to lower case, trim spaces, remove double spaces

    running_order["name"] = running_order["name"].str.lower().str.strip().str.replace(' +', ' ')
    running_order["name"] = running_order["name"].astype(str).apply(normalize_names.normalize_name, convert_dtype=False)
    running_order.replace('', pd.NA, inplace=True)
    running_order.replace('nan', pd.NA, inplace=True)
    logging.info(f'Name missing in {sum(running_order.name.isna())} rows')
    running_order = running_order.dropna(subset="name")
    shared.log_df(running_order)
    logging.info(f"running_order: {running_order.head(1).T}")
    logging.info(f"running_order: {running_order.info()}")
    running_order["team"] = running_order["team_base_name"].str.upper()
    running_order["year"] = shared.forecast_year()
    running_order["pace"] = 'NA'
    running_order["emit"] = 'NA'
    #
    running_order = running_order[
        ['name', 'ro_orig_name', 'team_id', 'team', 'team_country', 'year', 'pace', 'emit', 'leg']]
    for running_order_rec in running_order.to_dict(orient='records'):
        logging.info(running_order_rec)
        raw_runs_by_name[running_order_rec['name']].append(running_order_rec)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s [%(threadName)s] %(funcName)s [%(levelname)s] %(message)s')
    _group_runs_to_runners()
