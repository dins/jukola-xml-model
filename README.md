# jukola-xml-model
Analyze and estimate Jukola Relay results

## Setup
```bash
poetry install
# Enable jupyter execution time measurement extension
poetry run jupyter contrib nbextension install --user
poetry run jupyter nbextension enable execute_time/ExecuteTime
```

Fetch xml files (history):

```bash
time for year in $(seq 1992 2019); do echo "YEAR $year"; time wget -P data https://results.jukola.com/tulokset/results_j${year}_ju.xml; done
```
Next manually replace `&` characters with `&amp;` (but not `&amp;` with `&&amp;`) in all xml files.

Right after the race fetch results from "online" site: ` time curl "https://online.jukola.com/tulokset/results_j2023_ve.xml" > data/results_j2023_ve.xml`

Convert xml to csv:

```bash
RACE_TYPE=ve && time for year in $(seq 1992 2019); do echo "YEAR $year RACE: $RACE_TYPE"; time poetry run python result_xml_to_csv.py $year $RACE_TYPE && head data/results_with_dist_j${year}_${RACE_TYPE}.tsv; done
time poetry run python count_names.py
```

Fetch team country and running orders:

```bash
time for year in $(seq 2009 2019); do echo "YEAR $year"; time poetry run python fetch_team_countries.py ${year} && wc data/team_countries_j${year}_ju.tsv; done
RACE_TYPE=ve FORECAST_YEAR=2022 time poetry run python fetch_online_team_countries.py && RACE_TYPE=ju FORECAST_YEAR=2022 time poetry run python fetch_online_team_countries.py 
RACE_TYPE=ve FORECAST_YEAR=2022 time poetry run python final_running_order.py && RACE_TYPE=ju FORECAST_YEAR=2022 time poetry run python final_running_order.py  # Post race running order from results
```

Then run a script.

### Run a single script 
```bash
time ./process-recent-years.sh
```

Start jupyter:
```bash
nice poetry run jupyter notebook
```


## TODO

* Speedup processing:
  * preprocess name joins (mapping history to a competitor)
  * Vectorize simulation
  * reduce categorial variables?
* Check the difference on estimates when num_years is 3 and 4 
* Move code from notebooks to .py files for better version control
* Try regularization
* replace & with &amp; in xml files, but not &amp; with &&amp;
* Post analyze darkness and mass start estimates
* Weighted means and stds
* k-fold validation
* Race and terrain specific things:
  * Estimate Jukola paces from Venla paces
  * Real time estimates for intermediaries
  * Data from year 2010 made predictions worse. Solve it by some kind of year/leg speed factor?
  * Match Venla names in Jukola
* Data clean ups:
  * Add runners from disqualified teams
  * Match people with emit number, for example those that changed lastname at some point.
* Document that we no longer use lognormal. It's now log Student T. 
* Use country specific continuous variables instead of classes. country_median for example. 
    