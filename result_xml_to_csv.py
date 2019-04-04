import csv
import datetime
import logging
import sys
import numpy as np
import math
import time
import xml.etree.ElementTree as ET

# time pipenv run python result_xml_to_csv.py 2017 ve

# time for year in $(seq 2012 2018); do echo "YEAR $year"; time pipenv run python result_xml_to_csv.py $year ve && head data/results_with_dist_j${year}_ve.tsv; done

# wget -P data http://online.jukola.com/tulokset/results_j2018_ju.xml

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

year = sys.argv[1]
ve_or_ju = sys.argv[2]
input_file = f'data/results_j{year}_{ve_or_ju}.xml'
logging.info("Reading " + input_file)
tree = ET.parse(input_file)
root = tree.getroot()

# open a file for writing

out_file_name = f'data/results_with_dist_j{year}_{ve_or_ju}.tsv'
csv_file = open(out_file_name, 'w')

# create the csv writer object

csvwriter = csv.writer(csv_file, delimiter="\t", quoting=csv.QUOTE_ALL)
header = ["team-id", "placement", "team-time", "team-name", "team-nro", "leg-nro", "emit", "leg-time",
          "competitor-name", "weighted_avg_pace", "weighted_pace_std", "disqualified"]

csvwriter.writerow(header)


def parse_time(control_time_text):
    try:
        return time.strptime(control_time_text, '%S')
    except ValueError:
        try:
            return time.strptime(control_time_text, '%M:%S')
        except ValueError:
            try:
                return time.strptime(control_time_text, '%H:%M:%S')
            except ValueError:
                print("Cannot parse " + control_time_text)
                raise

def weighted_avg_and_std(values, weights):
    """
    Return the weighted average and standard deviation.

    values, weights -- Numpy ndarrays with the same shape.
    """
    average = np.average(values, weights=weights)
    # Fast and numerically precise:
    variance = np.average((values-average)**2, weights=weights)
    return (average, math.sqrt(variance))


for team in root.iter('team'):
    for leg in team.iter('leg'):
        row = []
        row.append(team.find("teamid").text)
        row.append(team.findtext("placement", "NA"))
        row.append(team.findtext("tsecs", "NA"))
        row.append(team.find("teamname").text)
        row.append(team.find("teamnro").text)

        row.append(leg.find("legnro").text)
        row.append(leg.findtext("emit", "NA"))

        # if no tsecs (=runner or team disqualified?)
        default_leg_time = "NA"
        row.append(leg.findtext("tsecs", default_leg_time))

        competitor_name = leg.find("nm").text
        row.append(competitor_name)

        control_paces = []
        control_distances = []
        disqualified = False
        for control in leg.iter('control'):
            cd_text = control.find("cd").text
            if cd_text == "-" or cd_text is None:
                disqualified = True # Top teams have these but are not disqualified

            else:
                struct_time = parse_time(cd_text)
                cd_secs = int(datetime.timedelta(hours=struct_time.tm_hour, minutes=struct_time.tm_min,
                                                 seconds=struct_time.tm_sec).total_seconds())
                distance_element = control.find("cl")
                if distance_element is not None:
                    distance_meters = int(distance_element.text)
                    control_pace = (cd_secs / 60.0) / (distance_meters / 1000.0)

                    control_paces.append(control_pace)
                    control_distances.append(distance_meters)

        if len(control_paces) > 0:
            # TODO use log values
            (weighted_avg_pace, weighted_pace_std) = weighted_avg_and_std(control_paces, control_distances)
            #logging.info(f"{weighted_avg_pace} {weighted_pace_std}")
        else:
            (weighted_avg_pace, weighted_pace_std) = ("NA", "NA")
            #logging.info(control_paces)
            #logging.info(control_distances)
            #logging.info(f"{competitor_name}: {weighted_avg_pace} {weighted_pace_std}")
        row.append(weighted_avg_pace)
        row.append(weighted_pace_std)
        row.append(disqualified)
        csvwriter.writerow(row)

csv_file.close()
logging.info("Wrote " + out_file_name)
