from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import pytest
from typer.testing import CliRunner

from edgecase_atlas.cli import app
from edgecase_atlas.engine import AtlasEngine
from edgecase_atlas.fixtures import FaultyDemonstrationAgent
from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.reporting import render_html_report
from edgecase_atlas.serialization import run_document

runner = CliRunner()


@pytest.mark.asyncio
async def test_run_embeds_ordered_property_snapshot_and_report_uses_only_artifact(
    tmp_path: Path,
) -> None:
    run = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=1
    )
    document = run_document(run)
    assert [item["property_id"] for item in document["property_pack"]] == [
        item.property_id for item in STARTER_PROPERTY_PACK
    ]
    certificate = document["certificates"][0]
    assert certificate["property"] == document["property_pack"][0]
    assert certificate["property"]["description"] == STARTER_PROPERTY_PACK[0].description
    assert certificate["property"]["scope_note"] == STARTER_PROPERTY_PACK[0].scope_note
    assert certificate["output_distribution"]["actions"]
    assert certificate["output_distribution"]["risks"]

    certificate["property"]["description"] = "Frozen artifact assumption sentinel."
    document["property_pack"][0]["description"] = "Selected pack artifact sentinel."
    output = tmp_path / "snapshot.html"
    render_html_report(document, output)
    html = output.read_text(encoding="utf-8")
    assert "Frozen artifact assumption sentinel." in html
    assert "Selected pack artifact sentinel." in html


@pytest.mark.asyncio
async def test_report_contains_complete_reproducibility_fields(tmp_path: Path) -> None:
    run = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=1
    )
    document = run_document(run)
    certificate = document["certificates"][0]
    output = tmp_path / "complete.html"
    render_html_report(document, output)
    html = output.read_text(encoding="utf-8")
    for expected in (
        certificate["property"]["description"],
        certificate["property"]["scope_note"],
        str(certificate["changed_fields"][0]["from_value"]),
        str(certificate["changed_fields"][0]["to_value"]),
        str(certificate["seed"]),
        certificate["model_config_hash"],
        certificate["software_version"],
        f"{certificate['latency_ms']} ms",
        certificate["replay_command"],
        "Output distributions",
        "Actions:",
        "Risks:",
    ):
        assert expected in html


def test_identical_cli_run_reuses_ids_and_replaces_complete_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    args = ["test", "--config", "atlas.yaml", "--budget", "1", "--seed", "42"]
    assert runner.invoke(app, args).exit_code == 0
    run_path = next((tmp_path / "runs").glob("*.json"))
    certificate_path = next((tmp_path / "certificates").glob("*.json"))
    trace_path = next((tmp_path / "traces").glob("*.jsonl"))
    first_run_id = json.loads(run_path.read_text(encoding="utf-8"))["metadata"]["run_id"]
    first_certificate_id = json.loads(certificate_path.read_text(encoding="utf-8"))[
        "certificate_id"
    ]
    first_events = [
        json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]

    assert runner.invoke(app, args).exit_code == 0
    assert len(list((tmp_path / "runs").glob("*.json"))) == 1
    assert len(list((tmp_path / "certificates").glob("*.json"))) == 1
    assert json.loads(run_path.read_text(encoding="utf-8"))["metadata"]["run_id"] == first_run_id
    assert (
        json.loads(certificate_path.read_text(encoding="utf-8"))["certificate_id"]
        == first_certificate_id
    )
    all_events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert all_events == first_events
    assert sum(item["event_type"] == "run_started" for item in all_events) == 1
    assert sum(item["event_type"] == "run_completed" for item in all_events) == 1


def test_report_rejects_run_id_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    crafted = tmp_path / "crafted.json"
    crafted.write_text(json.dumps({"metadata": {"run_id": "../escape"}}), encoding="utf-8")
    result = runner.invoke(app, ["report", str(crafted), "--format", "html"])
    assert result.exit_code != 0
    assert not (tmp_path / "escape.html").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("software_version", "99.0.0"),
        ("engine_config_hash", "mismatch"),
        ("property_semantics_digest", "mismatch"),
        ("reproduction_trials", 6),
    ],
)
def test_replay_rejects_incompatible_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    assert (
        runner.invoke(
            app, ["test", "--config", "atlas.yaml", "--budget", "1", "--seed", "42"]
        ).exit_code
        == 0
    )
    certificate_path = next((tmp_path / "certificates").glob("*.json"))
    data = json.loads(certificate_path.read_text(encoding="utf-8"))
    data[field] = value
    modified = tmp_path / f"modified-{field}.json"
    modified.write_text(json.dumps(data), encoding="utf-8")
    assert runner.invoke(app, ["replay", str(modified)]).exit_code != 0


def test_jinja_template_is_packaged() -> None:
    assert files("edgecase_atlas").joinpath("templates/report.html.j2").is_file()
