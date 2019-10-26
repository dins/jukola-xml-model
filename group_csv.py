import collections
import csv
import logging
import sys
from collections import defaultdict
import shared
import numpy as np

# time pipenv run python group_csv.py ve && head data/grouped_paces_ve.tsv

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

ve_or_ju = sys.argv[1]

# time for year in $(seq 2011 2017); do echo "$year: [$(curl http://results.jukola.com/tulokset/fi/j${year}_ju/ | grep "<td><a href='/tulokset/fi/" | grep -E "Vaihto |Maali "| cut -d " " -f 3| tr ',' '.' | tr '\n' ',')]," >> years.txt; done

by_name = defaultdict(list)


def read_team_countries(year, ve_or_ju):
    with open(f'data/team_countries_j{year}_{ve_or_ju}.tsv') as csvfile:
        csvreader = csv.reader(csvfile, delimiter="\t")
        next(csvreader, None)  # skip the headers
        country_by_team_id = {}
        for row in csvreader:
            team_id = int(row[0])
            team_country = row[2].upper()
            country_by_team_id[team_id] = team_country

        return country_by_team_id


for year in shared.years[ve_or_ju]:
    country_by_team_id = read_team_countries(year, ve_or_ju)

    in_file_name = f'data/results_with_dist_j{year}_{ve_or_ju}.tsv'
    with open(in_file_name) as csvfile:
        csvreader = csv.reader(csvfile, delimiter="\t")
        next(csvreader, None)  # skip the headers
        for row in csvreader:
            team_id = int(row[0])
            team_base_name = row[3].upper()
            name = row[8].lower()
            leg_nro = int(row[5])
            leg_time_str = row[7]

            if leg_time_str == "NA":
                leg_pace = "NA"
            else:
                leg_distance = shared.leg_distance(ve_or_ju, int(year), leg_nro)
                leg_pace = round((int(leg_time_str) / 60) / leg_distance, 3)

            run = {}
            run["name"] = name
            run["team_id"] = team_id
            run["team"] = team_base_name
            run["team_country"] = "NA"
            if team_id in country_by_team_id:
                run["team_country"] = country_by_team_id[team_id]
            run["year"] = year
            run["pace"] = leg_pace
            run["leg_nro"] = leg_nro
            if len(name) > 3:
                by_name[name].append(run)
            else:
                if leg_pace != "NA":
                    print(f"Ignoring too short name '{name}' and run {run}")
        csvfile.close()


def open_output_file(out_file_name, column_names):
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

column_names = ["mean_team_id", "teams", "name", "num_runs", "num_valid_times", "mean_pace", "stdev", "log_stdev", "most_common_leg",
                "most_common_country"] + shared.pace_columns
(out_file, csvwriter) = open_output_file(f'data/grouped_paces_{ve_or_ju}.tsv', column_names)

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
        mean_pace = round(np.average(float_paces), 4)
        stdev = round(np.std(float_paces), 4)
        log_stdev = round(np.std(np.log(float_paces)), 4)
        legs = map(lambda run: run["leg_nro"], runs)
        most_common_leg = collections.Counter(legs).most_common()[0][0]
        countries = map(lambda run: run["team_country"], runs)
        most_common_country = collections.Counter(countries).most_common()[0][0]
    else:
        mean_pace = "NA"
        stdev = "NA"

    row = [median_team_id, joined_teams, unique_name, len(runs), len(valid_paces), mean_pace, stdev, log_stdev, most_common_leg,
           most_common_country] + available_paces
    csvwriter.writerow(row)

out_file.close()

runs_file_cols = ["name", "year", "team_id", "team", "team_country", "pace", "leg_nro", "num_runs"]
(runs_out_file, runs_csvwriter) = open_output_file(f'data/runs_{ve_or_ju}.tsv', runs_file_cols)

for unique_name, runs in by_unique_name.items():
    for run in runs:
        pace = run["pace"]
        if pace != "NA":
            row = [unique_name, run["year"], run["team_id"], run["team"], run["team_country"], pace, run["leg_nro"],
                   len(runs)]
            runs_csvwriter.writerow(row)

runs_out_file.close()
