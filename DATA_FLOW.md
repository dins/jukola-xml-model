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
        └────────────┴───────────────────────────┘
                     │
                     ▼
          process-recent-years.sh / process-one-race.sh
                     │
        ┌────────────┼──────────────────────────────────┐
        ▼            ▼                                   ▼
count_names.py  result_xml_to_csv.py          shared.py (leg distances)
        │            │                                │
        ▼            ▼                                ▼
team_countries_*.tsv  results_with_dist_*.tsv  distances dict
        │            │                                │
        └────────────┴───────────────────────────────┘
                     │
                     ▼
            Model training / post-race analysis (notebooks)
```

---

## Running Order Data (3 Sources)

### Source A: Registration Site (`fetch_running_order.py`)

- **URL**: `https://registration.jukola.com/?kisa=j{YEAR}&view=1&sarja={VE_OR_JU}&...`
- **Method**: HTML scraping (parses team lists from registration page)
- **Output**: `data/running_order_final_{VE_OR_JU}_fy_{YEAR}.tsv`
- **Derived**: `data/team_countries_j{YEAR}_{VE_OR_JU}.tsv`
- **When**: Default source for all years **except** the most recent completed year

### Source B: Online JSON API (`process_online_running_order.py`)

- **Input**: Pre-downloaded JSON from `data/online-running-order/`
- **JSON URL**: `https://online.jukola.com/tulokset-new/online/online_j{YEAR}_{VE_OR_JU}_competitors.json`
- **Output**: `data/online_running_order_{VE_OR_JU}_fy_{YEAR}.tsv`
- **Derived**: `data/online_team_countries_j{YEAR}_{VE_OR_JU}.tsv`
- **When**: Recent years where registration site data is unreliable
- **Advantage**: Structured JSON (no HTML scraping)

### Source C: Team Countries Only (`fetch_online_team_countries.py`)

- **URL**: `https://online.jukola.com/tulokset-new/online/online_j{YEAR}_{RACE_TYPE}_competitors.json`
- **Method**: Parses pre-downloaded JSON for team-country mappings
- **Output**: `data/team_countries_j{YEAR}_{RACE_TYPE}.tsv`
- **When**: One-off fetch for current race year (via `RACE_TYPE` and `FORECAST_YEAR` env vars)
- **Purpose**: Team base names and countries without full running order

---

## Results with Distances

- **Converter**: `result_xml_to_csv.py`
- **Input**: `data/results_j{YEAR}_{VE_OR_JU}.xml`
- **Output**: `data/results_with_dist_j{YEAR}_{VE_OR_JU}.tsv`

### XML Source URLs

1. **Archived** (reliable after race): `https://results.jukola.com/tulokset/results_j{YEAR}_{VE_OR_JU}.xml`
2. **Online** (during/after race): `https://online.jukola.com/tulokset-new/xml/results_j{YEAR}_{VE_OR_JU}.xml`

### Output TSV Columns

| Column | Description |
|--------|-------------|
| `team-id` | Team identifier |
| `placement` | Race placement |
| `team-time` | Total team time (seconds) |
| `team-name` | Team name |
| `team-nro` | Team number |
| `leg-nro` | Leg number |
| `emit` | Emit (chip) ID |
| `leg-time` | Leg completion time (seconds) |
| `competitor-name` | Competitor name |
| `weighted_log_mean_pace` | Weighted avg log pace |
| `weighted_log_pace_std` | Log pace std dev |
| `disqualified` | DQ status |
| `leg_distance` | Leg distance (meters) |

---

## Terrain / Trail Data

Static data in `Jukola-terrain/`:

| File | Description |
|------|-------------|
| `ideal-paces-ju.tsv` | Ideal paces — Jukolan viesti |
| `ideal-paces-ke.tsv` | Ideal paces — Kenraali harjoitus |
| `ideal-paces-ve.tsv` | Ideal paces — Venlojen viesti |
| `ju-ideal-times.csv` | Ideal times per leg — Jukolan viesti |
| `ve-ideal-times.csv` | Ideal times per leg — Venlojen viesti |
| `terrrain-descriptions.json` | Terrain type descriptions |
| `viitoitus.csv` | Waymarking info |

**Used by**: Model training scripts, `ideal_paces_cleanup.py`, post-race notebooks.

---

## Leg Distances (Hardcoded)

Leg distances are **hardcoded in `shared.py`** (`distances` dict).

- **Accessor**: `shared.leg_distance(ve_or_ju, year, leg)`
- **Update**: Manually before race.

---

## Output File Index

### `data/` Directory

| File | Produced By | Purpose |
|------|-------------|---------|
| `running_order_final_{VE_OR_JU}_fy_{YEAR}.tsv` | `fetch_running_order.py` | Running order from registration |
| `online_running_order_{VE_OR_JU}_fy_{YEAR}.tsv` | `process_online_running_order.py` | Running order from online JSON |
| `team_countries_j{YEAR}_{VE_OR_JU}.tsv` | `fetch_running_order.py` | Team-country mappings (registration) |
| `online_team_countries_j{YEAR}_{VE_OR_JU}.tsv` | `process_online_running_order.py` | Team-country mappings (online) |
| `results_with_dist_j{YEAR}_{VE_OR_JU}.tsv` | `result_xml_to_csv.py` | Results with leg distances |

### `data/online-running-order/` Directory

Pre-downloaded JSON files from online.jukola.com API.

### `reports/` Directory

Post-race analysis output (generated by model scripts).

### `results/` Directory

Model prediction outputs by model version (e.g., `ngboost-norm-tuned-reviewed/`):
- `ngboost_metrics_{RACE_TYPE}_fy_{YEAR}.json` — Performance metrics
- `running_order_samples_v2_{RACE_TYPE}_fy_{YEAR}.json` — Simulated pace samples

---

## External Dependencies

| Domain | URL | Provides |
|--------|-----|----------|
| Registration | `registration.jukola.com` | Running order (HTML) |
| Online API | `online.jukola.com` | Live results JSON |
| Results archive | `results.jukola.com` | Archived XML results |