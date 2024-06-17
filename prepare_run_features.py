import logging

import pandas as pd

import shared


# time RACE_TYPE=ve FORECAST_YEAR=2022 poetry run python prepare_run_features.py

# os.environ['FORECAST_YEAR'] = "2019"


def combine_estimates_with_running_order():
    running_order_with_estimates = _load_pymc_history_values_for_running_order_names()

    estimates = running_order_with_estimates.rename(columns={"ro_orig_name": "name", "leg_dist": "dist"})

    path = f"data/running_order_with_estimates_{shared.race_id_str()}.tsv"
    estimates.to_csv(path, sep="\t", index=False)
    logging.info(f'Wrote: {path}')

    shared.log_df(estimates[['num_runs', "log_std", "log_mean"]].groupby('num_runs').agg(["mean"]).round(2))


def _load_pymc_history_values_for_running_order_names():
    # unique_name	num_runs	name	team_id	team	team_country	year	pace	emit	leg	median_pace	log_stdev
    runs = pd.read_csv(f'data/long_runs_and_running_order_{shared.race_id_str()}.tsv', delimiter='\t')
    # runs = runs.dropna(subset=['pace'])
    # runs["log_pace"] = np.log(runs["pace"])
    running_order = runs[runs['year'] == shared.forecast_year()]

    results_dir = '~/koodi/Statistical-Rethinking/pymc5-stats-rethink/results/fulldata-jax-v9'
    # results_dir = '~/koodi/Statistical-Rethinking/pymc5-stats-rethink/results/jax-dev'
    path = f'{results_dir}/pymc5_v3_estimates_{shared.race_id_str()}.tsv'

    history_estimates = pd.read_csv(path, delimiter='\t')
    history_estimates.info()
    history_estimates = history_estimates.drop(columns=['num_runs', 'median_pace'])

    missing_estimate_0 = history_estimates[history_estimates['log_mean'].isna()]
    logging.info(
        f'Found {len(missing_estimate_0)} runners without history estimate:\n{missing_estimate_0.to_string(index=False)}')
    assert len(missing_estimate_0) == 0, "All should have estiamte pace"

    running_order_with_estimates = pd.merge(running_order, history_estimates, on='unique_name', how='left',
                                            suffixes=['_ro', '_history']).reset_index()

    shared.log_df(running_order_with_estimates[['unique_name', 'num_runs', 'log_mean']])

    debug_df = running_order_with_estimates[running_order_with_estimates['unique_name'].str.contains('jonna virtanen')]
    shared.log_df(debug_df[['unique_name', 'num_runs', 'log_mean', 'log_std']])

    # TODO team is currently, team_base_name
    running_order_with_estimates = running_order_with_estimates[[
        'team_id', 'team', 'team_country', 'leg', 'leg_dist', 'unique_name', 'ro_orig_name',
        'num_runs', 'log_mean', 'log_std',
        'personal_start_95', 'personal_end_95', 'pace_samples',
    ]]
    logging.info(
        f"running_order_with_estimates {len(running_order_with_estimates)} rows, columns: {running_order_with_estimates.columns}")

    missing_estimate = running_order_with_estimates[running_order_with_estimates['log_mean'].isna()]
    logging.info(f'Found {len(missing_estimate)} runners without estimate:\n{missing_estimate.to_string(index=False)}')

    # TODO HACK: just add the median for all unknown runners
    fresh_runners = running_order_with_estimates['num_runs'] <= 2
    log_pace_median = running_order_with_estimates[fresh_runners]['log_mean'].dropna().median()
    running_order_with_estimates['log_mean'] = running_order_with_estimates['log_mean'].fillna(log_pace_median)
    log_pace_std_median = running_order_with_estimates[fresh_runners]['log_std'].dropna().median()
    running_order_with_estimates['log_std'] = running_order_with_estimates['log_std'].fillna(log_pace_std_median)

    running_order_with_estimates.info()

    return running_order_with_estimates


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s [%(threadName)s] %(funcName)s [%(levelname)s] %(message)s')
    logging.info("Creating static individual estimates for running order")
    combine_estimates_with_running_order()
