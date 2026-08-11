import pytest

from edgecase_atlas.engine import AtlasEngine
from edgecase_atlas.fixtures import FaultyDemonstrationAgent
from edgecase_atlas.properties import STARTER_PROPERTY_PACK


@pytest.mark.asyncio
async def test_engine_emits_deterministic_minimal_reproducing_certificates() -> None:
    first = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=5
    )
    second = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=5
    )

    assert first.certificates
    assert [item.certificate.certificate_id for item in first.certificates] == [
        item.certificate.certificate_id for item in second.certificates
    ]
    certificate = first.certificates[0]
    assert certificate.label == "1-minimal under the declared reducer set"
    assert certificate.certificate.reproduction_count >= 4
    assert certificate.certificate.reproduction_trials == 5
    assert "atlas replay" in certificate.certificate.replay_command
    assert first.call_ledger.target_calls_total == (
        first.call_ledger.search_calls
        + first.call_ledger.confirmation_calls
        + first.call_ledger.minimization_calls
    )
    assert first.metadata.held_out_confirmation_seed_stream == "held-out-confirmation"
