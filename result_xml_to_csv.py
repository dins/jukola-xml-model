import csv
import datetime
import time
import sys
import logging
import xml.etree.ElementTree as ET

#

year = sys.argv[1]
tree = ET.parse('data/results_j%s_ju.xml' % year)
root = tree.getroot()

# open a file for writing

out_file_name = 'data/csv-results_j%s_ju.tsv' % year
csv_file = open(out_file_name, 'w')

# create the csv writer object

csvwriter = csv.writer(csv_file, delimiter="\t", quoting=csv.QUOTE_ALL)
header = ["team-id", "placement", "team-time", "team-nro", "team-name", "leg-nro", "emit", "leg-time", "competitor-name",
          "control-times"]

csvwriter.writerow(header)


def parse_time(control_time_text):
    try:
        return time.strptime(control_time_text, '%M:%S')
    except ValueError:
        try:
            return time.strptime(control_time_text, '%H:%M:%S')
        except ValueError:
            print("Cannot parse " + control_time_text)
            raise


for team in root.iter('team'):
    for leg in team.iter('leg'):
        row = []
        row.append(team.find("teamid").text)
        row.append(team.findtext("placement", "NA"))
        row.append(team.findtext("tsecs", "NA"))
        row.append(team.find("teamnro").text)
        row.append(team.find("teamname").text)

        row.append(leg.find("legnro").text)
        row.append(leg.findtext("emit", "NA"))
        row.append(leg.findtext("tsecs", "NA"))
        row.append(leg.find("nm").text)

        control_times = []
        for control_time in leg.iter('ct'):
            struct_time = parse_time(control_time.text)
            ct_secs = datetime.timedelta(hours=struct_time.tm_hour, minutes=struct_time.tm_min,
                                         seconds=struct_time.tm_sec).total_seconds()
            control_times.append(str(int(ct_secs)))

        row.append(";".join(control_times))

        csvwriter.writerow(row)

csv_file.close()
logging.info("Wrote " + out_file_name)