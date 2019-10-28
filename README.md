# jukola-xml-model
Analyze and estimate Jukola Relay results

## Setup
```bash
pipenv sync
```

Fetch xml files (history) and running orders:

```bash
time for year in $(seq 1992 2018); do echo "YEAR $year"; time wget -P data https://results.jukola.com/tulokset/results_j${year}_ju.xml; done
time for year in $(seq 2009 2018); do echo "YEAR $year"; time pipenv run python fetch_team_countries.py ${year} && wc data/team_countries_j${year}_ju.tsv; done
time for year in $(seq 2012 2018); do echo "YEAR $year"; time pipenv run python fetch_running_order.py ${year} && wc data/running_order_j${year}_ju.tsv; done

```

Convert xml to csv and join years by runner name and team:

```bash
time for year in $(seq 1992 2018); do echo "YEAR $year"; time pipenv run python result_xml_to_csv.py $year ve && head data/results_with_dist_j${year}_ve.tsv; done
time pipenv run python group_csv.py ve && head data/grouped_paces_ve.tsv
time pipenv run python cluster_names.py && head data/name_pace_classes_ve.tsv
```

Start jupyter:
```bash
nice pipenv run jupyter notebook
```

Run notebooks in following order:
1. `unknown-runners.ipynb` requires `runs_ve.tsv` and plots and explores data
1. `preprocess-priors.ipynb` requires `runs_ve.tsv` and produces `gbr_*_ve.sav`
1. `estimate_paces.ipynb` requires `grouped_paces_ve.tsv` and produces `simple_preds_for_runners_with_history_14062019_ve.csv`
1. `combine-estimates-with-running-order.ipynb` requires `running_order_j2019_ve.tsv` and `simple_preds_for_runners_with_history_14062019_ve.csv` and produces `running_order_2019_with_estimates_ve.tsv`
1. `2019-relay-simulation.ipynb` requires `running_order_2019_with_estimates_ve.tsv` and produces `web-lib/for_web_ve_2019.json`
1. `post-race-analysis.ipynb` requires `web-lib/for_web_ve_2019.json` and produces `web-lib/for_web_ve_2019.json`


And navigate to `2018-lognormal-estimates` in browser.



## TODO

* Reduce number of notebooks. Put code to .py files for better version control
* Run for Venlas and Jukola at the same time
* replace & with &amp; in xml files
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
  * Clean up names, double spaces, lastname first name, 
  * Bayesian model for first name /last propability?
* Compare distributions. Is there something better than lognormal?
* Use grouped instead runs for priors. Might reduce overfitting to particular runner for example.
* Use country specific continous varriables instead of classes. country_median for example. 
    