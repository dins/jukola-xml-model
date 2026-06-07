from __future__ import annotations

import functools
import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
from typing import Iterable, Mapping, Sequence


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
        """Add SAME_RUNNER candidate links and optional compatibility labels for a group of runs."""
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
        self, *, include_unlinked_singletons: bool = False
    ) -> None:
        """Recompute current LinkedRunners from all CandidateLinks collected so far."""
        self.linked_runners = resolve_links(
            runs=self.all_runs,
            candidate_links=self.candidate_links,
            unique_name_by_run_id=self.unique_name_by_run_id,
            include_unlinked_singletons=include_unlinked_singletons,
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


class LegacyAtMostOneMultiTeamYearRule(LinkingRule):
    """Preserves current group_names.py behavior for names with at most one multi-team result year."""

    rule_name = "legacy_at_most_one_multi_team_year"

    def update_run_links(self, state: LinkingState) -> None:
        for normalized_name, name_runs in state.unlinked_runs_by_name.items():
            years_with_multiple_teams = self._years_with_multiple_result_teams(name_runs)

            if len(years_with_multiple_teams) > 1:
                continue

            state.add_same_runner_group(
                name_runs,
                unique_name=normalized_name,
                rule_name=self.rule_name,
                reason="legacy rule: at most one result year has multiple teams for this name",
            )

    @staticmethod
    def _years_with_multiple_result_teams(runs: Sequence[Run]) -> list[int]:
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
        team_union = UnionFind()

        for run in runs:
            team_union.add(run.team_name)

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
                team_union.union(first_team_name, team_name)

        runs_by_component: dict[str, list[Run]] = defaultdict(list)
        for run in runs:
            component_id = team_union.find(run.team_name)
            runs_by_component[component_id].append(run)

        return [
            sorted(component_runs, key=lambda run: run.run_id)
            for _, component_runs in sorted(runs_by_component.items())
        ]


class ManualExceptionRule(LinkingRule):
    """Links configured run_id groups before normal automatic rules run."""

    rule_name = "manual_exception"

    def __init__(self, run_id_groups: Sequence[Sequence[str]]) -> None:
        self.run_id_groups = [
            list(run_id_group) for run_id_group in run_id_groups
        ]

    def update_run_links(self, state: LinkingState) -> None:
        runs_by_id = state.runs_by_id

        for run_id_group in self.run_id_groups:
            runs = [runs_by_id[run_id] for run_id in run_id_group]
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
    include_unlinked_singletons: bool = False,
) -> list[LinkedRunner]:
    """Return inferred linked runners from the currently known candidate links."""
    all_runs = sorted(runs, key=lambda run: run.run_id)
    links = list(candidate_links)
    labels = unique_name_by_run_id or {}

    _raise_if_duplicate_run_ids(all_runs)
    run_ids = {run.run_id for run in all_runs}

    union_find = UnionFind()
    for run in all_runs:
        union_find.add(run.run_id)

    same_runner_links = (
        link for link in links if link.relation == LinkRelation.SAME_RUNNER
    )

    for link in same_runner_links:
        if link.left_run_id not in run_ids or link.right_run_id not in run_ids:
            raise KeyError(f"CandidateLink references unknown run_id: {link}")

        union_find.union(link.left_run_id, link.right_run_id)

    runs_by_component: dict[str, list[Run]] = defaultdict(list)
    for run in all_runs:
        runs_by_component[union_find.find(run.run_id)].append(run)

    linked_runners: list[LinkedRunner] = []

    for component_runs in runs_by_component.values():
        run_list = sorted(component_runs, key=lambda run: run.run_id)
        has_label = any(run.run_id in labels for run in run_list)
        has_multiple_runs = len(run_list) > 1

        if include_unlinked_singletons or has_label or has_multiple_runs:
            linked_runners.append(_make_linked_runner(run_list, labels))

    return sorted(
        linked_runners,
        key=lambda runner: (runner.unique_name, runner.linked_runner_id),
    )


class UnionFind:
    """Small deterministic union-find used by resolve_links."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, value: str) -> None:
        """Add a value as its own component if it is not already present."""
        self._parent.setdefault(value, value)

    def find(self, value: str) -> str:
        """Return the stable component representative for a value."""
        if value not in self._parent:
            raise KeyError(f"Unknown union-find value: {value}")

        parent = self._parent[value]
        if parent != value:
            self._parent[value] = self.find(parent)

        return self._parent[value]

    def union(self, left: str, right: str) -> None:
        """Merge two components using deterministic representative ordering."""
        left_parent = self.find(left)
        right_parent = self.find(right)

        if left_parent == right_parent:
            return

        if right_parent < left_parent:
            left_parent, right_parent = right_parent, left_parent

        self._parent[right_parent] = left_parent


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
        LegacyAtMostOneMultiTeamYearRule(),
        SameNameEmitConnectedTeamRule(),
    ]

    logging.info(f"Starting to group {len(runs)} runs with {len(active_rules)} linking rules")
    for rule in active_rules:
        # Before rule runs, count current runners
        old_linked = len(state.linked_runners)
        logging.info(f"Starting rule {rule.rule_name}")
        rule.update_run_links(state)
        state.refresh_linked_runners(include_unlinked_singletons=False)
        # After rule runs, count and report new runners
        new_linked = len(state.linked_runners) - old_linked
        logging.info(f"Rule {rule.rule_name} linked {new_linked} new runners")

    state.refresh_linked_runners(include_unlinked_singletons=True)
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
    return f"linked-runner-{digest}"


def _raise_if_duplicate_run_ids(runs: Iterable[Run]) -> None:
    run_ids = [run.run_id for run in runs]
    if len(run_ids) == len(set(run_ids)):
        return

    from collections import Counter

    counts = Counter(run_ids)
    duplicate_run_ids = sorted(run_id for run_id, count in counts.items() if count > 1)

    if duplicate_run_ids:
        raise ValueError(f"Duplicate run_id values: {duplicate_run_ids[:10]}")
