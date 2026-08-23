"""Generate the competition story from verified launch metrics."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REQUIRED_COUNTS = (
    "completed_test_runs",
    "distinct_users",
    "independent_cli_users",
    "pilot_respondents",
    "clarity_positive_respondents",
    "repeated_users",
)
REQUIRED_TEXT = ("public_app_url", "repository_url", "evidence_cutoff_utc")


def _https_url(value: str, field: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute HTTPS URL")
    return value


def validate_metrics(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("metrics must be a JSON object")
    expected = set(REQUIRED_COUNTS + REQUIRED_TEXT)
    missing = expected - raw.keys()
    extra = raw.keys() - expected
    if missing or extra:
        raise ValueError(f"metrics keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
    for field in REQUIRED_COUNTS:
        value = raw[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field} must be a nonnegative integer")
    for field in REQUIRED_TEXT:
        if not isinstance(raw[field], str) or not raw[field].strip():
            raise ValueError(f"{field} must be resolved before story generation")
    _https_url(raw["public_app_url"], "public_app_url")
    _https_url(raw["repository_url"], "repository_url")
    if raw["clarity_positive_respondents"] > raw["pilot_respondents"]:
        raise ValueError("clarity-positive respondents cannot exceed pilot respondents")
    if raw["independent_cli_users"] > raw["distinct_users"]:
        raise ValueError("independent CLI users cannot exceed distinct users")
    if raw["repeated_users"] > raw["distinct_users"]:
        raise ValueError("repeated users cannot exceed distinct users")
    return raw


def generate_story(metrics: dict[str, Any]) -> str:
    values = validate_metrics(metrics)
    story = (
        "AI driving-decision agents can sound plausible while violating editable safety "
        "assumptions. I built EdgeCase Atlas, a developer tool that creates valid paired "
        "counterfactuals, repeats stochastic checks, minimizes failures, and exports replayable "
        "certificates. The hardest engineering problem was preserving scenario validity and "
        "complete call accounting while reducing flaky failures without overstating the evidence. "
        "I designed the typed schema, five-property pack, deterministic engine, adapters, CLI, "
        "no-key web demo, and offline reports. By the evidence cutoff, Atlas completed "
        f"{values['completed_test_runs']} test runs for {values['distinct_users']} distinct users; "
        f"{values['independent_cli_users']} independently ran the CLI, and "
        f"{values['clarity_positive_respondents']} of {values['pilot_respondents']} pilot "
        "respondents said the minimized pair improved debugging clarity. Next, I will compare "
        "five matched search methods and confirm retained failures on fresh simulator seeds."
    )
    if len(story.split()) > 150:
        raise AssertionError("generated story exceeds 150 words")
    return story


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: generate_story.py METRICS.json STORY.md", file=sys.stderr)
        return 2
    source, destination = map(Path, argv[1:])
    try:
        metrics = json.loads(source.read_text(encoding="utf-8"))
        story = generate_story(metrics)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"story generation failed: {exc}", file=sys.stderr)
        return 1
    destination.write_text(f"# Competition story\n\n{story}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
