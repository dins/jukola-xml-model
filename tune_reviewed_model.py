#!/usr/bin/env python3
import argparse
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from multiprocessing import Process, Semaphore
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import optuna
from optuna.storages import JournalStorage
from optuna.storages.journal import JournalFileBackend

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TuningConfig:
    race_type: str
    backtest_years: tuple[int, ...]
    study_name: str
    n_workers: int
    seed_base: int
    run_root: Path
    xml_model_root: Path
    journal_path: Path
    deadline_timestamp: Optional[float]
    backtest_semaphore: Any


# ---------------------------------------------------------------------------
# Optuna Search Space
# ---------------------------------------------------------------------------


def suggest_params(trial: optuna.Trial, race_type: str) -> Dict[str, Any]:
    """Define the search space for ngboost-norm-tuned-reviewed.ipynb."""

    # [I 2026-05-22 01:34:30,368] Trial 427 finished with value: 1.1791135697335187 and parameters:
    # {'Base__min_samples_leaf': 70, 'n_estimators': 250, 'Base__max_depth': 10,
    # 'Base__max_features': 0.8814660047756667, 'learning_rate': 0.007132733920820354,
    # 'col_sample': 0.97289050032128, 'minibatch_frac': 0.5080133685253934}. Best is trial 427 with value: 1.1791135697335187.

    # Notebook adds 50 by default (not for tuning).
    # Early stopping should handle the rest.
    if race_type == "ju":
        n_estimators = trial.suggest_int("n_estimators", 300, 400, step=100)
        min_samples_leaf = trial.suggest_int(
            "Base__min_samples_leaf", 300, 300, step=50
        )
    else:
        n_estimators = trial.suggest_int("n_estimators", 300, 300, step=100)
        min_samples_leaf = trial.suggest_int(
            "Base__min_samples_leaf", 200, 200, step=50
        )

    return {
        "Base__max_depth": trial.suggest_int(
            "Base__max_depth", low=12, high=12, step=2
        ),
        "Base__min_samples_leaf": min_samples_leaf,
        "Base__max_features": trial.suggest_float(
            "Base__max_features", 0.8, 1.0, step=0.1
        ),
        # NGBoost parameters
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.05),
        "col_sample": trial.suggest_float("col_sample", 0.1, 1.0),
        "minibatch_frac": trial.suggest_float("minibatch_frac", 0.8, 1.0, step=0.1),
        "n_estimators": n_estimators,
    }


# ---------------------------------------------------------------------------
# Objective Function
# ---------------------------------------------------------------------------


