import logging
import numpy as np
import polars as pl
from scipy import stats
from dataclasses import dataclass

import shared

@dataclass
class BoxCoxParams:
    lmbda: float
    bc_mean: float
    bc_std: float

def standardize(series: np.ndarray | pl.Series) -> tuple[np.ndarray | pl.Series, float, float]:
    mean = float(np.nanmean(series))
    std = float(np.nanstd(series))
    return (series - mean) / std, mean, std

def fake_standardize(series: np.ndarray | pl.Series) -> tuple[np.ndarray | pl.Series, float, float]:
    mean = 0
    std = 1
    return (series - mean) / std, mean, std

def boxcox_and_normalize(values: np.ndarray | pl.Series, params: BoxCoxParams) -> np.ndarray:
    """Box-Cox transform and normalize out-of-sample values"""
    bc_transformed = stats.boxcox(values, lmbda=params.lmbda)
    return (bc_transformed - params.bc_mean) / params.bc_std

def inverse_normalized_and_boxcox(normalized_bc_values: np.ndarray, params: BoxCoxParams) -> np.ndarray:
    # Reverse normalization
    data_unnormalized = normalized_bc_values * params.bc_std + params.bc_mean
    # Reverse Box-Cox
    if params.lmbda == 0:
        data_untransformed = np.exp(data_unnormalized)
    else:
       # Calculate the term inside the power operation
        inside = data_unnormalized * params.lmbda + 1
        # Clip to a small positive value to avoid negatives/zero
        inside = np.clip(inside, 1e-6, None)
        data_untransformed = inside ** (1 / params.lmbda)
    
    return data_untransformed

def fit_boxcox_and_normalize(
    runs_df: pl.DataFrame, 
    history_reference_df: pl.DataFrame
) -> tuple[np.ndarray | pl.Series, BoxCoxParams]:
    """Fits Box-Cox parameters on historical data and transforms both paces and terrain coefficients."""
    
    capped_paces = np.clip(runs_df["pace"].to_numpy(), a_min=4, a_max=40)
    history_capped_paces = np.clip(history_reference_df["pace"].to_numpy(), a_min=4, a_max=40)
    
    no_nans_history_capped_paces = history_capped_paces[~np.isnan(history_capped_paces)]
    logging.info(
        f'history capped paces: {min(no_nans_history_capped_paces)} - {max(no_nans_history_capped_paces)}'
    )
    
    _, race_specific_bc_lambda = stats.boxcox(no_nans_history_capped_paces)
    history_bc_transformed_paces = stats.boxcox(
        no_nans_history_capped_paces,
        lmbda=race_specific_bc_lambda,
    )
    _, bc_mean, bc_std = fake_standardize(history_bc_transformed_paces)
    
    bc_transformed_paces = stats.boxcox(capped_paces, lmbda=race_specific_bc_lambda)
    normalized_bc_paces = (bc_transformed_paces - bc_mean) / bc_std

    boxcox_params = BoxCoxParams(lmbda=race_specific_bc_lambda, bc_mean=bc_mean, bc_std=bc_std)
    
    logging.info(
        f'{shared.race_id_str()} {race_specific_bc_lambda=}, {boxcox_params=}'
    )
    
    return normalized_bc_paces, boxcox_params
