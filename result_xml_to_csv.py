import csv
import datetime
import logging
import sys
import time
import xml.etree.ElementTree as ET

# time pipenv run python result_xml_to_csv.py 2017

# time for year in $(seq 2011 2017); do echo "YEAR $year"; time wget -P data http://online.jukola.com/tulokset/results_j${year}_ju.xml; done
# time for year in $(seq 2012 2017); do echo "YEAR $year"; time pipenv run python result_xml_to_csv.py $year && head data/csv-results_j${year}_ju.tsv; done

# wget -P data http://online.jukola.com/tulokset/results_j2018_ju.xml

year = sys.argv[1]
tree = ET.parse('data/results_j%s_ju.xml' % year)
root = tree.getroot()

# open a file for writing

out_file_name = 'data/csv-results_j%s_ju.tsv' % year
csv_file = open(out_file_name, 'w')

# create the csv writer object

csvwriter = csv.writer(csv_file, delimiter="\t", quoting=csv.QUOTE_ALL)
header = ["team-id", "placement", "team-time", "team-name", "team-nro", "leg-nro", "emit", "leg-time",
          "competitor-name", "control-times"]

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
        row.append(team.find("teamname").text)
        row.append(team.find("teamnro").text)

        row.append(leg.find("legnro").text)
        row.append(leg.findtext("emit", "NA"))

        control_times = []
        for control_time in leg.iter('ct'):
            struct_time = parse_time(control_time.text)
            ct_secs = datetime.timedelta(hours=struct_time.tm_hour, minutes=struct_time.tm_min,
                                         seconds=struct_time.tm_sec).total_seconds()
            control_times.append(str(int(ct_secs)))

        default_leg_time = "NA"
        if len(control_times) > 0:
            # FIXME this is sometimes ok, sometimes also totally wrong.
            default_leg_time = control_times[-1] # Use last control as default if no tsecs (=disqualified?)
        row.append(leg.findtext("tsecs", default_leg_time))

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
