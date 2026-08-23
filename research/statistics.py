"""Dependency-free deterministic statistics for paired campaigns."""

from __future__ import annotations

import itertools
import math
import random
from collections.abc import Mapping, Sequence


def _differences(x: Sequence[float], y: Sequence[float]) -> list[float]:
    if not x or len(x) != len(y):
        raise ValueError("Paired samples must be nonempty and equal length")
    values = [float(a) - float(b) for a, b in zip(x, y, strict=True)]
    if any(not math.isfinite(value) for value in values):
        raise ValueError("Samples must contain only finite values")
    return values


def paired_randomization_test(
    treatment: Sequence[float],
    comparator: Sequence[float],
    *,
    alternative: str = "greater",
    seed: int = 0,
    permutations: int = 100_000,
) -> dict[str, float | int | str]:
    """Use exact sign enumeration through 20 blocks, then seeded Monte Carlo."""
    differences = _differences(treatment, comparator)
    if alternative not in {"greater", "two-sided"} or permutations < 1:
        raise ValueError("Unsupported alternative or permutation count")
    observed = sum(differences) / len(differences)
    exact = len(differences) <= 20
    rng = random.Random(seed)  # noqa: S311
    patterns = (
        itertools.product((-1.0, 1.0), repeat=len(differences))
        if exact
        else (
            tuple(1.0 if rng.getrandbits(1) else -1.0 for _ in differences)
            for _ in range(permutations)
        )
    )
    extreme = total = 0
    for pattern in patterns:
        statistic = sum(s * d for s, d in zip(pattern, differences, strict=True)) / len(differences)
        extreme += (
            statistic >= observed if alternative == "greater" else abs(statistic) >= abs(observed)
        )
        total += 1
    correction = 0 if exact else 1
    return {
        "difference_mean": observed,
        "p_value": (extreme + correction) / (total + correction),
        "permutations": total,
        "mode": "exact" if exact else "monte_carlo",
    }


def paired_permutation_test(
    x: Sequence[float], y: Sequence[float], **kwargs: object
) -> dict[str, float | int | str]:
    return paired_randomization_test(x, y, **kwargs)  # type: ignore[arg-type]


def paired_bootstrap_ci(
    treatment: Sequence[float],
    comparator: Sequence[float],
    *,
    confidence: float = 0.95,
    resamples: int = 10_000,
    seed: int = 0,
) -> dict[str, float]:
    differences = _differences(treatment, comparator)
    if not 0 < confidence < 1 or resamples < 2:
        raise ValueError("Invalid confidence or resample count")
    rng = random.Random(seed)  # noqa: S311
    estimates = sorted(
        sum(rng.choice(differences) for _ in differences) / len(differences)
        for _ in range(resamples)
    )
    tail = (1.0 - confidence) / 2.0
    return {
        "difference_mean": sum(differences) / len(differences),
        "lower": estimates[math.floor(tail * resamples)],
        "upper": estimates[min(resamples - 1, math.ceil((1 - tail) * resamples) - 1)],
        "confidence": confidence,
    }


def holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    if not p_values or any(not math.isfinite(p) or not 0 <= p <= 1 for p in p_values.values()):
        raise ValueError("P-values must be a nonempty mapping within [0, 1]")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (label, value) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - rank) * value))
        adjusted[label] = running
    return {label: adjusted[label] for label in p_values}
