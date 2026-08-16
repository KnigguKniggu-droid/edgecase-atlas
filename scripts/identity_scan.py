"""Fail closed on public identity, secret, path, and private-artifact leaks."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ANONYMOUS_AUTHOR: Final = "EdgeCase Atlas"
PRIVATE_PATTERNS_FILE: Final = ".identity-scan-private-patterns"
FORBIDDEN_FILENAME_TERMS: Final = ("task5", "mentor", "institution")
GENERATED_DIRECTORIES: Final = ("runs", "certificates", "reports", "traces", "artifacts")
REQUIRED_IGNORED_PATHS: Final = (
    ".env",
    ".env.local",
    ".streamlit/secrets.toml",
    "runs/sample.json",
    "certificates/sample.json",
    "reports/sample.html",
    "traces/sample.jsonl",
    "research/data/raw/sample.jsonl",
    "weights" + ".gguf",
    "weights" + ".bin",
    "weights" + ".safetensors",
    PRIVATE_PATTERNS_FILE,
)

_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_LOCAL_PATH = re.compile(
    r"(?i)(?:\b[A-Z]:[\\/]+Users[\\/]+[^\s\"']+|/(?:Users|home)/[^\s\"']+)"
)
_MODEL_WEIGHT = re.compile(r"(?i)\b[\w.-]+\.(?:gguf|safetensors|pt|pth|ckpt)\b")
_SECRET = re.compile(
    r"(?i)(?:\bsk-(?:proj-|test-)?[A-Z0-9_-]{20,}\b|"
    r"\bgh[pousr]_[A-Z0-9_]{20,}\b|"
    r"\bAKIA[A-Z0-9]{16}\b|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"(?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*[\"']"
    r"[A-Z0-9+/=_-]{20,}[\"'])"
)
_NOREPLY = re.compile(r"(?i)^[A-Z0-9._%+-]+@users\.noreply\.github\.com$")


@dataclass(frozen=True, order=True)
class Finding:
    """One scanner finding without the sensitive matched value."""

    path: Path
    kind: str

    def safe_message(self) -> str:
        return f"{self.path.as_posix()}: {self.kind}"


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *arguments],  # noqa: S607
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _public_files(root: Path) -> tuple[Path, ...]:
    result = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    paths = {root / item for item in result.stdout.split("\0") if item}
    for directory_name in GENERATED_DIRECTORIES:
        directory = root / directory_name
        if directory.is_dir():
            paths.update(path for path in directory.rglob("*") if path.is_file())
    return tuple(sorted(path for path in paths if path.is_file()))


def _private_values(root: Path) -> tuple[str, ...]:
    path = root / PRIVATE_PATTERNS_FILE
    if not path.is_file():
        return ()
    return tuple(
        value
        for line in path.read_text(encoding="utf-8").splitlines()
        if (value := line.strip()) and not value.startswith("#")
    )


def _email_is_public_fixture(value: str) -> bool:
    lowered = value.casefold()
    return bool(_NOREPLY.fullmatch(value)) or lowered.endswith(
        ("@example.com", "@example.test", ".invalid")
    )


def git_identity_is_anonymous(name: str, email: str) -> bool:
    """Allow only the project pseudonym and a GitHub noreply address."""
    return name == ANONYMOUS_AUTHOR and bool(_NOREPLY.fullmatch(email))


def scan_filename(path: Path) -> list[Finding]:
    """Scan one publishable filename without inspecting its contents."""
    findings: set[Finding] = set()
    lowered_name = path.as_posix().casefold()
    if any(term in lowered_name for term in FORBIDDEN_FILENAME_TERMS):
        findings.add(Finding(path, "forbidden_filename"))
    if _MODEL_WEIGHT.search(path.name):
        findings.add(Finding(path, "model_weight"))
    return sorted(findings)


def scan_text(
    path: Path,
    text: str,
    *,
    private_values: tuple[str, ...] = (),
) -> list[Finding]:
    """Scan text while returning rule names, never matched sensitive values."""
    findings: set[Finding] = set()
    if _LOCAL_PATH.search(text):
        findings.add(Finding(path, "local_path"))
    if _SECRET.search(text):
        findings.add(Finding(path, "secret"))
    if path.name != ".gitignore" and _MODEL_WEIGHT.search(text):
        findings.add(Finding(path, "model_weight"))
    if any(not _email_is_public_fixture(match.group()) for match in _EMAIL.finditer(text)):
        findings.add(Finding(path, "personal_email"))
    if any(re.search(re.escape(value), text, re.IGNORECASE) for value in private_values):
        findings.add(Finding(path, "private_pattern"))
    return sorted(findings)


def validate_ignored_paths(root: Path) -> list[Finding]:
    """Require every sensitive or generated path class to remain ignored."""
    findings: list[Finding] = []
    for value in REQUIRED_IGNORED_PATHS:
        result = subprocess.run(  # noqa: S603
            ["git", "check-ignore", "--no-index", "--quiet", "--", value],  # noqa: S607
            cwd=root,
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            findings.append(Finding(Path(value), "not_ignored"))
    return findings


def _git_identity_findings(root: Path) -> set[Finding]:
    findings: set[Finding] = set()
    history = _git(root, "log", "--format=%an%x09%ae", "--all").stdout.splitlines()
    for index, line in enumerate(history, 1):
        name, separator, email = line.partition("\t")
        if separator != "\t" or not git_identity_is_anonymous(name, email):
            findings.add(Finding(Path(f"<git-author-{index}>"), "git_identity"))
    return findings


def scan_repository(root: Path) -> list[Finding]:
    """Scan publishable content, generated output, ignore rules, and Git authors."""
    root = root.resolve()
    findings = set(validate_ignored_paths(root)) | _git_identity_findings(root)
    private_values = _private_values(root)
    for path in _public_files(root):
        relative_path = path.relative_to(root)
        findings.update(scan_filename(relative_path))
        data = path.read_bytes()
        if b"\0" not in data:
            findings.update(
                scan_text(
                    relative_path,
                    data.decode("utf-8", errors="replace"),
                    private_values=private_values,
                )
            )
    return sorted(findings)


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    options = parser.parse_args(arguments)
    try:
        findings = scan_repository(options.root)
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        print("Identity scan could not complete.")
        return 2
    if findings:
        for finding in findings:
            print(finding.safe_message())
        print(f"Identity scan failed with {len(findings)} finding(s).")
        return 1
    print("Identity scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
