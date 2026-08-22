"""Run every local EdgeCase Atlas 0.1.0 release gate."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def require_python_312(version: tuple[int, int]) -> None:
    if version != (3, 12):
        raise RuntimeError("Release verification requires Python 3.12.")


def _venv_python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _venv_atlas(environment: Path) -> Path:
    return environment / ("Scripts/atlas.exe" if os.name == "nt" else "bin/atlas")


def clean_install_commands(
    python: Path,
    environment: Path,
    wheel: Path,
    root: Path,
) -> tuple[tuple[str, ...], ...]:
    clean_python = _venv_python(environment)
    clean_atlas = _venv_atlas(environment)
    smoke_script = f"{root.as_posix()}/scripts/smoke_test.py"
    import_check = (
        "from pathlib import Path; import edgecase_atlas; "
        "p=Path(edgecase_atlas.__file__).resolve(); "
        "assert Path(sys.prefix).resolve() in p.parents"
    )
    return (
        (str(python), "-m", "venv", "--system-site-packages", str(environment)),
        (str(clean_python), "-m", "pip", "install", str(wheel)),
        (str(clean_python), "-c", "import sys; " + import_check),
        (
            str(clean_python),
            smoke_script,
            "--atlas",
            str(clean_atlas),
            "--cli-only",
        ),
    )


def release_commands(python: Path, wheel_directory: Path) -> tuple[tuple[str, ...], ...]:
    executable = str(python)
    return (
        (executable, "scripts/identity_scan.py"),
        (executable, "-m", "ruff", "check", "."),
        (executable, "-m", "mypy", "src/edgecase_atlas"),
        (executable, "-m", "pytest", "-q"),
        (executable, "scripts/smoke_test.py", "--streamlit-only"),
        (
            executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-cache-dir",
            "--wheel-dir",
            str(wheel_directory),
        ),
    )


def _run(command: tuple[str, ...], root: Path) -> bool:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    return subprocess.run(command, cwd=root, env=environment, check=False).returncode == 0  # noqa: S603


def main() -> int:
    try:
        require_python_312(sys.version_info[:2])
    except RuntimeError as error:
        print(str(error))
        return 2
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="edgecase-atlas-release-") as temporary_directory:
        temporary = Path(temporary_directory)
        wheel_directory = temporary / "wheel"
        wheel_directory.mkdir()
        for command in release_commands(Path(sys.executable), wheel_directory):
            if not _run(command, root):
                print(f"Release verification failed: {command[1]}")
                return 1
        wheels = list(wheel_directory.glob("edgecase_atlas-0.1.0-*.whl"))
        if len(wheels) != 1:
            print("Release verification failed: wheel selection")
            return 1
        for command in clean_install_commands(
            Path(sys.executable), temporary / "clean", wheels[0], root
        ):
            if not _run(command, temporary):
                print(f"Release verification failed: {command[1]}")
                return 1
    print("Release verification passed for EdgeCase Atlas 0.1.0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
