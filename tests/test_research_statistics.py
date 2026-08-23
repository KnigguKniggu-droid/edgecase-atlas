from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from research.statistics import holm_adjust, paired_bootstrap_ci, paired_randomization_test

ROOT = Path(__file__).resolve().parents[1]


def test_exact_randomization_bootstrap_and_holm() -> None:
    assert paired_randomization_test([2, 3, 4], [1, 1, 1]) == {
        "difference_mean": 2.0,
        "p_value": 0.125,
        "permutations": 8,
        "mode": "exact",
    }
    first = paired_bootstrap_ci([2, 4, 8], [1, 1, 1], resamples=200, seed=7)
    assert first == paired_bootstrap_ci([2, 4, 8], [1, 1, 1], resamples=200, seed=7)
    assert first["lower"] <= first["difference_mean"] <= first["upper"]
    assert holm_adjust({"H2": 0.01, "H3": 0.04, "H4": 0.03, "H5": 0.8}) == {
        "H2": 0.04,
        "H3": 0.09,
        "H4": 0.09,
        "H5": 0.8,
    }
    with pytest.raises(ValueError):
        holm_adjust({"H2": math.nan})


@pytest.mark.asyncio
async def test_calibration_runs_but_cannot_claim_research() -> None:
    from research.run_protocol import run_calibration

    result = await run_calibration(seed=42, budget=1)
    assert result["results_status"] == "synthetic_fixture_calibration_not_confirmatory_research"
    assert result["target_calls_total"] >= 2


def test_machine_readable_protocol_is_explicitly_unrun() -> None:
    prereg = yaml.safe_load((ROOT / "research/preregistration.yaml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load(
        (ROOT / "research/experiment-manifest.yaml").read_text(encoding="utf-8")
    )
    assert prereg["results_status"] == "not_run"
    assert manifest["status"] == "planned"
    assert all(value is None for value in manifest["artifacts"].values())


def test_run_protocol_direct_script_help_works_from_repository_root() -> None:
    completed = subprocess.run(
        [sys.executable, "research/run_protocol.py", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "synthetic calibration" in completed.stdout.casefold()
