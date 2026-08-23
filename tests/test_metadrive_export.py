from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from edgecase_atlas.cli import app
from edgecase_atlas.engine import recompute_certificate_id
from edgecase_atlas.metadrive_export import export_metadrive_abstract
from edgecase_atlas.models import FailureCertificate

SAMPLE = Path(__file__).parents[1] / "samples" / "sample-certificate.json"


def _certificate() -> FailureCertificate:
    return FailureCertificate.model_validate_json(SAMPLE.read_text(encoding="utf-8"))


def test_export_is_deterministic_and_explicitly_abstract() -> None:
    certificate = _certificate()
    first = export_metadrive_abstract(certificate)
    second = export_metadrive_abstract(certificate)

    assert first == second
    assert first["status"] == "abstract_export_not_simulator_validation"
    assert first["paired_seeds"] == {
        "certificate": 42,
        "source_scenario": 42,
        "follow_up_scenario": 42,
    }
    scenarios = first["scenarios"]
    assert isinstance(scenarios, dict)
    source = scenarios["source"]
    assert isinstance(source, dict)
    assert source["ego_speed_mps"] == 6.0 * 0.44704
    mapping = first["action_to_controller_mapping"]
    assert isinstance(mapping, dict)
    assert set(mapping) == {"stop", "prepare_stop", "reduce_speed", "increase_gap", "proceed"}


def test_export_rejects_forged_identity_and_replay_command() -> None:
    certificate = _certificate()
    changed_decision = certificate.source_decisions[0].model_copy(
        update={"explanation": "tampered"}
    )
    stale = certificate.model_copy(
        update={"source_decisions": (changed_decision, *certificate.source_decisions[1:])}
    )
    try:
        export_metadrive_abstract(stale)
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("stale certificate identity accepted")

    forged = certificate.model_copy(update={"replay_command": "atlas replay forged.json"})
    forged = forged.model_copy(update={"certificate_id": recompute_certificate_id(forged)})
    try:
        export_metadrive_abstract(forged)
    except ValueError as exc:
        assert "canonical" in str(exc)
    else:
        raise AssertionError("forged replay command accepted")


def test_export_metadrive_cli_writes_canonical_json(tmp_path: Path) -> None:
    output = tmp_path / "bridge.json"
    result = CliRunner().invoke(app, ["export-metadrive", str(SAMPLE), "--output", str(output)])

    assert result.exit_code == 0, result.output
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["schema_version"] == "edgecase-atlas-metadrive-abstract-v1"
    assert f"Export: {output}" in result.output
