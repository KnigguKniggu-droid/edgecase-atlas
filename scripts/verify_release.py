"""Run every local EdgeCase Atlas 0.1.0 release gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def require_python_312(version: tuple[int, int]) -> None:
    if version != (3, 12):
        raise RuntimeError("Release verification requires Python 3.12.")


def release_commands(python: Path, wheel_directory: Path) -> tuple[tuple[str, ...], ...]:
    executable = str(python)
    return (
        (executable, "scripts/identity_scan.py"),
        (executable, "-m", "ruff", "check", "."),
        (executable, "-m", "mypy", "src/edgecase_atlas"),
        (executable, "-m", "pytest", "-q"),
        (executable, "scripts/smoke_test.py"),
        (
            executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--no-cache-dir",
            "--wheel-dir",
            str(wheel_directory),
        ),
    )


def main() -> int:
    try:
        require_python_312(sys.version_info[:2])
    except RuntimeError as error:
        print(str(error))
        return 2
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="edgecase-atlas-wheel-") as wheel_directory:
        for command in release_commands(Path(sys.executable), Path(wheel_directory)):
            result = subprocess.run(command, cwd=root, check=False)  # noqa: S603
            if result.returncode != 0:
                print(f"Release verification failed: {command[1]}")
                return 1
    print("Release verification passed for EdgeCase Atlas 0.1.0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
