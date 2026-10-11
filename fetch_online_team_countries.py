import csv

import requests

import logging_config
import shared

logger = logging_config.configure_logging(__name__)

# time RACE_TYPE=ve FORECAST_YEAR=2022 uv run python fetch_online_team_countries.py && wc data/team_countries_j2022_ve.tsv


def _fetch_and_parse_rows(url):
    logger.info("Fetching " + url)
    response = requests.get(url, timeout=15).json()
    logger.info(f"Found {response}")

    output_rows = []

    club_names_by_index = {club[0]: club[1] for club in response["Clubs"]}
    logger.info(f"club_names_by_index {club_names_by_index}")
    for competitor in response["Competitors"]:
        team_id = competitor[3]
        club_index = competitor[1]
        team_country = competitor[2]
        assert len(team_country) == 3, f"Unexpected country name length for '{team_country}'"
        team_base_name = club_names_by_index[club_index]
        logger.info(
            "Team line: "
            + " "
            + str(team_id)
            + " "
            + team_country
            + " "
            + team_base_name
        )
        output_rows.append([team_id, team_base_name, team_country])

    return output_rows


def fetch_team_countries(year, race_type):
    out_file_name = f"data/team_countries_j{year}_{race_type}.tsv"
    with open(out_file_name, "w") as csv_file:
        csvwriter = csv.writer(csv_file, delimiter="\t", quoting=csv.QUOTE_ALL)
        header = ["team_id", "team_base_name", "team_country"]

        csvwriter.writerow(header)

        url = f"https://online.jukola.com/tulokset-new/online/online_j{year}_{race_type}_competitors.json"
        output_rows = _fetch_and_parse_rows(url)
        for row in output_rows:
            csvwriter.writerow(row)

    logger.info("Wrote " + out_file_name)


year = shared.forecast_year()
race_type = shared.race_type()
fetch_team_countries(year, race_type)
