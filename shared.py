import csv
import logging
import os

import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

num_pace_years = 9
pace_columns = [f"pace_{i}" for i in range(1, num_pace_years + 1)]

np.random.seed(2019)

def race_type(default="ve"):
    type = os.getenv('RACE_TYPE', default)
    logging.info(f"RACE_TYPE: {type}")
    return type


def forecast_year(default=2021):
    year = os.getenv('FORECAST_YEAR', default)
    logging.info(f"FORECAST_YEAR: {year}")
    return int(year)


def race_id_str():
    return f"{race_type()}_fy_{forecast_year()}"


years = {
    "ve": ["2019", "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"],
    "ju": ["2019", "2018", "2017", "2016", "2015", "2014", "2013", "2012", "2011"]
}

# 2020 missing
all_years = [1992, 1993, 1994, 1995, 1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009,
             2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2021]


def history_years():
    all_years = years[race_type()]
    fy = str(forecast_year())
    history = list(filter(lambda year: year != fy, all_years))
    logging.info(f"history_years: {history}")
    return history


# time for year in $(seq 1992 2019); do ./parse-leg-distances.sh $year ve; done
distances = {
    "ve": {
        1992: [6.8, 6.7, 5.7, 8.6],
        1993: [6.2, 6.7, 5.6, 8.5],
        1994: [7.4, 7.4, 5.7, 8.6],
        1995: [5.8, 5.7, 7.9, 8.3],
        1996: [7.9, 7.9, 6.1, 9.1],
        1997: [6.8, 4.7, 4.7, 7.3],
        1998: [6.8, 4.7, 4.7, 7.3],
        1999: [7.0, 7.0, 6.2, 8.8],
        2000: [6.3, 6.3, 7.3, 7.7],
        2001: [6.9, 6.2, 7.1, 8.1],
        2002: [5.6, 5.3, 6.2, 8.0],
        2003: [5.0, 4.9, 5.1, 6.5],
        2004: [7.8, 4.5, 7.7, 4.4],
        2005: [5.1, 5.2, 6.1, 7.8],
        2006: [5.4, 5.9, 5.2, 7.8],
        2007: [5.7, 5.7, 6.2, 7.7],
        2008: [7.1, 7.1, 5.6, 8.1],
        2009: [7.1, 6.6, 6.0, 8.9],
        2010: [5.1, 4.4, 6.2, 7.5],
        2011: [6.9, 6.2, 5.1, 8.5],
        2012: [5.7, 5.8, 7.2, 8.4],
        2013: [8.2, 6.2, 6.2, 8.7],
        2014: [5.1, 5.0, 6.7, 7.4],
        2015: [8.0, 6.0, 6.2, 8.8],
        2016: [7.1, 6.7, 6.0, 9.1],
        2017: [6.7, 6.6, 5.8, 8.0],
        2018: [6.2, 6.2, 5.4, 7.9],
        2019: [6.0, 5.7, 7.3, 7.9],
        2020: [7.3, 5.4, 9.1, 8.5],
        2021: [7.3, 5.4, 9.1, 8.5]
    },
    "ju": {
        1992: [12.2, 12.7, 14.4, 8.4, 8.3, 10.4, 13.7],
        1993: [12.2, 14.3, 10.0, 8.3, 12.6, 8.3, 14.8],
        1994: [12.2, 12.3, 9.0, 16.4, 9.3, 8.9, 14.0],
        1995: [10.0, 11.9, 13.0, 8.3, 8.3, 10.4, 14.1],
        1996: [13.1, 13.5, 10.7, 8.9, 8.9, 12.2, 16.6],
        1997: [12.1, 11.1, 13.0, 7.3, 11.9, 6.4, 14.6],
        1998: [10.0, 10.0, 12.8, 6.8, 6.8, 11.0, 13.1],
        1999: [13.4, 13.4, 15.7, 8.8, 8.8, 11.0, 14.5],
        2000: [13.0, 13.0, 14.2, 8.4, 8.4, 11.9, 16.2],
        2001: [12.1, 12.2, 13.2, 7.4, 7.4, 9.7, 14.7],
        2002: [10.7, 10.7, 12.8, 6.3, 6.4, 10.3, 14.2],
        2003: [11.4, 11.9, 13.3, 6.6, 6.6, 10.2, 14.4],
        2004: [13.8, 13.7, 14.9, 8.5, 8.5, 12.0, 15.7],
        2005: [13.2, 11.3, 14.2, 7.5, 7.6, 9.8, 15.1],
        2006: [11.3, 11.1, 13.0, 7.7, 7.7, 9.3, 14.3],
        2007: [10.7, 10.7, 13.8, 7.6, 7.6, 10.0, 15.0],
        2008: [11.5, 12.3, 13.1, 7.8, 7.9, 9.8, 13.8],
        2009: [12.5, 12.7, 14.7, 9.5, 9.6, 11.3, 16.6],
        2010: [9.8, 10.0, 11.3, 6.9, 6.8, 9.2, 13.4],
        2011: [11.5, 11.4, 13.6, 8.3, 8.5, 10.5, 15.6],
        2012: [12.7, 12.7, 14.1, 7.7, 8.1, 10.2, 15.1],
        2013: [12.2, 13.0, 14.4, 7.8, 7.7, 11.7, 15.1],
        2014: [10.1, 11.5, 10.2, 7.6, 7.7, 10.7, 14.0],
        2015: [13.8, 12.3, 15.8, 8.1, 8.6, 12.6, 14.6],
        2016: [10.7, 12.8, 14.1, 8.6, 8.7, 12.4, 16.5],
        2017: [12.8, 14.3, 12.3, 7.7, 7.8, 11.1, 13.8],
        2018: [11.0, 11.9, 12.7, 8.8, 8.7, 10.8, 15.1],
        2019: [10.9, 10.5, 13.2, 7.3, 7.8, 11.1, 12.9],
        2020: [12.9, 12.9, 16.6, 9.1, 8.9, 11.0, 16.4],
        2021: [12.9, 12.9, 16.6, 9.1, 8.9, 11.0, 16.4]
    }
}


