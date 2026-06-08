from __future__ import annotations

import functools
import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
from typing import Iterable, Mapping, Sequence
from rapidfuzz.distance import JaroWinkler
from itertools import combinations


class RunSource(Enum):
    """Identifies whether a run came from final results or forecast-year running order."""

    RESULT = "result"
    RUNNING_ORDER = "running_order"


class LinkRelation(Enum):
    """Describes the relationship proposed by a linking rule."""

    SAME_RUNNER = "same_runner"
    DIFFERENT_RUNNER = "different_runner"


@dataclass(frozen=True)
class Run:
    """One observed year/race/team/leg row that may later be linked to a runner identity."""

    run_id: str
    year: int
    race_type: str
    team_id: int
    team_name: str
    team_country: str
    leg: int
    normalized_name: str
    emit_id: str | None
    pace: float | None
    source: RunSource
    original_name: str | None = None


@dataclass(frozen=True)
class CandidateLink:
    """One rule's proposed relation between two runs before final grouping."""

    left_run_id: str
    right_run_id: str
    relation: LinkRelation
    rule_name: str
    reason: str = ""


@dataclass(frozen=True)
class LinkedRunner:
    """An inferred runner identity produced from accepted CandidateLinks."""

    linked_runner_id: str
    unique_name: str
    runs: tuple[Run, ...]


class LinkingRule(ABC):
    """A pipeline step that may add CandidateLinks to LinkingState."""

    rule_name: str

    @abstractmethod
    def update_run_links(self, state: "LinkingState") -> None:
        """Inspect current state and add linking evidence through state methods."""
        ...


@dataclass
class LinkingState:
    """Mutable pipeline state passed through all linking rules."""

    all_runs: list[Run]
    candidate_links: list[CandidateLink] = field(default_factory=list)
    unique_name_by_run_id: dict[str, str] = field(default_factory=dict)
    linked_runners: list[LinkedRunner] = field(default_factory=list)
    unlinked_runs: list[Run] = field(default_factory=list)

    @classmethod
    def from_runs(cls, runs: Iterable[Run]) -> "LinkingState":
        """Create initial state where no rules have linked any runs yet."""
        all_runs = sorted(runs, key=lambda run: run.run_id)
        _raise_if_duplicate_run_ids(all_runs)
        return cls(all_runs=all_runs, unlinked_runs=all_runs)

    @functools.cached_property
    def runs_by_id(self) -> dict[str, Run]:
        """Return all runs keyed by stable run_id."""
        return {run.run_id: run for run in self.all_runs}

    @staticmethod
    def _runs_by_normalized_name(runs: Iterable[Run]) -> dict[str, list[Run]]:
        runs_by_name: dict[str, list[Run]] = defaultdict(list)

        for run in runs:
            runs_by_name[run.normalized_name].append(run)

        return {
            name: sorted(name_runs, key=lambda run: run.run_id)
            for name, name_runs in sorted(runs_by_name.items())
        }

    @functools.cached_property
    def unlinked_runs_by_name(self) -> dict[str, list[Run]]:
        """Return unlinked runs grouped by normalized full name."""
        return self._runs_by_normalized_name(self.unlinked_runs)

    def add_same_runner_group(
        self,
        runs: Iterable[Run],
        *,
        unique_name: str | None,
        rule_name: str,
        reason: str,
    ) -> None:
        """Add SAME_RUNNER candidate links and an optional unique_name for a group of runs."""
        grouped_runs = sorted(runs, key=lambda run: run.run_id)

        if not grouped_runs:
            return

        if unique_name is not None:
            for run in grouped_runs:
                self.unique_name_by_run_id[run.run_id] = unique_name

        candidate_links = _candidate_links_to_anchor(
            runs=grouped_runs,
            relation=LinkRelation.SAME_RUNNER,
            rule_name=rule_name,
            reason=reason,
        )
        self.candidate_links.extend(candidate_links)

    def add_candidate_link(self, candidate_link: CandidateLink) -> None:
        """Add one CandidateLink after checking that both run ids exist."""
        run_ids = set(self.runs_by_id)

        if candidate_link.left_run_id not in run_ids:
            raise KeyError(f"Unknown left_run_id: {candidate_link.left_run_id}")

        if candidate_link.right_run_id not in run_ids:
            raise KeyError(f"Unknown right_run_id: {candidate_link.right_run_id}")

        self.candidate_links.append(candidate_link)

    def refresh_linked_runners(
        self, *, include_single_run_runners: bool = False
    ) -> None:
        """Recompute current LinkedRunners from all CandidateLinks collected so far."""
        self.linked_runners = resolve_links(
            runs=self.all_runs,
            candidate_links=self.candidate_links,
            unique_name_by_run_id=self.unique_name_by_run_id,
            include_single_run_runners=include_single_run_runners,
        )
        linked_run_ids = {
            run.run_id
            for linked_runner in self.linked_runners
            for run in linked_runner.runs
        }
        self.unlinked_runs = [
            run for run in self.all_runs if run.run_id not in linked_run_ids
        ]
        self.__dict__.pop("unlinked_runs_by_name", None)


