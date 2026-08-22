from __future__ import annotations

import asyncio
import json

import pytest
from app import ui
from scripts.smoke_test import _scan_payloads, scan_artifacts

from edgecase_atlas.engine import AtlasEngine
from edgecase_atlas.fixtures import FaultyDemonstrationAgent
from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.serialization import run_document, validate_run_document


def test_report_validator_rejects_forged_certificate() -> None:
    run = asyncio.run(
        AtlasEngine().run(FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=1)
    )
    document = json.loads(json.dumps(run_document(run)))
    document["certificates"][0]["follow_up_decisions"][0]["action"] = "stop"
    with pytest.raises(ValueError, match="digest"):
        validate_run_document(document)


def test_report_validator_rejects_inconsistent_call_ledger() -> None:
    run = asyncio.run(
        AtlasEngine().run(FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=1)
    )
    document = json.loads(json.dumps(run_document(run)))
    document["call_ledger"]["target_calls_total"] += 1
    with pytest.raises(ValueError, match="ledger total"):
        validate_run_document(document)


def test_public_limits_bound_budget_and_artifact_size(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError):
        ui.validate_public_request(
            property_ids=("red_signal_no_proceed",),
            sample_property_id="red_signal_no_proceed",
            seed=42,
            budget=ui.PUBLIC_BUDGET_MAX + 1,
            custom_text="",
        )
    request = ui.validate_public_request(
        property_ids=("red_signal_no_proceed",),
        sample_property_id="red_signal_no_proceed",
        seed=42,
        budget=1,
        custom_text="",
    )
    monkeypatch.setattr(ui, "PUBLIC_ARTIFACT_MAX_BYTES", 1)
    with pytest.raises(ValueError, match="size limit"):
        asyncio.run(ui.build_demo_artifacts(request))


def test_report_validator_rejects_forged_metadata_and_coverage() -> None:
    run = asyncio.run(
        AtlasEngine().run(FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=1)
    )
    document = json.loads(json.dumps(run_document(run)))
    document["metadata"]["candidate_budget"] = 99
    with pytest.raises(ValueError, match=r"digest|budget|metadata"):
        validate_run_document(document)
    document = json.loads(json.dumps(run_document(run)))
    document["coverage"]["cells"].append("forged:cell")
    with pytest.raises(ValueError, match="coverage"):
        validate_run_document(document)


def test_smoke_scans_fail_closed_on_nul(tmp_path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_bytes(b"{}\0private")
    with pytest.raises(RuntimeError, match="privacy scan"):
        scan_artifacts((artifact,))
    with pytest.raises(RuntimeError, match="privacy scan"):
        _scan_payloads({"download.json": b"{}\0private"})


def test_public_rate_limit_bounds_sequential_work() -> None:
    ui._PUBLIC_RUN_TIMES.clear()
    assert all(ui.claim_public_run(float(index)) for index in range(ui.PUBLIC_RUNS_PER_MINUTE))
    assert ui.claim_public_run(float(ui.PUBLIC_RUNS_PER_MINUTE)) is False
    assert ui.claim_public_run(61.0) is True
    ui._PUBLIC_RUN_TIMES.clear()
