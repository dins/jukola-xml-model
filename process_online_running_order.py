import csv
import json
import logging
import re
import sys

import pandas as pd

import normalize_names
import shared

# time poetry run python process_online_running_order.py 2023

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s [%(threadName)s] %(funcName)s [%(levelname)s] %(message)s')


def fetch_running_order(year, ve_or_ju):
    def leg_dist(leg):
        dist = shared.distances[ve_or_ju][year]
        return dist[leg - 1]

    def parse_team_base_name(team_name):
        p = "^(.+) ([0-9]+)$"
        matches = re.match(p, team_name)
        team_base_name = matches.group(1)
        return team_base_name

    # out_file_name = f"data/running_order_final_{ve_or_ju}_fy_{year}.tsv"

    # read json file
    with open(f'data/online-running-order/online_running_order_{year}_{ve_or_ju}.json') as json_file:
        data = json.load(json_file)

    teams = data[ve_or_ju.upper()]
    logging.info(f"{len(teams)=}")
    logging.info(f"{teams[0]=}")
    logging.info(f"{teams[1]=}")

    runners = []
    for team in teams:
        team_id = team[0]
        team_base_name = team[1]  # club name
        team_number = team[2]
        team_name = f"{team_base_name} {team_number}"
        team_country = team[3]
        runner_names = team[4]
        for index, runner_name in enumerate(runner_names):
            name = normalize_names.normalize_name(runner_name)
            leg = index + 1
            ld = leg_dist(leg)
            # ["team_id", "team", "team_base_name", "team_country", "leg", "leg_dist", "name"]
            runner = {
                "team_id": team_id,
                "team": team_name,
                "team_base_name": team_base_name,
                "team_country": team_country,
                "leg": leg,
                "leg_dist": ld,
                "name": name,
                "original_name": runner_name,
                "team_number": team_number
            }
            runners.append(runner)
    logging.info(f"{len(runners)=}")
    logging.info(f"{runners[0]=}")
    raw_df = pd.json_normalize(runners)
    # logging.info(f"{raw_df.info()=}")
    logging.info(f"{raw_df.head()=}")

    out_file_name = f"data/online_running_order_{ve_or_ju}_fy_{year}.tsv"
    raw_df.to_csv(out_file_name, sep="\t", index=False, quoting=csv.QUOTE_ALL)

    logging.info("Wrote " + out_file_name)

    # Write team_countries file also
    team_countries = raw_df[["team_id", "team_base_name", "team_country"]].sort_values("team_id").drop_duplicates()
    tc_file = f'data/online_team_countries_j{year}_{ve_or_ju}.tsv'
    team_countries.to_csv(tc_file, sep="\t", index=False)
    logging.info("Wrote " + tc_file)

    return out_file_name


def _summarize(running_order_file):
    df = pd.read_csv(running_order_file, delimiter="\t")
    summary = df.agg({"team_id": ["count", "nunique"], "team_country": ["count", "nunique"]})
    shared.log_df(summary)


if __name__ == "__main__":
    year = int(sys.argv[1])

    ve_file = fetch_running_order(year, "ve")
    if year != 2099:
        ju_file = fetch_running_order(year, "ju")

    _summarize(ve_file)
    if year != 2099:
        _summarize(ju_file)
