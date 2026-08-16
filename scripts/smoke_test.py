"""Bounded no-key release smoke for CLI artifacts and the Streamlit demonstration."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml  # type: ignore[import-untyped]
from streamlit.testing.v1 import AppTest


@dataclass(frozen=True)
class SmokeResult:
    certificate_count: int
    fixture_sha256: str
    synthetic_pack_sha256: str
    elapsed_seconds: float


def fixture_fingerprint(document: dict[str, Any]) -> str:
    """Hash stable run and certificate identifiers, excluding measured timing."""
    payload = {
        "run_id": document["metadata"]["run_id"],
        "certificate_ids": sorted(
            certificate["certificate_id"] for certificate in document["certificates"]
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _atlas_command(python: Path) -> list[str]:
    executable = python.with_name("atlas.exe" if os.name == "nt" else "atlas")
    if executable.is_file():
        return [str(executable)]
    return [str(python), "-c", "from edgecase_atlas.cli import app; app()"]


def _environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key != "LLAMA_MODEL_PATH" and "OPENAI" not in key.upper()
    }


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


def _cli_run(working_directory: Path, *, complete: bool) -> dict[str, Any]:
    atlas = _atlas_command(Path(sys.executable))
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
    document = json.loads(run_path.read_text(encoding="utf-8"))
    assert all(json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines())
    assert "<!doctype html>" in report_path.read_text(encoding="utf-8").casefold()
    if complete:
        _run([*atlas, "replay", str(certificate_path)], working_directory)
        report_path.unlink()
        _run([*atlas, "report", str(run_path), "--format", "html"], working_directory)
        if not report_path.is_file():
            raise RuntimeError("CLI report was not recreated.")
    return document


def _synthetic_pack_checksum(root: Path) -> str:
    manifest = yaml.safe_load(
        (root / "research" / "reproducibility-manifest.yaml").read_text(encoding="utf-8")
    )
    relative_path = Path(manifest["synthetic_seed_pack"]["path"])
    digest = hashlib.sha256((root / relative_path).read_bytes()).hexdigest()
    if digest != manifest["synthetic_seed_pack"]["sha256"]:
        raise RuntimeError("Synthetic seed-pack checksum does not match the manifest.")
    return digest


def _streamlit_smoke(root: Path) -> None:
    original_path = sys.path.copy()
    try:
        sys.path.insert(0, str(root))
        app = AppTest.from_file(
            str(root / "app" / "streamlit_app.py"), default_timeout=30
        ).run()
        if app.exception:
            raise RuntimeError("Streamlit no-key demonstration failed to load.")
        button = next(item for item in app.button if item.label == "Run demonstration")
        app = button.click().run(timeout=30)
        if app.exception or not app.success or len(app.get("download_button")) != 3:
            raise RuntimeError("Streamlit no-key demonstration failed to produce artifacts.")
    finally:
        sys.path[:] = original_path


def run_smoke(root: Path) -> SmokeResult:
    """Run two deterministic fixture campaigns plus replay, report, and UI boundaries."""
    root = root.resolve()
    started = time.perf_counter()
    with TemporaryDirectory(prefix="edgecase-atlas-smoke-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        first_directory = temporary_root / "first"
        second_directory = temporary_root / "second"
        first_directory.mkdir()
        second_directory.mkdir()
        first = _cli_run(first_directory, complete=True)
        second = _cli_run(second_directory, complete=False)
    first_fingerprint = fixture_fingerprint(first)
    if first_fingerprint != fixture_fingerprint(second):
        raise RuntimeError("Fixture run checksum is not deterministic.")
    _streamlit_smoke(root)
    pack_checksum = _synthetic_pack_checksum(root)
    return SmokeResult(
        certificate_count=len(first["certificates"]),
        fixture_sha256=first_fingerprint,
        synthetic_pack_sha256=pack_checksum,
        elapsed_seconds=time.perf_counter() - started,
    )


def main() -> int:
    try:
        result = run_smoke(Path(__file__).resolve().parents[1])
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
        "Release smoke passed: "
        f"{result.certificate_count} certificate(s), "
        f"fixture sha256 {result.fixture_sha256}, "
        f"synthetic pack sha256 {result.synthetic_pack_sha256}, "
        f"{result.elapsed_seconds:.2f} seconds."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
