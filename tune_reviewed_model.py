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
from multiprocessing import Process
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


# ---------------------------------------------------------------------------
# Optuna Search Space
# ---------------------------------------------------------------------------


def suggest_params(trial: optuna.Trial, race_type: str) -> Dict[str, Any]:
    """Define the search space for ngboost-norm-tuned-reviewed.ipynb."""


    # [I 2026-05-22 01:34:30,368] Trial 427 finished with value: 1.1791135697335187 and parameters:
    # {'Base__min_samples_leaf': 70, 'n_estimators': 250, 'Base__max_depth': 10,
    # 'Base__max_features': 0.8814660047756667, 'learning_rate': 0.007132733920820354,
    # 'col_sample': 0.97289050032128, 'minibatch_frac': 0.5080133685253934}. Best is trial 427 with value: 1.1791135697335187.
    min_samples_leaf = trial.suggest_int("Base__min_samples_leaf", 60, 200, step=10)

    # Notebook adds 50 by default (not for tuning).
    # Early stopping should handle the rest.
    if race_type == "ju":
        n_estimators = trial.suggest_int("n_estimators", 200, 800, step=10)
    else:
        n_estimators = trial.suggest_int("n_estimators", 200, 500, step=10)

    return {
        "Base__max_depth": trial.suggest_int("Base__max_depth", low=4, high=12, step=2),
        "Base__min_samples_leaf": min_samples_leaf,
        "Base__max_features": trial.suggest_float("Base__max_features", 0.5, 1.0),
        # NGBoost parameters
        "learning_rate": trial.suggest_float("learning_rate", 0.0005, 0.1, log=True),
        "col_sample": trial.suggest_float("col_sample", 0.5, 1.0),
        "minibatch_frac": trial.suggest_float("minibatch_frac", 0.3, 1.0),
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

    for year in config.backtest_years:
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
            with open(log_path, "w") as f:
                subprocess.run(
                    cmd,
                    cwd=config.xml_model_root,
                    env=env,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
        except subprocess.CalledProcessError:
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

        yearly_scores.append(float(fy_custom_tuning_score))

        # Intermediate report to Optuna for pruning
        trial.report(float(np.mean(yearly_scores)), step=len(yearly_scores) - 1)
        if trial.should_prune():
            raise optuna.TrialPruned()

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
    parser.add_argument("--n-workers", type=int, default=8)
    parser.add_argument(
        "--deadline", help="Expected completion time (local time HH:MM)"
    )
    parser.add_argument(
        "--enqueue-params-json",
        help="Path to a JSON file containing initial parameters to jump-start the study.",
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
        param_path = Path(args.enqueue_params_json)
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

            journal_path.parent.mkdir(parents=True, exist_ok=True)
            storage = JournalStorage(JournalFileBackend(str(journal_path)))
            study = optuna.create_study(
                study_name=study_name,
                storage=storage,
                load_if_exists=True,
                direction="minimize",
            )
            # Avoid enqueuing multiple times if restarting the script
            if len(study.trials) == 0:
                try:
                    study.enqueue_trial(optuna_params)
                    logging.info(
                        f"Enqueued initial parameters from {param_path} into study {study_name}"
                    )
                except Exception as e:
                    logging.error(
                        f"Failed to enqueue parameters from {param_path}: {e}"
                    )
            else:
                logging.info(
                    f"Study {study_name} already has trials. Skipping enqueue to avoid duplication."
                )
        else:
            logging.warning(f"Enqueue params file not found: {param_path}. Ignoring.")

    deadline_timestamp = None
    if args.deadline:
        deadline_timestamp = parse_deadline(args.deadline)

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

    for p in processes:
        p.join()

    logging.info("Tuning complete.")


if __name__ == "__main__":
    main()
