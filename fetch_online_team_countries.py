import csv
import logging

import requests

import shared

# RACE_TYPE=ve FORECAST_YEAR=2021 time pipenv run python fetch_online_team_countries.py && wc data/team_countries_j2021_ve.tsv

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


def _fetch_and_parse_rows(url):
    logging.info("Fetching " + url)
    response = requests.get(url, timeout=15).json()
    logging.info(f"Found {response}")

    output_rows = []

    club_names_by_index = {club[0]: club[1] for club in response["Clubs"]}
    logging.info(f"club_names_by_index {club_names_by_index}")
    for competitor in response["Competitors"]:
        team_id = competitor[3]
        club_index = competitor[1]
        team_country = competitor[2]
        team_base_name = club_names_by_index[club_index]
        logging.info("Team line: " + " " + str(team_id) + " " + team_country + " " + team_base_name)
        output_rows.append([team_id, team_base_name, team_country])

    return output_rows


def fetch_team_countries(year, race_type):
    out_file_name = f'data/team_countries_j{year}_{race_type}.tsv'
    csv_file = open(out_file_name, 'w')

    csvwriter = csv.writer(csv_file, delimiter="\t", quoting=csv.QUOTE_ALL)
    header = ["team_id", "team_base_name", "team_country"]

    csvwriter.writerow(header)

    url = f"https://online.jukola.com/tulokset-new/online/online_j{year}_{race_type}_competitors.json"
    output_rows = _fetch_and_parse_rows(url)
    for row in output_rows:
        csvwriter.writerow(row)

    csv_file.close()
    logging.info("Wrote " + out_file_name)


year = shared.forecast_year()
race_type = shared.race_type()
fetch_team_countries(year, race_type)
