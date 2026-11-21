import json
import logging
import os
import sys

import count_names
import logging_config
import shared

logger = logging.getLogger(__name__)

# time uv run python normalize_names.py


def _stats_path() -> str:
    """Per-forecast-year name stats, falling back to the legacy global file."""
    per_year = f"data/name-counts/name-stats-{shared.forecast_year()}.json"
    if os.path.exists(per_year):
        return per_year
    logger.warning(
        "Per-year name stats %s not found, falling back to data/name_counts.json",
        per_year,
    )
    return "data/name_counts.json"


def read_first_names() -> set:
    with open(_stats_path()) as json_file:
        name_counts = json.load(json_file)
        first_names = {count["name"] for count in name_counts if count["is_firstname"]}
        return first_names


first_names = read_first_names()


def is_firstname(name: str) -> bool:
    return name.lower() in first_names


def normalize_name(orig_name: str) -> str:
    name = count_names.cleanup_name(orig_name)

    splits = name.split()
    if len(splits) <= 1:
        if len(name) > 0:
            logger.info(f"Ignoring possibly invalid name '{orig_name}'")
        return name

    if len(splits) == 2:
        if not is_firstname(splits[0]) and not is_firstname(splits[1]):
            logger.info(f"NOT swithcing name '{orig_name}'")
        if not is_firstname(splits[0]) and is_firstname(splits[1]):
            switched_name = f"{splits[1]} {splits[0]}"
            logger.info(f"switched name '{orig_name}' TO '{switched_name}'")
            return switched_name

    return name


if __name__ == "__main__":
    logging_config.configure_logging()
    orig_name = sys.argv[1]
    normalized = normalize_name(orig_name)
    logger.info(f'orig_name: "{orig_name}"  -->  normalized: "{normalized}"')