class UniqueFullNameOneRunPerYearRule(LinkingRule):
    """Links a normalized full-name group when that name has at most one run in each year."""

    rule_name = "unique_full_name_one_run_per_year"

    @staticmethod
    def _has_at_most_one_run_per_year(runs: Sequence[Run]) -> bool:
        run_count_by_year: dict[int, int] = defaultdict(int)

        for run in runs:
            run_count_by_year[run.year] += 1

        return all(run_count <= 1 for run_count in run_count_by_year.values())

    def update_run_links(self, state: LinkingState) -> None:
        for normalized_name, name_runs in state.unlinked_runs_by_name.items():
            if not self._has_at_most_one_run_per_year(name_runs):
                continue

            state.add_same_runner_group(
                name_runs,
                unique_name=normalized_name,
                rule_name=self.rule_name,
                reason="same normalized full name and at most one run per year",
            )


class AllowOneOverlapYearRule(LinkingRule):
    """Groups a same-name set unless it has more than one overlap year.

    An overlap year is a year where the name appears in more than one team's
    results, which suggests two different runners (namesakes) rather than one
    runner changing teams. A single overlap year is tolerated and the runs stay
    grouped as one runner.
    """

    rule_name = "allow_one_overlap_year"

    def update_run_links(self, state: LinkingState) -> None:
        for normalized_name, name_runs in state.unlinked_runs_by_name.items():
            overlap_years = self._overlap_years(name_runs)

            if len(overlap_years) > 1:
                continue

            state.add_same_runner_group(
                name_runs,
                unique_name=normalized_name,
                rule_name=self.rule_name,
                reason="at most one result year has multiple teams for this name",
            )

    @staticmethod
    def _overlap_years(runs: Sequence[Run]) -> list[int]:
        teams_by_year: dict[int, set[str]] = defaultdict(set)

        for run in runs:
            if run.source != RunSource.RESULT:
                continue

            if run.pace is None:
                continue

            teams_by_year[run.year].add(run.team_name)

        return sorted(
            year for year, team_names in teams_by_year.items() if len(team_names) > 1
        )


class SameNameEmitConnectedTeamRule(LinkingRule):
    """Splits an unresolved same-name group by teams connected through shared Emit ids."""

    rule_name = "same_name_emit_connected_team"

    def update_run_links(self, state: LinkingState) -> None:
        for normalized_name, name_runs in state.unlinked_runs_by_name.items():
            grouped_runs = self._split_runs_by_emit_connected_teams(name_runs)

            for runs in grouped_runs:
                team_names = ";".join(sorted({run.team_name for run in runs}))
                unique_name = f"{normalized_name}:{team_names}"
                state.add_same_runner_group(
                    runs,
                    unique_name=unique_name,
                    rule_name=self.rule_name,
                    reason="same name split by Emit-connected team components",
                )

    @staticmethod
    def _split_runs_by_emit_connected_teams(
        runs: Sequence[Run],
    ) -> list[list[Run]]:
        team_groups = GroupMerger()

        for run in runs:
            team_groups.add(run.team_name)

        runs_by_emit: dict[str, list[Run]] = defaultdict(list)
        for run in runs:
            if run.emit_id is not None:
                runs_by_emit[run.emit_id].append(run)

        for emit_runs in runs_by_emit.values():
            team_names = sorted({run.team_name for run in emit_runs})

            if len(team_names) < 2:
                continue

            first_team_name = team_names[0]
            for team_name in team_names[1:]:
                team_groups.union(first_team_name, team_name)

        runs_by_team_group: dict[str, list[Run]] = defaultdict(list)
        for run in runs:
            team_group_id = team_groups.find(run.team_name)
            runs_by_team_group[team_group_id].append(run)

        return [
            sorted(team_group_runs, key=lambda run: run.run_id)
            for _, team_group_runs in sorted(runs_by_team_group.items())
        ]


