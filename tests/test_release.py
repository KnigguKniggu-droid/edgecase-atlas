"""Release verification, anonymity, and no-key smoke contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.identity_scan import (
    Finding,
    git_identity_is_anonymous,
    scan_filename,
    scan_repository,
    scan_text,
    validate_ignored_paths,
)
from scripts.smoke_test import fixture_fingerprint, run_smoke
from scripts.verify_release import release_commands, require_python_312

ROOT = Path(__file__).parents[1]


def test_identity_scan_accepts_anonymous_repository_and_required_ignores() -> None:
    assert validate_ignored_paths(ROOT) == []
    assert scan_repository(ROOT) == []


def test_identity_scan_detects_each_public_leak_class_without_echoing_values() -> None:
    secret = "sk-test-" + "abcdefghijklmnopqrstuvwxyz"
    private_email = "owner" + "@private.test"
    local_path = "C:" + r"\Users\sample\project"
    model_file = "private-model" + ".gguf"
    text = "\n".join((secret, private_email, local_path, model_file, "Unlisted Private Alias"))

    findings = scan_text(Path("unsafe.py"), text, private_values=("Unlisted Private Alias",))
    kinds = {finding.kind for finding in findings}

    assert {"local_path", "model_weight", "personal_email", "private_pattern", "secret"} <= kinds
    assert scan_filename(Path("private-task5-notes.md")) == [
        Finding(Path("private-task5-notes.md"), "forbidden_filename")
    ]
    assert not git_identity_is_anonymous("Private Person", private_email)
    rendered = "\n".join(finding.safe_message() for finding in findings)
    assert secret not in rendered
    assert private_email not in rendered


def test_fixture_fingerprint_ignores_runtime_metadata() -> None:
    first = {
        "metadata": {"run_id": "run-stable", "duration_ms": 10},
        "certificates": [{"certificate_id": "case-stable", "latency_ms": 1}],
    }
    second = {
        "metadata": {"run_id": "run-stable", "duration_ms": 999},
        "certificates": [{"certificate_id": "case-stable", "latency_ms": 500}],
    }

    assert fixture_fingerprint(first) == fixture_fingerprint(second)
    second["certificates"][0]["certificate_id"] = "case-changed"
    assert fixture_fingerprint(first) != fixture_fingerprint(second)


def test_no_key_release_smoke_runs_cli_replay_report_and_streamlit() -> None:
    result = run_smoke(ROOT)

    assert result.certificate_count >= 1
    assert result.fixture_sha256
    assert result.synthetic_pack_sha256
    assert result.elapsed_seconds < 600


def test_release_verifier_requires_python_312_and_all_gates(tmp_path: Path) -> None:
    require_python_312((3, 12))
    with pytest.raises(RuntimeError, match=r"Python 3\.12"):
        require_python_312((3, 11))

    commands = release_commands(Path("python"), tmp_path)
    joined = [" ".join(map(str, command)) for command in commands]
    assert any("ruff check ." in command for command in joined)
    assert any("mypy src/edgecase_atlas" in command for command in joined)
    assert any("pytest -q" in command for command in joined)
    assert any("scripts/identity_scan.py" in command for command in joined)
    assert any("scripts/smoke_test.py" in command for command in joined)
    assert any("pip wheel . --no-deps --no-build-isolation" in command for command in joined)


def test_release_configuration_and_docs_state_implemented_boundaries() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    decision_log = (ROOT / "docs" / "decision-log.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert 'python-version: "3.12"' in workflow
    assert "scripts/verify_release.py" in workflow
    assert "1-minimal reproducing contrast" in readme
    assert "Planned alpha workflow" not in readme
    assert "causal certificate" not in readme
    assert "1-minimal reproducing contrast" in decision_log
    assert "causal minimization" not in decision_log
    assert "private" in security.casefold()
    assert "synthetic" in contributing.casefold()
    assert "traces/" in gitignore
    assert ".identity-scan-private-patterns" in gitignore
