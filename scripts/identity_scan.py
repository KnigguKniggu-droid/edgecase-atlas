"""Fail closed on public identity, secret, path, and private-artifact leaks."""

from __future__ import annotations

import argparse
import hashlib
import os
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

_PUBLIC_BINARY_SHA256: Final = {
    "app/static/fonts/IBMPlexMono-Regular-Latin1.woff2": (
        "e8993d946649b9d01abb1ed06d574b19d8ea3e66b5c3948602db335c44c18e56"
    ),
    "app/static/fonts/IBMPlexMono-SemiBold-Latin1.woff2": (
        "b7acd05041ab65f3b7039e218ddd893065e11a07e85ea85019473152a51b6b7d"
    ),
    "app/static/fonts/IBMPlexSans-Bold-Latin1.woff2": (
        "914f1400f363e636b6f9cc7965aa807ff01e93586e1437617525cba0a62aa78d"
    ),
    "app/static/fonts/IBMPlexSans-Medium-Latin1.woff2": (
        "b5610af04d0d4b5a14a621d96d974b993e945a065db1a8861918f69ef9321934"
    ),
    "app/static/fonts/IBMPlexSans-Regular-Latin1.woff2": (
        "b5ad7bd39f996144915f0ad9849a90183b27d8c28ad97ed98af5b1bebc51f6b1"
    ),
    "app/static/fonts/IBMPlexSans-SemiBold-Latin1.woff2": (
        "fff0ab3a88b0b4aa0b693e4f0201359a15183b08e3fa5696d1918d8f0ade8ad5"
    ),
}
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_WINDOWS_PATH = re.compile(
    r"(?i)(?<![A-Z0-9_])(?:[A-Z]:[\\/][^\s\"'<>|]*|"
    r"\\\\[A-Z0-9._$-]+\\[^\s\"'<>|]+)"
)
_UNIX_PATH = re.compile(
    r"(?<![:/A-Za-z0-9._-])/(?:Users|home|root|tmp|var|etc|opt)/"
    r"(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+"
)
_MODEL_WEIGHT = re.compile(r"(?i)\b[\w.-]+\.(?:gguf|safetensors|pt|pth|ckpt)\b")
_SECRET = re.compile(
    r"(?im)(?:\bsk-(?:proj-|test-)?[A-Z0-9_-]{20,}\b|"
    r"\bgh[pousr]_[A-Z0-9_]{20,}\b|"
    r"\bAKIA[A-Z0-9]{16}\b|"
    r"\bAIza[A-Z0-9_-]{35}\b|"
    r"\b(?:sk|rk|pk)_(?:live|test)_[A-Z0-9]{16,}\b|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret|password)[ \t]*[:=][ \t]*"
    r"(?![ \t]*(?:$|[\"']?\$|[\"']?[<{]|TBD\b|REDACTED\b))"
    r"[\"']?[A-Z0-9+/=_-]{20,}[\"']?)"
)
_NOREPLY = re.compile(r"(?i)^[A-Z0-9._%+-]+@users\.noreply\.github\.com$")
_TAGGER = re.compile(r"(?m)^tagger (.*) <([^>]*)> \d+ [+-]\d+$")
_PATH_ALLOWLIST: Final = {
    "scripts/identity_scan.py": (
        r"C:\private\sample",
        r"C:\private\fixture-secret",
        r"D:\private\project",
        r"C:\\private\\sample",
        r"\\server\\share\\project",
        "/opt/private/project",
    ),
    "tests/test_streamlit_app.py": (
        r"C:\private\sample",
        r"C:\\private\\sample",
        r"C:\private\fixture-secret",
    ),
    "tests/test_release_hardening.py": (
        r"D:\private\project",
        r"\\server\\share\\project",
        "/opt/private/project",
    ),
}
_MODEL_ALLOWLIST: Final = {
    "scripts/identity_scan.py": (
        "weights" + ".gguf",
        "weights" + ".bin",
        "weights" + ".safetensors",
    )
}


@dataclass(frozen=True, order=True)
class Finding:
    """One scanner finding without the sensitive matched value."""

    path: Path
    kind: str

    def safe_message(self) -> str:
        return f"{self.path.as_posix()}: {self.kind}"


def _run(
    root: Path,
    arguments: list[str],
    *,
    input_bytes: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603
        ["git", *arguments],  # noqa: S607
        cwd=root,
        input=input_bytes,
        check=check,
        capture_output=True,
    )


