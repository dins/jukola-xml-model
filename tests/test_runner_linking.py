from runner_linking import (
    LinkingState,
    Run,
    LinkRelation,
    TypoConnectedEmitRule,
    RunSource,
    AllowOneOverlapYearRule,
    SameNameEmitConnectedTeamRule,
)


def test_typo_connected_emit_rule():
    runs = [
        Run(
            "r1",
            2018,
            "ve",
            1,
            "KAALIMAAN KAKARAT",
            "FIN",
            1,
            "salli wetterstrand (os kaalimaa)",
            "123",
            10.0,
            RunSource.RESULT,
        ),
        Run(
            "r2",
            2019,
            "ve",
            1,
            "KAALIMAAN KAKARAT",
            "FIN",
            1,
            "salli wetterstrand (os. kaalimaa)",
            "123",
            10.0,
            RunSource.RESULT,
        ),
        Run(
            "r3",
            2020,
            "ve",
            2,
            "OTHER TEAM",
            "FIN",
            1,
            "salli wetterstrand",
            "123",
            10.0,
            RunSource.RESULT,
        ),
    ]

    state = LinkingState.from_runs(runs)
    rule = TypoConnectedEmitRule(0.92)
    rule.update_run_links(state)

    links = [(link.left_run_id, link.right_run_id) for link in state.candidate_links]

    assert ("r1", "r2") in links or ("r2", "r1") in links
    assert state.candidate_links[0].relation == LinkRelation.SAME_RUNNER


def test_typo_rule_links_already_linked_runs():
    # Simulate the real pipeline.
    # Runs belong to "leena-maija kriktilä" and "leena-maija kriktillä", same emit "1237164", same team.
    # The normal rules will link exactly identical names together first.
    # Then the typo rule should link the TWO DIFFERENT normal name groups together.

    runs = [
        # Normal name 1
        Run(
            "r1",
            2019,
            "ve",
            1,
            "Vehkalahden Veikot",
            "FIN",
            1,
            "leena-maija kriktilä",
            "1237164",
            10.0,
            RunSource.RESULT,
        ),
        Run(
            "r2",
            2022,
            "ve",
            1,
            "Vehkalahden Veikot",
            "FIN",
            1,
            "leena-maija kriktilä",
            "1237164",
            10.0,
            RunSource.RESULT,
        ),
        Run(
            "r3",
            2017,
            "ju",
            1,
            "Vehkalahden Veikot",
            "FIN",
            1,
            "leena-maija kriktilä",
            "1237164",
            10.0,
            RunSource.RESULT,
        ),
        # Typo name
        Run(
            "r4",
            2017,
            "ve",
            1,
            "Vehkalahden Veikot",
            "FIN",
            1,
            "leena-maija kriktillä",
            "1237164",
            10.0,
            RunSource.RESULT,
        ),
    ]

    state = LinkingState.from_runs(runs)

    # Run the standard rules
    rule1 = AllowOneOverlapYearRule()  # Just an example normal rule
    rule2 = SameNameEmitConnectedTeamRule()
    rule3 = TypoConnectedEmitRule(0.92)

    rule1.update_run_links(state)
    state.refresh_linked_runners(include_single_run_runners=False)

    rule2.update_run_links(state)
    state.refresh_linked_runners(include_single_run_runners=False)

    rule3.update_run_links(state)
    state.refresh_linked_runners(include_single_run_runners=False)

    # We expect all 4 runs to be under a single linked runner.
    state.refresh_linked_runners(include_single_run_runners=True)
    assert len(state.linked_runners) == 1
    assert len(state.linked_runners[0].runs) == 4