class TypoConnectedEmitRule(LinkingRule):
    """Links runners with similar names that share Emit ID."""

    rule_name = "typo_connected_emit"

    def __init__(self, jaro_winkler_threshold: float = 0.96) -> None:
        self.threshold = jaro_winkler_threshold

    def update_run_links(self, state: LinkingState) -> None:
        runs_by_emit: dict[str, list[Run]] = defaultdict(list)

        # To connect typo groups that have already been grouped internally,
        # we must look at all runs, not just unlinked_runs.
        # But we only need to link names that haven't been linked together yet.
        for run in state.all_runs:
            if run.emit_id is not None:
                runs_by_emit[run.emit_id].append(run)

        for emit_id, emit_runs in runs_by_emit.items():
            runs_by_name: dict[str, list[Run]] = defaultdict(list)
            for run in emit_runs:
                runs_by_name[run.normalized_name].append(run)

            names = list(runs_by_name.keys())
            if len(names) < 2 or len(names) > 10:
                # Skip if emit has more than 10 names. Likely rental or team emit.
                continue

            for name_a, name_b in combinations(names, 2):
                similarity_score = JaroWinkler.similarity(name_a, name_b)
                if similarity_score >= self.threshold:
                    a_runs = runs_by_name[name_a]
                    b_runs = runs_by_name[name_b]
                    runs_to_link = a_runs + b_runs
                    years_a = {run.year for run in a_runs}
                    years_b = {run.year for run in b_runs}
                    common_years = years_a.intersection(years_b)

                    if common_years:
                        logging.info(
                            f"NOT Linking TYPOED by {emit_id} because common years {common_years}, names {similarity_score:.3f} {name_a} ~ {name_b} "
                        )
                    else:
                        logging.info(
                            f"Linking TYPOED by {emit_id} from [{len(names)}] names {similarity_score:.3f} {name_a} ~ {name_b} "
                        )
                        state.add_same_runner_group(
                            runs_to_link,
                            unique_name=None,
                            rule_name=self.rule_name,
                            reason="shared Emit ID and similar name",
                        )


class ChangedLastNameConnectedByFirstNameAndEmitRule(LinkingRule):
    """Links runners with exact same first name(s) and Emit ID, assuming last name changed."""

    rule_name = "changed_last_name_connected_by_first_name_and_emit"

    def update_run_links(self, state: LinkingState) -> None:
        runs_by_emit: dict[str, list[Run]] = defaultdict(list)

        for run in state.all_runs:
            if run.emit_id is not None:
                runs_by_emit[run.emit_id].append(run)

        for emit_id, group_runs in runs_by_emit.items():
            runs_by_name: dict[str, list[Run]] = defaultdict(list)
            for run in group_runs:
                runs_by_name[run.normalized_name].append(run)

            names = list(runs_by_name.keys())
            if len(names) < 2 or len(names) > 3:
                continue

            for name_a, name_b in combinations(names, 2):
                first_names_a = " ".join(name_a.split()[:-1])
                first_names_b = " ".join(name_b.split()[:-1])

                if first_names_a and first_names_a == first_names_b:
                    # Require that the active years for the two names do not overlap.
                    # Since it's a name change (like marriage), the runner shouldn't
                    # use both last names simultaneously across the same period.
                    years_a = {run.year for run in runs_by_name[name_a]}
                    years_b = {run.year for run in runs_by_name[name_b]}
                    common_years = years_a.intersection(years_b)
                    year_ranges_dont_overlap = min(years_a) > max(years_b) or min(
                        years_b
                    ) > max(years_a)
                    teams_a = {run.team_id for run in runs_by_name[name_a]}
                    teams_b = {run.team_id for run in runs_by_name[name_b]}

                    # This rule combines also some typoed last names,
                    # typos happen without year range guarantee
                    only_in_one_team = len(teams_a | teams_b) == 1

                    if not common_years and (
                        year_ranges_dont_overlap or only_in_one_team
                    ):
                        runs_to_link = runs_by_name[name_a] + runs_by_name[name_b]
                        logging.info(
                            f"Linking LASTNAME by emit {emit_id} with {len(names)} names: {name_a} -> {name_b}, one team: {only_in_one_team}"
                        )
                        state.add_same_runner_group(
                            runs_to_link,
                            unique_name=None,
                            rule_name=self.rule_name,
                            reason="shared Emit ID, exact same first name, and non-overlapping years",
                        )
                    else:
                        logging.info(
                            f"NOT Linking by emit {emit_id} with {len(names)} names: {name_a} -> {name_b}, years overlap: {years_a} / {years_b}"
                        )


