# Data Flow Documentation

Complete trace of data sources, processing scripts, and output files for the jukola-xml-model project.

---

## Table of Contents

1. [High-Level Data Flow](#high-level-data-flow)
2. [Running Order Data (3 Sources)](#running-order-data-3-sources)
3. [Results with Distances](#results-with-distances)
4. [Terrain / Trail Data](#terrain--trail-data)
5. [Leg Distances (Hardcoded)](#leg-distances-hardcoded)
6. [Output File Index](#output-file-index)
7. [External Dependencies](#external-dependencies)

---

## High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    External Data Sources                              │
│  registration.jukola.com  │  online.jukola.com  │  results.jukola.com│
└────────────────────┬────────────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
  fetch_running_order.py  process_online_running_order.py  fetch_online_team_countries.py
         │           │                                │
         ▼           ▼                                ▼
  running_order_final_*.tsv  online_running_order_*.tsv  team_countries_*.tsv
         │           │                                │
         └───────────┴────────────────────────────────┘
                     │
                     ▼
           process-recent-years.sh / process-one-race.sh
                     │
         ┌───────────┼─────────────────────────────────┐
         ▼           ▼                                 ▼
  count_names.py  result_xml_to_csv.py          shared.py (leg distances)
         │           │                              │
         ▼           ▼                              ▼
  team_countries_*.tsv  results_with_dist_*.tsv  distances dict
         │           │                              │
         └───────────┴──────────────────────────────┘
                     │
                     ▼
          Model training / post-race analysis (Python notebooks)
```

---

## Running Order Data (3 Sources)

The project fetches running order (competitor lineup) data from **three different sources**, each serving a specific purpose:

### Source A: Registration Site (`fetch_running_order.py`)

- **URL**: `https://registration.jukola.com/?kisa=j{YEAR}&view=1&sarja={VE_OR_JU}&...`
- **Method**: HTML scraping (parses team lists from registration page)
- **Output**: `data/running_order_final_{VE_OR_JU}_fy_{YEAR}.tsv`
- **Derived Output**: `data/team_countries_j{YEAR}_{VE_OR_JU}.tsv`
- **When Used**: Default source for all years **except** the most recent completed year
- **Key Fields**: team ID, team name, competitor name, country, start time, leg assignments
- **Code**: Lines 20-87 of `fetch_running_order.py`

### Source B: Online JSON API (`process_online_running_order.py`)

- **Input**: Pre-downloaded JSON file from `data/online-running-order/`
- **JSON Source URL**: `https://online.jukola.com/tulokset-new/online/online_j{YEAR}_{VE_OR_JU}_competitors.json`
- **Output**: `data/online_running_order_{VE_OR_JU}_fy_{YEAR}.tsv`
- **Derived Output**: `data/online_team_countries_j{YEAR}_{VE_OR_JU}.tsv`
- **When Used**: For recent years where registration site data is unreliable or outdated
- **Advantage**: Structured JSON (no HTML scraping needed)
- **Available Files** (as of 2026-04-19):
  | File | Year | Race Type |
  |------|------|-----------|
  | `online_running_order_2023_ju.json` | 2023 | Junior (Jukola) |
  | `online_running_order_2023_ve.json` | 2023 | Veteran (Viesti) |
  | `online_running_order_2024_ju.json` | 2024 | Junior |
  | `online_running_order_2024_ve.json` | 2024 | Veteran |
  | `online_running_order_2025_ke.json` | 2025 | Relay (Koulta) |
  | `online_running_order_2099_ve.json` | 2099 | Veteran |
- **Code**: Lines 20-141 of `process_online_running_order.py`

### Source C: Online Team Countries Only (`fetch_online_team_countries.py`)

- **URL**: `https://online.jukola.com/tulokset-new/online/online_j{YEAR}_{RACE_TYPE}_competitors.json`
- **Method**: JSON API parsing (extracts only team-country mappings)
- **Output**: `data/team_countries_j{YEAR}_{RACE_TYPE}.tsv`
- **When Used**: One-off fetch for the current race year/type (as set in `shared.py`)
- **Purpose**: Gets team base names and countries without full running order
- **Code**: Lines 33-53 of `fetch_online_team_countries.py`

---

## Results with Distances

- **Converter**: `result_xml_to_csv.py`
- **Input**: `data/results_j{YEAR}_{VE_OR_JU}.xml`
- **Output**: `data/results_with_dist_j{YEAR}_{VE_OR_JU}.tsv`

### XML Source URLs

Two possible sources for the XML results file:

1. **Archived results** (reliable after race): `https://results.jukola.com/tulokset/results_j{YEAR}_{VE_OR_JU}.xml`
2. **Online results** (available during/just after race): `https://online.jukola.com/tulokset-new/xml/results_j{YEAR}_{VE_OR_JU}.xml`

### Output TSV Columns

| Column | Description |
|--------|-------------|
| `team-id` | Unique team identifier |
| `placement` | Team placement in race |
| `team-time` | Total team time (seconds) |
| `team-name` | Team name |
| `team-nro` | Team number |
| `leg-nro` | Leg number |
| `emit` | Emit (chip) ID |
| `leg-time` | Leg completion time (seconds) |
| `competitor-name` | Competitor name |
| `weighted_log_mean_pace` | Weighted average log pace |
| `weighted_log_pace_std` | Std dev of weighted log paces |
| `disqualified` | Whether leg was disqualified |
| `leg_distance` | Distance of leg (meters) |

### Processing Logic

1. Parses XML `team` and `leg` elements
2. For each leg, extracts control times (`cd` fields) and computes control-level paces
3. Computes weighted log mean pace and standard deviation using leg distances as weights
4. Looks up leg distance from `shared.leg_distance()` (hardcoded per year/race type)

---

## Terrain / Trail Data

Static data provided by hand, stored in `Jukola-terrain/`:

| File | Description |
|------|-------------|
| `ideal-paces-ju.tsv` | Ideal paces for Junior (Jukola) terrain |
| `ideal-paces-ke.tsv` | Ideal paces for Koulta (relay) terrain |
| `ideal-paces-ve.tsv` | Ideal paces for Veteran (Viesti) terrain |
| `ju-ideal-times.csv` | Ideal times per leg for Junior |
| `ve-ideal-times.csv` | Ideal times per leg for Veteran |
| `terrrain-descriptions.json` | Terrain type descriptions |
| `viitoitus.csv` | Waymarking information |

**Used by**: Model training scripts, `ideal_paces_cleanup.py`, and post-race analysis notebooks.

---

## Leg Distances (Hardcoded)

Leg distances are **hardcoded in `shared.py`** in the `distances` dictionary:

```python
distances = {
    'ju': {
        '2025': [1050, 1350, ...],  # distances per leg
        '2024': [980, 1400, ...],
        ...
    },
    've': {
        ...
    }
}
```

- **Accessor**: `shared.leg_distance(race_type, year, leg_number)` (0-indexed leg number)
- **Update Frequency**: Each year after the race, distances are updated from official race data
- **Where to find new distances**: Official race results XML or from `Jukola-terrain/` files

---

## Output File Index

### `data/` Directory

| File | Produced By | Purpose |
|------|-------------|---------|
| `running_order_final_{VE_OR_JU}_fy_{YEAR}.tsv` | `fetch_running_order.py` | Full running order from registration site |
| `online_running_order_{VE_OR_JU}_fy_{YEAR}.tsv` | `process_online_running_order.py` | Running order from online JSON |
| `team_countries_j{YEAR}_{VE_OR_JU}.tsv` | `fetch_running_order.py` | Team-country mappings (from registration) |
| `online_team_countries_j{YEAR}_{VE_OR_JU}.tsv` | `process_online_running_order.py` | Team-country mappings (from online JSON) |
| `results_with_dist_j{YEAR}_{VE_OR_JU}.tsv` | `result_xml_to_csv.py` | Results with leg distances |

### `data/online-running-order/` Directory

Pre-downloaded JSON files from online.jukola.com API. To fetch new data:

```bash
curl https://online.jukola.com/tulokset-new/online/online_j{YEAR}_{VE_OR_JU}_competitors.json \
  > data/online-running-order/online_running_order_{YEAR}_{VE_OR_JU}.json
```

### `reports/` Directory

Post-race analysis output files (generated by model scripts, not covered in detail here).

### `results/` Directory

Model prediction outputs (ngboost predictions, running order samples).

---

## External Dependencies

| Domain | URL | What It Provides |
|--------|-----|------------------|
| Registration | `https://registration.jukola.com/` | Running order (competitor lineups) as HTML |
| Online API | `https://online.jukola.com/` | Live results JSON, competitors JSON (as structured data) |
| Results archive | `https://results.jukola.com/` | Archived XML results with full leg details |

### Rate Limiting / Timeout Notes

- `fetch_running_order.py`: timeout=15 seconds per request
- `process_online_running_order.py`: timeout=30 seconds per request
- `fetch_online_team_countries.py`: timeout=15 seconds per request
- No explicit rate limiting between multiple requests (fetch sequentially)

---

## How to Add a New Year's Data

1. **Fetch running order** (from registration site):
   ```bash
   # Edit shared.py to set FORECAST_YEAR and RACE_TYPE
   uv run python fetch_running_order.py
   ```

2. **Fetch results with distances**:
   ```bash
   curl https://results.jukola.com/tulokset/results_j{YEAR}_{VE_OR_JU}.xml \
     > data/results_j{YEAR}_{VE_OR_JU}.xml
   uv run python result_xml_to_csv.py {YEAR} {VE_OR_JU}
   ```

3. **Update leg distances** in `shared.py` (if they changed from previous years)

4. **Alternative: fetch from online JSON** (if registration site is unreliable):
   ```bash
   curl https://online.jukola.com/tulokset-new/online/online_j{YEAR}_{VE_OR_JU}_competitors.json \
     > data/online-running-order/online_running_order_{YEAR}_{VE_OR_JU}.json
   uv run python process_online_running_order.py