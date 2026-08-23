"""Domain-aware 1-minimization for reproducible paired property violations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from edgecase_atlas.evaluation import (
    AgentAdapter,
    CallLedger,
    ReproductionResult,
    SeedStreams,
    evaluate_suspected_violation,
)
from edgecase_atlas.generation import build_counterfactual
from edgecase_atlas.models import Actor, Counterfactual, Scenario
from edgecase_atlas.properties import REQUIRED_REPRODUCTIONS, SafetyProperty

_LABEL = "1-minimal under the declared reducer set"


@dataclass(frozen=True, slots=True)
class ReductionAttempt:
    """A complete record of one reducer operation and its engineering-gate result."""

    operation: str
    accepted: bool
    reason: str


@dataclass(frozen=True, slots=True)
class MinimizationResult:
    """A local 1-minimal reproducing contrast, not a global or causal optimum."""

    counterfactual: Counterfactual
    reproduction_count: int
    reproduction_trials: int
    reproduction: ReproductionResult
    accepted: bool
    label: str
    reducer_vocabulary: tuple[str, ...]
    attempts: tuple[ReductionAttempt, ...]
    terminal_audit_attempts: tuple[ReductionAttempt, ...]
    terminal_audit_complete: bool


@dataclass(frozen=True, slots=True)
class _Operation:
    name: str
    source: Scenario
    follow_up: Scenario


class HierarchicalMinimizer:
    """Apply greedy stages, then exhaustively test all remaining single operations."""

    reducer_vocabulary = (
        "remove_background_actor",
        "remove_optional_event_metadata",
        "simplify_actor_distance",
        "reduce_numeric_delta",
        "shorten_description",
    )

    async def minimize(
        self,
        adapter: AgentAdapter,
        property_: SafetyProperty,
        counterfactual: Counterfactual,
        streams: SeedStreams,
        ledger: CallLedger,
        *,
        trial_count: int = 5,
    ) -> MinimizationResult:
        """Reduce with a disjoint shrink stream and retain only 4-of-5 candidates.

        The final audit establishes only 1-minimality under ``reducer_vocabulary``. Future
        non-adaptive confirmation must use the reserved held-out stream outside this method.
        """
        if trial_count != 5:
            raise ValueError("The alpha minimizer requires exactly five engineering-gate trials")
        seeds = streams.shrink_seeds(trial_count)
        current = counterfactual
        attempts: list[ReductionAttempt] = []
        terminal_attempts: list[ReductionAttempt] = []
        current_reproduction = await self._reproduce(adapter, property_, current, seeds, ledger)
        attempts.append(
            ReductionAttempt(
                "initial_reproduction",
                current_reproduction.accepted,
                "4-of-5 engineering gate" if current_reproduction.accepted else "gate not met",
            )
        )
        if not current_reproduction.accepted:
            return MinimizationResult(
                current,
                current_reproduction.reproduction_count,
                current_reproduction.reproduction_trials,
                current_reproduction,
                False,
                _LABEL,
                self.reducer_vocabulary,
                tuple(attempts),
                (),
                False,
            )

        changed = True
        while changed:
            changed = False
            for operation in self._operations(current):
                accepted, reproduction, attempt = await self._try_operation(
                    adapter, property_, current, operation, seeds, ledger
                )
                attempts.append(attempt)
                if accepted:
                    current = operation_to_counterfactual(property_, operation, current.relation_id)
                    current_reproduction = reproduction
                    changed = True
                    break

        for operation in self._operations(current):
            accepted, _reproduction, attempt = await self._try_operation(
                adapter, property_, current, operation, seeds, ledger
            )
            if accepted:
                terminal_attempts.append(
                    ReductionAttempt(
                        attempt.operation, True, "terminal audit found reducible candidate"
                    )
                )
            else:
                terminal_attempts.append(attempt)
        terminal_audit_complete = all(not attempt.accepted for attempt in terminal_attempts)
        return MinimizationResult(
            current,
            current_reproduction.reproduction_count,
            current_reproduction.reproduction_trials,
            current_reproduction,
            terminal_audit_complete,
            _LABEL,
            self.reducer_vocabulary,
            tuple(attempts),
            tuple(terminal_attempts),
            terminal_audit_complete,
        )

    async def _reproduce(
        self,
        adapter: AgentAdapter,
        property_: SafetyProperty,
        counterfactual: Counterfactual,
        seeds: tuple[int, ...],
        ledger: CallLedger,
    ) -> ReproductionResult:
        return await evaluate_suspected_violation(
            adapter,
            property_,
            counterfactual,
            seeds,
            ledger,
            phase="minimization",
            required_reproductions=REQUIRED_REPRODUCTIONS,
        )

    async def _try_operation(
        self,
        adapter: AgentAdapter,
        property_: SafetyProperty,
        current: Counterfactual,
        operation: _Operation,
        seeds: tuple[int, ...],
        ledger: CallLedger,
    ) -> tuple[bool, ReproductionResult, ReductionAttempt]:
        try:
            candidate = operation_to_counterfactual(property_, operation, current.relation_id)
        except ValueError as error:
            return (
                False,
                ReproductionResult((), 0, 0, False, "minimization"),
                ReductionAttempt(operation.name, False, f"invalid: {error}"),
            )
        reproduction = await self._reproduce(adapter, property_, candidate, seeds, ledger)
        accepted = reproduction.accepted
        reason = "4-of-5 engineering gate" if accepted else "4-of-5 engineering gate not met"
        return accepted, reproduction, ReductionAttempt(operation.name, accepted, reason)

    def _operations(self, relation: Counterfactual) -> tuple[_Operation, ...]:
        operations: list[_Operation] = []
        operations.extend(_background_actor_operations(relation))
        operations.extend(_metadata_operations(relation))
        operations.extend(_distance_operations(relation))
        operations.extend(_numeric_delta_operations(relation))
        operations.extend(_description_operations(relation))
        return tuple(operations)


def operation_to_counterfactual(
    property_: SafetyProperty, operation: _Operation, relation_id: str
) -> Counterfactual:
    """Rebuild through typed, Z3, canonical-diff, and frozen-field validation."""
    return build_counterfactual(property_, operation.source, operation.follow_up, relation_id)


def _background_actor_operations(relation: Counterfactual) -> tuple[_Operation, ...]:
    source_by_id = {actor.actor_id: actor for actor in relation.source.actors}
    follow_by_id = {actor.actor_id: actor for actor in relation.follow_up.actors}
    output: list[_Operation] = []
    for actor_id in sorted(set(source_by_id) | set(follow_by_id)):
        source_actor = source_by_id.get(actor_id)
        follow_actor = follow_by_id.get(actor_id)
        if not _is_background(source_actor) or not _is_background(follow_actor):
            continue
        output.append(
            _Operation(
                f"remove_background_actor:{actor_id}",
                relation.source.model_copy(
                    update={
                        "actors": tuple(
                            actor for actor in relation.source.actors if actor.actor_id != actor_id
                        )
                    }
                ),
                relation.follow_up.model_copy(
                    update={
                        "actors": tuple(
                            actor
                            for actor in relation.follow_up.actors
                            if actor.actor_id != actor_id
                        )
                    }
                ),
            )
        )
    return tuple(output)


def _metadata_operations(relation: Counterfactual) -> tuple[_Operation, ...]:
    output: list[_Operation] = []
    actor_ids = sorted(
        {actor.actor_id for actor in relation.source.actors + relation.follow_up.actors}
    )
    for actor_id in actor_ids:
        source = _replace_actor_metadata(relation.source, actor_id)
        follow_up = _replace_actor_metadata(relation.follow_up, actor_id)
        if source != relation.source or follow_up != relation.follow_up:
            output.append(
                _Operation(f"remove_optional_event_metadata:{actor_id}", source, follow_up)
            )
    return tuple(output)


def _distance_operations(relation: Counterfactual) -> tuple[_Operation, ...]:
    output: list[_Operation] = []
    for actor_id in sorted(
        {actor.actor_id for actor in relation.source.actors + relation.follow_up.actors}
    ):
        source = _replace_actor_distance(relation.source, actor_id, 1.0)
        follow_up = _replace_actor_distance(relation.follow_up, actor_id, 1.0)
        if source != relation.source or follow_up != relation.follow_up:
            output.append(_Operation(f"simplify_actor_distance:{actor_id}", source, follow_up))
    return tuple(output)


def _numeric_delta_operations(relation: Counterfactual) -> tuple[_Operation, ...]:
    source = relation.source
    follow_up = relation.follow_up
    target_speed = source.speed_limit_mph + 1.0
    if (
        follow_up.speed_mph > source.speed_mph
        and follow_up.speed_mph > source.speed_limit_mph
        and follow_up.speed_mph > target_speed
    ):
        return (
            _Operation(
                "reduce_numeric_delta:speed_mph",
                source,
                follow_up.model_copy(update={"speed_mph": target_speed}),
            ),
        )
    return ()


def _description_operations(relation: Counterfactual) -> tuple[_Operation, ...]:
    source_text, follow_text = _shortened_descriptions(
        relation.source.description, relation.follow_up.description
    )
    if source_text == relation.source.description and follow_text == relation.follow_up.description:
        return ()
    return (
        _Operation(
            "shorten_description",
            relation.source.model_copy(update={"description": source_text}),
            relation.follow_up.model_copy(update={"description": follow_text}),
        ),
    )


def _shortened_descriptions(source: str, follow_up: str) -> tuple[str, str]:
    if "vehicle wording" in source and "car wording" in follow_up:
        return "vehicle wording", "car wording"
    return "Synthetic road.", "Synthetic road."


def _replace_actor_metadata(scenario: Scenario, actor_id: str) -> Scenario:
    return _replace_actor(
        scenario, actor_id, lambda actor: actor.model_copy(update={"event_metadata": ()})
    )


def _replace_actor_distance(scenario: Scenario, actor_id: str, distance_m: float) -> Scenario:
    return _replace_actor(
        scenario, actor_id, lambda actor: actor.model_copy(update={"distance_m": distance_m})
    )


def _replace_actor(
    scenario: Scenario, actor_id: str, transform: Callable[[Actor], Actor]
) -> Scenario:
    actors = tuple(
        transform(actor) if actor.actor_id == actor_id else actor for actor in scenario.actors
    )
    return scenario if actors == scenario.actors else scenario.model_copy(update={"actors": actors})


def _is_background(actor: Actor | None) -> bool:
    return actor is not None and actor.relevance == "background"
