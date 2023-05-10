import json
import logging

# time poetry run python normalize_names.py

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s [%(process)d] %(funcName)s [%(levelname)s] %(message)s')


def read_first_names():
    with open(f'data/name_counts.json') as json_file:
        name_counts = json.load(json_file)
        first_names = [count["name"] for count in name_counts if count["is_firstname"]]
        return first_names


first_names = read_first_names()


def is_firstname(name):
    return name.lower() in first_names


def normalize_name(orig_name):
    name = orig_name.strip()
    if " - " in name:
        logging.info(f"Trimming spaces around DASH '{orig_name}'")
        name = name.replace(" - ", "-")

    if "  " in name:
        logging.info(f"Trimming DOUBLE or multiple spaces '{orig_name}'")
        name = ' '.join(name.split())

    if "|" in name:
        logging.info(f"Trimming pipes '{orig_name}'")
        name = name.replace("|", "")

    splits = name.split()
    if len(splits) <= 1:
        if len(name) > 0:
            logging.info(f"Ignoring possibly invalid name '{orig_name}'")
        return name

    if len(splits) == 2:
        if not is_firstname(splits[0]) and not is_firstname(splits[1]):
            logging.info(f"NOT swithcing name '{orig_name}'")
        if not is_firstname(splits[0]) and is_firstname(splits[1]):
            swithced_name = f"{splits[1]} {splits[0]}"
            logging.info(f"swithced name '{orig_name}' TO '{swithced_name}'")
            return swithced_name

    return name
