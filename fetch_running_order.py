import csv
import logging
import re
import sys

import requests
from lxml import html

# time pipenv run python fetch_running_order.py 2017 && wc data/running_order_j2017_ju.tsv

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

distances = {
    "ve": {
        2011: [6.9, 6.2, 5.1, 8.5],
        2012: [5.7, 5.8, 7.2, 8.4],
        2013: [8.2, 6.2, 6.2, 8.7],
        2014: [5.1, 5.0, 6.7, 7.4],
        2015: [8.0, 6.0, 6.2, 8.8],
        2016: [7.1, 6.7, 6.0, 9.1],
        2017: [6.7, 6.6, 5.7, 8.0],
        2018: [6.2, 6.2, 5.4, 7.9]
    },
    "ju": {
        2011: [11.5, 11.4, 13.6, 8.3, 8.5, 10.5, 15.6],
        2012: [12.7, 12.7, 14.1, 7.7, 8.1, 10.2, 15.1],
        2013: [12.2, 13.0, 14.4, 7.8, 7.7, 11.7, 15.1],
        2014: [10.1, 11.5, 10.2, 7.6, 7.7, 10.7, 14.0],
        2015: [13.8, 12.3, 15.8, 8.1, 8.6, 12.6, 14.6],
        2016: [10.7, 12.8, 14.1, 8.6, 8.7, 12.4, 16.5],
        2017: [12.8, 14.3, 12.3, 7.7, 7.8, 11.1, 13.8],
        2018: [11.0, 11.9, 12.7, 8.8, 8.7, 10.8, 15.1]
    }
}


def fetch_running_order(year, ve_or_ju):
    def leg_dist(leg):
        dist = distances[ve_or_ju][year]
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
        for row in rows:
            team_id = next(iter(row.xpath('.//td[1]/text()') or []), None)
            if team_id is not None:
                team_name = next(iter(row.xpath('.//td[2]/text()')))
                current_team_id = team_id
                team_base_name = parse_team_base_name(team_name)
                current_team_name = team_name
                current_team_base_name = team_base_name
                logging.info("Team line: " + team_id + " " + team_name + " -> " + team_base_name)
            else:
                leg = next(iter(row.xpath('.//td[2]/text()') or []), None)
                name = next(iter(row.xpath('.//td[3]/text()') or []), None)
                if name is not None and name != " " and leg is not None:
                    leg = int(leg.strip())
                    name = name.strip()
                    logging.info(current_team_id + " " + current_team_name + " " + str(leg) + " '" + name + "'")
                    output_rows.append(
                        [current_team_id, current_team_name, current_team_base_name, leg, leg_dist(leg), name])
        return output_rows

    out_file_name = f'data/running_order_j{year}_{ve_or_ju}.tsv'
    csv_file = open(out_file_name, 'w')

    csvwriter = csv.writer(csv_file, delimiter="\t", quoting=csv.QUOTE_ALL)
    header = ["team_id", "team", "team_base_name", "leg", "leg_dist", "name"]

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
