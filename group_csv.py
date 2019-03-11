import csv
import logging

import numpy as np
from collections import defaultdict

# time pipenv run python group_csv.py && head data/grouped_paces_ju.tsv

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

years = ["2018", "2017", "2016", "2015", "2014", "2013", "2012"]

# time for year in $(seq 2011 2017); do echo "$year: [$(curl http://results.jukola.com/tulokset/fi/j${year}_ju/ | grep "<td><a href='/tulokset/fi/" | grep -E "Vaihto |Maali "| cut -d " " -f 3| tr ',' '.' | tr '\n' ',')]," >> years.txt; done
distances = {2011: [11.5, 11.4, 13.6, 8.3, 8.5, 10.5, 15.6],
             2012: [12.7, 12.7, 14.1, 7.7, 8.1, 10.2, 15.1],
             2013: [12.2, 13.0, 14.4, 7.8, 7.7, 11.7, 15.1],
             2014: [10.1, 11.5, 10.2, 7.6, 7.7, 10.7, 14.0],
             2015: [13.8, 12.3, 15.8, 8.1, 8.6, 12.6, 14.6],
             2016: [10.7, 12.8, 14.1, 8.6, 8.7, 12.4, 16.5],
             2017: [12.8, 14.3, 12.3, 7.7, 7.8, 11.1, 13.8],
             2018: [11.0, 11.9, 12.7, 8.8, 8.7, 10.8, 15.1]}

by_name = {}

for year in years:
    in_file_name = 'data/csv-results_j%s_ju.tsv' % year
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
                leg_distance = distances[int(year)][leg_nro - 1]
                leg_pace = round((int(leg_time_str) / 60) / leg_distance, 3)

            if not name in by_name:
                by_name[name] = []

            run = {}
            run["name"] = name
            run["team_id"] = team_id
            run["team"] = team_base_name
            run["year"] = year
            run["pace"] = leg_pace
            run["leg_nro"] = leg_nro
            by_name[name].append(run)
            if name == "jussi kallioniemi":
                logging.info(by_name[name])
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

column_names = ["mean_team_id", "teams", "name", "num_runs", "num_valid_times", "mean_pace", "stdev", "pace_1", "pace_2",
                "pace_3", "pace_4", "pace_5", "pace_6"]
(out_file, csvwriter) = open_output_file('data/grouped_paces_ju.tsv', column_names)

for unique_name, runs in by_unique_name.items():
    team_ids = map(lambda run: run["team_id"], runs)
    teams = map(lambda run: run["team"], runs)
    joined_teams = ";".join(set(teams))
    paces = map(lambda run: run["pace"], runs)

    valid_paces = [pace for pace in paces if pace != "NA"]
    six_paces = valid_paces[:6] + ["NA" for x in range(6 - len(valid_paces))]

    mean_team_id = round(np.average(list(team_ids)), 1)

    if len(valid_paces) > 6:
        print(unique_name)
        print(len(runs))
        for run in runs:
            print(run)

    if len(valid_paces) > 0:
        float_paces = np.array(valid_paces).astype(np.float)
        mean_pace = round(np.average(float_paces), 3)
        stdev = round(np.std(float_paces), 3)
    else:
        mean_pace = "NA"
        stdev = "NA"

    row = [mean_team_id, joined_teams, unique_name, len(runs), len(valid_paces), mean_pace, stdev] + six_paces
    csvwriter.writerow(row)

out_file.close()

runs_file_cols = ["name", "year", "team_id", "team", "pace", "leg_nro", "num_runs"]
(runs_out_file, runs_csvwriter) = open_output_file('data/runs_ju.tsv', runs_file_cols)

for unique_name, runs in by_unique_name.items():
    for run in runs:
        pace = run["pace"]
        if pace != "NA":
            row = [unique_name, run["year"], run["team_id"], run["team"], pace, run["leg_nro"], len(runs)]
            runs_csvwriter.writerow(row)

runs_out_file.close()