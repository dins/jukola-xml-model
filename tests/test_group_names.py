import pytest
import builtins
import os
import re
import pandas as pd
import shared
import group_names


TESTDATA_ROOT = "tests/testdata"
DEFAULT_TESTDATA_SUBDIR = "default-set"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        f"testdata(subdir): use '{TESTDATA_ROOT}/<subdir>' as the name_grouping input "
        f"directory. Defaults to '{TESTDATA_ROOT}/{DEFAULT_TESTDATA_SUBDIR}'.",
    )


def _resolve_testdata_dir(request) -> str:
    marker = request.node.get_closest_marker("testdata")
    subdir = marker.args[0] if marker and marker.args else DEFAULT_TESTDATA_SUBDIR
    return os.path.join(TESTDATA_ROOT, subdir)


def _detect_history_years(testdata_dir: str, race_type: str) -> list[str]:
    """Return sorted YYYY strings parsed from `results_with_dist_jYYYY_<race_type>.tsv` files."""
    pattern = re.compile(rf"^results_with_dist_j(\d{{4}})_{race_type}\.tsv$")
    years = []
    for filename in os.listdir(testdata_dir):
        match = pattern.match(filename)
        if match:
            years.append(match.group(1))
    if not years:
        raise FileNotFoundError(
            f"No 'results_with_dist_jYYYY_{race_type}.tsv' files found in "
            f"{testdata_dir}. Add at least one result fixture file."
        )
    return sorted(years)


_GROUPING_CACHE: dict[str, pd.DataFrame] = {}


