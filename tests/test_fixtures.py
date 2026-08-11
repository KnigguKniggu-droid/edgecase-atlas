from __future__ import annotations

import asyncio

from edgecase_atlas.fixtures import FaultyDemonstrationAgent, known_violation_cases


def test_faulty_agent_is_deterministic_for_fixed_scenario_and_seed() -> None:
    case = known_violation_cases()[0]
    agent = FaultyDemonstrationAgent()

    first = asyncio.run(agent.decide(case.counterfactual.source, seed=99))
    second = asyncio.run(agent.decide(case.counterfactual.source, seed=99))

    assert first == second


def test_known_cases_are_new_synthetic_scenarios() -> None:
    for case in known_violation_cases():
        assert case.counterfactual.source.provenance.source_kind == "synthetic"
        assert case.counterfactual.follow_up.provenance.source_kind == "synthetic"
        assert case.counterfactual.source.provenance.source_reference.startswith("edgecase-atlas")
