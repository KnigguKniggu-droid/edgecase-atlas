from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "docs" / "launch" / "generate_story.py"
SPEC = importlib.util.spec_from_file_location("generate_story", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def metrics() -> dict[str, object]:
    return {
        "completed_test_runs": 31,
        "distinct_users": 10,
        "independent_cli_users": 2,
        "pilot_respondents": 5,
        "clarity_positive_respondents": 3,
        "repeated_users": 2,
        "public_app_url": "https://example.streamlit.app",
        "repository_url": "https://github.com/example/edgecase-atlas",
        "evidence_cutoff_utc": "2026-08-22T18:00:00Z",
    }


def test_story_generation_is_deterministic_and_bounded() -> None:
    first = MODULE.generate_story(metrics())
    second = MODULE.generate_story(metrics())

    assert first == second
    assert len(first.split()) <= 150
    assert "31 test runs for 10 distinct users" in first
    assert "3 of 5 pilot respondents" in first
    assert "TBD" not in first


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("completed_test_runs", None, "nonnegative integer"),
        ("distinct_users", -1, "nonnegative integer"),
        ("public_app_url", "http://example.com", "HTTPS URL"),
    ],
)
def test_story_rejects_unresolved_or_invalid_metrics(
    field: str, value: object, message: str
) -> None:
    values = metrics()
    values[field] = value

    with pytest.raises(ValueError, match=message):
        MODULE.generate_story(values)


def test_story_rejects_inconsistent_counts() -> None:
    values = metrics()
    values["clarity_positive_respondents"] = 6

    with pytest.raises(ValueError, match="cannot exceed"):
        MODULE.generate_story(values)


def test_example_metrics_remain_deliberately_unresolved() -> None:
    example = json.loads(
        (ROOT / "docs" / "launch" / "metrics.example.json").read_text(encoding="utf-8")
    )

    with pytest.raises(ValueError, match="nonnegative integer"):
        MODULE.generate_story(example)
