import logging

import numpy as np
import pandas as pd
import shared
import re
from typing import Optional


# time poetry run python ideal_paces_cleanup.py

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s [%(threadName)s] %(funcName)s [%(levelname)s] %(message)s')



def parse_distance(distance_str: str) -> Optional[float]:
    """
    Extracts and averages distance values from a string, handling comma as decimal separator.

    Args:
        distance_str: A string containing distance information (e.g., "8,9 km" or "10,7 – 10,8 km").

    Returns:
        The average distance as a float, or None if no valid distance is found.
    """
    numbers = re.findall(r'(\d+,\d+)', distance_str)
    if not numbers:
        return None
    # Convert comma to dot and then to float
    numbers = [float(num.replace(',', '.')) for num in numbers]
    average = round(sum(numbers) / len(numbers), 2)
    print(f'{average},    {numbers=}')
    return average



def _cleanup_ideal_times(race_type, marked_route):
    raw = pd.read_csv(f'Jukola-terrain/{race_type}-ideal-times.csv', delimiter=";")
    raw["year"] = raw["Vuosi"]
    cleaned = raw[["year"]].copy()  # make a copy to avoid SettingWithCopy warnings

    cleaned["leg"] = raw["Osuus"].astype(int)
    cleaned["ideal_time"] = raw["Aika"].str.extract(r'(\d+)').astype(int)
    cleaned["vertical"] = raw["Nousu"].str.extract(r'(\d+)').astype(float)

    # raw['Osuuspituus_str'] = raw['Osuuspituus'].str.extract(r'(\d+,\d+)')
    # cleaned["leg_distance"] = raw['Osuuspituus_str'].str.replace(",", ".").astype(float)
    cleaned['leg_distance'] = raw['Osuuspituus'].apply(parse_distance)
    logging.info(f"Osuuspituudet:\n{cleaned[['year', 'leg_distance']]}")

    # def _resolve_leg_distance(row):
    #    return shared.leg_distance(race_type, row["year"], row["leg"])

    # cleaned["leg_distance"] = cleaned.apply(_resolve_leg_distance, axis=1)

    cleaned["ideal_pace"] = cleaned["ideal_time"] / cleaned["leg_distance"]
    cleaned["vertical_per_km"] = cleaned["vertical"] / cleaned["leg_distance"]

    marked_route_for_race_type = marked_route[marked_route["race_type"] == race_type]
    marked_route_for_race_type = marked_route_for_race_type[["year", "marking"]]
    cleaned = pd.merge(cleaned, marked_route_for_race_type, how="left", on=["year"])

    cleaned["log_ideal_pace"] = np.log(cleaned["ideal_pace"])
    leg_means = cleaned[["leg", "log_ideal_pace"]].groupby(["leg"]).agg("mean")
    shared.log_df(leg_means)
    cleaned["leg_avg"] = leg_means["log_ideal_pace"][cleaned["leg"]].values
    cleaned["terrain_coefficient"] = cleaned["log_ideal_pace"] / cleaned["leg_avg"]

    cleaned.to_csv(f'Jukola-terrain/ideal-paces-{race_type}.tsv', sep="\t", index=False)


marked_route = pd.read_csv(f'Jukola-terrain/viitoitus.csv', delimiter=";")
marked_route["marking"] = marked_route["viitoitus"]
marked_route_cleaned = marked_route[["year", "race_type", "marking"]]
logging.info(f"marked_route_cleaned: {marked_route_cleaned}")

_cleanup_ideal_times("ve", marked_route)
_cleanup_ideal_times("ju", marked_route)
