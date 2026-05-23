import numpy as np
import polars as pl
from boxcox_transform import BoxCoxParams, fit_boxcox_and_normalize, standardize


def _safe_number(value: float | int | None, fallback: float | int) -> float | int:
    if value is None:
        return fallback
    if isinstance(value, (float, np.floating)) and np.isnan(value):
        return fallback
    return value

def build_past_country_features(feature_df: pl.DataFrame, min_country_runners: int = 50) -> pl.DataFrame:
    country_feature_frames = []
    year_values = sorted(feature_df["year"].drop_nulls().unique().to_list())

    for current_year in year_values:
        current_year_df = feature_df.filter(pl.col("year") == current_year).select([
            "row_id",
            "team_country",
        ])
        past_df = feature_df.filter(pl.col("year") < current_year)

        if past_df.height == 0:
            country_feature_frames.append(
                current_year_df.with_columns([
                    pl.lit("OTHER").alias("team_country_truncated"),
                    pl.lit(0.0).alias("c_bcp_median"),
                    pl.lit(1.0).alias("c_bcp_std"),
                    pl.lit(0).cast(pl.Int64).alias("c_num_runs"),
                    pl.lit(0).cast(pl.Int64).alias("c_n_unique_runners"),
                ])
            )
            continue

        country_bucket_df = (
            past_df
            .group_by("team_country")
            .agg(
                pl.col("unique_name").n_unique().alias("country_runner_count")
            )
            .with_columns(
                pl.when(pl.col("country_runner_count") > min_country_runners)
                .then(pl.col("team_country"))
                .otherwise(pl.lit("OTHER"))
                .alias("team_country_truncated")
            )
        )

        past_country_df = past_df.join(
            country_bucket_df.select([
                "team_country",
                "team_country_truncated",
                "country_runner_count",
            ]),
            on="team_country",
            how="left",
        )

        country_prior_df = (
            past_country_df
            .group_by("team_country_truncated")
            .agg([
                pl.col("tcn_bc_pace").median().alias("c_bcp_median"),
                pl.col("tcn_bc_pace").std().alias("c_bcp_std"),
                pl.col("tcn_bc_pace").count().alias("c_num_runs"),
                pl.col("unique_name").n_unique().alias("c_n_unique_runners"),
            ])
        )

        global_country_stats = past_df.select([
            pl.col("tcn_bc_pace").median().alias("c_bcp_median"),
            pl.col("tcn_bc_pace").std().alias("c_bcp_std"),
            pl.col("tcn_bc_pace").count().alias("c_num_runs"),
            pl.col("unique_name").n_unique().alias("c_n_unique_runners"),
        ]).to_dicts()[0]

        fallback_c_bcp_median = _safe_number(global_country_stats["c_bcp_median"], 0.0)
        fallback_c_bcp_std = _safe_number(global_country_stats["c_bcp_std"], 1.0)
        fallback_c_num_runs = int(_safe_number(global_country_stats["c_num_runs"], 0))
        fallback_c_n_unique_runners = int(_safe_number(global_country_stats["c_n_unique_runners"], 0))

        current_year_country_df = (
            current_year_df
            .join(
                country_bucket_df.select([
                    "team_country",
                    "team_country_truncated",
                ]),
                on="team_country",
                how="left",
            )
            .with_columns(
                pl.col("team_country_truncated").fill_null("OTHER")
            )
            .join(country_prior_df, on="team_country_truncated", how="left")
            .with_columns([
                pl.col("c_bcp_median").fill_null(pl.lit(fallback_c_bcp_median)),
                pl.col("c_bcp_std").fill_null(pl.lit(fallback_c_bcp_std)),
                pl.col("c_num_runs").fill_null(pl.lit(fallback_c_num_runs)),
                pl.col("c_n_unique_runners").fill_null(pl.lit(fallback_c_n_unique_runners)),
            ])
        )

        country_feature_frames.append(current_year_country_df)

    return pl.concat(country_feature_frames, how="vertical_relaxed")


