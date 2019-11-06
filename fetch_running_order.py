import csv
import logging
import re
import sys
import shared
import normalize_names

import requests
from lxml import html

# time pipenv run python fetch_running_order.py 2017 && wc data/running_order_j2017_ju.tsv

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


def fetch_running_order(year, ve_or_ju):
    def leg_dist(leg):
        dist = shared.distances[ve_or_ju][year]
        return dist[leg - 1]

    def parse_team_base_name(team_name):
        p = "^(.+) ([0-9]+)$"
        matches = re.match(p, team_name)
        team_base_name = matches.group(1)
        return team_base_name

    def fetch_order(url):
        logging.info("Fetching " + url)
        page = requests.get(url, timeout=15)
        tree = html.fromstring(page.content.decode('ISO-8859-1').encode("utf-8").strip())
        rows = tree.xpath('//*[@id="site_main"]/table/tr')
        output_rows = []
        current_team_id = ""
        current_team_base_name = ""
        current_team_name = ""
        current_team_country = "NONE"
        for row in rows:
            team_id = next(iter(row.xpath('.//td[1]/text()') or []), None)
            if team_id is not None:
                team_name = next(iter(row.xpath('.//td[2]/text()')))
                current_team_country = next(iter(row.xpath('.//img/@title') or []), "NA")
                current_team_id = team_id
                team_base_name = parse_team_base_name(team_name)
                current_team_name = team_name
                current_team_base_name = team_base_name
                logging.info("Team line: " + current_team_country + " " + team_id + " " + team_name + " -> " + team_base_name)
            else:
                leg = next(iter(row.xpath('.//td[2]/text()') or []), None)
                name = next(iter(row.xpath('.//td[3]/text()') or []), None)
                if name is not None and name.strip() != ""  and name != " " and leg is not None:
                    leg = int(leg.strip())
                    name = normalize_names.normalize_name(name)
                    #logging.info(current_team_id + " " + current_team_name + " " + str(leg) + " '" + name + "'")
                    output_rows.append(
                        [current_team_id, current_team_name, current_team_base_name, current_team_country, leg,
                         leg_dist(leg), name])
        return output_rows

    out_file_name = f'data/running_order_j{year}_{ve_or_ju}.tsv'
    csv_file = open(out_file_name, 'w')

    csvwriter = csv.writer(csv_file, delimiter="\t", quoting=csv.QUOTE_ALL)
    header = ["team_id", "team", "team_base_name", "team_country", "leg", "leg_dist", "name"]

    csvwriter.writerow(header)

    url = f"https://registration.jukola.com/?kieli=en&kisa=j{year}&view=1&sarja={ve_or_ju}&jarj=kilpnro&jj=1"
    rows = fetch_order(url)
    for row in rows:
        csvwriter.writerow(row)

    csv_file.close()
    logging.info("Wrote " + out_file_name)


year = int(sys.argv[1])

fetch_running_order(year, "ve")
fetch_running_order(year, "ju")
