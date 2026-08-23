from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from edgecase_atlas.cli import app

runner = CliRunner()


@pytest.mark.parametrize(("certificate_count", "expected_code"), [(0, 0), (1, 1)])
def test_gate_exit_code_preserves_written_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    certificate_count: int,
    expected_code: int,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    run_path = tmp_path / "runs" / "run-example.json"
    trace_path = tmp_path / "traces" / "run-example.jsonl"
    report_path = tmp_path / "reports" / "run-example.html"
    for path in (run_path, trace_path, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("evidence", encoding="utf-8")

    async def fake_run_test(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "run": run_path,
            "trace": trace_path,
            "report": report_path,
            "certificate_count": certificate_count,
        }

    monkeypatch.setattr("edgecase_atlas.cli._run_test", fake_run_test)
    result = runner.invoke(
        app,
        ["gate", "--config", "atlas.yaml", "--budget", "1", "--seed", "42"],
    )

    assert result.exit_code == expected_code, result.output
    assert "Run:" in result.output
    assert "Trace:" in result.output
    assert "Report:" in result.output
    assert f"Certificates: {certificate_count}" in result.output
    assert run_path.exists() and trace_path.exists() and report_path.exists()


def test_composite_action_runs_gate_and_uploads_evidence() -> None:
    action = Path(".github/actions/atlas-test/action.yml").read_text(encoding="utf-8")
    assert "atlas validate" in action
    assert "atlas gate" in action
    assert "actions/upload-artifact@v4" in action
    assert "if-no-files-found: error" in action
