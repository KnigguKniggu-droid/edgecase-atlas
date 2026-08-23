"""Pure, deterministic data builders for the public product showcase."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from app.ui import (
        PUBLIC_ADAPTER_ID,
        PUBLIC_BUDGET_MAX,
        PUBLIC_BUDGET_MIN,
        PUBLIC_SEED_MAX,
    )
elif __package__:
    from .ui import (
        PUBLIC_ADAPTER_ID,
        PUBLIC_BUDGET_MAX,
        PUBLIC_BUDGET_MIN,
        PUBLIC_SEED_MAX,
    )
else:
    from ui import (
        PUBLIC_ADAPTER_ID,
        PUBLIC_BUDGET_MAX,
        PUBLIC_BUDGET_MIN,
        PUBLIC_SEED_MAX,
    )

from edgecase_atlas.comparison import compare_run_documents
from edgecase_atlas.engine import AtlasEngine, RunResult
from edgecase_atlas.fixtures import FaultyDemonstrationAgent
from edgecase_atlas.properties import STARTER_PROPERTY_PACK, SafetyProperty
from edgecase_atlas.serialization import canonical_json, run_document

# This matches the seed shown by the hosted public controls.
DEFAULT_PUBLIC_SEED = 42
SYNTHETIC_CALIBRATION_LABEL = "Synthetic calibration"
NOT_SAFETY_PERFORMANCE_LABEL = "Synthetic fixture results are not real safety performance."


class ReproductionRate(TypedDict):
    """Measured engineering-gate outcomes for one selected property."""

    reproductions: int
    trials: int
    rate: float | None


class ShowcaseMetrics(TypedDict):
    """Measured, JSON-safe summary of one in-memory Atlas run."""

    certificate_count: int
    property_count: int
    target_calls: int
    coverage_cells: int
    coverage_cell_ids: list[str]
    per_property_reproduction_rates: dict[str, ReproductionRate]


class CuratedArtifact(TypedDict):
    """One property-specific public artifact and its content digest."""

    label: str
    disclaimer: str
    adapter_id: str
    property_id: str
    metrics: ShowcaseMetrics
    artifact_sha256: str
    document: dict[str, object]


class PublicBenchmark(TypedDict):
    """Five-property synthetic calibration artifact."""

    label: str
    disclaimer: str
    adapter_id: str
    metrics: ShowcaseMetrics
    artifact_sha256: str
    document: dict[str, object]


class ComparisonPair(TypedDict):
    """Two compatible public run documents and their deterministic comparison."""

    label: str
    disclaimer: str
    adapter_id: str
    run_a_sha256: str
    run_b_sha256: str
    run_a: dict[str, object]
    run_b: dict[str, object]
    comparison: dict[str, object]


async def generate_curated_artifact(
    property_id: str,
    *,
    seed: int = DEFAULT_PUBLIC_SEED,
    budget: int = PUBLIC_BUDGET_MIN,
) -> CuratedArtifact:
    """Run any allowed starter property with the hosted no-key fixture."""
    _validate_public_bounds(seed=seed, budget=budget)
    property_ = _starter_property(property_id)
    run, document = await _run_fixture((property_,), seed=seed, budget=budget)
    return {
        "label": SYNTHETIC_CALIBRATION_LABEL,
        "disclaimer": NOT_SAFETY_PERFORMANCE_LABEL,
        "adapter_id": PUBLIC_ADAPTER_ID,
        "property_id": property_.property_id,
        "metrics": _measure(run),
        "artifact_sha256": _sha256(document),
        "document": document,
    }


async def generate_public_benchmark(
    *,
    seed: int = DEFAULT_PUBLIC_SEED,
    budget: int = PUBLIC_BUDGET_MAX,
) -> PublicBenchmark:
    """Run one synthetic candidate for each of the five starter properties."""
    _validate_public_bounds(seed=seed, budget=budget)
    if budget != len(STARTER_PROPERTY_PACK):
        raise ValueError("The public benchmark requires one candidate per starter property.")
    run, document = await _run_fixture(STARTER_PROPERTY_PACK, seed=seed, budget=budget)
    return {
        "label": SYNTHETIC_CALIBRATION_LABEL,
        "disclaimer": NOT_SAFETY_PERFORMANCE_LABEL,
        "adapter_id": PUBLIC_ADAPTER_ID,
        "metrics": _measure(run),
        "artifact_sha256": _sha256(document),
        "document": document,
    }


async def generate_sample_comparison_pair(
    *,
    seed: int = DEFAULT_PUBLIC_SEED,
    baseline_budget: int = PUBLIC_BUDGET_MIN,
    candidate_budget: int = PUBLIC_BUDGET_MAX,
) -> ComparisonPair:
    """Build two validated, property-pack-compatible runs for the compare page."""
    _validate_public_bounds(seed=seed, budget=baseline_budget)
    _validate_public_bounds(seed=seed, budget=candidate_budget)
    _, run_a = await _run_fixture(
        STARTER_PROPERTY_PACK,
        seed=seed,
        budget=baseline_budget,
    )
    _, run_b = await _run_fixture(
        STARTER_PROPERTY_PACK,
        seed=seed,
        budget=candidate_budget,
    )
    return {
        "label": SYNTHETIC_CALIBRATION_LABEL,
        "disclaimer": NOT_SAFETY_PERFORMANCE_LABEL,
        "adapter_id": PUBLIC_ADAPTER_ID,
        "run_a_sha256": _sha256(run_a),
        "run_b_sha256": _sha256(run_b),
        "run_a": run_a,
        "run_b": run_b,
        "comparison": compare_run_documents(run_a, run_b),
    }


async def _run_fixture(
    properties: tuple[SafetyProperty, ...], *, seed: int, budget: int
) -> tuple[RunResult, dict[str, object]]:
    run = await AtlasEngine().run(
        FaultyDemonstrationAgent(),
        properties,
        seed=seed,
        budget=budget,
    )
    return run, run_document(run)


def _measure(run: RunResult) -> ShowcaseMetrics:
    totals = {
        property_id: {"reproductions": 0, "trials": 0} for property_id in run.metadata.property_ids
    }
    for result in run.certificates:
        total = totals[result.certificate.property_id]
        total["reproductions"] += result.certificate.reproduction_count
        total["trials"] += result.certificate.reproduction_trials

    rates: dict[str, ReproductionRate] = {}
    for property_id, total in totals.items():
        reproductions = total["reproductions"]
        trials = total["trials"]
        rates[property_id] = {
            "reproductions": reproductions,
            "trials": trials,
            "rate": reproductions / trials if trials else None,
        }
    coverage_cell_ids = sorted(run.coverage_cells)
    return {
        "certificate_count": len(run.certificates),
        "property_count": len(run.metadata.property_ids),
        "target_calls": run.call_ledger.target_calls_total,
        "coverage_cells": len(coverage_cell_ids),
        "coverage_cell_ids": coverage_cell_ids,
        "per_property_reproduction_rates": rates,
    }


def _starter_property(property_id: str) -> SafetyProperty:
    if not isinstance(property_id, str):
        raise ValueError("Select an allowed starter property.")
    for property_ in STARTER_PROPERTY_PACK:
        if property_.property_id == property_id:
            return property_
    raise ValueError("Select an allowed starter property.")


def _validate_public_bounds(*, seed: int, budget: int) -> None:
    valid_seed = (
        isinstance(seed, int) and not isinstance(seed, bool) and 0 <= seed <= PUBLIC_SEED_MAX
    )
    valid_budget = (
        isinstance(budget, int)
        and not isinstance(budget, bool)
        and PUBLIC_BUDGET_MIN <= budget <= PUBLIC_BUDGET_MAX
    )
    if not valid_seed or not valid_budget:
        raise ValueError("Seed or budget is outside the public showcase range.")


def _sha256(document: dict[str, object]) -> str:
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()
