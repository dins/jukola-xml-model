# Data Flow Documentation

Trace of data sources, processing scripts, and output files for the jukola-xml-model project.

---

## High-Level Pipeline (`process-recent-years.sh`)

The production pipeline runs concurrently across multiple years and race types (`ju`, `ve`) using a worker pool (`xargs -P 8`). The batch execution handles parallelization and concludes by generating a final JSON summary report.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       External Data Sources                             │
│ registration.jukola.com │ online.jukola.com │ results.jukola.com        │
└─────────────────────────┴───────────────────┴───────────────────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ Data Ingestion Scripts│
                     └───────────┬───────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ process-recent-years.sh (Parallel Batch Execution Layer)                │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │ process-one-race.sh (Individual Race Pipeline)                  │   │
│   │                                                                 │   │
│   │  1. group_names.py                                              │   │
│   │        ▼                                                        │   │
│   │  2. ngboost-norm-tuned-reviewed.ipynb (NGBoost Model)           │   │
│   │        ▼                                                        │   │
│   │  3. prepare_run_features.py (Prepare for Simulation)            │   │
│   │        ▼                                                        │   │
│   │  4. relay-simulation-2024.ipynb (Relay Simulation)              │   │
│   │        ▼                                                        │   │
│   │  5. post-race-analysis-crps-nll.ipynb (Post-Race Evaluation)    │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                │                                        │
│                                ▼                                        │
│                       json_reports.py                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Data Ingestion & Running Order

The pipeline relies on downloading and parsing data from three distinct sources before modeling begins.

### Source A: Registration Site (`fetch_running_order.py`)
- **URL**: `https://registration.jukola.com/?kisa=j{YEAR}&view=1&sarja={VE_OR_JU}&...`
- **Output**: `data/running_order_final_{VE_OR_JU}_fy_{YEAR}.tsv`
- **Derived**: `data/team_countries_j{YEAR}_{VE_OR_JU}.tsv`

### Source B: Online JSON API (`process_online_running_order.py`)
- **Input**: Pre-downloaded JSON from `data/online-running-order/`
- **Output**: `data/online_running_order_{VE_OR_JU}_fy_{YEAR}.tsv`

### Source C: Team Countries Only (`fetch_online_team_countries.py`)
- **Output**: `data/team_countries_j{YEAR}_{RACE_TYPE}.tsv`
- **Purpose**: Quick fetch of team base names and countries without full running order.

### Results with Distances (`result_xml_to_csv.py`)
- **Input**: `data/results_j{YEAR}_{VE_OR_JU}.xml`
- **Output**: `data/results_with_dist_j{YEAR}_{VE_OR_JU}.tsv`

---

## 2. Individual Race Pipeline (`process-one-race.sh`)

This script handles the sequential processing for a single race type and forecast year combination.

### 2.1 Pre-processing (`group_names.py`)
- **Input**: `data/results_with_dist_j{YEAR}_{RACE_TYPE}.tsv` (History) & `data/running_order_final_{RACE_TYPE}_fy_{YEAR}.tsv` (Current)
- **Output**: `data/long_runs_and_running_order_{RACE_TYPE}_fy_{YEAR}.tsv`
- Standardizes and groups runner names across historical records to ensure consistent tracking of individuals.
- Merges historical results with the current running order to create the foundational dataset for the model.

### 2.2 Modeling (`ngboost-norm-tuned-reviewed.ipynb`)
- Performs internal feature engineering (Box-Cox transformations, rolling history metrics).
- Trains the NGBoost model or loads tuned parameters.
- Outputs individual runner pace estimates (distributions).

### 2.3 Simulation Prep (`prepare_run_features.py`)
- **Input**: `data/long_runs_and_running_order_{RACE_TYPE}_fy_{YEAR}.tsv` & `results/ngboost-norm-tuned-reviewed/running_order_samples_v2_{race_id}.json`
- **Output**: `data/running_order_with_estimates_{race_id}.tsv`
- Merges the NGBoost pace estimates with the current running order.
- Fills in missing estimates (e.g., for unknown runners) using medians, preparing a complete dataset for the relay simulation.

### 2.4 Simulation (`relay-simulation-2024.ipynb`)
- Simulates the entire relay race using the prepared runner pace distributions.
- Accounts for start times, mass starts, and team structures.

### 2.5 Evaluation (`post-race-analysis-crps-nll.ipynb`)
- **Output**: `reports/post_race_analysis_{race_id}.txt` (or `.json`)
- Evaluates the model's performance against actual race outcomes (CRPS, NLL, and R² metrics).
- *Note: Skipped if running in `BEFORE_RACE="true"` mode.*

---

## 3. Final Reporting (`json_reports.py`)

After all concurrent race pipelines complete in `process-recent-years.sh`, this script aggregates the outputs into standardized JSON format for easy consumption by web dashboards or external tools.

---

## Terrain / Trail Data

Static data utilized during feature engineering and simulation, stored in `Jukola-terrain/`:

| File | Description |
|------|-------------|
| `ideal-paces-ju.tsv` | Ideal paces — Jukolan viesti |
| `ideal-paces-ve.tsv` | Ideal paces — Venlojen viesti |
| `terrrain-descriptions.json` | Terrain type descriptions |
