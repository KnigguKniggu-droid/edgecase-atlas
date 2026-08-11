"""Adversarial evidence-identity and unavailable-cost invariants."""

from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic import ValidationError

from edgecase_atlas.engine import (
    AtlasEngine,
    _certificate_id,
    _engine_config_hash,
    _property_digest,
)
from edgecase_atlas.fixtures import FaultyDemonstrationAgent
from edgecase_atlas.models import FailureCertificate
from edgecase_atlas.properties import STARTER_PROPERTY_PACK


@pytest.mark.asyncio
async def test_terminal_audit_state_changes_content_addressed_certificate_identity() -> None:
    result = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK[:1], seed=19, budget=1
    )
    minimal = result.certificates[0].minimization
    property_ = STARTER_PROPERTY_PACK[0]
    adapter = FaultyDemonstrationAgent()
    original = _certificate_id(
        adapter, property_, minimal, 19, _property_digest(property_), _engine_config_hash()
    )
    changed = _certificate_id(
        adapter,
        property_,
        replace(minimal, terminal_audit_complete=not minimal.terminal_audit_complete),
        19,
        _property_digest(property_),
        _engine_config_hash(),
    )

    assert original != changed


@pytest.mark.asyncio
async def test_unknown_cost_cannot_serialize_a_nonzero_value() -> None:
    result = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK[:1], seed=23, budget=1
    )
    values = result.certificates[0].certificate.model_dump()
    values["estimated_cost_usd"] = 0.01
    values["cost_estimate_available"] = False

    with pytest.raises(ValidationError, match="Unknown cost estimates"):
        FailureCertificate.model_validate(values)
