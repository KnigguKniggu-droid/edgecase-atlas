from __future__ import annotations

import json
import time
from pathlib import Path

from typer.testing import CliRunner

from edgecase_atlas.cli import app

runner = CliRunner()


def test_init_does_not_overwrite_without_force_and_validate_works(tmp_path: Path) -> None:
    config = tmp_path / "atlas.yaml"
    first = runner.invoke(app, ["init", "--path", str(config)])
    assert first.exit_code == 0
    original = config.read_text(encoding="utf-8")
    second = runner.invoke(app, ["init", "--path", str(config)])
    assert second.exit_code != 0
    assert config.read_text(encoding="utf-8") == original
    assert runner.invoke(app, ["validate", str(config)]).exit_code == 0


def test_cli_test_replay_report_and_deterministic_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    started = time.perf_counter()
    result = runner.invoke(
        app,
        ["test", "--config", "atlas.yaml", "--budget", "1", "--seed", "42"],
    )
    assert result.exit_code == 0, result.output
    assert time.perf_counter() - started < 60
    run_paths = list((tmp_path / "runs").glob("*.json"))
    certificate_paths = list((tmp_path / "certificates").glob("*.json"))
    trace_paths = list((tmp_path / "traces").glob("*.jsonl"))
    report_paths = list((tmp_path / "reports").glob("*.html"))
    assert len(run_paths) == len(certificate_paths) == len(trace_paths) == len(report_paths) == 1
    run_data = json.loads(run_paths[0].read_text(encoding="utf-8"))
    assert run_data["metadata"]["seed"] == 42
    trace_lines = trace_paths[0].read_text(encoding="utf-8").splitlines()
    assert all(json.loads(line) for line in trace_lines)

    replay = runner.invoke(app, ["replay", str(certificate_paths[0])])
    assert replay.exit_code == 0, replay.output
    assert "4/5" in replay.output or "5/5" in replay.output

    report_paths[0].unlink()
    report = runner.invoke(app, ["report", str(run_paths[0]), "--format", "html"])
    assert report.exit_code == 0, report.output
    assert report_paths[0].exists()


def test_replay_rejects_model_configuration_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["test", "--config", "atlas.yaml", "--budget", "1", "--seed", "42"])
    certificate = next((tmp_path / "certificates").glob("*.json"))
    data = json.loads(certificate.read_text(encoding="utf-8"))
    data["model_config_hash"] = "mismatch"
    certificate.write_text(json.dumps(data), encoding="utf-8")
    result = runner.invoke(app, ["replay", str(certificate)])
    assert result.exit_code != 0