def run_notebook_trial(trial: optuna.Trial, config: TuningConfig) -> float:
    params = suggest_params(trial, config.race_type)
    trial_id = f"trial-{trial.number:05d}"
    trial_root = (config.run_root / config.study_name / trial_id).resolve()
    trial_root.mkdir(parents=True, exist_ok=True)

    # Save params to JSON for the notebook to pick up
    params_path = trial_root / "params.json"
    with open(params_path, "w") as f:
        json.dump(params, f, indent=2)

    yearly_scores: List[float] = []

    def run_year(year: int) -> float:
        logging.info(
            "Trial %d: Processing %s year %d", trial.number, config.race_type, year
        )

        # Paths for this specific year in this trial
        year_work_dir = trial_root / f"fy_{year}"
        year_work_dir.mkdir(parents=True, exist_ok=True)

        # Isolate outputs completely
        metrics_json_path = year_work_dir / "metrics.json"
        results_dir = year_work_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        executed_notebook_path = (
            year_work_dir / f"ngboost-{config.race_type}-{year}-executed.ipynb"
        )
        log_path = year_work_dir / "execution.log"

        env = os.environ.copy()
        env.update(
            {
                "RACE_TYPE": config.race_type,
                "FORECAST_YEAR": str(year),
                "PROCESSING_BATCH_ID": f"optuna-{config.study_name}/{trial_id}/fy_{year}",
                "NGB_PARAMS_JSON": str(params_path),
                "NGB_EXTRA_ITERATIONS": "0",
                "NGB_METRICS_JSON": str(metrics_json_path),
                "NGB_RESULTS_DIR": str(results_dir),
                "OPTUNA_TRIAL_NUMBER": str(trial.number),
                "ENABLE_DEBUG_PLOTS": "0",
                "BATCH_RUN_TS": f"optuna_{trial.number}_{int(time.time())}",
            }
        )

        # Direct execution of the notebook via nbconvert
        # This bypasses the shell scripts and gives us full control over paths
        cmd = [
            "uv",
            "run",
            "jupyter",
            "nbconvert",
            "--to",
            "notebook",
            "--execute",
            "--ExecutePreprocessor.timeout=36000",
            "--output",
            str(executed_notebook_path),
            "ngboost-norm-tuned-reviewed.ipynb",
        ]

        try:
            with config.backtest_semaphore:
                with open(log_path, "w") as f:
                    subprocess.run(
                        cmd,
                        cwd=config.xml_model_root,
                        env=env,
                        stdout=f,
                        stderr=subprocess.STDOUT,
                        check=True,
                    )
        except subprocess.CalledProcessError as e:
            # Check if process died due to termination signals:
            #  130 / -2 : SIGINT (Ctrl-C)
            # -15       : SIGTERM (Termination signal)
            #  137 / -9 : SIGKILL (Force kill)
            if e.returncode in (130, -2, -15, 137, -9):
                # Process was killed/interrupted
                logging.warning(
                    f"Trial {trial.number} year {year} notebook execution interrupted (code {e.returncode})."
                )
                # We MUST raise KeyboardInterrupt instead of TrialPruned here so the main loop aborts
                # instead of just pruning the trial and starting a new one.
                raise KeyboardInterrupt(
                    f"Notebook execution interrupted for year {year}"
                )
            logging.error(
                "Trial %d failed for year %d. See %s", trial.number, year, log_path
            )
            raise optuna.TrialPruned(f"Notebook execution failed for year {year}")

        # Extract metric
        if not metrics_json_path.exists():
            logging.error(
                "Trial %d: Metrics file missing at %s", trial.number, metrics_json_path
            )
            raise optuna.TrialPruned(f"Metrics missing for year {year}")

        with open(metrics_json_path, "r") as f:
            metrics = json.load(f)

        # We optimize for forecast year custom score: NLL (Negative Log-Likelihood) + interval penalty
        fy_metrics = metrics.get("forecast_year_metrics")
        if fy_metrics is None:
            logging.error(
                "Trial %d: Forecast year metrics missing for year %d. "
                "This usually means actual results for that year are missing from 'data/'.",
                trial.number,
                year,
            )
            raise optuna.TrialPruned(f"Forecast metrics missing for year {year}")

        fy_custom_tuning_score = fy_metrics.get("tuning_score")
        if fy_custom_tuning_score is None:
            logging.error(
                "Trial %d: tuning_score missing in forecast_year_metrics for year %d",
                trial.number,
                year,
            )
            raise optuna.TrialPruned(f"tuning_score missing for year {year}")

        return float(fy_custom_tuning_score)

    # Run backtests in parallel with a thread pool
    running_years = set(config.backtest_years)
    try:
        with ThreadPoolExecutor(max_workers=len(config.backtest_years)) as executor:
            futures = {
                executor.submit(run_year, year): year for year in config.backtest_years
            }
            for future in as_completed(futures):
                year = futures[future]
                yearly_scores.append(future.result())
                running_years.remove(year)
    except KeyboardInterrupt:
        for year in running_years:
            logging.info(
                "Trial %d backtest %d received signal SIGINT. Terminating.",
                trial.number,
                year,
            )
        # Re-raise so Optuna can catch it, mark the trial as FAIL/INTERRUPTED, and exit gracefully
        raise

    return float(np.mean(yearly_scores))


# ---------------------------------------------------------------------------
# Worker & Study Management
# ---------------------------------------------------------------------------


def parse_deadline(deadline_str: str) -> float:
    """Parse HH:MM and return absolute timestamp."""
    match = re.match(r"^(\d{1,2}):(\d{2})$", deadline_str)
    if not match:
        raise ValueError(f"Invalid deadline format: {deadline_str}. Use HH:MM.")

    hours, minutes = map(int, match.groups())
    now = datetime.now()
    target = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

    if target < now:
        target += timedelta(days=1)

    return target.timestamp()


