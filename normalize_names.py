import json
import logging
import re
import sys


# time poetry run python normalize_names.py


def read_first_names() -> set:
    with open(f'data/name_counts.json') as json_file:
        name_counts = json.load(json_file)
        first_names = {count["name"] for count in name_counts if count["is_firstname"]}
        return first_names


first_names = read_first_names()


def is_firstname(name):
    return name.lower() in first_names


def correct_hyphen_spacing_in_names(name):
    # Remove extra spaces around hyphens
    corrected_name = re.sub(r'\s*-\s*', '-', name)
    # Ensure only one space between words
    corrected_name = re.sub(r'\s+', ' ', corrected_name)
    return corrected_name

def normalize_name(orig_name):
    name = orig_name.strip()
    name = correct_hyphen_spacing_in_names(name)

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s [%(threadName)s] %(funcName)s [%(levelname)s] %(message)s')
    orig_name = sys.argv[1]
    normalized = normalize_name(orig_name)
    logging.info(f'orig_name: "{orig_name}"  -->  normalized: "{normalized}"')
