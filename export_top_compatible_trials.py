#!/usr/bin/env python3
import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, cast

import optuna
from optuna.storages import JournalStorage
from optuna.storages.journal import JournalFileBackend
from optuna.trial import TrialState

from tune_reviewed_model import suggest_params


class MockTrial:
    def __init__(self):
        self.ranges = {}

    def suggest_int(self, name, low, high, step=1, log=False):
        self.ranges[name] = ("int", low, high, step)
        return low

    def suggest_float(self, name, low, high, step=None, log=False):
        self.ranges[name] = ("float", low, high)
        return low

    def suggest_categorical(self, name, choices):
        self.ranges[name] = ("categorical", choices)
        return choices[0]


def coerce_params(params: Dict[str, Any], expected_ranges: Dict[str, Any]) -> Dict[str, Any]:
    coerced = {}
    for name, range_info in expected_ranges.items():
        type_ = range_info[0]
        val = params.get(name, range_info[1])  # Default to 'low' if missing

        if type_ == "int":
            low, high, step = range_info[1], range_info[2], range_info[3]
            # Clip to boundaries
            val = max(low, min(high, val))
            # Snap to nearest step
            steps_from_low = round((val - low) / step)
            val = low + steps_from_low * step
            # Ensure we don't exceed high due to rounding
            val = min(val, high)
            coerced[name] = int(val)
        elif type_ == "float":
            low, high = range_info[1], range_info[2]
            # Clip to boundaries
            val = max(low, min(high, val))
            coerced[name] = float(val)
        elif type_ == "categorical":
            choices = range_info[1]
            if val not in choices:
                val = choices[0]
            coerced[name] = val
    return coerced


def main():
    parser = argparse.ArgumentParser(
        description="Export the best N compatible trials from an Optuna study."
    )
    parser.add_argument(
        "--race-type",
        required=True,
        choices=["ju", "ve", "ke"],
        help="Race type (ju, ve, or ke)",
    )
    parser.add_argument("--study-name", required=True, help="Optuna study name")
    parser.add_argument(
        "--journal-path",
        help="Optuna journal path (default: .optuna/reviewed-journal-{race-type}.log)",
    )
    parser.add_argument(
        "--output-dir",
        default="best-params",
        help="Base directory for output (default: best-params)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top trials to export (default: 10)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    study_name = args.study_name
    journal_path = Path(
        args.journal_path or f".optuna/reviewed-journal-{args.race_type}.log"
    )

    if not journal_path.exists():
        logging.error(f"Journal file not found: {journal_path}")
        return

    logging.info(f"Loading study '{study_name}' from {journal_path}")

    storage = JournalStorage(JournalFileBackend(str(journal_path)))
    try:
        study = optuna.load_study(study_name=study_name, storage=storage)
    except KeyError:
        logging.error(f"Study '{study_name}' not found in the journal.")
        return
    except Exception as e:
        logging.error(f"Failed to load study: {e}")
        return

    # Determine expected ranges by running our MockTrial through the search space function
    mock_trial = MockTrial()
    suggest_params(cast(optuna.Trial, mock_trial), args.race_type)
    expected_ranges = mock_trial.ranges
    logging.info(f"Expected parameter ranges for {args.race_type}: {expected_ranges}")

    completed_trials = [
        t for t in study.trials if t.state == TrialState.COMPLETE and t.value is not None
    ]

    if not completed_trials:
        logging.warning("No completed trials found in study.")
        return

    # Sort trials by value
    is_minimize = study.direction == optuna.study.StudyDirection.MINIMIZE
    completed_trials.sort(key=lambda t: t.value, reverse=not is_minimize)

    top_trials = completed_trials[: args.top_n]

    logging.info(
        f"Found {len(completed_trials)} completed trials. Exporting and coercing top {len(top_trials)}."
    )

    out_base = (
        Path(args.output_dir)
        / f"race_type={args.race_type}"
        / f"study={study_name}"
        / "top_trials"
    )
    out_base.mkdir(parents=True, exist_ok=True)

    for i, t in enumerate(top_trials):
        coerced_params = coerce_params(t.params, expected_ranges)
        file_path = out_base / f"rank_{i+1}_trial_{t.number}.json"
        with open(file_path, "w") as f:
            json.dump(coerced_params, f, indent=2)
        
        logging.info(f"Rank {i+1}: Trial {t.number} (Value: {t.value:.4f}) -> {file_path}")
        # Log if any parameter was coerced
        for k, v in t.params.items():
            if k in coerced_params and coerced_params[k] != v:
                logging.info(f"  Coerced {k}: {v} -> {coerced_params[k]}")


if __name__ == "__main__":
    main()
