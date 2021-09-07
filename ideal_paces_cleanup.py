import logging

import pandas as pd

import shared

# time pipenv run python ideal_paces_cleanup.py

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


def _cleanup_ideal_times(race_type, marked_route):
    raw = pd.read_csv(f'Jukola-terrain/{race_type}-ideal-times.csv', delimiter=";")
    raw["year"] = raw["Vuosi"]
    cleaned = raw[["year"]].copy()  # make a copy to avoid SettingWithCopy warnings

    cleaned["leg"] = raw["Osuus"].astype(int)
    cleaned["ideal_time"] = raw["Aika"].str.extract('(\d+)').astype(int)
    cleaned["vertical"] = raw["Nousu"].str.extract('(\d+)')

    def _resolve_leg_distance(row):
        return shared.leg_distance(race_type, row["year"], row["leg"])

    cleaned["leg_distance"] = cleaned.apply(_resolve_leg_distance, axis=1)
    cleaned["ideal_pace"] = cleaned["ideal_time"] / cleaned["leg_distance"]

    marked_route_for_race_type = marked_route[marked_route["race_type"] == race_type]
    marked_route_for_race_type = marked_route_for_race_type[["year", "marking"]]
    cleaned = pd.merge(cleaned, marked_route_for_race_type, how="left", on=["year"])
    cleaned.to_csv(f'Jukola-terrain/ideal-paces-{race_type}.tsv', sep="\t", index=False)


marked_route = pd.read_csv(f'Jukola-terrain/viitoitus.csv', delimiter=";")
marked_route["marking"] = marked_route["viitoitus"]
marked_route_cleaned = marked_route[["year", "race_type", "marking"]]
logging.info(f"marked_route_cleaned: {marked_route_cleaned}")

_cleanup_ideal_times("ve", marked_route)
_cleanup_ideal_times("ju", marked_route)
