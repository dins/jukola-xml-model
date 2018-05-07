import csv

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

years = ["2017", "2016", "2015", "2014", "2013", "2012"]

# time for year in $(seq 2011 2017); do echo "$year: [$(curl http://results.jukola.com/tulokset/fi/j${year}_ju/ | grep "<td><a href='/tulokset/fi/" | grep -E "Vaihto |Maali "| cut -d " " -f 3| tr ',' '.' | tr '\n' ',')]," >> years.txt; done
distances = {2011: [11.5,11.4,13.6,8.3,8.5,10.5,15.6],
             2012: [12.7,12.7,14.1,7.7,8.1,10.2,15.1],
             2013: [12.2,13.0,14.4,7.8,7.7,11.7,15.1],
             2014: [10.1,11.5,10.2,7.6,7.7,10.7,14.0],
             2015: [13.8,12.3,15.8,8.1,8.6,12.6,14.6],
             2016: [10.7,12.8,14.1,8.6,8.7,12.4,16.5],
             2017: [12.8,14.3,12.3,7.7,7.8,11.1,13.8]}

by_name = {}

for year in years:
    in_file_name = 'data/csv-results_j%s_ju.tsv' % year
    with open(in_file_name) as csvfile:
        csvreader = csv.reader(csvfile, delimiter="\t")
        next(csvreader, None)  # skip the headers
        for row in csvreader:
            team_base_name = row[3].upper()
            name = row[8].lower()
            leg_nro = int(row[5])
            leg_time_str = row[7]

            if leg_time_str == "NA":
                leg_pace = "NA"
            else:
                leg_distance = distances[int(year)][leg_nro - 1]
                leg_pace = round((int(leg_time_str) / 60) / leg_distance, 3)

            runner = {}
            if not name in by_name:
                by_name[name] = []
                runner["teams"] = []
                runner["years"] = []
                runner["means"] = []
                by_name[name].append(runner)
            else:
                def is_duplicate_name(runner):
                    return year in runner["years"]


                duplicates = list(filter(is_duplicate_name, by_name[name]))
                def has_team(runner):
                    return team_base_name in runner["teams"]


                same_team = list(filter(has_team, by_name[name]))
                if len(same_team) == 1:
                    runner = same_team[0]
                elif len(duplicates) == 0:
                    runner = by_name[name][0]
                else:
                    runner["teams"] = []
                    runner["years"] = []
                    runner["means"] = []
                    by_name[name].append(runner)

            runner["teams"].append(team_base_name)
            runner["years"].append(year)
            runner["means"].append(leg_pace)
            if name == "petri hirvonen":
                logging.info(by_name[name])
        csvfile.close()

out_file_name = 'data/grouped_paces_ju.tsv'
out_file = open(out_file_name, 'w')
csvwriter = csv.writer(out_file, delimiter="\t", quoting=csv.QUOTE_ALL)
header = ["teams", "name",  "kaimat", "pace_mean_1", "pace_mean_2", "pace_mean_3", "pace_mean_4", "pace_mean_5", "pace_mean_6"]
csvwriter.writerow(header)

for name, runners in by_name.items():
    for runner in runners:
        teams = set(runner["teams"])
        joined_teams = ";".join(teams)
        means = runner["means"]
        six_means = means[:6] + ["NA" for x in range(6 - len(means))]

        row = [joined_teams, name, len(runners)] + six_means
        csvwriter.writerow(row)

out_file.close()