import pytest

from edgecase_atlas.evaluation import CallLedger, SeedStreams
from edgecase_atlas.fixtures import FaultyDemonstrationAgent, known_violation_cases
from edgecase_atlas.minimizer import HierarchicalMinimizer


@pytest.mark.asyncio
async def test_minimizer_returns_1_minimal_label_and_terminal_audit() -> None:
    case = known_violation_cases()[1]
    result = await HierarchicalMinimizer().minimize(
        FaultyDemonstrationAgent(),
        case.property,
        case.counterfactual,
        SeedStreams(17),
        CallLedger(),
    )

    assert result.accepted is True
    assert result.label == "1-minimal under the declared reducer set"
    assert result.terminal_audit_complete is True
    assert result.counterfactual.changed_fields
    assert result.reproduction_count >= 4
