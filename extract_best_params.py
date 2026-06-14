#!/usr/bin/env python3
import argparse
import json
import logging
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import optuna
from optuna.storages import JournalStorage
from optuna.storages.journal import JournalFileBackend
from optuna.trial import TrialState


def _is_discrete(values):
    """Treat a parameter as discrete (use mode) if every observed value is
    integer-valued; continuous (use median) otherwise. Optuna stores stepped
    ints as ints and floats as floats, so this matches the search space."""
    return all(isinstance(v, int) or (isinstance(v, float) and float(v).is_integer())
               for v in values)


def _consensus_value(name, values, trial_weights):
    """Mode for discrete params (ties broken toward better-scoring trials),
    median for continuous params. `trial_weights` ranks each contributing trial
    so a tie in the mode is decided by trial quality, not file order."""
    if _is_discrete(values):
        counts = Counter(values)
        top = max(counts.values())
        tied = [v for v, c in counts.items() if c == top]
        if len(tied) == 1:
            return type(values[0])(tied[0]), "mode"
        # tie-break: pick the tied value whose trials scored best (lowest weight)
        best = min(tied, key=lambda val: min(
            w for v, w in zip(values, trial_weights) if v == val))
        return type(values[0])(best), "mode(tie->best)"
    return float(statistics.median(values)), "median"


def build_consensus(top_trials):
    """top_trials: list of optuna trials, already sorted best-first.
    Returns (consensus_params, per_param_method)."""
    param_names = sorted({k for t in top_trials for k in t.params})
    consensus, methods = {}, {}
    # weight = rank index (0 = best); used only for mode tie-breaks
    weights = list(range(len(top_trials)))
    for name in param_names:
        vals, w = [], []
        for rank, t in enumerate(top_trials):
            if name in t.params:
                vals.append(t.params[name])
                w.append(weights[rank])
        if not vals:
            continue
        consensus[name], methods[name] = _consensus_value(name, vals, w)
    return consensus, methods


def main():
    parser = argparse.ArgumentParser(
        description="Extract best and consensus parameters from an Optuna study."
    )
    parser.add_argument("--race-type", required=True, choices=["ju", "ve", "ke"])
    parser.add_argument("--study-name", help="Optuna study name")
    parser.add_argument("--journal-path",
                        help="default: .optuna/reviewed-journal-{race-type}.log")
    parser.add_argument("--output-dir", default="best-params")
    parser.add_argument(
        "--top-trials-for-consensus", type=int, default=5,
        help="Number of top trials aggregated into consensus.json (default: 5)")
    parser.add_argument(
        "--trial-min", type=int, default=None,
        help="Consider only trials with number >= trial_min (post-feature-change cutoff)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")

    study_name = args.study_name or f"v6-tuning-{args.race_type}"
    journal_path = Path(args.journal_path
                        or f".optuna/reviewed-journal-{args.race_type}.log")
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

    completed = [t for t in study.trials
                 if t.state == TrialState.COMPLETE and t.value is not None]
    if args.trial_min is not None:
        completed = [t for t in completed if t.number >= args.trial_min]
    if not completed:
        logging.error("No completed trials found in the study.")
        return

    is_min = study.direction == optuna.study.StudyDirection.MINIMIZE
    completed.sort(key=lambda t: t.value, reverse=not is_min)

    best_trial = completed[0]
    n = min(args.top_trials_for_consensus, len(completed))
    top_trials = completed[:n]
    consensus_params, methods = build_consensus(top_trials)

    extraction_time = datetime.now(timezone.utc).isoformat()
    top_numbers = [t.number for t in top_trials]
    top_values = [t.value for t in top_trials]
    score_spread = (max(top_values) - min(top_values)) if len(top_values) > 1 else 0.0

    # Flag where consensus disagrees with the single best trial.
    disagreements = {
        k: {"best": best_trial.params.get(k), "consensus": v}
        for k, v in consensus_params.items()
        if k in best_trial.params and best_trial.params[k] != v
           and not (isinstance(v, float) and isinstance(best_trial.params[k], (int, float))
                    and abs(v - best_trial.params[k]) < 1e-9)
    }

    out_dir = (Path(args.output_dir)
               / f"race_type={args.race_type}"
               / f"study={study_name}")
    out_dir.mkdir(parents=True, exist_ok=True)

    best_doc = {
        "meta": {
            "kind": "single_best",
            "study_name": study_name,
            "race_type": args.race_type,
            "trial_referenced": best_trial.number,
            "trial_value": best_trial.value,
            "direction": "minimize" if is_min else "maximize",
            "trial_min_cutoff": args.trial_min,
            "extraction_time_utc": extraction_time,
        },
        "params": best_trial.params,
    }
    consensus_doc = {
        "meta": {
            "kind": "consensus",
            "study_name": study_name,
            "race_type": args.race_type,
            "trials_referenced": top_numbers,
            "trials_referenced_count": n,
            "trial_values": top_values,
            "trial_value_best": min(top_values) if is_min else max(top_values),
            "trial_value_spread": score_spread,
            "aggregation_method_per_param": methods,
            "disagreement_with_best": disagreements,
            "direction": "minimize" if is_min else "maximize",
            "trial_min_cutoff": args.trial_min,
            "extraction_time_utc": extraction_time,
        },
        "params": consensus_params,
    }

    best_path = out_dir / "params.json"
    consensus_path = out_dir / "consensus.json"
    with open(best_path, "w") as f:
        json.dump(best_doc, f, indent=2)
    with open(consensus_path, "w") as f:
        json.dump(consensus_doc, f, indent=2)

    logging.info(f"Best trial {best_trial.number} (value {best_trial.value:.4f}) -> {best_path}")
    logging.info(f"Consensus over {n} trials {top_numbers} -> {consensus_path}")
    logging.info(f"Consensus score spread across top {n}: {score_spread:.4f} "
                 f"(noise floor ~0.015; a spread near/below this means a flat basin)")
    if disagreements:
        for k, d in disagreements.items():
            logging.info(f"  consensus differs from best on {k}: best={d['best']} consensus={d['consensus']}")
    else:
        logging.info("  consensus matches single best on every parameter")

    print(json.dumps(consensus_doc, indent=2))


if __name__ == "__main__":
    main()