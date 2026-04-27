# Feature Engineering Documentation for ngBoost-Norm-Tuned-Reviewed

This document details the feature engineering pipeline used in the `ngboost-norm-tuned-reviewed.ipynb` notebook.

---

## 1. Data Foundation and Preprocessing

### 1.1 Box-Cox Transformation of Target Variable

The target variable (pace) undergoes a **Box-Cox transformation** to normalize the distribution. The transformation is calculated using historical data only to prevent leakage.

```python
_, race_specific_bc_lambda = stats.boxcox(no_nans_history_capped_paces)
bc_transformed_paces = stats.boxcox(capped_paces, lmbda=race_specific_bc_lambda)
normalized_bc_paces = (bc_transformed_paces - bc_mean) / bc_std
```

### 1.2 Base Features

| Feature | Description |
|---------|-------------|
| `leg` | Integer leg number (1-based) |
| `first_time` | Boolean: True if this is the runner's first recorded run |
| `run_num_norm` | Normalized run count: `run_num / median(run_num)` |
| `roll_5y_years_since_results` | Years since the last 5 results (rolling mean) |
| `normalized_team_id` | `team_id / median(team_id)` |
| `normalized_leg_dist` | `leg_dist / mean(leg_dist)` |
| `tcn_bc_pace` | **Pace adjusted for terrain**: `bc_pace / terrain_coefficient` |
| `vcn_bc_pace` | **Pace adjusted for vertical**: `bc_pace / vertical_coef` |

---

## 2. Historical Performance Features

Historical features are computed per-runner (`unique_name`) using rolling windows and cumulative statistics.

### 2.1 Active Historical Features
- `history_bcp_median`: Cumulative median of Box-Cox pace.
- `roll_5y_tcn_bcp_mean`: Rolling 5-run mean of terrain-adjusted pace.
- `roll_5y_tcn_bcp_std`: Rolling 5-run standard deviation.
- `roll_tcn_bcp_min`: Rolling 10-run minimum (best performance).

---

## 3. Team-Based Features

- `other_team_members_roll_5y_tcn_bcp_mean`: Collective strength of teammates (excluding focal runner).
- `other_team_members_with_history`: Count of teammates with prior data.

---

## 4. Country-Based Bayesian Prior Features

Runners are grouped by their team's country to provide a "prior" for runners with no history.

- `c_bcp_median`: Median Box-Cox pace for the country.
- `c_bcp_median_nti_interaction`: Interaction between country strength and team ID (proxy for team depth).

---

## 5. Interaction Features

- `roll_tcn_bcp_med_mean_diff_tc_interaction`: Interaction between runner's consistency and terrain difficulty.
- `roll_vcn_bcp_mean_vc_interaction`: Interaction between runner's historical vertical performance and current leg's vertical climb.
- `fn_scaled_pace_tc_interaction`: Scaled pace (national championship baseline) interacted with terrain.

---

## 6. Model Integration

- **Model**: `ngboost.NGBRegressor`
- **Base Learner**: `DecisionTreeRegressor(criterion='friedman_mse')`
- **Distribution**: `Normal` (Gaussian)
- **Loss**: Log-likelihood
- **Metric**: CRPS (Continuous Ranked Probability Score)
