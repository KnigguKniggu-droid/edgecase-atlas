"""Bounded no-key release smoke for CLI artifacts and the Streamlit demonstration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml  # type: ignore[import-untyped]
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.identity_scan import scan_bytes, scan_filename  # noqa: E402


@dataclass(frozen=True)
class SmokeResult:
    certificate_count: int
    fixture_sha256: str
    synthetic_pack_sha256: str
    elapsed_seconds: float


def fixture_fingerprint(document: dict[str, Any]) -> str:
    payload = {
        "run_id": document["metadata"]["run_id"],
        "certificate_ids": sorted(
            certificate["certificate_id"] for certificate in document["certificates"]
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def scan_artifacts(paths: Iterable[Path]) -> None:
    for index, path in enumerate(paths, 1):
        label = Path(f"generated-artifact-{index}{path.suffix}")
        data = path.read_bytes()
        findings = scan_filename(label) + scan_bytes(label, data)
        if findings:
            raise RuntimeError("A generated artifact failed the release privacy scan.")


def _scan_payloads(payloads: dict[str, bytes]) -> None:
    for name, payload in payloads.items():
        path = Path(name)
        findings = scan_filename(path) + scan_bytes(path, payload)
        if findings:
            raise RuntimeError("A rendered download failed the release privacy scan.")


@contextmanager
def without_credentials() -> Iterator[None]:
    blocked = {
        key: value
        for key, value in os.environ.items()
        if key == "LLAMA_MODEL_PATH"
        or any(token in key.upper() for token in ("OPENAI", "API_KEY", "TOKEN", "SECRET"))
    }
    try:
        for key in blocked:
            os.environ.pop(key, None)
        yield
    finally:
        os.environ.update(blocked)


def _environment() -> dict[str, str]:
    with without_credentials():
        return os.environ.copy()


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # noqa: S603
        command,
        cwd=cwd,
        env=_environment(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Smoke command failed: {command[-1]}")
    return result


def _default_atlas() -> list[str]:
    executable = Path(sys.executable).with_name("atlas.exe" if os.name == "nt" else "atlas")
    return (
        [str(executable)]
        if executable.is_file()
        else [
            sys.executable,
            "-c",
            "from edgecase_atlas.cli import app; app()",
        ]
    )


def _cli_run(atlas: list[str], working_directory: Path, *, complete: bool) -> dict[str, Any]:
    _run([*atlas, "init"], working_directory)
    _run([*atlas, "validate", "atlas.yaml"], working_directory)
    _run(
        [*atlas, "test", "--config", "atlas.yaml", "--budget", "1", "--seed", "42"],
        working_directory,
    )
    run_path = next((working_directory / "runs").glob("*.json"))
    certificate_path = next((working_directory / "certificates").glob("*.json"))
    trace_path = next((working_directory / "traces").glob("*.jsonl"))
    report_path = next((working_directory / "reports").glob("*.html"))
    scan_artifacts((run_path, certificate_path, trace_path, report_path))
    document = json.loads(run_path.read_text(encoding="utf-8"))
    if complete:
        _run([*atlas, "replay", str(certificate_path)], working_directory)
        report_path.unlink()
        _run([*atlas, "report", str(run_path), "--format", "html"], working_directory)
        scan_artifacts((report_path,))
    return document


def _synthetic_pack_checksum(root: Path) -> str:
    manifest = yaml.safe_load(
        (root / "research/reproducibility-manifest.yaml").read_text(encoding="utf-8")
    )
    path = root / manifest["synthetic_seed_pack"]["path"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest["synthetic_seed_pack"]["sha256"]:
        raise RuntimeError("Synthetic seed-pack checksum does not match the manifest.")
    return digest


def _visible_text(app: AppTest) -> str:
    values: list[str] = []
    for kind in (
        "title",
        "header",
        "subheader",
        "caption",
        "info",
        "warning",
        "error",
        "success",
        "markdown",
        "code",
        "metric",
        "status",
    ):
        for item in app.get(kind):
            values.extend(str(getattr(item, name, "")) for name in ("value", "label", "options"))
    return "\n".join(values)


def _streamlit_smoke(root: Path) -> None:
    original_path = sys.path.copy()
    try:
        sys.path.insert(0, str(root))
        with without_credentials():
            app = AppTest.from_file(str(root / "app/streamlit_app.py"), default_timeout=30).run()
            if app.exception:
                raise RuntimeError("Streamlit no-key demonstration failed to load.")
            app = (
                next(item for item in app.button if item.label == "Run counterfactual test")
                .click()
                .run(timeout=30)
            )
            reproduced_failure = any(
                "Reproducible failure found" in item.value for item in app.error
            )
            if (
                app.exception
                or not reproduced_failure
                or len(app.get("download_button")) != 3
            ):
                raise RuntimeError("Streamlit no-key demonstration failed to produce artifacts.")
            artifacts = app.session_state["atlas_run_artifacts"]
            _scan_payloads(
                {
                    "download.json": artifacts.json_bytes,
                    "download.jsonl": artifacts.jsonl_bytes,
                    "download.html": artifacts.html_bytes,
                    "rendered.txt": _visible_text(app).encode(),
                }
            )
    finally:
        sys.path[:] = original_path


def run_smoke(
    root: Path,
    *,
    atlas: list[str] | None = None,
    cli: bool = True,
    streamlit: bool = True,
) -> SmokeResult:
    started = time.perf_counter()
    first: dict[str, Any] = {"certificates": [], "metadata": {"run_id": "streamlit-only"}}
    if cli:
        with TemporaryDirectory(prefix="edgecase-atlas-smoke-") as temporary_directory:
            temporary_root = Path(temporary_directory)
            first_directory, second_directory = temporary_root / "first", temporary_root / "second"
            first_directory.mkdir()
            second_directory.mkdir()
            command = atlas or _default_atlas()
            first = _cli_run(command, first_directory, complete=True)
            second = _cli_run(command, second_directory, complete=False)
        if fixture_fingerprint(first) != fixture_fingerprint(second):
            raise RuntimeError("Fixture run checksum is not deterministic.")
    if streamlit:
        _streamlit_smoke(root.resolve())
    return SmokeResult(
        len(first["certificates"]),
        fixture_fingerprint(first),
        _synthetic_pack_checksum(root.resolve()),
        time.perf_counter() - started,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atlas", type=Path)
    parser.add_argument("--cli-only", action="store_true")
    parser.add_argument("--streamlit-only", action="store_true")
    options = parser.parse_args()
    try:
        result = run_smoke(
            ROOT,
            atlas=[str(options.atlas)] if options.atlas else None,
            cli=not options.streamlit_only,
            streamlit=not options.cli_only,
        )
    except (
        AssertionError,
        KeyError,
        OSError,
        RuntimeError,
        StopIteration,
        subprocess.TimeoutExpired,
    ):
        print("Release smoke failed without retaining partial artifacts.")
        return 1
    print(
        f"Release smoke passed: {result.certificate_count} certificate(s), "
        f"fixture sha256 {result.fixture_sha256}, synthetic pack sha256 "
        f"{result.synthetic_pack_sha256}, {result.elapsed_seconds:.2f} seconds."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