class ManualExceptionRule(LinkingRule):
    """Links configured run_id groups before normal automatic rules run."""

    rule_name = "manual_exception"

    manually_connected_run_id_groups: list[list[str]] = [
        [  # Milja Kallio
            "2024-ju-810-5",
            "2026-ju-350-5",
        ],
        [  # Saku Laine
            "2021-ju-925-1",
            "2023-ju-685-6",
            "2021-ju-938-4",
            "2026-ju-350-3",
        ],
    ]

    def update_run_links(self, state: LinkingState) -> None:
        runs_by_id = state.runs_by_id

        for run_id_group in self.manually_connected_run_id_groups:
            valid_run_ids = sorted(
                list(set(runs_by_id.keys()).intersection(run_id_group))
            )
            if valid_run_ids != sorted(run_id_group):
                logging.warning(
                    f"Not all configured run_ids ({run_id_group} != {valid_run_ids}) are valid."
                )
            if valid_run_ids:
                runs = [runs_by_id[run_id] for run_id in valid_run_ids]
                nammes = {run.normalized_name for run in runs}
                logging.info(f"Manually linking names {nammes}")
                state.add_same_runner_group(
                    runs,
                    unique_name=None,
                    rule_name=self.rule_name,
                    reason="manual configured run_id group",
                )


def resolve_links(
    runs: Iterable[Run],
    candidate_links: Iterable[CandidateLink],
    unique_name_by_run_id: Mapping[str, str] | None = None,
    include_single_run_runners: bool = False,
) -> list[LinkedRunner]:
    """Return inferred linked runners from the currently known candidate links."""
    all_runs = sorted(runs, key=lambda run: run.run_id)
    candidate_links = list(candidate_links)
    unique_name_by_run_id = unique_name_by_run_id or {}

    _raise_if_duplicate_run_ids(all_runs)
    run_ids = {run.run_id for run in all_runs}

    group_merger = GroupMerger()
    for run in all_runs:
        group_merger.add(run.run_id)

    same_runner_links = (
        link for link in candidate_links if link.relation == LinkRelation.SAME_RUNNER
    )

    for link in same_runner_links:
        if link.left_run_id not in run_ids or link.right_run_id not in run_ids:
            raise KeyError(f"CandidateLink references unknown run_id: {link}")

        group_merger.union(link.left_run_id, link.right_run_id)

    runs_by_group: dict[str, list[Run]] = defaultdict(list)
    for run in all_runs:
        runs_by_group[group_merger.find(run.run_id)].append(run)

    linked_runners: list[LinkedRunner] = []

    for group_runs in runs_by_group.values():
        run_list = sorted(group_runs, key=lambda run: run.run_id)
        has_unique_name = any(run.run_id in unique_name_by_run_id for run in run_list)
        has_multiple_runs = len(run_list) > 1

        if include_single_run_runners or has_unique_name or has_multiple_runs:
            linked_runners.append(_make_linked_runner(run_list, unique_name_by_run_id))

    return sorted(
        linked_runners,
        key=lambda runner: (runner.unique_name, runner.linked_runner_id),
    )


