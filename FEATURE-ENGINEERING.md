# Feature Engineering Documentation for ngBoost-Norm-Tuned-Reviewed

This document comprehensively details the complex feature engineering pipeline used in addition to the ngBoost model in the `ngboost-norm-tuned-reviewed.ipynb` notebook. The feature engineering transforms raw race data into sophisticated features that capture runner characteristics, historical performance patterns, team dynamics, and contextual modifiers.

---

## Table of Contents

1. [Data Foundation and Preprocessing](#1-data-foundation-and-preprocessing)
2. [Historical Performance Features](#2-historical-performance-features)
3. [Team-Based Features](#3-team-based-features)
4. [Country-Based Hierarchical Bayesian Prior Features](#4-country-based-hierarchical-bayesian-prior-features)
5. [Interaction Features](#5-interaction-features)
6. [Feature Selection and Final Model](#6-feature-selection-and-final-model)
7. [Data Leakage Prevention (Commented Out)](#7-data-leakage-prevention-commented-out)
8. [Train/Validation/Test Split](#8-trainvalidationtest-split)
9. [ngBoost Model Integration](#9-ngboost-model-integration)
10. [Key Design Principles](#10-key-design-principles)
11. [Appendices](#11-appendices)

---

## 1. Data Foundation and Preprocessing

### 1.1 Box-Cox Transformation of Target Variable

The target variable (race time) undergoes a **Box-Cox transformation** to normalize the distribution:

```python
bc_pace = (df['bc_pace_lambda'] * (df['tc'].max() - df['tc']) + df['tc']) / df['bc_pace_lambda'] / df['tc']
```

This transforms the raw total time (`tc`) into a normalized pace value (`bc_pace`) that serves as the primary regression target. The transformation is applied per-leg and per-race, with the lambda parameter estimated from the data.

### 1.2 Base Features (Computed for Every Row)

The following base features are computed for every row in the dataset during the `compute_features()` function:

| Feature | Description |
|---------|-------------|
| `leg` | Integer leg number (1-based), extracted from the `leg` column |
| `first_time` | Boolean: True if this is the runner's first recorded time |
| `run_num_norm` | Normalized run number within the leg: `(run_num - 1) / (max_run_num_in_leg - 1)` |
| `run_num` | Raw run number (position in running order within the leg) |
| `roll_5y_years_since_results` | Years since the most recent result: `2026 - max(year)` |
| `tc` | Total time for the leg in seconds |
| `vc` | Vertical climb for the leg in meters |
| `vn` | Vertical descent for the leg in meters |
| `distance` | Distance of the leg in meters (from `runner_df`, filled with 1000m default) |
| `normalized_tc` | **Central feature**: `log(tc / distance) * 10000` — log-normalized pace |
| `vcn` | **Central feature**: `(vc - vn) / distance * 1000` — net vertical per distance |
| `vcn_bc_pace` | **Central feature**: `vcn / bc_pace * 100` — normalized pace adjusted for vertical |
| `marking_norm` | **Central feature**: Normalized marking value from competitor data |
| `vertical_coef` | **Central feature**: `vcn / (vcn + 15)` — saturated vertical coefficient (asymptote at 15) |
| `terrain_coefficient` | **Central feature**: `log(distance / 1000) / log(45 / 1000)` — terrain difficulty (asymptote at 4500m) |
| `fn_scaled_pace` | **Central feature**: `(bc_pace - 160) / 380` — normalized from national championship pace (160s/km men, 380s/km women) |
| `normalized_team_id` | Numerical encoding of team affiliation |

### 1.3 Derived Pace Columns

Two additional pace columns are created for use in historical feature computation:

```python
df['tcn_bc_pace'] = df['vcn_bc_pace']  # Primary pace metric for historical features
df['leg_bcp'] = df['bc_pace']             # Raw BC pace for leg-specific features
```

**Note**: `tcn_bc_pace` is simply an alias for `vcn_bc_pace`, the vertical-adjusted normalized pace. This is the primary metric used throughout the historical feature computation.

### 1.4 Data Preparation

After computing features, the dataset is filtered:
- **Drop rows with missing values** in key columns (`bc_pace`, `bc_pace_lambda`, `tc`, `vcn_bc_pace`)
- **Drop rows where `bc_pace_lambda <= 0`** (invalid Box-Cox transformation)
- **Drop rows where `bc_pace_lambda is NaN`**
- **Drop rows with `tc > 30000`** (outlier detection: >8.3 hours)
- **Drop rows with `bc_pace > 1000`** (outlier: >16:40/km pace)
- **Drop rows with `bc_pace < 10`** (outlier: <0:10/km pace)
- **Drop rows with `distance > 100000`** (outlier: >100km leg)

After filtering, the dataset is sorted by `unique_name` and `run_num` to ensure proper ordering for historical feature computation.

---

## 2. Historical Performance Features

Historical features are computed using a **group-by-unique_name** aggregation, meaning all features are computed per-runner across all their historical records. This is the most computationally intensive part of the pipeline, involving multiple rolling windows and statistical measures.

### 2.1 Rolling Windows

Three rolling windows are used for per-runner historical computation:

| Window | Purpose |
|--------|---------|
| **5** | Short-term performance (last ~5 results) |
| **10** | Medium-term performance (last ~10 results) |
| **15** | Longer-term performance (last ~15 results) |

Additionally, **cumulative** (full history) features are computed using `.cummax()` and cumulative operations.

### 2.2 Central Tendency Features

These features capture the typical/average performance of a runner:

| Feature | Description |
|---------|-------------|
| `history_bcp_median` | **Long-term anchor**: Median of all `bc_pace` values (cumulative) |
| `history_bcp_mean` | Mean of all `bc_pace` values (cumulative) |
| `roll_5y_tcn_bcp_mean` | **Short-term indicator**: Rolling-5 median of `vcn_bc_pace` |
| `roll_10y_tcn_bcp_mean` | Rolling-10 median of `vcn_bc_pace` |
| `roll_15y_tcn_bcp_mean` | Rolling-15 median of `vcn_bc_pace` |
| `roll_5y_bcp_mean` | Rolling-5 mean of `bc_pace` |
| `roll_10y_bcp_mean` | Rolling-10 mean of `bc_pace` |
| `roll_15y_bcp_mean` | Rolling-15 mean of `bc_pace` |

### 2.3 Dispersion Features

These features capture the variability/consistency of a runner's performance:

| Feature | Description |
|---------|-------------|
| `history_tcn_bcp_std` | **Long-term anchor**: Std of all `vcn_bc_pace` values (cumulative) |
| `roll_5y_tcn_bcp_std` | Rolling-5 std of `vcn_bc_pace` |
| `roll_10y_tcn_bcp_std` | Rolling-10 std of `vcn_bc_pace` |
| `roll_15y_tcn_bcp_std` | Rolling-15 std of `vcn_bc_pace` |
| `roll_5y_bcp_std` | Rolling-5 std of `bc_pace` |
| `roll_10y_bcp_std` | Rolling-10 std of `bc_pace` |
| `roll_15y_bcp_std` | Rolling-15 std of `bc_pace` |

### 2.4 Shape Features (Skewness and Kurtosis)

These features capture the distribution shape of a runner's performance:

| Feature | Description |
|---------|-------------|
| `roll_5y_tcn_bcp_skew` | Rolling-5 skewness of `vcn_bc_pace` |
| `roll_10y_tcn_bcp_skew` | Rolling-10 skewness of `vcn_bc_pace` |
| `roll_15y_tcn_bcp_skew` | Rolling-15 skewness of `vcn_bc_pace` |
| `roll_5y_tcn_bcp_kurtosis` | Rolling-5 kurtosis of `vcn_bc_pace` |
| `roll_10y_tcn_bcp_kurtosis` | Rolling-10 kurtosis of `vcn_bc_pace` |
| `roll_15y_tcn_bcp_kurtosis` | Rolling-15 kurtosis of `vcn_bc_pace` |

### 2.5 Robustness Features (IQR and Median-Mean Difference)

These features use robust statistics less sensitive to outliers:

| Feature | Description |
|---------|-------------|
| `roll_5y_tcn_bcp_iqr` | Rolling-5 interquartile range (IQR) of `vcn_bc_pace` |
| `roll_10y_tcn_bcp_iqr` | Rolling-10 IQR |
| `roll_15y_tcn_bcp_iqr` | Rolling-15 IQR |
| `roll_5y_tcn_bcp_med_mean_diff` | Rolling-5 median minus mean of `vcn_bc_pace` |
| `roll_10y_tcn_bcp_med_mean_diff` | Rolling-10 difference |
| `roll_15y_tcn_bcp_med_mean_diff` | Rolling-15 difference |

### 2.6 Min/Max Features

| Feature | Description |
|---------|-------------|
| `roll_5y_tcn_bcp_min` | Rolling-5 minimum `vcn_bc_pace` (best recent performance) |
| `roll_10y_tcn_bcp_min` | Rolling-10 minimum |
| `roll_15y_tcn_bcp_min` | Rolling-15 minimum |
| `roll_5y_tcn_bcp_max` | Rolling-5 maximum `vcn_bc_pace` (worst recent performance) |
| `roll_10y_tcn_bcp_max` | Rolling-10 maximum |
| `roll_15y_tcn_bcp_max` | Rolling-15 maximum |

### 2.7 Derived Historical Features

Additional features computed from the base historical statistics:

| Feature | Description |
|---------|-------------|
| `history_tcn_bcp_std_diff` | **Derived**: `history_bcp_mean - history_bcp_median` (mean-median difference from full history) |
| `roll_5y_history_std_ratio` | **Derived**: `roll_5y_tcn_bcp_std / history_tcn_bcp_std` — recent-vs-long-term variability ratio |
| `roll_5y_history_mean_ratio` | **Derived**: `roll_5y_tcn_bcp_mean / history_bcp_mean` — recent-vs-long-term performance ratio |

### 2.8 Pace Leg Ratio Features

These features capture performance relative to the runner's typical pace:

| Feature | Description |
|---------|-------------|
| `pace_leg_ratio` | **Computed per row**: `bc_pace / leg_bcp` — ratio of this leg's pace to the runner's BC pace |
| `roll_5y_pace_leg_ratio_mean` | Rolling-5 mean of pace_leg_ratio |
| `roll_10y_pace_leg_ratio_mean` | Rolling-10 mean |
| `roll_15y_pace_leg_ratio_mean` | Rolling-15 mean |
| `roll_5y_pace_leg_ratio_std` | Rolling-5 std of pace_leg_ratio |
| `roll_10y_pace_leg_ratio_std` | Rolling-10 std |
| `roll_15y_pace_leg_ratio_std` | Rolling-15 std |
| `roll_5y_pace_leg_ratio_min` | Rolling-5 minimum |
| `roll_10y_pace_leg_ratio_min` | Rolling-10 minimum |
| `roll_15y_pace_leg_ratio_min` | Rolling-15 minimum |
| `roll_5y_pace_leg_ratio_max` | Rolling-5 maximum |
| `roll_10y_pace_leg_ratio_max` | Rolling-10 maximum |
| `roll_15y_pace_leg_ratio_max` | Rolling-15 maximum |

### 2.9 Terrain/Vertical Specific Features

Features specific to terrain and vertical conditions:

| Feature | Description |
|---------|-------------|
| `roll_5y_tc_mean` | Rolling-5 mean of total time (`tc`) |
| `roll_10y_tc_mean` | Rolling-10 mean of `tc` |
| `roll_15y_tc_mean` | Rolling-15 mean of `tc` |
| `roll_5y_tc_std` | Rolling-5 std of `tc` |
| `roll_10y_tc_std` | Rolling-10 std of `tc` |
| `roll_15y_tc_std` | Rolling-15 std of `tc` |
| `roll_5y_vc_mean` | Rolling-5 mean of vertical climb (`vc`) |
| `roll_10y_vc_mean` | Rolling-10 mean of `vc` |
| `roll_15y_vc_mean` | Rolling-15 mean of `vc` |
| `roll_5y_vc_std` | Rolling-5 std of `vc` |
| `roll_10y_vc_std` | Rolling-10 std of `vc` |
| `roll_15y_vc_std` | Rolling-15 std of `vc` |
| `roll_5y_vn_mean` | Rolling-5 mean of vertical descent (`vn`) |
| `roll_10y_vn_mean` | Rolling-10 mean of `vn` |
| `roll_15y_vn_mean` | Rolling-15 mean of `vn` |
| `roll_5y_vn_std` | Rolling-5 std of `vn` |
| `roll_10y_vn_std` | Rolling-10 std of `vn` |
| `roll_15y_vn_std` | Rolling-15 std of `vn` |

### 2.10 Summary Historical Features

Aggregated across all historical features for a summary statistic:

| Feature | Description |
|---------|-------------|
| `history_mean_num_features` | Count of non-null values in history-based features |
| `history_roll_mean_num_features` | Count of non-null values in rolling history features |
| `history_roll_mean_num_features_5` | Count of non-null values in rolling-5 features |
| `history_roll_mean_num_features_10` | Count of non-null values in rolling-10 features |
| `history_roll_mean_num_features_15` | Count of non-null values in rolling-15 features |

---

## 3. Team-Based Features

### 3.1 Other Team Members Features

These features aggregate statistics about a runner's teammates (excluding the focal runner):

```python
# Group by team_and_country_bucket, exclude the focal runner
temp_df = all_times_df.groupby('team_and_country_bucket').sum_cols(
    exclude_col='unique_name',    # Exclude focal runner's name
    exclude_value=runner_name,    # Exclude this specific runner
    numeric_only=True
)
```

| Feature | Description |
|---------|-------------|
| `other_team_members_roll_5y_tcn_bcp_mean` | Mean of rolling-5 `vcn_bc_pace` of teammates |
| `other_team_members_roll_5y_tcn_bcp_std` | Std of rolling-5 `vcn_bc_pace` of teammates |
| `other_team_members_with_history` | Count of teammates with historical data |
| `other_team_members_total` | Total count of teammates |

**Note**: These features are designed to capture team dynamics and the collective strength of the team.

### 3.2 Team Bucket Features

Team identification is derived from the `team_and_country_bucket` column, which groups teams by their country affiliation:

```python
df['normalized_team_id'] = df['team_and_country_bucket'].factorize()[0] + 1
```

This creates a numerical encoding of team affiliation, where teams sharing the same country bucket receive the same ID.

---

## 4. Country-Based Hierarchical Bayesian Prior Features

### 4.1 Country Bucketing

Runners are grouped by country using the `country_bucket` column:

```python
country_groups = df.groupby('country_bucket')
```

### 4.2 Country-Level Statistics

For each country bucket, the following statistics are computed:

| Feature | Description |
|---------|-------------|
| `c_bcp_median` | Median `bc_pace` within the country bucket |
| `c_bcp_std` | Std `bc_pace` within the country bucket |
| `c_num_runs` | Total number of runs by runners in this country bucket |
| `c_n_unique_runners` | Number of unique runners in this country bucket |

### 4.3 Fallback to Global Statistics

If a country bucket has insufficient data (fewer than 5 runs), features fall back to global statistics:

| Feature | Description |
|---------|-------------|
| `c_bcp_median_fallback` | Global median (used when `c_num_runs < 5`) |
| `c_bcp_std_fallback` | Global std (used when `c_num_runs < 5`) |

### 4.4 Country Prior-Adjusted Historical Features

The country-level statistics are combined with individual historical statistics to create Bayesian-prior-adjusted features:

| Feature | Description |
|---------|-------------|
| `c_bcp_adj_median` | Country-median-adjusted median: weighted combination of individual median and country median |
| `c_bcp_adj_std` | Country-median-adjusted std |
| `c_bcp_adj_median_ti` | Time-indexed version of adjusted median |
| `c_bcp_adj_std_ti` | Time-indexed version of adjusted std |

### 4.5 Country Prior Interaction Features

These features interact the country prior statistics with other model features:

| Feature | Description |
|---------|-------------|
| `c_bcp_median_nti_interaction` | `normalized_team_id * c_bcp_median` |
| `c_bcp_median_marking_interaction` | `marking_norm * c_bcp_median` |
| `c_bcp_median_tc_interaction` | `tc * c_bcp_median` |
| `c_bcp_median_vc_interaction` | `vertical_coef * c_bcp_median` |

---

## 5. Interaction Features

Interaction features capture non-linear relationships and synergies between base features and historical statistics. These are critical for the model to learn complex patterns.

### 5.1 Historical × Terrain Interactions

| Feature | Formula |
|---------|---------|
| `roll_tcn_bcp_med_mean_diff_tc_interaction` | `roll_tcn_bcp_med_mean_diff * terrain_coefficient` |
| `roll_vcn_bcp_mean_tc_interaction` | `roll_vcn_bcp_mean / terrain_coefficient` |

### 5.2 Historical × Vertical Interactions

| Feature | Formula |
|---------|---------|
| `roll_vcn_bcp_mean_vc_interaction` | `roll_vcn_bcp_mean * vertical_coef` |

### 5.3 Historical × Marking Interactions

| Feature | Formula |
|---------|---------|
| `roll_vcn_bcp_mean_marking_interaction` | `roll_vcn_bcp_mean / marking_norm` |

### 5.4 Scaled Pace × Feature Interactions

| Feature | Formula |
|---------|---------|
| `fn_scaled_pace_tc_interaction` | `terrain_coefficient * fn_scaled_pace` |
| `fn_scaled_pace_c_bcp_median_vc_interaction` | `vertical_coef * fn_scaled_pace * c_bcp_median` |

---

## 6. Feature Selection and Final Model

### 6.1 Initial Feature List

The initial feature list comprises **~150 features** (including base, historical, team, country, interaction, and leg dummy features). This is the complete set before any selection or filtering.

### 6.2 Features Used in the Final Model (After first_pass_drops)

The following features are **active** in the final model (after removing `first_pass_drops`):

#### Core Features (6)
| Feature | Description |
|---------|-------------|
| `leg` | Integer leg number |
| `first_time` | Boolean: first time for this runner |
| `run_num_norm` | Normalized run number |
| `roll_5y_years_since_results` | Years since most recent result |
| `normalized_team_id` | Numerical team ID |
| `history_bcp_median` | Long-term median anchor |

#### Historical Central Tendency (3 active)
| Feature | Description |
|---------|-------------|
| `roll_5y_tcn_bcp_mean` | **Short-term indicator**: Rolling-5 median |

#### Historical Dispersion (3 active)
| Feature | Description |
|---------|-------------|
| `roll_5y_tcn_bcp_std` | Rolling-5 std |

#### Historical Shape (2 active)
| Feature | Description |
|---------|-------------|
| *(None — both skew and kurtosis dropped)* |

#### Historical Robustness (1 active)
| Feature | Description |
|---------|-------------|
| `roll_5y_tcn_bcp_min` | Rolling-5 minimum |

#### Pace Leg Ratio (3 active)
| Feature | Description |
|---------|-------------|
| `roll_5y_pace_leg_ratio_mean` | Rolling-5 mean ratio |
| `roll_pace_leg_ratio_std` | Rolling std |

#### Terrain/Vertical (1 active)
| Feature | Description |
|---------|-------------|
| `roll_5y_tc_mean` | Rolling-5 mean tc |

#### Scaled Pace (2 active)
| Feature | Description |
|---------|-------------|
| `fn_scaled_pace` | National championship scaled pace |
| `fn_scaled_pace_tc_interaction` | Terrain × scaled pace |
| `fn_scaled_pace_c_bcp_median_vc_interaction` | Vertical × scaled pace × country median |

#### Team Features (2 active)
| Feature | Description |
|---------|-------------|
| `other_team_members_roll_5y_tcn_bcp_mean` | Teammates' rolling-5 mean |
| `other_team_members_with_history` | Teammates with history |

#### Country Prior Interactions (2 active)
| Feature | Description |
|---------|-------------|
| `c_bcp_median_nti_interaction` | Team ID × country median |

#### Historical × Terrain/Vertical/Marking Interactions (3 active)
| Feature | Description |
|---------|-------------|
| `roll_tcn_bcp_med_mean_diff_tc_interaction` | Med-mean diff × terrain |
| `roll_vcn_bcp_mean_tc_interaction` | Rolling mean / terrain |
| `roll_vcn_bcp_mean_vc_interaction` | Rolling mean × vertical |
| `roll_vcn_bcp_mean_marking_interaction` | Rolling mean / marking |

### 6.3 first_pass_drops (Removed from Final Model)

The following **11 features** are explicitly removed via `first_pass_drops`:

| Feature | Reason for Removal |
|---------|-------------------|
| `roll_5y_history_std_ratio` | Redundant with std features |
| `roll_tcn_bcp_skew` | Shape feature, noisy |
| `roll_tcn_bcp_kurtosis` | Shape feature, noisy |
| `roll_tcn_bcp_iqr` | Redundant with std |
| `roll_tcn_bcp_med_mean_diff` | Redundant with med_mean_diff_tc_interaction |
| `history_tcn_bcp_std` | Redundant with rolling std |
| `history_tcn_bcp_std_diff` | Redundant with rolling std diff |
| `roll_vcn_bcp_std` | Redundant with other std |
| `roll_pace_leg_ratio_std` | Redundant with pace_leg_ratio_mean |
| `roll_5y_history_mean_ratio` | Redundant with history_std_ratio |

### 6.4 leaky_until_rebuilt (Placeholder)

Currently empty. This list is reserved for features that require per-runner rebuilds to prevent data leakage.

---

## 7. Data Leakage Prevention (Commented Out)

**CRITICAL**: The data leakage prevention code is **currently commented out** (wrapped in `"""`). The following features would be zeroed for `run_num > 2`:

| Feature | Description |
|---------|-------------|
| `roll_5y_tcn_bcp_mean` | Rolling-5 mean |
| `roll_5y_pace_leg_ratio_mean` | Rolling-5 pace ratio mean |
| `roll_5y_pace_leg_ratio_std` | Rolling-5 pace ratio std |
| `roll_5y_pace_leg_ratio_min` | Rolling-5 pace ratio min |
| `roll_5y_pace_leg_ratio_max` | Rolling-5 pace ratio max |
| `roll_5y_tc_mean` | Rolling-5 tc mean |
| `roll_5y_tc_std` | Rolling-5 tc std |
| `roll_5y_vc_mean` | Rolling-5 vc mean |
| `roll_5y_vc_std` | Rolling-5 vc std |
| `roll_5y_vn_mean` | Rolling-5 vn mean |
| `roll_5y_vn_std` | Rolling-5 vn std |
| `other_team_members_roll_5y_tcn_bcp_mean` | Team members rolling-5 mean |
| `other_team_members_with_history` | Team members with history |

**Rationale**: These features depend on the running order (which runners follow whom), which is not known before the race starts. Zeroing them for `run_num > 2` prevents data leakage by replacing future-dependent features with zero (representing "unknown" or "average" values).

**However**, this code is **NOT currently executed** due to the `"""` wrapper.

---

## 8. Train/Validation/Test Split

### 8.1 Sampling Method

```python
df['strata_key'] = df.apply(lambda r: f"{r['unique_name']}_r{int(r['run_num'])}", axis=1)
sample = df.groupby('strata_key')['tc'].mean().sample(n=15, replace=False)
```

- **Strata key**: `{unique_name}_r{run_num}` — unique identifier for each runner-leg combination
- **Sampling unit**: The mean of `tc` for each strata key
- **Sample size**: 15 samples
- **Method**: Without replacement (`replace=False`)

### 8.2 Split Structure

The 15 samples are split into:
- **Training**: 60% (9 samples)
- **Validation**: 20% (3 samples)
- **Test**: 20% (3 samples)

### 8.3 Important Note

The split is performed on **strata-level aggregates** (mean tc per runner-leg combination), not on individual rows. This means all rows belonging to the same strata key end up in the same split.

---

## 9. ngBoost Model Integration

### 9.1 Model Configuration

```python
ngBoostModel = ngboost.NGBaseRegressor(
    V=BoostedV,           # Custom variance-weighted boosting
    L=LogLikelihood,      # Log-likelihood objective
    D=Dist,               # Normal distribution
    GBTask=GBTask,        # Custom GBDT task
    criterion='bootstrap',
    learning_rate=0.048255389170885296,
    max_depth=3,
    min_samples_leaf=2625,
    n_estimators=1317,
    natural_gradient=True,
    natural_gradient_niter=4,
    pred_int_quantiles=[0.1, 0.9],
    random_state=random_state,
)
```

### 9.2 Distribution and Loss Function

- **Distribution**: Normal (Gaussian)
- **Loss**: Negative Log-Likelihood (NLL)
- **Natural Gradient**: Enabled (4 iterations per fit)

### 9.3 Evaluation Metric

```python
def calculate_metrics(actual, predicted_samples):
    mean_preds = predicted_samples.mean(axis=0)
    true_medians = actual['tc']
    
    # CRPS (Continuous Ranked Probability Score)
    crps_values = compute_crps(true_medians, mean_preds, actual['bc_pace'])
    
    # NLL (Negative Log-Likelihood)
    std_preds = predicted_samples.std(axis=0)
    nll = compute_nll(true_medians, std_preds, actual['bc_pace'])
```

- **Primary**: CRPS (lower is better)
- **Secondary**: NLL (lower is better)

---

## 10. Key Design Principles

1. **Log-Normalization**: All pace features use log normalization (`log(tc/distance) * 10000`) to handle the wide range of race times and ensure scale invariance.

2. **Multi-Window Historical Aggregation**: Features are computed across three rolling windows (5, 10, 15) to capture both short-term and long-term performance patterns.

3. **Robust Statistics**: Heavy use of median, IQR, and skewness/kurtosis to handle outliers in the data.

4. **Hierarchical Priors**: Country-level Bayesian priors provide regularization for runners with limited history.

5. **Interaction Features**: Extensive interaction features capture non-linear relationships between terrain, vertical climb, marking, and historical performance.

6. **Data Leakage Prevention**: Rolling features dependent on running order are zeroed for `run_num > 2` to prevent data leakage (currently commented out).

7. **Stratified Sampling**: Train/validation/test split uses strata keys based on runner-leg combinations to ensure representative samples.

8. **Box-Cox Transformation**: The target variable undergoes Box-Cox transformation to normalize the distribution and improve model performance.

---

## 11. Appendices

### Appendix A: Naming Conventions

| Prefix | Meaning |
|--------|---------|
| `history_` | Cumulative (full history) statistic |
| `roll_Ny_` | Rolling N-window statistic |
| `roll_tcn_` | Rolling on `tcn_bc_pace` (vertical-adjusted pace) |
| `roll_bcp_` | Rolling on `bc_pace` (Box-Cox pace) |
| `roll_vcn_` | Rolling on `vcn_bc_pace` (vertical-adjusted pace) |
| `c_` | Country-level bucket statistic |
| `fn_` | Function-derived / scaled feature |
| `normalized_` | Numerical encoding of categorical variable |

### Appendix B: Suffixes

| Suffix | Meaning |
|--------|---------|
| `_bcp` | Box-Cox pace |
| `_tcn` | Total time normalized (vcn_bc_pace) |
| `_vcn` | Vertical climb per distance |
| `_tc` | Total time |
| `_vc` | Vertical climb |
| `_vn` | Vertical descent |
| `_mean` | Mean |
| `_std` | Standard deviation |
| `_median` | Median |
| `_skew` | Skewness |
| `_kurtosis` | Kurtosis |
| `_iqr` | Interquartile range |
| `_med_mean_diff` | Median minus mean |
| `_min` | Minimum |
| `_max` | Maximum |
| `_ratio` | Ratio (division) |
| `_interaction` | Interaction (multiplication) |

### Appendix C: Feature Categories Summary

| Category | Count (approx) |
|----------|---------------|
| Base features | ~20 |
| Historical central tendency | ~21 |
| Historical dispersion | ~21 |
| Historical shape (skew/kurt) | ~12 |
| Historical robustness (IQR, med-mean) | ~12 |
| Pace leg ratio | ~18 |
| Terrain/vertical specific | ~24 |
| Team features | ~4 |
| Country prior | ~8 |
| Interaction features | ~15 |
| Summary historical | ~5 |
| **Total (before selection)** | **~150** |
| **Total (after first_pass_drops)** | **~139** |

### Appendix D: Data Flow Diagram

```
Raw Data (runner_df, competitors, leg_results)
    │
    ├─► compute_features() ────────────────────────────────┐
    │   │                                                    │
    │   ├─► Base features (normalized_tc, bc_pace, etc.)    │
    │   ├─► Derived pace columns (tcn_bc_pace, leg_bcp)     │
    │   └─► Filtering (drop NaN, outliers)                  │
    │                                                        │
    ├─► Historical features (groupby unique_name) ─────────┤
    │   ├─► Central tendency (median, mean)                 │
    │   ├─► Dispersion (std)                                │
    │   ├─► Shape (skewness, kurtosis)                      │
    │   ├─► Robustness (IQR, med-mean diff)                 │
    │   ├─► Min/Max                                         │
    │   ├─► Pace leg ratio                                  │
    │   └─► Terrain/vertical specific                       │
    │                                                        │
    ├─► Team features (groupby team_and_country_bucket) ───┤
    │   └─► Other team members statistics                   │
    │                                                        │
    ├─► Country prior (groupby country_bucket) ────────────┤
    │   ├─► Country statistics (median, std)                │
    │   ├─► Fallback to global                              │
    │   └─► Country prior-adjusted features                 │
    │                                                        │
    ├─► Interaction features ──────────────────────────────┤
    │   ├─► Historical × Terrain                            │
    │   ├─► Historical × Vertical                           │
    │   ├─► Historical × Marking                            │
    │   └─► Scaled pace × Features                          │
    │                                                        │
    └─► Feature selection (first_pass_drops) ────────────────┘
            │
            ▼
    Final Feature Set (~139 features)
            │
            ▼
    ngBoost Model Training
            │
            ▼
    CRPS + NLL Evaluation