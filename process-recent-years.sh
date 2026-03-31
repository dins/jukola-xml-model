#!/usr/bin/env bash
set -euf -o pipefail

export RUN_TS=$(date -u '+%Y%m%d_%H%M%S')
export SCRIPT_START_TIME=$(date +%s)

time uv run python count_names.py
echo "$(date -u +"%F %T") count_names.py DONE"

# 1. Define the worker logic as a standard, readable function
function process_race_worker() {
  local current_race_type=$1
  local current_forecast_year=$2

  local log_path="logs/parallel-${current_race_type}-${current_forecast_year}-${RUN_TS}.log"
  local now=$(date +%s)
  local start_secs=$((now - SCRIPT_START_TIME))

  echo "$(date -u +"%F %T") Starting at ${start_secs} secs, ${log_path}"

  # Run the script and capture duration
  if RACE_TYPE="${current_race_type}" FORECAST_YEAR="${current_forecast_year}" RUN_TS="${RUN_TS}" ./process-one-race.sh > "${log_path}" 2>&1; then
    local end_now=$(date +%s)
    local duration=$((end_now - now))
    echo "$(date -u +"%F %T") DONE ${log_path} in ${duration} secs"
  else
    echo "$(date -u +"%F %T") FAILED ${log_path}"
  fi
}

# 2. Export the function so xargs subshells can execute it
export -f process_race_worker

# 3. Define the queue as a flat list of arguments (type, year, type, year)
pending_races=(
  "ju" "2025" "ju" "2024" "ju" "2023" "ju" "2022" "ju" "2021" "ju" "2019" "ju" "2018" "ju" "2017"
  "ve" "2025" "ve" "2024" "ve" "2023" "ve" "2022" "ve" "2021" "ve" "2019" "ve" "2018" "ve" "2017"
)


# 4. Use xargs to pass arguments to our exported function
# -n 2: Passes exactly 2 arguments (Type and Year) to the function at a time
# -P 8: Maintains exactly 8 workers concurrently
printf "%s\n" "${pending_races[@]}" | xargs -n 2 -P 7 bash -c 'process_race_worker "$1" "$2"' _

echo "DONE ${RUN_TS}"

time uv run python json_reports.py