def build_past_first_name_features(feature_df: pl.DataFrame, min_fn_runners: int = 50) -> pl.DataFrame:
    fn_feature_frames = []
    year_values = sorted(feature_df["year"].drop_nulls().unique().to_list())

    # Ensure first_name is extracted
    if "first_name" not in feature_df.columns:
        feature_df = feature_df.with_columns(
            pl.col("unique_name").str.split(" ").list.get(0).str.to_lowercase().alias("first_name")
        )

    for current_year in year_values:
        current_year_df = feature_df.filter(pl.col("year") == current_year).select([
            "row_id",
            "first_name",
        ])
        past_df = feature_df.filter(pl.col("year") < current_year)

        if past_df.height == 0:
            fn_feature_frames.append(
                current_year_df.with_columns([
                    pl.lit("OTHER").alias("fn_bucket"),
                    pl.lit(1.0).alias("fn_scaled_pace"),
                    pl.lit(0).cast(pl.Int64).alias("fn_num_runs"),
                ])
            )
            continue

        fn_bucket_df = (
            past_df
            .filter(pl.col("pace").is_not_null())
            .group_by("first_name")
            .agg(
                pl.len().alias("fn_valid_results")
            )
            .with_columns(
                pl.when(pl.col("fn_valid_results") > min_fn_runners)
                .then(pl.col("first_name"))
                .otherwise(pl.lit("OTHER"))
                .alias("fn_bucket")
            )
        )

        past_fn_df = past_df.join(
            fn_bucket_df.select(["first_name", "fn_bucket"]),
            on="first_name",
            how="left",
        ).with_columns(pl.col("fn_bucket").fill_null("OTHER"))

        fn_prior_df = (
            past_fn_df
            .group_by("fn_bucket")
            .agg([
                pl.col("pace_leg_ratio").drop_nulls().median().alias("fn_scaled_pace"),
                pl.col("pace_leg_ratio").is_not_null().sum().alias("fn_num_runs"),
            ])
        )

        current_year_fn_df = (
            current_year_df
            .join(
                fn_bucket_df.select([
                    "first_name",
                    "fn_bucket",
                ]),
                on="first_name",
                how="left",
            )
            .with_columns(pl.col("fn_bucket").fill_null("OTHER"))
            .join(fn_prior_df, on="fn_bucket", how="left")
            .with_columns([
                pl.col("fn_scaled_pace").fill_null(pl.lit(1.0)),
                pl.col("fn_num_runs").fill_null(pl.lit(0)),
            ])
        )

        fn_feature_frames.append(current_year_fn_df)

    return pl.concat(fn_feature_frames, how="vertical_relaxed")