def _git(root: Path, *arguments: str) -> str:
    return _run(root, list(arguments)).stdout.decode("utf-8", errors="replace")


def _public_files(root: Path) -> tuple[Path, ...]:
    result = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    paths = {root / item for item in result.split("\0") if item}
    for directory_name in GENERATED_DIRECTORIES:
        directory = root / directory_name
        if directory.is_dir():
            paths.update(path for path in directory.rglob("*") if path.is_file())
    return tuple(sorted(path for path in paths if path.is_file()))


def running_in_ci() -> bool:
    """Report whether this is a hosted CI run.

    The private-term list is deliberately local-only and gitignored, so it can never exist on a
    CI runner. Everywhere else its absence means the private-term check silently did nothing.
    """
    return os.environ.get("CI", "").strip().casefold() in {"1", "true", "yes", "on"}


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


def _has_unallowed_match(
    pattern: re.Pattern[str],
    text: str,
    allowed: tuple[str, ...],
) -> bool:
    return any(match.group() not in allowed for match in pattern.finditer(text))


def scan_text(
    path: Path,
    text: str,
    *,
    private_values: tuple[str, ...] = (),
) -> list[Finding]:
    """Scan text while returning rule names, never matched sensitive values."""
    findings: set[Finding] = set()
    path_key = path.as_posix()
    allowed_paths = _PATH_ALLOWLIST.get(path_key, ())
    if _has_unallowed_match(_WINDOWS_PATH, text, allowed_paths) or _has_unallowed_match(
        _UNIX_PATH, text, allowed_paths
    ):
        findings.add(Finding(path, "local_path"))
    if _SECRET.search(text):
        findings.add(Finding(path, "secret"))
    allowed_models = _MODEL_ALLOWLIST.get(path_key, ())
    if path.name != ".gitignore" and _has_unallowed_match(_MODEL_WEIGHT, text, allowed_models):
        findings.add(Finding(path, "model_weight"))
    if any(not _email_is_public_fixture(match.group()) for match in _EMAIL.finditer(text)):
        findings.add(Finding(path, "personal_email"))
    if any(re.search(re.escape(value), text, re.IGNORECASE) for value in private_values):
        findings.add(Finding(path, "private_pattern"))
    return sorted(findings)


def scan_bytes(
    path: Path,
    data: bytes,
    *,
    private_values: tuple[str, ...] = (),
) -> list[Finding]:
    """Fail closed except for exact hash-pinned public binary assets."""
    expected_hash = _PUBLIC_BINARY_SHA256.get(path.as_posix())
    if expected_hash is not None:
        if hashlib.sha256(data).hexdigest() == expected_hash:
            return []
        return [Finding(path, "opaque_binary")]
    if b"\0" in data:
        return [Finding(path, "opaque_binary")]
    return scan_text(path, data.decode("utf-8", errors="replace"), private_values=private_values)


def validate_ignored_paths(root: Path) -> list[Finding]:
    """Require every sensitive or generated path class to remain ignored."""
    findings: list[Finding] = []
    for value in REQUIRED_IGNORED_PATHS:
        result = _run(
            root,
            ["check-ignore", "--no-index", "--quiet", "--", value],
            check=False,
        )
        if result.returncode != 0:
            findings.append(Finding(Path(value), "not_ignored"))
    return findings


def _redact(findings: list[Finding], label: str) -> set[Finding]:
    return {Finding(Path(label), finding.kind) for finding in findings}


def _commit_findings(root: Path, private_values: tuple[str, ...]) -> set[Finding]:
    findings: set[Finding] = set()
    for index, commit in enumerate(_git(root, "rev-list", "--all").splitlines(), 1):
        metadata = _git(
            root,
            "show",
            "-s",
            "--format=%an%x00%ae%x00%cn%x00%ce%x00%B",
            commit,
        ).split("\0", 4)
        if len(metadata) != 5:
            findings.add(Finding(Path(f"<git-commit-{index}>"), "git_metadata"))
            continue
        author_name, author_email, committer_name, committer_email, message = metadata
        if not git_identity_is_anonymous(
            author_name, author_email
        ) or not git_identity_is_anonymous(committer_name, committer_email):
            findings.add(Finding(Path(f"<git-commit-{index}>"), "git_identity"))
        findings.update(
            _redact(
                scan_text(Path("commit-message.txt"), message, private_values=private_values),
                f"<git-commit-{index}>",
            )
        )
    return findings


