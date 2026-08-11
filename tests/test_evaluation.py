import pytest

from edgecase_atlas.evaluation import CallLedger, SeedStreams, evaluate_suspected_violation
from edgecase_atlas.fixtures import FaultyDemonstrationAgent, known_violation_cases


@pytest.mark.asyncio
async def test_confirmation_records_each_member_of_every_pair() -> None:
    case = known_violation_cases()[1]
    ledger = CallLedger()
    result = await evaluate_suspected_violation(
        FaultyDemonstrationAgent(),
        case.property,
        case.counterfactual,
        SeedStreams(31).confirmation_seeds(5),
        ledger,
        phase="confirmation",
    )

    assert result.accepted is True
    assert result.reproduction_count == 5
    assert len(result.source_decisions) == 5
    assert len(result.follow_up_decisions) == 5
    assert ledger.target_calls_total == 10
    assert ledger.confirmation_calls == 10
    assert ledger.search_calls == 0
    assert ledger.minimization_calls == 0


def test_seed_streams_are_disjoint_and_deterministic() -> None:
    streams = SeedStreams(99)

    assert streams.search_seeds(5) == SeedStreams(99).search_seeds(5)
    assert set(streams.search_seeds(5)).isdisjoint(streams.shrink_seeds(5))
    assert set(streams.search_seeds(5)).isdisjoint(streams.confirmation_seeds(5))
    assert set(streams.shrink_seeds(5)).isdisjoint(streams.confirmation_seeds(5))
