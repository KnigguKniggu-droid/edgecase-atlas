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


async def test_a_late_adapter_failure_keeps_the_certificates_already_found() -> None:
    """One bad call must not discard evidence, but a target that never worked must still raise.

    The engine accumulates certificates across many candidates. Letting an exception escape
    threw away every certificate found before it. Absorbing the error unconditionally would
    have been worse: a misconfigured agent would look like a clean run.
    """
    from edgecase_atlas.adapters import AdapterExecutionError
    from edgecase_atlas.engine import AtlasEngine
    from edgecase_atlas.fixtures import FaultyDemonstrationAgent
    from edgecase_atlas.properties import STARTER_PROPERTY_PACK

    class FailsAfterAWhile:
        """Behaves like the faulty fixture, then breaks once evidence exists."""

        def __init__(self, fail_after: int) -> None:
            self._inner = FaultyDemonstrationAgent()
            self._calls = 0
            self._fail_after = fail_after

        async def decide(self, scenario: object, seed: int) -> object:
            self._calls += 1
            if self._calls > self._fail_after:
                raise AdapterExecutionError("target went away")
            return await self._inner.decide(scenario, seed)  # type: ignore[arg-type]

    # Enough calls to bank at least one certificate, then fail.
    late = FailsAfterAWhile(fail_after=400)
    result = await AtlasEngine().run(
        late,  # type: ignore[arg-type]
        STARTER_PROPERTY_PACK,
        seed=11,
        budget=60,
    )
    assert result.certificates, "a late failure discarded every certificate already found"

    # A target that fails immediately has produced nothing worth keeping, so it must surface.
    import pytest

    never = FailsAfterAWhile(fail_after=0)
    with pytest.raises(AdapterExecutionError):
        await AtlasEngine().run(
            never,  # type: ignore[arg-type]
            STARTER_PROPERTY_PACK,
            seed=11,
            budget=60,
        )
