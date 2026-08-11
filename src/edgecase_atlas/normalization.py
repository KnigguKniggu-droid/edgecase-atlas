"""Deterministic label normalization at adapter boundaries."""

from __future__ import annotations

import re

from edgecase_atlas.models import Action, Risk

_WHITESPACE = re.compile(r"[\s-]+")
_ACTION_ALIASES: dict[str, Action] = {
    "stop": "stop",
    "brake": "stop",
    "prepare_stop": "prepare_stop",
    "prepare_to_stop": "prepare_stop",
    "slow_down": "reduce_speed",
    "reduce_speed": "reduce_speed",
    "increase_gap": "increase_gap",
    "proceed": "proceed",
    "go": "proceed",
}
_RISK_ALIASES: dict[str, Risk] = {
    "low": "low",
    "medium": "medium",
    "moderate": "medium",
    "high": "high",
    "critical": "critical",
}


def _canonicalize(value: str) -> str:
    return _WHITESPACE.sub("_", value.strip().casefold())


def normalize_action(value: str) -> Action:
    """Return an action from an explicitly supported vocabulary."""
    normalized = _ACTION_ALIASES.get(_canonicalize(value))
    if normalized is None:
        raise ValueError(f"Unknown action label: {value!r}")
    return normalized


def normalize_risk(value: str) -> Risk:
    """Return a risk from an explicitly supported vocabulary."""
    normalized = _RISK_ALIASES.get(_canonicalize(value))
    if normalized is None:
        raise ValueError(f"Unknown risk label: {value!r}")
    return normalized
