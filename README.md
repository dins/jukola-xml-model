# jukola-xml-model
Analyze and estimate Jukola Relay results

## Setup
```bash
pipenv sync
```

Fetch xml files (history):

```bash
time for year in $(seq 1992 2019); do echo "YEAR $year"; time wget -P data https://results.jukola.com/tulokset/results_j${year}_ju.xml; done
```
Next manually replace `&` characters with `&amp;` in xml files, but not `&amp;` with `&&amp;` in all xml files.

Convert xml to csv:

```bash
time for year in $(seq 1992 2019); do echo "YEAR $year"; time pipenv run python result_xml_to_csv.py $year ve && head data/results_with_dist_j${year}_ve.tsv; done
time pipenv run python count_names.py
```

Fetch team country and running orders:

```bash
time for year in $(seq 2009 2019); do echo "YEAR $year"; time pipenv run python fetch_team_countries.py ${year} && wc data/team_countries_j${year}_ju.tsv; done
time for year in $(seq 2012 2019); do echo "YEAR $year"; time pipenv run python fetch_running_order.py ${year} && wc data/running_order_j${year}_ju.tsv; done
```

join years by runner name and team:

```bash
RACE_TYPE=ve FORECAST_YEAR=2019 time pipenv run python group_csv.py && RACE_TYPE=ju FORECAST_YEAR=2019 time pipenv run python group_csv.py
RACE_TYPE=ve FORECAST_YEAR=2019 time pipenv run python cluster_names.py && RACE_TYPE=ju FORECAST_YEAR=2019 time pipenv run python cluster_names.py
```

Then either run a script or start jupyter and run notebooks in browser.

### Run a single script 
```bash
RACE_TYPE=ve FORECAST_YEAR=2019 time ./preprocess-simulate-and-analyze-2019.sh && RACE_TYPE=ju FORECAST_YEAR=2019 time ./preprocess-simulate-and-analyze-2019.sh
```

### start jupyter and run notebooks in browser
Start jupyter:
```bash
nice pipenv run jupyter notebook
```

Run notebooks in following order:
1. Optional `unknown-runners.ipynb` requires `runs_ve.tsv` and plots and explores data
1. `preprocess-priors-grouped.ipynb` requires `grouped_paces_ve.tsv` and produces `gbr_*_ve.sav`
1. `2019-relay-simulation.ipynb` requires `grouped_paces_ve.tsv`, `gbr_*_ve.sav` and `running_order_j2019_ve.tsv` and produces `web-lib/for_web_ve_2019.json`
    - Produces and uses also internally `simple_preds_for_runners_with_history_14062019_ve.csv`, `running_order_2019_with_estimates_ve.tsv` 
1. `post-race-analysis.ipynb` requires `web-lib/for_web_ve_2019.json` and produces `web-lib/for_web_ve_2019.json`


## TODO

* Check the difference on estimates when num_years is 3 and 4 
* Put code from notebooks to .py files for better version control
* Tune hyperparameters with https://scikit-optimize.github.io/stable/
* After tuning fit prior models with whole data set (test set will be the year to predict)
* Try regularization
* Run for Venlas and Jukola at the same time
* replace & with &amp; in xml files, but not &amp; with &&amp;
* Post analyze darkness and mass start estimates
* Weighted means and stds
* k-fold validation
* Race and terrain specific things:
  * Estimate Jukola paces from Venla paces
  * Estimate paces from optimal times given by track designers
  * Real time estimates for intermediaries
  * Data from year 2010 made predictions worse. Solve it by some kind of year/leg speed factor?
* Data clean ups:
  * Add runners from disqualified teams
  * Match people with emit number, for example those that changed lastname at some point.
* Document that we no longer use lognormal. It's now log Student T. 
* Use country specific continous varriables instead of classes. country_median for example. 
    