import csv
import logging

import pandas as pd

import shared

# RACE_TYPE=ve FORECAST_YEAR=2022 time poetry run python final_running_order.py && head data/running_order_final_ve_fy_2022.tsv

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


def create_running_order_from_results():
    year = shared.forecast_year()
    race_type = shared.race_type()

    country_by_team_id = shared.read_team_countries(year, race_type)

    def leg_dist(leg):
        dist = shared.distances[race_type][year]
        return dist[leg - 1]

    results = pd.read_csv(f'data/results_with_dist_j{year}_{race_type}.tsv', delimiter="\t")
    final = pd.DataFrame()
    final["team_id"] = results["team-id"]
    final["team"] = [f"{name} {number}" for name, number in zip(results["team-name"], results["team-nro"])]
    final["team_base_name"] = results["team-name"]
    final["team_country"] = results["team-id"].map(country_by_team_id)
    final["leg"] = results["leg-nro"]
    final["leg_dist"] = results["leg-nro"].map(leg_dist)
    final["name"] = results["competitor-name"]

    final = final.sort_values(by=['team_id', 'leg'])
    final = final[final["name"].str.strip() != ""]
    final.to_csv(f"data/running_order_final_{shared.race_id_str()}.tsv", "\t", quoting=csv.QUOTE_ALL, index=False)

    # Write team_countries file also
    team_countries = final[["team_id", "team_base_name", "team_country"]].sort_values("team_id").drop_duplicates()
    tc_file = f'data/team_countries_j{year}_{race_type}.tsv'
    team_countries.to_csv(tc_file, sep="\t", index=False)
    logging.info("Wrote " + tc_file)


create_running_order_from_results()
