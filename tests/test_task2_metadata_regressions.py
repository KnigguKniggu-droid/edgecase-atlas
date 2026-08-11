"""Regression coverage for truthful adaptive seed-stream metadata."""

from __future__ import annotations

import pytest

from edgecase_atlas.engine import AtlasEngine
from edgecase_atlas.models import Decision, Scenario
from edgecase_atlas.properties import STARTER_PROPERTY_PACK


class NoViolationAgent:
    model_id = "no-violation-agent"

    async def decide(self, scenario: Scenario, seed: int) -> Decision:
        del scenario, seed
        return Decision(
            action="reduce_speed", risk="high", explanation="Synthetic no-violation fixture."
        )


@pytest.mark.asyncio
async def test_executed_seed_streams_include_only_actual_work() -> None:
    engine = AtlasEngine()
    empty = await engine.run(NoViolationAgent(), STARTER_PROPERTY_PACK, seed=3, budget=0)
    no_violation = await engine.run(NoViolationAgent(), STARTER_PROPERTY_PACK, seed=3, budget=1)

    assert empty.metadata.executed_seed_streams == ()
    assert no_violation.metadata.executed_seed_streams == ("search",)
    assert (
        empty.metadata.held_out_confirmation_seed_stream not in empty.metadata.executed_seed_streams
    )
    assert (
        no_violation.metadata.held_out_confirmation_seed_stream
        not in no_violation.metadata.executed_seed_streams
    )
