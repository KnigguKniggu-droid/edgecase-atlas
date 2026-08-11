from __future__ import annotations

import json

import pytest

from edgecase_atlas.evaluation import CallLedger, evaluate_pair
from edgecase_atlas.fixtures import known_violation_cases
from edgecase_atlas.models import Decision, Scenario
from edgecase_atlas.serialization import canonical_json


@pytest.mark.asyncio
async def test_successful_invocations_capture_complete_pair_evidence() -> None:
    case = known_violation_cases()[0]

    class Adapter:
        last_call_cost_usd = 0.01

        async def decide(self, scenario: Scenario, _seed: int) -> Decision:
            return Decision(action="stop", risk="high", explanation=scenario.scenario_id)

    ledger = CallLedger()
    await evaluate_pair(Adapter(), case.property, case.counterfactual, 17, ledger, phase="search")
    source, follow_up = ledger.invocations
    assert source.property_id == case.property_id
    assert source.relation_id == case.counterfactual.relation_id
    assert source.pair_role == "source"
    assert source.scenario == case.counterfactual.source
    assert source.decision is not None
    assert source.seed == 17
    assert source.succeeded is True
    assert follow_up.pair_role == "follow_up"
    assert follow_up.scenario == case.counterfactual.follow_up
    assert follow_up.ordinal == 2


@pytest.mark.asyncio
async def test_failed_invocation_never_reuses_stale_cost_or_decision() -> None:
    case = known_violation_cases()[0]

    class Adapter:
        def __init__(self) -> None:
            self.calls = 0
            self.last_call_cost_usd: float | None = None

        async def decide(self, _scenario: Scenario, _seed: int) -> Decision:
            self.calls += 1
            if self.calls == 1:
                self.last_call_cost_usd = 0.25
                return Decision(action="stop", risk="high", explanation="first")
            raise RuntimeError("sanitized failure")

    ledger = CallLedger()
    with pytest.raises(RuntimeError):
        await evaluate_pair(
            Adapter(), case.property, case.counterfactual, 19, ledger, phase="search"
        )
    assert ledger.target_calls_total == 2
    assert ledger.estimated_cost_usd == pytest.approx(0.25)
    failed = ledger.invocations[-1]
    assert failed.pair_role == "follow_up"
    assert failed.decision is None
    assert failed.cost_estimate_available is False
    assert failed.estimated_cost_usd == 0.0
    assert failed.error_type == "RuntimeError"
    assert ledger.cost_estimate_available is False


@pytest.mark.asyncio
async def test_invocation_trace_is_canonical_json_safe() -> None:
    case = known_violation_cases()[0]

    class Adapter:
        last_call_cost_usd = 0.0

        async def decide(self, _scenario: Scenario, _seed: int) -> Decision:
            return Decision(action="stop", risk="high", explanation="trace")

    ledger = CallLedger()
    await evaluate_pair(Adapter(), case.property, case.counterfactual, 23, ledger, phase="search")
    payload = canonical_json(ledger.invocations)
    decoded = json.loads(payload)
    assert decoded[0]["scenario"]["schema_version"] == "av-text-v1"
    assert decoded[0]["decision"]["action"] == "stop"
