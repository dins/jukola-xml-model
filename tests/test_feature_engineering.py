import polars as pl
from feature_engineering import build_past_first_name_features

def test_build_past_first_name_features_assigns_buckets_and_accumulates_correctly():
    # Synthetic data with 3 years: 2018, 2019, 2020
    # Oskari A, Oskari B, Oskari C, Oskari D run.
    # Total "oskari" unique full names up to 2019 = 4 (which is > threshold if threshold=3)
    
    df = pl.DataFrame({
        "unique_name": ["Oskari A", "Oskari B", "Oskari C", "Matti A", "Oskari A", "Oskari D", "Matti A", "Oskari A", "Oskari B", "Matti A", "Pekka A"],
        "year": [2018, 2018, 2018, 2018, 2019, 2019, 2019, 2020, 2020, 2020, 2020],
        "pace_leg_ratio": [1.0, 3.0, 2.0, 5.0, 2.0, 4.0, 6.0, 3.0, 5.0, 7.0, 10.0],
        "pace": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], # All valid
        "row_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    })
    
    # We set min_unique_full_names = 3
    # In 2018: past_df is empty. Everyone is OTHER.
    # In 2019: past_df has 3 unique oskari (A, B, C), 1 unique matti. Oskari <= 3 (not strictly > 3). Everyone is OTHER.
    # In 2020: past_df has 4 unique oskari (A, B, C, D). Oskari > 3, so Oskari becomes "oskari". Matti is OTHER.
    
    fn_features = build_past_first_name_features(df, min_unique_full_names=3)
    result = df.join(fn_features.drop("first_name"), on="row_id", how="left")
    
    # Check 2018
    res_2018 = result.filter(pl.col("year") == 2018)
    assert res_2018["fn_bucket"].to_list() == ["OTHER", "OTHER", "OTHER", "OTHER"]
    assert res_2018["fn_scaled_pace_v2"].to_list() == [1.0, 1.0, 1.0, 1.0] # Fallback is 1.0
    
    # Check 2019
    res_2019 = result.filter(pl.col("year") == 2019)
    assert res_2019["fn_bucket"].to_list() == ["OTHER", "OTHER", "OTHER"]
    # 2019 OTHER median should be median of all 2018 paces: [1.0, 3.0, 2.0, 5.0] -> 2.5
    assert res_2019["fn_scaled_pace_v2"].to_list() == [2.5, 2.5, 2.5]
    assert res_2019["fn_num_runs"].to_list() == [4, 4, 4]
    
    # Check 2020
    # In 2020, Oskari is "oskari", Matti is "OTHER", Pekka is "OTHER"
    res_2020 = result.filter(pl.col("year") == 2020).sort("row_id")
    assert res_2020["fn_bucket"].to_list() == ["oskari", "oskari", "OTHER", "OTHER"]
    # 2020 "oskari" median should be median of all past oskari paces: [1.0, 3.0, 2.0, 2.0, 4.0] -> 2.0
    assert res_2020.filter(pl.col("fn_bucket") == "oskari")["fn_scaled_pace_v2"][0] == 2.0
    assert res_2020.filter(pl.col("fn_bucket") == "oskari")["fn_num_runs"][0] == 5
    
    # 2020 "OTHER" median should be median of all past OTHER paces: Matti in 2018, 2019: [5.0, 6.0] -> 5.5
    assert res_2020.filter(pl.col("fn_bucket") == "OTHER")["fn_scaled_pace_v2"][0] == 5.5
    assert res_2020.filter(pl.col("fn_bucket") == "OTHER")["fn_num_runs"][0] == 2

def test_build_past_first_name_features_counts_unique_full_names_correctly():
    df = pl.DataFrame({
        "unique_name": ["Oskari A", "Oskari A", "Oskari B", "Oskari A"],
        "year": [2018, 2018, 2018, 2019],
        "pace_leg_ratio": [1.0, 2.0, None, 2.0],
        "pace": [1.0, 1.0, None, 1.0], # Oskari B pace is None
        "row_id": [1, 2, 3, 4]
    })
    
    # In 2019, history has 3 Oskari rows but only 2 unique names: Oskari A and Oskari B.
    # Note: Oskari B has None pace, but we still count the unique name.
    # Set threshold to 1. Since 2 > 1, Oskari becomes its own bucket.
    fn_features = build_past_first_name_features(df, min_unique_full_names=1)
    result = df.join(fn_features.drop("first_name"), on="row_id", how="left")
    
    res_2019 = result.filter(pl.col("year") == 2019)
    assert res_2019["fn_bucket"][0] == "oskari"

