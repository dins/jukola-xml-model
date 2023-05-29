import collections
import csv
import logging
from collections import defaultdict

import numpy as np
import pandas as pd

import normalize_names
import shared

# RACE_TYPE=ve FORECAST_YEAR=2022 time poetry run python group_csv.py && head data/grouped_paces_ve.tsv

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s [%(process)d] %(funcName)s [%(levelname)s] %(message)s')

ve_or_ju = shared.race_type()

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
            name = row[8].lower()
            name = normalize_names.normalize_name(name)
            leg = int(row[5])
            emit_str = row[6]
            leg_time_str = row[7]

            if leg_time_str == "NA":
                leg_pace = "NA"
            else:
                leg_distance = shared.leg_distance(ve_or_ju, int(year), leg)
                leg_pace = round((int(leg_time_str) / 60) / leg_distance, 3)

            if len(name) <= 5:
                if leg_pace != "NA":
                    print(
                        f"Ignoring too short name '{name}' with leg_pace {leg_pace} from {year}/{ve_or_ju} {team_id}/{leg}")
            else:
                run = {}
                run["name"] = name
                run["team_id"] = team_id
                run["team"] = team_base_name
                run["team_country"] = "NA"
                if team_id in country_by_team_id:
                    run["team_country"] = country_by_team_id[team_id]
                run["year"] = year
                run["pace"] = leg_pace
                run["emit"] = emit_str
                run["leg"] = leg
                by_name[name].append(run)
        csvfile.close()


def open_output_file(out_file_name, column_names):
    print(f"Writing output to {out_file_name}")
    out_file = open(out_file_name, 'w')
    csvwriter = csv.writer(out_file, delimiter="\t", quoting=csv.QUOTE_ALL)
    csvwriter.writerow(column_names)
    return (out_file, csvwriter)


by_unique_name = {}


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
                found_connections.update(_get_connected_teams(connection))
        return found_connections

    connected_teams_sets = set()
    for team, connected_teams in teams_connected_by_emit.items():
        connected_teams_sets.add(frozenset(_get_connected_teams(team, connected_teams)))

    connected_teams_sets = [connections for connections in connected_teams_sets if len(connections) > 1]

    return connected_teams_sets


for name, runs in by_name.items():
    run_years = list(map(lambda run: run["year"], runs))
    unique_years = set(run_years)

    qualified_runs = [run for run in runs if run["pace"] != "NA"]

    # try to distinguish different people with same name from each other
    # kaima vs tuplaaja
    # namesakes vs those individuals who run multiple legs in one race
    unique_teams_by_year = defaultdict(set)
    for run in qualified_runs:
        year = run["year"]
        unique_teams_by_year[year].add(run["team"])

    years_with_multiple_teams = [year for year, teams in unique_teams_by_year.items() if len(teams) > 1]
    has_multiple_teams_at_least_in_one_year = len(years_with_multiple_teams) > 0
    has_multiple_teams_only_in_one_year = len(years_with_multiple_teams) == 1

    connected_teams_sets = _connect_teams_by_emit(runs)

    if len(years_with_multiple_teams) > 1:
        logging.info(
            f"{name} Multiple teams, ONE: {has_multiple_teams_only_in_one_year} {years_with_multiple_teams=} {connected_teams_sets=}\n{pd.DataFrame.from_dict(runs)}")

    if not has_multiple_teams_at_least_in_one_year or has_multiple_teams_only_in_one_year:
        by_unique_name[name] = runs
    else:
        by_team_set = defaultdict(list)
        for run in runs:
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
            team_names = ';'.join(team_set)
            unique_name = f"{name}:{team_names}"
            by_unique_name[unique_name] = runs_in_teams
            logging.info(f"{unique_name} SPLIT\n{pd.DataFrame.from_dict(runs_in_teams)}")

column_names = ["mean_team_id", "teams", "name", "num_runs", "num_valid_times", "mean_pace", "stdev", "log_stdev",
                "most_common_leg", "most_common_country", "years_and_legs"] + shared.pace_columns
(out_file, csvwriter) = open_output_file(f'data/grouped_paces_{shared.race_id_str()}.tsv', column_names)

max_years = shared.num_pace_years

for unique_name, runs in by_unique_name.items():
    team_ids = map(lambda run: run["team_id"], runs)
    teams = map(lambda run: run["team"], runs)
    joined_teams = ";".join(set(teams))
    paces = map(lambda run: run["pace"], runs)

    valid_paces = [pace for pace in paces if pace != "NA"]
    available_paces = valid_paces[:max_years] + ["NA" for x in range(max_years - len(valid_paces))]

    median_team_id = round(np.median(list(team_ids)), 1)

    if len(valid_paces) > max_years + 2:
        print(unique_name)
        print(len(runs))
        for run in runs:
            print(run)

    if len(valid_paces) > 0:
        float_paces = np.array(valid_paces).astype(float)
        # TODO weighted mean to emphasize recent values
        # CHEAP TRICK: Use median instead of mean to filter out one time accidents,
        # the std will still carry the uncertainty caused by those
        # TODO change to median_log_pace
        median_pace = round(np.median(float_paces), 4)
        stdev = round(np.std(float_paces), 4)
        log_stdev = round(np.std(np.log(float_paces)), 4)
        legs = map(lambda run: run["leg"], runs)
        most_common_leg = collections.Counter(legs).most_common()[0][0]
        countries = map(lambda run: run["team_country"], runs)
        most_common_country = collections.Counter(countries).most_common()[0][0]
        years_and_legs = map(lambda run: f'{run["year"]}.{run["leg"]}', runs)
        years_and_legs_str = " ".join(years_and_legs)
    else:
        median_pace = "NA"
        stdev = "NA"

    for run in runs:
        run["median_pace"] = str(median_pace)
        run["log_stdev"] = str(log_stdev)

    row = [median_team_id, joined_teams, unique_name, len(runs), len(valid_paces), median_pace, stdev, log_stdev,
           most_common_leg, most_common_country, years_and_legs_str] + available_paces
    csvwriter.writerow(row)

out_file.close()

# TODO add "leg_distance" column to runs.tsv
runs_file_cols = ["name", "year", "team_id", "team", "team_country", "pace", "leg", "num_runs", "median_pace",
                  "log_stdev"]
(runs_out_file, runs_csvwriter) = open_output_file(f'data/runs_{shared.race_id_str()}.tsv',
                                                   runs_file_cols)

for unique_name, runs in by_unique_name.items():
    for run in runs:
        pace = run["pace"]
        if pace != "NA":
            row = [unique_name, run["year"], run["team_id"], run["team"], run["team_country"], pace, run["leg"],
                   len(runs), run["median_pace"], run["log_stdev"]]
            runs_csvwriter.writerow(row)

runs_out_file.close()
