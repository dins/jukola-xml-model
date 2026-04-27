# Data Flow Documentation

Trace of data sources, processing scripts, and output files for the jukola-xml-model project.

---

## High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    External Data Sources                                 │
│  registration.jukola.com  │  online.jukola.com  │  results.jukola.com│
└────────────────────┬─────────────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
fetch_running_order.py  process_online_running_order.py  fetch_online_team_countries.py
        │            │                            │
        ▼            ▼                            ▼
running_order_final_*.tsv  online_running_order_*.tsv  team_countries_*.tsv
        │            │                            │
        └────────────┴──────────┬─────────────────┘
                                │
                                ▼
                      prepare_run_features.py
                                │
                                ▼
           long_runs_and_running_order_{race_id}.tsv
                                │
                                ▼
            ngboost-norm-tuned-reviewed.ipynb (Model)
                                │
        ┌───────────────────────┴─────────────────────────┐
        ▼                                                 ▼
reports/post_race_analysis_*.json           results/ngboost-dev/*.json
(Performance Metrics)                       (Simulated Pace Samples)
```

---

## Data Preparation Step (`prepare_run_features.py`)

This is a critical intermediate step that merges historical results with the current running order to create the input for the model.

- **Input**:
    - `data/results_with_dist_j{YEAR}_{RACE_TYPE}.tsv` (Historical results)
    - `data/running_order_final_{RACE_TYPE}_fy_{YEAR}.tsv` (Current running order)
- **Output**: `data/long_runs_and_running_order_{RACE_TYPE}_fy_{YEAR}.tsv`
- **Purpose**: Creates a flat file with all features (Box-Cox pace, terrain stats, team history) required for the model.

---

## Running Order Data (3 Sources)

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

---

## Results with Distances

- **Converter**: `result_xml_to_csv.py`
- **Input**: `data/results_j{YEAR}_{VE_OR_JU}.xml`
- **Output**: `data/results_with_dist_j{YEAR}_{VE_OR_JU}.tsv`

---

## Terrain / Trail Data

Static data in `Jukola-terrain/`:

| File | Description |
|------|-------------|
| `ideal-paces-ju.tsv` | Ideal paces — Jukolan viesti |
| `ideal-paces-ve.tsv` | Ideal paces — Venlojen viesti |
| `terrrain-descriptions.json` | Terrain type descriptions |

---

## Model Outputs

### `reports/` Directory
- `post_race_analysis_{race_id}.json`: CRPS, NLL, and R² metrics.

### `results/` Directory
- `running_order_samples_v2_{race_id}.json`: 1000-2000 pace samples per runner for relay simulation.