class GroupMerger:
    """Merges values into groups and reports which group each value is in.

    Each value belongs to a group that is identified by one of its members, the
    "group representative". Initially every value is alone in its own group and
    is therefore its own representative. ``union`` merges the groups of two
    values so they share one representative; ``find`` returns the representative
    of a value's group, so two values are in the same group exactly when they
    have the same representative. The representative is chosen deterministically
    (the smallest member) so results do not depend on insertion order.

    This is the classic disjoint-set / union-find structure, used here to merge
    runs (or teams) that belong together.
    """

    def __init__(self) -> None:
        # Maps each value to another member of its group; following these links
        # repeatedly always ends at the group representative (a value that maps
        # to itself).
        self._group_rep: dict[str, str] = {}

    def add(self, value: str) -> None:
        """Add a value as its own group if it is not already present."""
        self._group_rep.setdefault(value, value)

    def find(self, value: str) -> str:
        """Return the representative of the group the value belongs to."""
        if value not in self._group_rep:
            raise KeyError(f"Unknown group value: {value}")

        linked_value = self._group_rep[value]
        if linked_value != value:
            # Point straight at the representative so future lookups are fast.
            self._group_rep[value] = self.find(linked_value)

        return self._group_rep[value]

    def union(self, left: str, right: str) -> None:
        """Merge the groups of two values, keeping the smaller representative."""
        left_rep = self.find(left)
        right_rep = self.find(right)

        if left_rep == right_rep:
            return

        if right_rep < left_rep:
            left_rep, right_rep = right_rep, left_rep

        self._group_rep[right_rep] = left_rep


def link_runs(
    runs: list[Run],
) -> list[LinkedRunner]:
    """Run the default priority pipeline and return final linked runners."""
    return link_runs_with_state(runs=runs).linked_runners


def link_runs_with_state(
    runs: list[Run],
) -> LinkingState:
    """Run the pipeline and return final state for diagnostics."""
    state = LinkingState.from_runs(runs)
    active_rules = [
        UniqueFullNameOneRunPerYearRule(),
        AllowOneOverlapYearRule(),
        SameNameEmitConnectedTeamRule(),
        TypoConnectedEmitRule(),
        ChangedLastNameConnectedByFirstNameAndEmitRule(),
        ManualExceptionRule(),
    ]

    logging.info(
        f"Starting to group {len(runs)} runs with {len(active_rules)} linking rules"
    )
    for rule in active_rules:
        # Before rule runs, count current runners
        old_linked = len(state.linked_runners)
        logging.info(f"Starting rule {rule.rule_name}")
        rule.update_run_links(state)
        state.refresh_linked_runners(include_single_run_runners=False)
        # After rule runs, count and report new runners
        new_linked = len(state.linked_runners) - old_linked
        logging.info(f"Rule {rule.rule_name} linked {new_linked} new runners")

    state.refresh_linked_runners(include_single_run_runners=True)
    return state


def _candidate_links_to_anchor(
    runs: Sequence[Run],
    relation: LinkRelation,
    rule_name: str,
    reason: str,
) -> list[CandidateLink]:
    sorted_runs = sorted(runs, key=lambda run: run.run_id)

    if len(sorted_runs) < 2:
        return []

    anchor_run = sorted_runs[0]
    return [
        CandidateLink(
            left_run_id=anchor_run.run_id,
            right_run_id=run.run_id,
            relation=relation,
            rule_name=rule_name,
            reason=reason,
        )
        for run in sorted_runs[1:]
    ]


def _make_linked_runner(
    runs: Sequence[Run],
    unique_name_by_run_id: Mapping[str, str],
) -> LinkedRunner:
    unique_names = {
        unique_name_by_run_id[run.run_id]
        for run in runs
        if run.run_id in unique_name_by_run_id
    }

    if len(unique_names) == 1:
        unique_name = next(iter(unique_names))
    else:
        unique_name = _fallback_unique_name(runs)

    return LinkedRunner(
        linked_runner_id=_make_linked_runner_id(runs),
        unique_name=unique_name,
        runs=tuple(sorted(runs, key=lambda run: run.run_id)),
    )


def _fallback_unique_name(runs: Sequence[Run]) -> str:
    names = sorted({run.normalized_name for run in runs})

    if len(names) == 1:
        return names[0]

    return ";".join(names)


def _make_linked_runner_id(runs: Sequence[Run]) -> str:
    run_ids = "|".join(sorted(run.run_id for run in runs))
    digest = hashlib.sha1(run_ids.encode("utf-8")).hexdigest()[:16]
    return digest


def _raise_if_duplicate_run_ids(runs: Iterable[Run]) -> None:
    run_ids = [run.run_id for run in runs]
    if len(run_ids) == len(set(run_ids)):
        return

    from collections import Counter

    counts = Counter(run_ids)
    duplicate_run_ids = sorted(run_id for run_id, count in counts.items() if count > 1)

    if duplicate_run_ids:
        raise ValueError(f"Duplicate run_id values: {duplicate_run_ids[:10]}")
