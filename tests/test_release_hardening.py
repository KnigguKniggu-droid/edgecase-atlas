"""Adversarial release-boundary regressions."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from scripts.identity_scan import scan_repository, scan_text
from scripts.smoke_test import scan_artifacts, without_credentials
from scripts.verify_release import clean_install_commands

from edgecase_atlas.engine import recompute_certificate_id
from edgecase_atlas.models import FailureCertificate

ROOT = Path(__file__).parents[1]


def _git(root: Path, *arguments: str, environment: dict[str, str] | None = None) -> None:
    executable = shutil.which("git")
    assert executable is not None
    subprocess.run(  # noqa: S603
        [executable, *arguments],
        cwd=root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_history_scan_catches_deleted_blob_metadata_messages_and_tags(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init", "--initial-branch=main")
    private_email = "owner" + "@private.test"
    secret = "API_KEY=" + "abcdefghijklmnopqrstuvwxyz012345"
    local_path = "D:" + r"\private\project"
    leak = "\n".join((private_email, secret, local_path))
    leaked_file = root / "removed.txt"
    leaked_file.write_text(leak, encoding="utf-8")
    _git(root, "add", "removed.txt")
    first_environment = os.environ.copy()
    first_environment.update(
        {
            "GIT_AUTHOR_NAME": "EdgeCase Atlas",
            "GIT_AUTHOR_EMAIL": "edgecase-atlas@users.noreply.github.com",
            "GIT_COMMITTER_NAME": "Private Committer",
            "GIT_COMMITTER_EMAIL": private_email,
        }
    )
    _git(root, "commit", "-m", "message " + private_email, environment=first_environment)
    tag_environment = os.environ.copy()
    tag_environment.update(
        {"GIT_COMMITTER_NAME": "Private Tagger", "GIT_COMMITTER_EMAIL": private_email}
    )
    _git(
        root,
        "-c",
        "user.name=Private Tagger",
        "-c",
        "user.email=" + private_email,
        "tag",
        "-a",
        "annotated-release",
        "-m",
        secret,
        environment=tag_environment,
    )
    leaked_file.unlink()
    _git(root, "add", "-u")
    _git(
        root,
        "-c",
        "user.name=EdgeCase Atlas",
        "-c",
        "user.email=edgecase-atlas@users.noreply.github.com",
        "commit",
        "-m",
        "remove fixture",
    )
    _git(root, "tag", "private-task5-lightweight")

    findings = scan_repository(root)
    kinds = {finding.kind for finding in findings}
    rendered = "\n".join(finding.safe_message() for finding in findings)

    assert {"forbidden_filename", "git_identity", "local_path", "personal_email", "secret"} <= kinds
    assert private_email not in rendered
    assert secret not in rendered
    assert local_path not in rendered


@pytest.mark.parametrize(
    "unsafe_value",
    (
        "API_KEY=" + "abcdefghijklmnopqrstuvwxyz012345",
        "AIza" + "A" * 35,
        "sk_live_" + "A" * 24,
        "D:" + r"\private\project",
        "\\\\server\\share\\project",
        "/opt/private/project",
    ),
)
def test_scan_text_rejects_unquoted_keys_and_generic_absolute_paths(unsafe_value: str) -> None:
    assert scan_text(Path("public.txt"), unsafe_value)


@pytest.mark.parametrize(
    "safe_value",
    (
        "OPENAI_API_KEY=",
        "OPENAI_API_KEY=${OPENAI_API_KEY}",
        "https://api.example.test/v1",
        "research/data/synthetic.jsonl",
    ),
)
def test_scan_text_allows_placeholders_urls_and_relative_paths(safe_value: str) -> None:
    assert scan_text(Path("public.txt"), safe_value) == []


def test_scan_text_path_allowlist_is_scoped_to_declared_fixture() -> None:
    fixture = "C:" + r"\private\sample"
    assert scan_text(Path("tests/test_streamlit_app.py"), fixture) == []
    assert scan_text(Path("public.txt"), fixture)


def test_artifact_scan_rejects_generated_html_leak_without_echoing_value(tmp_path: Path) -> None:
    secret = "API_KEY=" + "abcdefghijklmnopqrstuvwxyz012345"
    report = tmp_path / "report.html"
    report.write_text(f"<!doctype html><p>{secret}</p>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="generated artifact") as captured:
        scan_artifacts((report,))

    assert secret not in str(captured.value)


def test_streamlit_credential_scrub_restores_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "sk-test-" + "abcdefghijklmnopqrstuvwxyz"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    with without_credentials():
        assert "OPENAI_API_KEY" not in os.environ

    assert os.environ["OPENAI_API_KEY"] == secret


def test_clean_install_commands_use_exact_wheel_and_no_editable_source(tmp_path: Path) -> None:
    wheel = tmp_path / "edgecase_atlas-0.1.0-py3-none-any.whl"
    commands = clean_install_commands(Path("python"), tmp_path / "clean", wheel, ROOT)
    joined = [" ".join(map(str, command)) for command in commands]

    assert any("-m venv --system-site-packages" in command for command in joined)
    assert any(str(wheel) in command and "pip install" in command for command in joined)
    assert all("-e" not in command.split() for command in joined)
    assert any("scripts/smoke_test.py" in command and "--cli-only" in command for command in joined)
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "pip install -e" not in workflow


def test_curated_sample_certificate_and_report_match_manifest() -> None:
    manifest = json.loads((ROOT / "samples" / "manifest.json").read_text(encoding="utf-8"))
    certificate_path = ROOT / manifest["certificate"]["path"]
    report_path = ROOT / manifest["report"]["path"]

    assert (
        hashlib.sha256(certificate_path.read_bytes()).hexdigest()
        == manifest["certificate"]["sha256"]
    )
    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == manifest["report"]["sha256"]
    certificate = FailureCertificate.model_validate_json(
        certificate_path.read_text(encoding="utf-8")
    )
    assert recompute_certificate_id(certificate) == certificate.certificate_id
    assert certificate.model_id == "faulty-demonstration-agent-v1"
    report = report_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in report.casefold()
    assert certificate.certificate_id in report
    assert scan_artifacts((certificate_path, report_path)) is None
