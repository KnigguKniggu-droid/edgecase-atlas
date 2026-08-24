"""Adversarial release-boundary regressions."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from scripts.identity_scan import (
    _SECRET,
    PRIVATE_PATTERNS_FILE,
    running_in_ci,
    scan_repository,
    scan_text,
)
from scripts.identity_scan import (
    main as identity_scan_main,
)
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


def test_identity_scan_never_claims_a_pass_it_did_not_perform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing private-term list must stop the local gate instead of printing a clean pass.

    The list is gitignored and local-only, so its absence outside CI means the private-term
    check ran against nothing. Reporting success there would make the privacy gate decorative.
    """
    monkeypatch.delenv("CI", raising=False)
    assert not (tmp_path / PRIVATE_PATTERNS_FILE).exists()

    assert identity_scan_main([str(tmp_path)]) == 2
    output = capsys.readouterr().out
    assert "Identity scan incomplete" in output
    assert "Identity scan passed" not in output


def test_ci_detection_only_accepts_explicit_truthy_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CI", raising=False)
    assert not running_in_ci()
    for value in ("true", "TRUE", " 1 ", "yes", "on"):
        monkeypatch.setenv("CI", value)
        assert running_in_ci()
    for value in ("", "false", "0", "no"):
        monkeypatch.setenv("CI", value)
        assert not running_in_ci()


def test_requirements_match_the_project_dependencies() -> None:
    """The hosted deploy installs from requirements.txt, so it must mirror pyproject exactly.

    It also ends with ``.`` so the project itself is reinstalled on every deploy. Without that,
    the hosted environment keeps an older build of ``edgecase_atlas`` while files under ``app``
    deploy live from the repository, and any app module importing a newly added package symbol
    raises ImportError in production while every local gate still passes.
    """
    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = list(project["project"]["dependencies"])

    lines = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert lines[-1] == ".", "requirements.txt must install this project on every deploy"
    assert lines[:-1] == declared, "requirements.txt drifted from pyproject dependencies"

def test_secret_scan_recognises_the_common_credential_formats() -> None:
    """Every token format below is one a leak would realistically arrive in.

    The values are assembled at runtime rather than written out, because a literal token
    shape in this file would be found by the very scanner it is testing. The repository uses
    the same split-string idiom in scripts/identity_scan.py for the ignored-path list.
    """
    leaks = {
        "openai": "sk" + "-proj-" + "A" * 24,
        "github": "gh" + "p_" + "B" * 24,
        "aws": "AK" + "IA" + "C" * 16,
        "google": "AI" + "za" + "D" * 35,
        "stripe": "sk" + "_live_" + "E" * 20,
        "slack": "xo" + "xb-1111111111-2222222222-" + "F" * 24,
        "huggingface": "hf" + "_" + "G" * 34,
        "gitlab": "gl" + "pat-" + "H" * 20,
        "npm": "np" + "m_" + "I" * 36,
        "telegram": "123456789" + ":AA" + "J" * 33,
        "jwt": "ey" + "J" + "K" * 12 + ".ey" + "J" + "L" * 12 + "." + "M" * 20,
    }
    for name, value in leaks.items():
        assert _SECRET.search(value), f"{name} credential format is not detected"

    # Things that legitimately appear in this repository must not trip it.
    benign = (
        "f54ce18cc0fc592735ebba2cc5c2e7292496722a9468c1e05bfabcd6807ebe27",
        "case-64445e166d17c168c66b",
        "The reproduction gate accepts a failure at four of five reruns.",
        "atlas replay certificates/case-64445e166d17c168c66b.json",
    )
    for value in benign:
        assert not _SECRET.search(value), f"false positive on {value!r}"
