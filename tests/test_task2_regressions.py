"""Regression tests for Task 2 reproducibility and audit boundaries."""

from __future__ import annotations

import pytest
from hypothesis import given, settings

from edgecase_atlas.constraints import validate_scenario
from edgecase_atlas.engine import AtlasEngine
from edgecase_atlas.evaluation import (
    CallLedger,
    SeedStreams,
    evaluate_pair,
    evaluate_suspected_violation,
)
from edgecase_atlas.fixtures import FaultyDemonstrationAgent, known_violation_cases
from edgecase_atlas.generation import generate_corpus, scenario_strategy
from edgecase_atlas.minimizer import HierarchicalMinimizer
from edgecase_atlas.models import Decision, Scenario
from edgecase_atlas.properties import STARTER_PROPERTY_PACK


class PatternHazardAgent:
    """Synthetic stochastic fixture whose hazard violation set is explicit by request seed."""

    model_id = "pattern-hazard-agent"

    def __init__(self, violating_seeds: frozenset[int]) -> None:
        self.violating_seeds = violating_seeds

    async def decide(self, scenario: Scenario, seed: int) -> Decision:
        has_hazard = any(actor.actor_type == "hazard" for actor in scenario.actors)
        if has_hazard and seed in self.violating_seeds:
            return Decision(
                action="proceed", risk="low", explanation="Synthetic pattern violation."
            )
        return Decision(
            action="reduce_speed", risk="high", explanation="Synthetic baseline caution."
        )


class DescriptionSensitiveHazardAgent:
    """Keeps a failed terminal description operation available for the audit."""

    model_id = "description-sensitive-hazard-agent"

    async def decide(self, scenario: Scenario, seed: int) -> Decision:
        del seed
        has_hazard = any(actor.actor_type == "hazard" for actor in scenario.actors)
        if has_hazard and "relevant hazard" in scenario.description:
            return Decision(
                action="proceed", risk="low", explanation="Synthetic wording condition."
            )
        return Decision(
            action="reduce_speed", risk="high", explanation="Synthetic baseline caution."
        )


class RaisingAgent:
    model_id = "raising-agent"

    async def decide(self, scenario: Scenario, seed: int) -> Decision:
        del scenario, seed
        raise RuntimeError("Synthetic adapter failure")


@settings(max_examples=20)
@given(scenario_strategy())
def test_hypothesis_strategy_yields_z3_valid_scenario_models(scenario: Scenario) -> None:
    assert isinstance(scenario, Scenario)
    assert validate_scenario(scenario).valid


def test_different_generation_seeds_produce_different_ordered_corpora() -> None:
    assert generate_corpus(STARTER_PROPERTY_PACK, seed=1, budget=10) != generate_corpus(
        STARTER_PROPERTY_PACK, seed=2, budget=10
    )


@pytest.mark.asyncio
async def test_three_of_five_engineering_gate_is_rejected() -> None:
    case = known_violation_cases()[1]
    result = await evaluate_suspected_violation(
        PatternHazardAgent(frozenset({1, 2, 3})),
        case.property,
        case.counterfactual,
        (1, 2, 3, 4, 5),
        CallLedger(),
        phase="confirmation",
    )

    assert result.reproduction_count == 3
    assert result.accepted is False


@pytest.mark.asyncio
async def test_four_of_five_engineering_gate_is_accepted() -> None:
    case = known_violation_cases()[1]
    result = await evaluate_suspected_violation(
        PatternHazardAgent(frozenset({1, 2, 3, 4})),
        case.property,
        case.counterfactual,
        (1, 2, 3, 4, 5),
        CallLedger(),
        phase="confirmation",
    )

    assert result.reproduction_count == 4
    assert result.accepted is True


@pytest.mark.asyncio
async def test_every_attempted_adapter_call_is_charged_even_when_it_raises() -> None:
    case = known_violation_cases()[1]
    ledger = CallLedger()

    with pytest.raises(RuntimeError, match="Synthetic adapter failure"):
        await evaluate_pair(
            RaisingAgent(), case.property, case.counterfactual, 7, ledger, phase="search"
        )

    assert ledger.target_calls_total == 1
    assert ledger.search_calls == 1


def test_seed_streams_reserve_unexecuted_held_out_confirmation() -> None:
    streams = SeedStreams(101)
    search = set(streams.search_seeds(7))
    engineering = set(streams.engineering_gate_seeds(7))
    shrink = set(streams.shrink_seeds(7))
    held_out = set(streams.held_out_confirmation_seeds(7))

    assert search.isdisjoint(engineering)
    assert search.isdisjoint(shrink)
    assert search.isdisjoint(held_out)
    assert engineering.isdisjoint(shrink)
    assert engineering.isdisjoint(held_out)
    assert shrink.isdisjoint(held_out)


@pytest.mark.asyncio
async def test_minimizer_validates_both_sides_and_exhausts_terminal_single_operations() -> None:
    case = known_violation_cases()[1]
    result = await HierarchicalMinimizer().minimize(
        DescriptionSensitiveHazardAgent(),
        case.property,
        case.counterfactual,
        SeedStreams(41),
        CallLedger(),
    )

    assert result.accepted is True
    assert validate_scenario(result.counterfactual.source).valid
    assert validate_scenario(result.counterfactual.follow_up).valid
    assert result.terminal_audit_complete is True
    assert result.terminal_audit_attempts
    assert all(not attempt.accepted for attempt in result.terminal_audit_attempts)
    assert any(
        "shorten_description" in attempt.operation for attempt in result.terminal_audit_attempts
    )


@pytest.mark.asyncio
async def test_engine_tracks_all_phases_preserves_trace_and_replay_determinism() -> None:
    first = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=5
    )
    second = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=5
    )

    assert first.call_ledger.search_calls == 10
    assert first.call_ledger.confirmation_calls == 50
    assert first.call_ledger.minimization_calls > 0
    assert first.call_ledger.target_calls_total == (
        first.call_ledger.search_calls
        + first.call_ledger.confirmation_calls
        + first.call_ledger.minimization_calls
    )
    assert first.metadata.held_out_confirmation_seed_stream == "held-out-confirmation"
    assert "held-out-confirmation" not in first.metadata.executed_seed_streams
    assert [point.charged_target_calls for point in first.coverage_trajectory[:6]] == [
        2,
        4,
        6,
        8,
        10,
        12,
    ]
    assert [item.certificate.certificate_id for item in first.certificates] == [
        item.certificate.certificate_id for item in second.certificates
    ]
    assert [item.certificate.replay_command for item in first.certificates] == [
        item.certificate.replay_command for item in second.certificates
    ]
    for item in first.certificates:
        assert item.certificate.source_decisions == item.minimization.reproduction.source_decisions
        assert (
            item.certificate.follow_up_decisions
            == item.minimization.reproduction.follow_up_decisions
        )
        assert item.certificate.replay_command == (
            f"atlas replay certificates/{item.certificate.certificate_id}.json --seed 42"
        )
