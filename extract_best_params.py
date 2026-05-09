#!/usr/bin/env python3
import argparse
import json
import logging
from pathlib import Path

import optuna
from optuna.storages import JournalStorage
from optuna.storages.journal import JournalFileBackend


def main():
    parser = argparse.ArgumentParser(
        description="Extract best parameters from an Optuna study."
    )
    parser.add_argument(
        "--race-type",
        required=True,
        choices=["ju", "ve", "ke"],
        help="Race type (ju, ve, or ke)",
    )
    parser.add_argument(
        "--study-name", help="Optuna study name (default: v6-tuning-{race-type})"
    )
    parser.add_argument(
        "--journal-path",
        help="Optuna journal path (default: .optuna/reviewed-journal-{race-type}.log)",
    )
    parser.add_argument(
        "--output-dir",
        default="best-params",
        help="Base directory for output (default: best-params)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    study_name = args.study_name or f"v6-tuning-{args.race_type}"
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

    try:
        best_trial = study.best_trial
    except ValueError:
        logging.error("No completed trials found in the study.")
        return

    logging.info(f"Best Trial ID: {best_trial.number}")
    logging.info(f"Best Value (CRPS): {best_trial.value:.4f}")

    # Target path: {output_dir}/race_type={race_type}/study={study_name}/params.json
    output_path = (
        Path(args.output_dir)
        / f"race_type={args.race_type}"
        / f"study={study_name}"
        / "params.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(best_trial.params, f, indent=2)

    logging.info(f"Successfully saved best params to {output_path}")
    print(json.dumps(best_trial.params, indent=2))


if __name__ == "__main__":
    main()
