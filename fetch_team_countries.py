import csv
import logging
import sys

import requests
from lxml import html

# time poetry run python fetch_team_countries.py 2022 && wc data/team_countries_j2022_ju.tsv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s [%(threadName)s] %(funcName)s [%(levelname)s] %(message)s')


def fetch_team_country(year, ve_or_ju):
    def fetch_order(url):
        logging.info("Fetching " + url)
        page = requests.get(url, timeout=15)
        #tree = html.fromstring(page.content.decode('ISO-8859-1').encode("utf-8").strip())
        tree = html.fromstring(page.content.decode('utf-8').strip())
        rows = tree.xpath('//*[@id="site_main"]/table/table/tr')
        logging.info(f"Found {len(rows)} rows")
        assert len(rows) > 100
        output_rows = []
        for row in rows:
            if (len(row.xpath('td[1]')) > 0):
                team_id = next(iter(row.xpath('.//td[1]/text()') or []), None)
                team_base_name = next(iter(row.xpath('.//td[2]/a/text()') or []), "NA")
                team_country_name = next(iter(row.xpath('.//td[3]/img/@title') or []), "NA")

                # 1. Get the full URL:
                img_url = next(iter(row.xpath('.//td[3]/img/@src') or []), None)

                if img_url:
                    # 2. Take everything after the last slash, then strip “.png”
                    filename = img_url.rsplit('/', 1)[-1]       # e.g. "FIN.png"
                    team_country_code = filename.rsplit('.', 1)[0]  # -> "FIN"
                else:
                    team_country_code = "NA"

                logging.info(f"Team line: {team_id} {team_country_code} {team_country_name} {team_base_name} ")
                output_rows.append([team_id, team_base_name, team_country_code, team_country_name])

        return output_rows

    out_file_name = f'data/team_countries_j{year}_{ve_or_ju}.tsv'
    csv_file = open(out_file_name, 'w')

    csvwriter = csv.writer(csv_file, delimiter="\t", quoting=csv.QUOTE_ALL)
    header = ["team_id", "team_base_name", "team_country", "team_country_name"]

    csvwriter.writerow(header)

    url = f"https://results.jukola.com/tulokset/fi/j{year}_{ve_or_ju}/{ve_or_ju}/kilpailijat/?eka=kaikki"
    # url = f"https://registration.jukola.com/?kieli=en&kisa=j{year}&view=1&sarja={ve_or_ju}&jarj=kilpnro&jj=1"
    #        https://registration.jukola.com/?kieli=fi&kisa=j2022&view=1&sarja=ve&jarj=kilpnro&jj=1
    #url = f"https://registration.jukola.com/?kieli=fi&kisa=j{year}&view=1&sarja={ve_or_ju}&jarj=kilpnro"
    output_rows = fetch_order(url)
    for row in output_rows:
        csvwriter.writerow(row)

    csv_file.close()
    logging.info("Wrote " + out_file_name)


year = int(sys.argv[1])

fetch_team_country(year, "ve")
fetch_team_country(year, "ju")
