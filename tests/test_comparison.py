from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from edgecase_atlas.cli import app
from edgecase_atlas.comparison import compare_run_documents, coverage_trajectory_auc
from edgecase_atlas.engine import AtlasEngine
from edgecase_atlas.fixtures import FaultyDemonstrationAgent
from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.serialization import run_document, write_canonical_json


def _document(*, seed: int, budget: int) -> dict[str, object]:
    run = asyncio.run(
        AtlasEngine().run(
            FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=seed, budget=budget
        )
    )
    return run_document(run)


def test_coverage_trajectory_auc_includes_origin_and_handles_zero_calls() -> None:
    assert coverage_trajectory_auc([]) == 0.0
    assert (
        coverage_trajectory_auc(
            [
                {"charged_target_calls": 2, "observed_cells": 4},
                {"charged_target_calls": 4, "observed_cells": 6},
            ]
        )
        == 14.0
    )


def test_compare_run_documents_is_deterministic_and_reports_deltas() -> None:
    run_a = _document(seed=42, budget=1)
    run_b = _document(seed=43, budget=2)

    first = compare_run_documents(run_a, run_b)
    second = compare_run_documents(run_a, run_b)

    assert first == second
    assert first["schema_version"] == "atlas-comparison-v1"
    assert first["runs"] == {
        "a": run_a["metadata"]["run_id"],
        "b": run_b["metadata"]["run_id"],
    }
    assert first["call_totals"]["delta"] == (
        run_b["call_ledger"]["target_calls_total"] - run_a["call_ledger"]["target_calls_total"]
    )
    assert first["coverage"]["cells_added"] == sorted(
        set(run_b["coverage"]["cells"]) - set(run_a["coverage"]["cells"])
    )
    assert first["coverage"]["cells_removed"] == sorted(
        set(run_a["coverage"]["cells"]) - set(run_b["coverage"]["cells"])
    )
    assert first["certificates"]["added"] == sorted(first["certificates"]["added"])
    assert first["certificates"]["removed"] == sorted(first["certificates"]["removed"])


def test_compare_rejects_invalid_or_incompatible_runs() -> None:
    run_a = _document(seed=42, budget=1)
    invalid = json.loads(json.dumps(run_a))
    invalid["call_ledger"]["target_calls_total"] += 1
    with pytest.raises(ValueError, match="ledger"):
        compare_run_documents(run_a, invalid)

    incompatible = json.loads(json.dumps(run_a))
    incompatible["schema_version"] = "atlas-run-v2"
    with pytest.raises(ValueError, match="Unsupported"):
        compare_run_documents(run_a, incompatible)


def test_compare_cli_writes_json_and_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    run = _document(seed=42, budget=1)
    run_a = write_canonical_json(tmp_path / "a.json", run)
    run_b = write_canonical_json(tmp_path / "b.json", run)
    runner = CliRunner()

    json_result = runner.invoke(app, ["compare", str(run_a), str(run_b), "--format", "json"])
    assert json_result.exit_code == 0, json_result.output
    json_output = next((tmp_path / "comparisons").glob("*.json"))
    assert json.loads(json_output.read_text(encoding="utf-8"))["schema_version"] == (
        "atlas-comparison-v1"
    )

    html_result = runner.invoke(app, ["compare", str(run_a), str(run_b), "--format", "html"])
    assert html_result.exit_code == 0, html_result.output
    html = next((tmp_path / "comparisons").glob("*.html")).read_text(encoding="utf-8")
    assert "EdgeCase Atlas run comparison" in html
    assert "https://" not in html and "http://" not in html
