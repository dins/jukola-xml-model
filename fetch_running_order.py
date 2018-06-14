import csv
import logging
import re

import requests
from lxml import html

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


def leg_dist(leg):
    #dist = [12.7, 14.2, 12.3, 7.6, 7.9, 10.9, 13.8] # 2017
    dist = [11, 11.9, 12.8, 8.7, 8.7, 10.8, 15.3] # 2018
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


out_file_name = 'data/running_order_j2018_ju.tsv'
csv_file = open(out_file_name, 'w')

csvwriter = csv.writer(csv_file, delimiter="\t", quoting=csv.QUOTE_ALL)
header = ["team_id", "team", "team_base_name", "leg", "leg_dist", "name"]

csvwriter.writerow(header)

url = "https://registration.jukola.com/?kieli=en&kisa=j2018&view=1&sarja=ju&jarj=kilpnro&jj=1"
rows = fetch_order(url)
for row in rows:
    csvwriter.writerow(row)

csv_file.close()
logging.info("Wrote " + out_file_name)