@pytest.fixture
def grouped_dataframe(monkeypatch, request):
    testdata_dir = _resolve_testdata_dir(request)

    # Return a copy from cache if we already ran name_grouping for this test directory
    if testdata_dir in _GROUPING_CACHE:
        return _GROUPING_CACHE[testdata_dir].copy()

    # Otherwise, set up the mock environment and run name_grouping
    history_years = _detect_history_years(testdata_dir, race_type="ve")

    monkeypatch.setattr(shared, "history_years", lambda: history_years)
    monkeypatch.setattr(shared, "race_type", lambda default="ve": "ve")
    monkeypatch.setattr(shared, "forecast_year", lambda: 2026)
    monkeypatch.setattr(shared, "race_id_str", lambda: "ve_fy_test")

    original_open = builtins.open

    def mocked_open(file, *args, **kwargs):
        if str(file).startswith("data/results_with_dist_j"):
            file = str(file).replace("data/", f"{testdata_dir}/")
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", mocked_open)

    import polars as pl

    original_pl_read_csv = pl.read_csv

    def mocked_pl_read_csv(source, *args, **kwargs):
        if str(source).startswith("data/running_order_final_"):
            source = f"{testdata_dir}/running_order_final_ve_fy_test.tsv"
        elif str(source).startswith("data/results_with_dist_j"):
            source = str(source).replace("data/", f"{testdata_dir}/")
        return original_pl_read_csv(source, *args, **kwargs)

    monkeypatch.setattr(pl, "read_csv", mocked_pl_read_csv)

    captured_dfs = {}
    original_to_csv = pd.DataFrame.to_csv

    def mocked_to_csv(self, path_or_buf=None, *args, **kwargs):
        if path_or_buf and str(path_or_buf).startswith("data/long_runs_"):
            captured_dfs["output"] = self.copy()
            # We don't actually write to disk to avoid polluting data/
            return None
        return original_to_csv(self, path_or_buf, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_csv", mocked_to_csv)

    # Execute the entire name_grouping process
    group_names._group_runs_to_runners()

    # The name_grouping process should have captured the final dataframe
    assert "output" in captured_dfs, "Output dataframe was not saved!"

    # Store in cache and return a safe copy
    _GROUPING_CACHE[testdata_dir] = captured_dfs["output"]
    return _GROUPING_CACHE[testdata_dir].copy()


def test_kaima_is_split(grouped_dataframe):
    # Kaima: "kaisa vainikka"
    # Should be split into multiple unique_name variations
    kaisa_runs = grouped_dataframe[
        grouped_dataframe["unique_name"].str.startswith("kaisa vainikka", na=False)
    ]
    unique_kaisas = kaisa_runs["unique_name"].nunique()
    assert unique_kaisas > 1, (
        f"Expected kaisa vainikka to be split, found {unique_kaisas} unique names"
    )


def test_tuplaaja_remains_grouped(grouped_dataframe):
    # Tuplaaja: "johanna öberg"
    # Runs multiple legs in the same year, should remain grouped
    johanna_runs = grouped_dataframe[
        grouped_dataframe["unique_name"].str.startswith("johanna öberg", na=False)
    ]
    unique_johannas = johanna_runs["unique_name"].nunique()
    assert unique_johannas == 1, (
        f"Expected johanna öberg to be grouped together, found {unique_johannas}"
    )


def test_emit_connection_merges_teams(grouped_dataframe):
    # Emit Connection: "eija rantala"
    # She has two namesakes: One in Ounasvaaran Hiihtoseura.
    # The other runs for Helsingin Suunnistajat and Espoon Suunta, connected by Emit.
    eija_runs = grouped_dataframe[
        grouped_dataframe["unique_name"].str.startswith("eija rantala", na=False)
    ]
    unique_eijas = eija_runs["unique_name"].nunique()
    assert unique_eijas == 2, (
        f"Expected eija rantala to be split into 2 people, found {unique_eijas}"
    )

    # Check that the emit connection worked: Helsingin Suunnistajat and Espoon Suunta are merged
    hs_es_eija = eija_runs[
        eija_runs["team"].isin(["HELSINGIN SUUNNISTAJAT", "ESPOON SUUNTA"])
    ]
    assert hs_es_eija["unique_name"].nunique() == 1, (
        "Emit connection failed to merge HS and ES!"
    )


def test_normal_runner_accumulates_run_num(grouped_dataframe):
    # Normal Runner: "magdalena olsson"
    # Runs in the same team across all years. Should be fully sequential.
    magdalena_runs = grouped_dataframe[
        grouped_dataframe["unique_name"].str.startswith("magdalena olsson", na=False)
    ]
    assert magdalena_runs["unique_name"].nunique() == 1, "Normal runner got split!"
    assert len(magdalena_runs) == 5, (
        "Magdalena should have 4 history runs + 1 running order run"
    )

    # Check that run_num is correctly accumulated (1, 2, 3, 4, 5)
    run_nums = magdalena_runs.sort_values("year")["run_num"].tolist()
    assert run_nums == [1, 2, 3, 4, 5], f"run_num sequential count failed: {run_nums}"


def test_running_order_is_merged_with_null_pace(grouped_dataframe):
    # Running Order (Future Year) Merge
    # In running order, pace is NaN/missing.
    # The 2026 run for Magdalena should be present and pace should be null.
    magdalena_runs = grouped_dataframe[
        grouped_dataframe["unique_name"].str.startswith("magdalena olsson", na=False)
    ]
    ro_magdalena = magdalena_runs[magdalena_runs["year"] == 2026]
    assert len(ro_magdalena) == 1, "Failed to merge running order data"
    assert pd.isna(ro_magdalena["pace"].iloc[0]), "Running order pace should be null"


def test_statistics_and_ideals_are_calculated(grouped_dataframe):
    # Statistics & Ideals
    # Check that median_pace and log_stdev are calculated
    assert "median_pace" in grouped_dataframe.columns
    assert "log_stdev" in grouped_dataframe.columns
    magdalena_runs = grouped_dataframe[
        grouped_dataframe["unique_name"].str.startswith("magdalena olsson", na=False)
    ]
    assert pd.notna(magdalena_runs["median_pace"].iloc[0]), "median_pace not calculated"
    # Check ideals merge (e.g. terrain_coefficient)
    assert "terrain_coefficient" in grouped_dataframe.columns
    assert pd.notna(magdalena_runs["terrain_coefficient"].iloc[0]), (
        "Ideals merge failed"
    )


def test_run_id_format(grouped_dataframe):
    # Check run_id composite key
    assert "run_id" in grouped_dataframe.columns, (
        "run_id was not added to the output dataframe"
    )
    sample_run = grouped_dataframe.iloc[0]
    expected_run_id = f"{int(sample_run['year'])}-ve-{int(sample_run['team_id'])}-{int(sample_run['leg'])}"
    assert sample_run["run_id"] == expected_run_id, (
        f"run_id format incorrect. Expected {expected_run_id}, got {sample_run['run_id']}"
    )


def test_team_changes_without_overlaps(grouped_dataframe):
    # Team changes without overlaps: "agata olejnik"
    # Runs in multiple teams but never more than one team per year.
    # We assume team changes are likely, so if there is only one run per full name per year,
    # there is no reason to assume namesakes. They remain grouped.
    agata_runs = grouped_dataframe[grouped_dataframe["name"] == "agata olejnik"]
    assert agata_runs["unique_name"].nunique() == 1, (
        "Expected runner changing teams without overlapping years to remain grouped"
    )


def test_missing_pace_does_not_trigger_split(grouped_dataframe):
    # Missing Pace Handling: "heidi nevalainen"
    # In 2018, she has a valid run and a DNF (NA pace) run in two different teams.
    # In 2022, she has two valid runs in different teams.
    # Because NA paces do not count towards the overlapping years threshold, she only has 1 overlap year (2022).
    # Thus, according to the Tuplaaja heuristic, she is not split.
    heidi_runs = grouped_dataframe[grouped_dataframe["name"] == "heidi nevalainen"]
    assert heidi_runs["unique_name"].nunique() == 1, (
        "Expected missing pace (NA) to not count towards namesake split threshold"
    )


def test_partial_emit_linking_during_split(grouped_dataframe):
    # Partial Emit Linking: "jonna virtanen"
    # Overlaps in 2018, 2019, 2022 across 3 teams ("HUIKKA RASTILLA", "ÅBO KLYX", "NOSTARS").
    # Emit connects "HUIKKA RASTILLA" and "ÅBO KLYX", but "NOSTARS" has distinct emits.
    # Therefore, she should split into exactly 2 personas.
    jonna_runs = grouped_dataframe[grouped_dataframe["name"] == "jonna virtanen"]
    jonna_personas = jonna_runs["unique_name"].unique()
    assert len(jonna_personas) == 2, (
        f"Expected Jonna to split into 2 people, got {len(jonna_personas)}"
    )
    linked_persona_runs = jonna_runs[
        jonna_runs["team"].isin(["HUIKKA RASTILLA", "ÅBO KLYX"])
    ]
    assert linked_persona_runs["unique_name"].nunique() == 1, (
        "Emit connection failed to link teams during a split"
    )


def test_short_name_filtering(grouped_dataframe):
    # Short Name Filtering: "n n"
    # Should be entirely dropped because length <= 5 characters.
    n_n_runs = grouped_dataframe[grouped_dataframe["name"] == "n n"]
    assert len(n_n_runs) == 0, "Expected 'n n' to be dropped due to short length"


def test_basic_data_integrity(grouped_dataframe):
    # Verify basic data integrity
    assert "pace" in grouped_dataframe.columns
    assert "unique_name" in grouped_dataframe.columns
    assert len(grouped_dataframe) > 0


@pytest.mark.testdata("typo_emit_connection")
def test_typo_rule_merges_kriktila_via_emit(grouped_dataframe: pd.DataFrame):
    # Typo connection: "leena-maija kriktilä" and "leena-maija kriktillä"
    # Should be grouped together because they share the Emit ID "1237164".
    # Uses isolated testdata to test linking previously linked identities.
    leena_runs = grouped_dataframe[
        grouped_dataframe["name"].str.startswith("leena-maija krikti", na=False)
    ]
    unique_leenas = leena_runs["unique_name"].nunique()

    assert unique_leenas == 1, (
        f"Expected leena-maija kriktilä and leena-maija kriktillä to be merged into 1 person, found {unique_leenas}"
    )


@pytest.mark.testdata("changed_last_name")
def test_changed_last_name_connected_by_first_name_and_emit(
    grouped_dataframe: pd.DataFrame,
):
    # Tests a case where a runner has changed their last name (e.g. marriage):
    # "piia heiniö" -> "piia ruuskanen". They share the same first name and same Emit ID.
    piia_runs = grouped_dataframe[
        grouped_dataframe["name"].isin(["piia heiniö", "piia ruuskanen"])
    ]
    unique_piias = piia_runs["unique_name"].nunique()

    assert unique_piias == 1, (
        f"Expected piia heiniö and piia ruuskanen to be merged into 1 person, found {unique_piias}"
    )

    expected_names = ["piia heiniö", "piia ruuskanen"]
    assert list(sorted(piia_runs["name"].unique())) == expected_names
