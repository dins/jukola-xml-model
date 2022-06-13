import collections
import csv
import logging
from collections import defaultdict

import numpy as np

import normalize_names
import shared

# RACE_TYPE=ve FORECAST_YEAR=2022 time pipenv run python group_csv.py && head data/grouped_paces_ve.tsv

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

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
for name, runs in by_name.items():
    run_years = list(map(lambda run: run["year"], runs))
    unique_years = set(run_years)

    if len(run_years) == len(unique_years):
        by_unique_name[name] = runs
    else:
        by_team = defaultdict(list)
        for run in runs:
            team_name = run["team"]
            by_team[team_name].append(run)
        for team_name, runs_in_team in by_team.items():
            unique_name = name + ":" + team_name
            by_unique_name[unique_name] = runs_in_team

column_names = ["mean_team_id", "teams", "name", "num_runs", "num_valid_times", "mean_pace", "stdev", "log_stdev",
                "most_common_leg",
                "most_common_country"] + shared.pace_columns
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
        float_paces = np.array(valid_paces).astype(np.float)
        # TODO weighted mean to emphasize recent values
        # CHEAP TRICK: Use median instead of mean to filter out one time accidents,
        # the std will still carry the uncertainty caused by those
        mean_pace = round(np.median(float_paces), 4)
        stdev = round(np.std(float_paces), 4)
        log_stdev = round(np.std(np.log(float_paces)), 4)
        legs = map(lambda run: run["leg"], runs)
        most_common_leg = collections.Counter(legs).most_common()[0][0]
        countries = map(lambda run: run["team_country"], runs)
        most_common_country = collections.Counter(countries).most_common()[0][0]
    else:
        mean_pace = "NA"
        stdev = "NA"

    row = [median_team_id, joined_teams, unique_name, len(runs), len(valid_paces), mean_pace, stdev, log_stdev,
           most_common_leg,
           most_common_country] + available_paces
    csvwriter.writerow(row)

out_file.close()

runs_file_cols = ["name", "year", "team_id", "team", "team_country", "pace", "leg", "num_runs"]
(runs_out_file, runs_csvwriter) = open_output_file(f'data/runs_{shared.race_id_str()}.tsv',
                                                   runs_file_cols)

for unique_name, runs in by_unique_name.items():
    for run in runs:
        pace = run["pace"]
        if pace != "NA":
            row = [unique_name, run["year"], run["team_id"], run["team"], run["team_country"], pace, run["leg"],
                   len(runs)]
            runs_csvwriter.writerow(row)

runs_out_file.close()