def _tag_findings(root: Path, private_values: tuple[str, ...]) -> set[Finding]:
    findings: set[Finding] = set()
    tags = _git(root, "for-each-ref", "--format=%(refname:short)", "refs/tags").splitlines()
    for index, tag in enumerate(tags, 1):
        label = f"<git-tag-{index}>"
        findings.update(_redact(scan_filename(Path(tag)), label))
        findings.update(_redact(scan_text(Path("tag-name.txt"), tag), label))
        if _git(root, "cat-file", "-t", f"refs/tags/{tag}").strip() != "tag":
            continue
        body = _git(root, "cat-file", "tag", f"refs/tags/{tag}")
        header, _, message = body.partition("\n\n")
        tagger = _TAGGER.search(header)
        if tagger is None or not git_identity_is_anonymous(tagger.group(1), tagger.group(2)):
            findings.add(Finding(Path(label), "git_identity"))
        findings.update(
            _redact(
                scan_text(Path("tag-message.txt"), message, private_values=private_values),
                label,
            )
        )
    return findings


def _blob_payloads(root: Path, object_ids: list[str]) -> list[bytes]:
    if not object_ids:
        return []
    result = _run(
        root, ["cat-file", "--batch"], input_bytes=("\n".join(object_ids) + "\n").encode()
    )
    payloads: list[bytes] = []
    position = 0
    for _ in object_ids:
        header_end = result.stdout.index(b"\n", position)
        size = int(result.stdout[position:header_end].rsplit(b" ", 1)[1])
        start = header_end + 1
        payloads.append(result.stdout[start : start + size])
        position = start + size + 1
    return payloads


def _history_blob_findings(root: Path, private_values: tuple[str, ...]) -> set[Finding]:
    findings: set[Finding] = set()
    objects = [
        line.partition(" ") for line in _git(root, "rev-list", "--objects", "--all").splitlines()
    ]
    with_paths = [(object_id, path) for object_id, separator, path in objects if separator and path]
    if not with_paths:
        return findings
    check = (
        _run(
            root,
            ["cat-file", "--batch-check=%(objectname) %(objecttype)"],
            input_bytes=("\n".join(object_id for object_id, _ in with_paths) + "\n").encode(),
        )
        .stdout.decode("ascii", errors="replace")
        .splitlines()
    )
    blobs = [item for item, line in zip(with_paths, check, strict=True) if line.endswith(" blob")]
    for index, ((_, raw_path), payload) in enumerate(
        zip(blobs, _blob_payloads(root, [object_id for object_id, _ in blobs]), strict=True),
        1,
    ):
        path = Path(raw_path)
        label = f"<git-blob-{index}>"
        findings.update(_redact(scan_filename(path), label))
        findings.update(_redact(scan_text(Path("history-name.txt"), raw_path), label))
        findings.update(_redact(scan_bytes(path, payload, private_values=private_values), label))
    return findings


def scan_repository(root: Path) -> list[Finding]:
    """Scan publishable files, reachable history, refs, ignore rules, and identities."""
    root = root.resolve()
    private_values = _private_values(root)
    findings = set(validate_ignored_paths(root))
    findings.update(_commit_findings(root, private_values))
    findings.update(_tag_findings(root, private_values))
    findings.update(_history_blob_findings(root, private_values))
    for path in _public_files(root):
        relative_path = path.relative_to(root)
        findings.update(scan_filename(relative_path))
        data = path.read_bytes()
        findings.update(scan_bytes(relative_path, data, private_values=private_values))
    return sorted(findings)


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    options = parser.parse_args(arguments)
    patterns_available = (options.root / PRIVATE_PATTERNS_FILE).is_file()
    if not patterns_available and not running_in_ci():
        print(
            f"Identity scan incomplete: {PRIVATE_PATTERNS_FILE} is missing, so no private term "
            "was checked. Create it locally with one term per line; it stays gitignored."
        )
        return 2
    try:
        findings = scan_repository(options.root)
    except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError):
        print("Identity scan could not complete.")
        return 2
    if findings:
        for finding in findings:
            print(finding.safe_message())
        print(f"Identity scan failed with {len(findings)} finding(s).")
        return 1
    if patterns_available:
        print("Identity scan passed.")
    else:
        print("Identity scan passed without private-term coverage (CI has no local term list).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
