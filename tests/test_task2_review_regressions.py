"""Regression tests for the independent Task 2 review findings."""

from __future__ import annotations

import pytest
from hypothesis import given, settings

from edgecase_atlas.coverage import CoverageTracker
from edgecase_atlas.engine import AtlasEngine
from edgecase_atlas.evaluation import CallLedger, evaluate_suspected_violation
from edgecase_atlas.fixtures import FaultyDemonstrationAgent, known_violation_cases
from edgecase_atlas.generation import (
    generate_corpus,
    scenario_from_primitive,
    scenario_primitive_strategy,
)
from edgecase_atlas.models import Decision, FailureCertificate, Scenario
from edgecase_atlas.properties import STARTER_PROPERTY_PACK


def _property(property_id: str):
    return next(item for item in STARTER_PROPERTY_PACK if item.property_id == property_id)


class RedRiskAgent:
    model_id = "red-risk-agent"

    def __init__(self, risk: str, config: dict[str, object] | None = None) -> None:
        self.risk = risk
        self.model_config = {} if config is None else config

    async def decide(self, scenario: Scenario, seed: int) -> Decision:
        del seed
        if scenario.signal == "red":
            return Decision(action="proceed", risk=self.risk, explanation="Synthetic red defect.")
        return Decision(action="reduce_speed", risk="high", explanation="Synthetic source pass.")


@settings(max_examples=20)
@given(scenario_primitive_strategy())
def test_hypothesis_and_production_share_typed_scenario_constructor(primitive) -> None:
    scenario = scenario_from_primitive(primitive)

    assert isinstance(scenario, Scenario)
    assert scenario == scenario_from_primitive(primitive)


@pytest.mark.asyncio
async def test_red_generation_is_an_isolated_passing_source_failing_follow_up() -> None:
    red_property = _property("red_signal_no_proceed")
    generated = generate_corpus((red_property,), seed=13, budget=1)[0].counterfactual
    result = await evaluate_suspected_violation(
        FaultyDemonstrationAgent(),
        red_property,
        generated,
        (1, 2, 3, 4, 5),
        CallLedger(),
        phase="confirmation",
    )

    assert generated.source.signal != "red"
    assert generated.follow_up.signal == "red"
    assert {change.path for change in generated.changed_fields} == {"scenario_id", "signal"}
    assert all(decision.action != "proceed" for decision in result.source_decisions)
    assert all(decision.action == "proceed" for decision in result.follow_up_decisions)
    assert result.accepted is True


@pytest.mark.asyncio
async def test_coverage_extends_to_every_charged_minimization_call() -> None:
    result = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=5
    )

    assert (
        result.coverage_trajectory[-1].charged_target_calls == result.call_ledger.target_calls_total
    )
    assert result.coverage_estimand == "search-and-engineering-gate observable coverage"


@pytest.mark.asyncio
async def test_certificate_id_hashes_decision_evidence_and_unknown_cost_is_explicit() -> None:
    red_property = (_property("red_signal_no_proceed"),)
    low = await AtlasEngine().run(RedRiskAgent("low"), red_property, seed=5, budget=1)
    medium = await AtlasEngine().run(RedRiskAgent("medium"), red_property, seed=5, budget=1)
    certificate = low.certificates[0].certificate
    round_trip = FailureCertificate.model_validate_json(certificate.model_dump_json())

    assert certificate.certificate_id != medium.certificates[0].certificate.certificate_id
    assert certificate.cost_estimate_available is False
    assert certificate.estimated_cost_usd == 0.0
    assert round_trip.cost_estimate_available is False
    assert round_trip.certificate_id == certificate.certificate_id


@pytest.mark.asyncio
async def test_run_identity_includes_target_configuration_and_property_semantics() -> None:
    first = await AtlasEngine().run(
        RedRiskAgent("low", {"temperature": 0}), STARTER_PROPERTY_PACK[:1], seed=8, budget=1
    )
    second = await AtlasEngine().run(
        RedRiskAgent("low", {"temperature": 1}), STARTER_PROPERTY_PACK[:1], seed=8, budget=1
    )

    assert first.metadata.run_id != second.metadata.run_id


def test_non_applicable_predicate_is_not_evaluated() -> None:
    case = known_violation_cases()[1]
    tracker = CoverageTracker()
    red_property = _property("red_signal_no_proceed")
    snapshot = tracker.observe(
        red_property,
        case.counterfactual,
        case.source_decision,
        case.follow_up_decision,
        charged_target_calls=2,
    )

    assert "applicability:red_signal_no_proceed:not_applicable" in snapshot.cells
    assert "predicate:red_signal_no_proceed:not_evaluated" in snapshot.cells
    assert "predicate:red_signal_no_proceed:satisfied" not in snapshot.cells