def build_features(runs_df: pl.DataFrame, forecast_year: int) -> tuple[pl.DataFrame, list[str], BoxCoxParams]:
    history_reference_df = runs_df.filter(pl.col("year") < forecast_year)
    
    normalized_bc_paces, boxcox_params = fit_boxcox_and_normalize(runs_df, history_reference_df)

    history_tc_values = history_reference_df["terrain_coefficient"].to_numpy()
    _, tc_mean, tc_std = standardize(history_tc_values)
    normalized_tc = (runs_df["terrain_coefficient"].to_numpy() - tc_mean) / tc_std

    bc_df = runs_df.with_columns([
        pl.Series("bc_pace", normalized_bc_paces),
        pl.Series("normalized_tc", normalized_tc),
        (pl.col("marking_per_km") / history_reference_df["marking_per_km"].median()).alias("marking_norm"),
        (pl.col("vertical_per_km") / history_reference_df["vertical_per_km"].median()).alias("vertical_coef"),
        (pl.col("team_id") / pl.col("team_id").median().over("year") + 1).alias("normalized_team_id"),
        (pl.col("leg_dist") / pl.col("leg_dist").mean().over("year") + 1).alias("normalized_leg_dist"),
        (pl.col("run_num") / pl.col("run_num").median().over("year")).alias("run_num_norm"),
        (pl.col("run_num") <= 1).alias("first_time"),
        (pl.col("year") - pl.col("year").shift(1).rolling_mean(window_size=5, min_samples=1).over("unique_name")).alias("roll_5y_years_since_results"),
        (pl.col("pace") / pl.col("pace").median().over(["year", "leg"])).alias("pace_leg_ratio"),
    ]).fill_nan(None)
    
    bc_df = bc_df.sort(["unique_name", "run_num"]).with_row_index("row_id")
    
    bc_df = bc_df.with_columns([
        (pl.col("bc_pace") / pl.col("terrain_coefficient")).alias("tcn_bc_pace"),
        (pl.col("bc_pace") / pl.col("vertical_coef")).alias("vcn_bc_pace"),
    ])

    """
    fn_feature_df = build_past_first_name_features(bc_df)
    bc_df = bc_df.join(
        fn_feature_df.select([
            "row_id",
            "fn_bucket",
            "fn_scaled_pace",
            "fn_num_runs",
        ]),
        on="row_id",
        how="left",
    )
    """
    
    bc_df = bc_df.with_columns([
        #(pl.col("tcn_bc_pace") * pl.col("normalized_team_id")).alias("tcn_bcp_ti_interaction"),
        #(pl.col("tcn_bc_pace") / pl.col("run_num")).alias("tcn_bcp_run_num_interaction"),
        (pl.col("normalized_team_id") / pl.col("run_num_norm")).alias("run_num_ti_interaction"),
    ])
    
    bc_df = bc_df.with_columns([
        #Not in model
        pl.col("pace").shift(1).cumulative_eval(pl.element().drop_nulls().median()).over("unique_name").alias("history_pace_median"),
        
        pl.col("tcn_bc_pace").shift(1).cumulative_eval(pl.element().drop_nulls().median()).over("unique_name").alias("history_tcn_bcp_median"),
    
        #pl.col("bc_pace").shift(1).rolling_mean(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_bcp_mean"),
        
        pl.col("bc_pace").shift(1).rolling_median(window_size=15, min_samples=6).over("unique_name").alias("history_bcp_median"),

        pl.col("tcn_bc_pace").shift(1).rolling_mean(window_size=10, min_samples=1).over("unique_name").alias("roll_tcn_bcp_mean"),
        pl.col("vcn_bc_pace").shift(1).rolling_mean(window_size=10, min_samples=1).over("unique_name").alias("roll_vcn_bcp_mean"),
        pl.col("tcn_bc_pace").shift(1).rolling_mean(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_tcn_bcp_mean"),
        #pl.col("tcn_bcp_ti_interaction").shift(1).rolling_mean(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_tcn_bcp_ti_interaction_mean"),
        #pl.col("tcn_bcp_run_num_interaction").shift(1).rolling_mean(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_tcn_bcp_run_num_interaction_mean"),
        pl.col("bc_pace").shift(1).rolling_std(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_bcp_std"),
        pl.col("pace").shift(1).rolling_mean(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_pace_mean"),
        pl.col("pace_leg_ratio").shift(1).rolling_mean(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_pace_leg_ratio_mean"),
        pl.col("pace_leg_ratio").shift(1).rolling_std(window_size=10, min_samples=3).over("unique_name").alias("roll_pace_leg_ratio_std"),
        pl.col("bc_pace").shift(1).cumulative_eval(pl.element().std()).over("unique_name").alias("history_bcp_std"),
        pl.col("tcn_bc_pace").shift(1).cumulative_eval(pl.element().std()).over("unique_name").alias("history_tcn_bcp_std"),
        pl.col("tcn_bc_pace").shift(1).rolling_skew(window_size=15, min_samples=5).over("unique_name").alias("roll_tcn_bcp_skew"),
        pl.col("tcn_bc_pace").shift(1).rolling_kurtosis(window_size=15, min_samples=5).over("unique_name").alias("roll_tcn_bcp_kurtosis"),
        pl.col("pace").shift(1).rolling_skew(window_size=15, min_samples=5).over("unique_name").alias("roll_pace_skew"),
        (
            pl.col("tcn_bc_pace").shift(1).rolling_mean(10, min_samples=3).over("unique_name")
            - pl.col("tcn_bc_pace").shift(1).rolling_median(10, min_samples=3).over("unique_name")
        ).alias("roll_tcn_bcp_med_mean_diff"),
        (
            pl.col("tcn_bc_pace").shift(1).rolling_quantile(0.75, window_size=10, min_samples=4).over("unique_name")
            - pl.col("tcn_bc_pace").shift(1).rolling_quantile(0.25, window_size=10, min_samples=4).over("unique_name")
        ).alias("roll_tcn_bcp_iqr"),
        (
            pl.col("vcn_bc_pace").shift(1).rolling_quantile(0.75, window_size=10, min_samples=4).over("unique_name")
            - pl.col("vcn_bc_pace").shift(1).rolling_quantile(0.25, window_size=10, min_samples=4).over("unique_name")
        ).alias("roll_vcn_bcp_iqr"),
        pl.col("tcn_bc_pace").shift(1).rolling_std(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_tcn_bcp_std"),
        pl.col("tcn_bc_pace").shift(1).rolling_std(window_size=10, min_samples=1).over("unique_name").alias("roll_tcn_bcp_std"),
        pl.col("vcn_bc_pace").shift(1).rolling_std(window_size=10, min_samples=1).over("unique_name").alias("roll_vcn_bcp_std"),
        pl.col("tcn_bc_pace").shift(1).rolling_min(window_size=10, min_samples=1).over("unique_name").alias("roll_tcn_bcp_min"),
        #pl.col("tcn_bc_pace").shift(1).rolling_max(window_size=10, min_samples=1).over("unique_name").alias("roll_tcn_bcp_max"),
        pl.col("terrain_coefficient").shift(1).rolling_mean(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_tc_mean"),
        pl.col("vertical_coef").shift(1).rolling_mean(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_vc_mean"),
        #pl.col("terrain_coefficient").shift(1).rolling_mean(window_size=10, min_samples=1).over("unique_name").alias("roll_tc_mean"),
        #pl.col("terrain_coefficient").shift(1).cumulative_eval(pl.element().drop_nulls().mean()).over("unique_name").alias("history_tc_mean"),
        #pl.col("normalized_team_id").shift(1).rolling_mean(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_nti_mean"),
        #pl.col("normalized_leg_dist").shift(1).rolling_mean(window_size=5, min_samples=1).over("unique_name").alias("roll_5y_ndist_mean"),
    ])
    
    country_feature_df = build_past_country_features(bc_df, min_country_runners=50)
    bc_df = bc_df.join(
        country_feature_df.select([
            "row_id",
            "team_country_truncated",
            "c_bcp_median",
            "c_bcp_std",
            "c_num_runs",
            "c_n_unique_runners",
        ]),
        on="row_id",
        how="left",
    )
    
    
    team_group_cols = ["year", "team_id"]
    history_col = "roll_5y_tcn_bcp_mean"
    
    team_history_df = (
        bc_df
        .group_by(team_group_cols)
        .agg([
            pl.len().alias("team_members_total"),
            pl.col(history_col).count().alias("team_members_with_history"),
            pl.col(history_col).fill_null(0.0).sum().alias("team_history_sum"),
            (
                pl.col(history_col).fill_null(0.0) * pl.col(history_col).fill_null(0.0)
            ).sum().alias("team_history_sumsq"),
        ])
    )
    
    bc_df = (
        bc_df
        .join(team_history_df, on=team_group_cols, how="left")
        .with_columns([
            pl.col(history_col).fill_null(0.0).alias("own_history_value"),
            pl.col(history_col).is_not_null().cast(pl.Int64).alias("own_history_known"),
        ])
        .with_columns([
            (
                pl.col("team_members_with_history") - pl.col("own_history_known")
            ).alias("other_team_members_with_history"),
            (
                pl.col("team_history_sum") - pl.col("own_history_value")
            ).alias("other_team_history_sum"),
            (
                pl.col("team_history_sumsq")
                - pl.col("own_history_value") * pl.col("own_history_value")
            ).alias("other_team_history_sumsq"),
        ])
        .with_columns([
            pl.when(pl.col("other_team_members_with_history") > 0)
            .then(
                pl.col("other_team_history_sum")
                / pl.col("other_team_members_with_history")
            )
            .otherwise(None)
            .alias("other_team_members_roll_5y_tcn_bcp_mean"),
    
            pl.when(pl.col("other_team_members_with_history") > 1)
            .then(
                (
                    pl.col("other_team_history_sumsq")
                    - (
                        pl.col("other_team_history_sum")
                        * pl.col("other_team_history_sum")
                        / pl.col("other_team_members_with_history")
                    )
                )
                / (pl.col("other_team_members_with_history") - 1)
            )
            .otherwise(None)
            .alias("other_team_members_roll_5y_tcn_bcp_var"),
        ])
        .with_columns([
            pl.when(pl.col("other_team_members_roll_5y_tcn_bcp_var").is_not_null())
            .then(pl.col("other_team_members_roll_5y_tcn_bcp_var").sqrt())
            .otherwise(None)
            .alias("other_team_members_roll_5y_tcn_bcp_std"),
        ])
        .drop([
            "own_history_value",
            "own_history_known",
            "team_history_sum",
            "team_history_sumsq",
            "other_team_history_sum",
            "other_team_history_sumsq",
            "other_team_members_roll_5y_tcn_bcp_var",
        ])
    )
    
    
    bc_df = bc_df.with_columns([
        #(pl.col("roll_5y_tcn_bcp_mean") / pl.col("history_tcn_bcp_median")).alias("roll_5y_history_median_ratio"),
        (pl.col("roll_5y_tcn_bcp_std") / pl.col("history_tcn_bcp_std")).alias("roll_5y_history_std_ratio"),
        (pl.col("history_bcp_std") - pl.col("history_tcn_bcp_std")).alias("history_tcn_bcp_std_diff"),
        (pl.col("roll_tcn_bcp_med_mean_diff") * pl.col("terrain_coefficient")).alias("roll_tcn_bcp_med_mean_diff_tc_interaction"),
        (pl.col("roll_vcn_bcp_mean") / pl.col("marking_norm")).alias("roll_vcn_bcp_mean_marking_interaction"),
        #(pl.col("roll_5y_tcn_bcp_mean") * pl.col("vertical_coef")).alias("roll_5y_tcn_bcp_vertical_interaction"),
    
        # Top feature
        (pl.col("roll_5y_pace_leg_ratio_mean") * pl.col("terrain_coefficient")).alias("roll_5y_pace_leg_ratio_tc_interaction"),
    
        
        (pl.col("roll_vcn_bcp_mean") * pl.col("vertical_coef")).alias("roll_vcn_bcp_mean_vc_interaction"),
        #(pl.col("normalized_team_id") * pl.col("roll_tcn_bcp_std")).alias("roll_tcn_bcp_std_mean_nti_interaction"),
        #(pl.col("normalized_team_id") * pl.col("roll_tcn_bcp_mean")).alias("roll_tcn_bcp_mean_nti_interaction"),
        (pl.col("normalized_team_id") * pl.col("c_bcp_median")).alias("c_bcp_median_nti_interaction"),
        (pl.col("normalized_team_id") * pl.col("c_bcp_std")).alias("c_bcp_std_nti_interaction"),
        #(pl.col("normalized_team_id") * pl.col("fn_scaled_pace")).alias("fn_scaled_pace_nti_interaction"),
        # (pl.col("terrain_coefficient") * pl.col("fn_scaled_pace") * pl.col("c_bcp_median")).alias("fn_scaled_pace_c_bcp_median_tc_interaction"),
        (pl.col("terrain_coefficient") * pl.col("fn_scaled_pace") ).alias("fn_scaled_pace_tc_interaction"),
        #(pl.col("vertical_coef") / pl.col("roll_5y_vc_mean") ).alias("vc_to_vc_history_interaction"),
        (pl.col("vertical_coef") * pl.col("fn_scaled_pace") * pl.col("c_bcp_median")).alias("fn_scaled_pace_c_bcp_median_vc_interaction"),
    ])
    
    """
    cols_only_for_unknown_runners = [
        "c_bcp_median_nti_interaction",
        #"c_bcp_std_nti_interaction",
        "fn_scaled_pace_nti_interaction",
        "fn_scaled_pace_c_bcp_median_tc_interaction",
        "fn_scaled_pace_c_bcp_median_vertical_interaction",
    ]
    
    bc_df = bc_df.with_columns([
        pl.when(pl.col("run_num") > 2)
          .then(None)
          .otherwise(pl.col(col))
          .alias(col)
        for col in cols_only_for_unknown_runners
    ])
    """
    
    
    # Add dummy columns and keep the original 'leg' column
    bc_df = bc_df.with_columns(pl.col("leg").cast(pl.Int64))
    
    leg_dummies = bc_df.select("leg").to_dummies()
    leg_dummy_cols = [col for col in leg_dummies.columns if col != "leg"]
    
    bc_df = bc_df.hstack(leg_dummies.select(leg_dummy_cols))
    
    
    feature_names = leg_dummy_cols + [
        "leg",
        "first_time",
        "run_num_norm",
        "roll_5y_years_since_results",
        "normalized_team_id",
        # "roll_tcn_bcp_mean_nti_interaction",
        "history_bcp_median",
        "roll_5y_tcn_bcp_mean",
        #"roll_5y_history_median_ratio",
        "history_tcn_bcp_std",
        "roll_5y_tcn_bcp_std",
        "history_tcn_bcp_std_diff",
        #"roll_tcn_bcp_std_mean_nti_interaction",
        "roll_tcn_bcp_kurtosis",
        "roll_tcn_bcp_skew",
        "roll_tcn_bcp_med_mean_diff",
        "roll_tcn_bcp_iqr",
        "roll_vcn_bcp_iqr", 
        "roll_tcn_bcp_med_mean_diff_tc_interaction",
        "roll_5y_history_std_ratio",
        "roll_tcn_bcp_min",
        #"roll_tcn_bcp_max",
        #"roll_vcn_bcp_mean",
        "roll_vcn_bcp_mean_vc_interaction",
        "roll_vcn_bcp_std",
        "roll_5y_pace_leg_ratio_mean",
        "roll_pace_leg_ratio_std",
    
        #"roll_5y_pace_leg_ratio_tc_interaction",
        # "uniform_tc",
    
        #"roll_5y_tcn_bcp_ti_interaction_mean",
        #"roll_5y_tcn_bcp_run_num_interaction_mean",
        "roll_5y_tc_mean",
        #"roll_5y_vc_mean",
        "roll_vcn_bcp_mean_marking_interaction",
        #"roll_5y_tcn_bcp_vertical_interaction",
        "fn_scaled_pace",
        #"c_bcp_median",
        #"c_bcp_std",
        "c_bcp_median_nti_interaction",
        # "c_bcp_std_nti_interaction",
        #"fn_scaled_pace_nti_interaction",
        #"fn_scaled_pace_c_bcp_median_tc_interaction",
        "fn_scaled_pace_tc_interaction",
        "fn_scaled_pace_c_bcp_median_vc_interaction",
    
        'other_team_members_roll_5y_tcn_bcp_mean',
        'other_team_members_roll_5y_tcn_bcp_std',
        #'team_members_with_history',
        'other_team_members_with_history',
        #'team_members_total',
        
    ]
    
    leaky_until_rebuilt = []
    
    first_pass_drops = [
        #"roll_5y_history_median_ratio",
        "roll_5y_history_std_ratio",
        #"roll_tcn_bcp_skew",
        "roll_tcn_bcp_kurtosis",
        "roll_tcn_bcp_iqr",
        "roll_tcn_bcp_med_mean_diff",
        "roll_tcn_bcp_med_mean_diff_tc_interaction",
        "history_tcn_bcp_std",
        "history_tcn_bcp_std_diff",
        "roll_vcn_bcp_std",
        "roll_pace_leg_ratio_std",
    ]
    
    feature_names = [
        name for name in feature_names
        if name not in leaky_until_rebuilt + first_pass_drops
    ]
    
    return bc_df, feature_names, boxcox_params
