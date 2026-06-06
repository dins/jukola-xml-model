import pytest
import builtins
import pandas as pd

import shared
import group_names

@pytest.fixture
def mock_environment(monkeypatch):
    monkeypatch.setattr(shared, "history_years", lambda: ["2018", "2019", "2021", "2022"])
    monkeypatch.setattr(shared, "race_type", lambda default="ve": "ve")
    monkeypatch.setattr(shared, "forecast_year", lambda: 2026)
    monkeypatch.setattr(shared, "race_id_str", lambda: "ve_fy_test")

    original_open = builtins.open
    def mocked_open(file, *args, **kwargs):
        if str(file).startswith("data/results_with_dist_j"):
            file = str(file).replace("data/", "tests/testdata/")
        return original_open(file, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", mocked_open)

    original_read_csv = pd.read_csv
    def mocked_read_csv(filepath_or_buffer, *args, **kwargs):
        if str(filepath_or_buffer).startswith("data/running_order_final_"):
            filepath_or_buffer = "tests/testdata/running_order_final_ve_fy_test.tsv"
        return original_read_csv(filepath_or_buffer, *args, **kwargs)
    monkeypatch.setattr(pd, "read_csv", mocked_read_csv)

    captured_dfs = {}
    original_to_csv = pd.DataFrame.to_csv
    def mocked_to_csv(self, path_or_buf=None, *args, **kwargs):
        if path_or_buf and str(path_or_buf).startswith("data/long_runs_"):
            captured_dfs["output"] = self.copy()
            # We don't actually write to disk to avoid polluting data/
            return None
        return original_to_csv(self, path_or_buf, *args, **kwargs)
    monkeypatch.setattr(pd.DataFrame, "to_csv", mocked_to_csv)

    return captured_dfs

def test_group_names_e2e(mock_environment):
    # Execute the entire grouping pipeline
    group_names._group_runs_to_runners()

    # The pipeline should have captured the final dataframe
    assert "output" in mock_environment, "Output dataframe was not saved!"
    df = mock_environment["output"]

    # Let's verify specific known runners
    
    # 1. Kaima: "kaisa vainikka"
    # Should be split into multiple unique_name variations
    kaisa_runs = df[df["unique_name"].str.startswith("kaisa vainikka", na=False)]
    unique_kaisas = kaisa_runs["unique_name"].nunique()
    assert unique_kaisas > 1, f"Expected kaisa vainikka to be split, found {unique_kaisas} unique names"

    # 2. Tuplaaja: "johanna öberg"
    # Runs multiple legs in the same year, should remain grouped
    johanna_runs = df[df["unique_name"].str.startswith("johanna öberg", na=False)]
    unique_johannas = johanna_runs["unique_name"].nunique()
    assert unique_johannas == 1, f"Expected johanna öberg to be grouped together, found {unique_johannas}"

    # 3. Emit Connection: "eija rantala"
    # She has two namesakes: One in Ounasvaaran Hiihtoseura.
    # The other runs for Helsingin Suunnistajat and Espoon Suunta, connected by Emit.
    eija_runs = df[df["unique_name"].str.startswith("eija rantala", na=False)]
    unique_eijas = eija_runs["unique_name"].nunique()
    assert unique_eijas == 2, f"Expected eija rantala to be split into 2 people, found {unique_eijas}"
    
    # Check that the emit connection worked: Helsingin Suunnistajat and Espoon Suunta are merged
    hs_es_eija = eija_runs[eija_runs["team"].isin(["HELSINGIN SUUNNISTAJAT", "ESPOON SUUNTA"])]
    assert hs_es_eija["unique_name"].nunique() == 1, "Emit connection failed to merge HS and ES!"

    # 4. Normal Runner: "magdalena olsson"
    # Runs in the same team across all years. Should be fully sequential.
    magdalena_runs = df[df["unique_name"].str.startswith("magdalena olsson", na=False)]
    assert magdalena_runs["unique_name"].nunique() == 1, "Normal runner got split!"
    assert len(magdalena_runs) == 5, "Magdalena should have 4 history runs + 1 running order run"
    
    # Check that run_num is correctly accumulated (1, 2, 3, 4, 5)
    run_nums = magdalena_runs.sort_values("year")["run_num"].tolist()
    assert run_nums == [1, 2, 3, 4, 5], f"run_num sequential count failed: {run_nums}"
    
    # 5. Running Order (Future Year) Merge
    # In running order, pace is NaN/missing. 
    # The 2026 run for Magdalena should be present and pace should be null.
    ro_magdalena = magdalena_runs[magdalena_runs["year"] == 2026]
    assert len(ro_magdalena) == 1, "Failed to merge running order data"
    assert pd.isna(ro_magdalena["pace"].iloc[0]), "Running order pace should be null"

    # 6. Rare First Name Fallback
    # "karolin ohlsson" has a rare first name (<5 occurrences). 
    # She should receive the fallback 'OTHER' fn_scaled_pace value.
    # Note: we test that fn_scaled_pace is populated and identical to the fallback logic.
    karolin = df[df["unique_name"].str.startswith("karolin ohlsson", na=False)]
    assert not karolin.empty, "Rare first name runner missing"
    # Wait, the other rare names will also get the same fallback. 
    # e.g., 'eija' might also be rare if there's < 5 in our tiny test subset!
    eija = df[df["unique_name"].str.startswith("eija rantala", na=False)]
    assert karolin["fn_scaled_pace"].iloc[0] == eija["fn_scaled_pace"].iloc[0], "Rare first names should get the same fallback fn_scaled_pace"

    # 7. Statistics & Ideals
    # Check that median_pace and log_stdev are calculated
    assert "median_pace" in df.columns
    assert "log_stdev" in df.columns
    assert pd.notna(magdalena_runs["median_pace"].iloc[0]), "median_pace not calculated"
    # Check ideals merge (e.g. terrain_coefficient)
    assert "terrain_coefficient" in df.columns
    assert pd.notna(magdalena_runs["terrain_coefficient"].iloc[0]), "Ideals merge failed"

    # 8. Check run_id composite key
    assert "run_id" in df.columns, "run_id was not added to the output dataframe"
    sample_run = df.iloc[0]
    expected_run_id = f"{int(sample_run['year'])}-ve-{int(sample_run['team_id'])}-{int(sample_run['leg'])}"
    assert sample_run["run_id"] == expected_run_id, f"run_id format incorrect. Expected {expected_run_id}, got {sample_run['run_id']}"

    # 9. Team changes without overlaps: "agata olejnik"
    # Runs in multiple teams but never more than one team per year.
    # We assume team changes are likely, so if there is only one run per full name per year,
    # there is no reason to assume namesakes. They remain grouped.
    agata_runs = df[df["name"] == "agata olejnik"]
    assert agata_runs["unique_name"].nunique() == 1, "Expected runner changing teams without overlapping years to remain grouped"

    # 10. Missing Pace Handling: "heidi nevalainen"
    # In 2018, she has a valid run and a DNF (NA pace) run in two different teams.
    # In 2022, she has two valid runs in different teams.
    # Because NA paces do not count towards the overlapping years threshold, she only has 1 overlap year (2022).
    # Thus, according to the Tuplaaja heuristic, she is not split.
    heidi_runs = df[df["name"] == "heidi nevalainen"]
    assert heidi_runs["unique_name"].nunique() == 1, "Expected missing pace (NA) to not count towards namesake split threshold"

    # 11. Partial Emit Linking: "jonna virtanen"
    # Overlaps in 2018, 2019, 2022 across 3 teams ("HUIKKA RASTILLA", "ÅBO KLYX", "NOSTARS").
    # Emit connects "HUIKKA RASTILLA" and "ÅBO KLYX", but "NOSTARS" has distinct emits.
    # Therefore, she should split into exactly 2 personas.
    jonna_runs = df[df["name"] == "jonna virtanen"]
    jonna_personas = jonna_runs["unique_name"].unique()
    assert len(jonna_personas) == 2, f"Expected Jonna to split into 2 people, got {len(jonna_personas)}"
    linked_persona_runs = jonna_runs[jonna_runs["team"].isin(["HUIKKA RASTILLA", "ÅBO KLYX"])]
    assert linked_persona_runs["unique_name"].nunique() == 1, "Emit connection failed to link teams during a split"

    # 12. Short Name Filtering: "n n"
    # Should be entirely dropped because length <= 5 characters.
    n_n_runs = df[df["name"] == "n n"]
    assert len(n_n_runs) == 0, "Expected 'n n' to be dropped due to short length"

    # Verify basic data integrity
    assert "pace" in df.columns
    assert "unique_name" in df.columns
    assert len(df) > 0