def worker(worker_id: int, config: TuningConfig):
    # Each worker needs its own storage connection
    storage = JournalStorage(JournalFileBackend(str(config.journal_path)))

    # Use different seed per worker
    sampler = optuna.samplers.TPESampler(seed=config.seed_base + worker_id)

    study = optuna.create_study(
        study_name=config.study_name,
        storage=storage,
        load_if_exists=True,
        direction="minimize",
        sampler=sampler,
        # Explicitly disable pruning. The default MedianPruner is suspected to be pruning trials
        # prematurely, as partial cross-validation results (e.g., just the first year) may not
        # reliably represent the overall performance across all years.
        pruner=optuna.pruners.NopPruner(),
    )

    timeout = None
    if config.deadline_timestamp:
        timeout = max(0.0, config.deadline_timestamp - time.time())

    study.optimize(
        lambda t: run_notebook_trial(t, config),
        n_trials=None,
        timeout=timeout,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--race-type", default="ve", choices=["ju", "ve", "ke"])
    parser.add_argument(
        "--years", nargs="+", type=int, default=[2022, 2023, 2024, 2025]
    )
    parser.add_argument(
        "--study-name",
        help="Optuna study name (default: v6-tuning-{race-type})",
    )
    parser.add_argument("--n-workers", type=int, default=3)
    parser.add_argument(
        "--deadline", help="Expected completion time (local time HH:MM)"
    )
    parser.add_argument(
        "--enqueue-params-json",
        nargs="+",
        help="Path(s) to JSON file(s) containing initial parameters to jump-start the study.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--run-root", default=".optuna-runs")
    parser.add_argument(
        "--journal-path",
        help="Optuna journal path (default: .optuna/reviewed-journal-{race-type}.log)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    study_name = args.study_name or f"v6-tuning-{args.race_type}"
    journal_path = Path(
        args.journal_path or f".optuna/reviewed-journal-{args.race_type}.log"
    )

    # If enqueue params provided, load the study and enqueue BEFORE spinning up workers
    if args.enqueue_params_json:
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        storage = JournalStorage(JournalFileBackend(str(journal_path)))
        study = optuna.create_study(
            study_name=study_name,
            storage=storage,
            load_if_exists=True,
            direction="minimize",
        )
        for param_file in args.enqueue_params_json:
            param_path = Path(param_file)
            if param_path.exists():
                with open(param_path, "r") as f:
                    initial_params = json.load(f)

                # Map parameters matching notebook formatting to Optuna's format if necessary
                optuna_params = {}
                for k, v in initial_params.items():
                    if k in ["max_depth", "min_samples_leaf", "max_features"]:
                        optuna_params[f"Base__{k}"] = v
                    else:
                        optuna_params[k] = v

                try:
                    study.enqueue_trial(optuna_params, skip_if_exists=True)
                    logging.info(
                        f"Enqueued initial parameters from {param_path} into study {study_name}"
                    )
                except Exception as e:
                    logging.error(
                        f"Failed to enqueue parameters from {param_path}: {e}"
                    )
            else:
                logging.warning(
                    f"Enqueue params file not found: {param_path}. Ignoring."
                )

    deadline_timestamp = None
    if args.deadline:
        deadline_timestamp = parse_deadline(args.deadline)

    backtest_semaphore = Semaphore(8)

    config = TuningConfig(
        race_type=args.race_type,
        backtest_years=tuple(args.years),
        study_name=study_name,
        n_workers=args.n_workers,
        seed_base=args.seed,
        run_root=Path(args.run_root),
        xml_model_root=Path(".").resolve(),
        journal_path=journal_path,
        deadline_timestamp=deadline_timestamp,
        backtest_semaphore=backtest_semaphore,
    )

    config.journal_path.parent.mkdir(parents=True, exist_ok=True)

    if config.deadline_timestamp:
        deadline_str = datetime.fromtimestamp(config.deadline_timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        logging.info("Tuning will run until deadline: %s", deadline_str)

    logging.info("Starting tuning: %s", config)

    processes = []
    for i in range(config.n_workers):
        p = Process(target=worker, args=(i, config))
        p.start()
        processes.append(p)

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print()  # Print a newline so the log doesn't end up on the same line as ^C
        logging.info(
            "Interrupted by user. Waiting for workers to shut down gracefully and mark trials as failed (up to 15s)..."
        )
        # Give workers time to catch the SIGINT, fail their Optuna trials in the DB, and exit cleanly
        deadline = time.time() + 15.0
        for p in processes:
            timeout = max(0.0, deadline - time.time())
            p.join(timeout=timeout)

        # If any workers are STILL stuck after 15 seconds, forcefully kill them
        killed_any = False
        for p in processes:
            if p.is_alive():
                logging.warning(
                    f"Worker {p.pid} did not terminate gracefully in time. Force killing."
                )
                p.terminate()  # SIGTERM is safer than SIGKILL
                p.join(timeout=1.0)
                if p.is_alive():
                    p.kill()  # SIGKILL if it ignores SIGTERM
                killed_any = True

        if killed_any:
            for p in processes:
                p.join()

        logging.info("Tuning interrupted and workers terminated.")
        return

    logging.info("Tuning complete.")


if __name__ == "__main__":
    main()