def leg_distance(ve_or_ju, year, leg):
    dist = distances[ve_or_ju][year]
    return dist[leg - 1]


start_timestamp = {
    "ve": {
        2018: pd.Timestamp(year=2018, month=6, day=16, hour=14, tz="Europe/Helsinki"),
        2019: pd.Timestamp(year=2019, month=6, day=15, hour=14, tz="Europe/Helsinki"),
        2021: pd.Timestamp(year=2021, month=8, day=21, hour=13, minute=45, tz="Europe/Helsinki")
    },
    "ju": {
        2018: pd.Timestamp(year=2018, month=6, day=16, hour=23, tz="Europe/Helsinki"),
        2019: pd.Timestamp(year=2019, month=6, day=15, hour=23, tz="Europe/Helsinki"),
        2021: pd.Timestamp(year=2021, month=8, day=21, hour=23, tz="Europe/Helsinki")
    }
}

changeover_closing = {
    "ve": {
        2018: pd.Timestamp(year=2018, month=6, day=16, hour=18, minute=30, tz="Europe/Helsinki"),
        2019: pd.Timestamp(year=2019, month=6, day=15, hour=18, minute=30, tz="Europe/Helsinki"),
        2021: pd.Timestamp(year=2021, month=8, day=21, hour=18, minute=15, tz="Europe/Helsinki")
    },
    "ju": {
        2018: pd.Timestamp(year=2018, month=6, day=17, hour=8, minute=45, tz="Europe/Helsinki"),
        2019: pd.Timestamp(year=2019, month=6, day=16, hour=8, minute=45, tz="Europe/Helsinki"),
        2021: pd.Timestamp(year=2021, month=8, day=22, hour=8, minute=45, tz="Europe/Helsinki")
    }
}

dark_period = {
    2018: {
        "start": pd.Timestamp(year=2018, month=6, day=16, hour=22, minute=54, tz="Europe/Helsinki"),
        "end": pd.Timestamp(year=2018, month=6, day=17, hour=3, minute=41, tz="Europe/Helsinki")
    },
    2019: {
        "start": pd.Timestamp(year=2019, month=6, day=15, hour=23, minute=4, tz="Europe/Helsinki"),
        "end": pd.Timestamp(year=2019, month=6, day=16, hour=3, minute=41, tz="Europe/Helsinki")
    },
    2021: {
        "start": pd.Timestamp(year=2021, month=8, day=21, hour=21, minute=30, tz="Europe/Helsinki"),
        "end": pd.Timestamp(year=2021, month=8, day=22, hour=5, minute=13, tz="Europe/Helsinki")
    }
}

num_legs = {
    "ve": 4,
    "ju": 7
}


def log_df(value):
    if isinstance(value, str):
        logging.info(value)
    else:
        logging.info(f"FY{forecast_year()}\n{value}")


def write_simple_text_report(reports, file_name):
    with open(f'reports/{file_name}', 'w') as outfile:
        for line in reports:
            outfile.write(f"{line}\n")


def read_team_countries(year, race_type):
    with open(f'data/team_countries_j{year}_{race_type}.tsv') as csvfile:
        csvreader = csv.reader(csvfile, delimiter="\t")
        next(csvreader, None)  # skip the headers
        country_by_team_id = {}
        for row in csvreader:
            team_id = int(row[0])
            team_country = row[2].upper()
            country_by_team_id[team_id] = team_country

        return country_by_team_id
