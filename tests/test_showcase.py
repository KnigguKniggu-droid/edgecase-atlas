"""Deterministic public showcase artifacts built only from the synthetic fixture."""

from __future__ import annotations

import hashlib
import json

import pytest
from app.showcase import (
    DEFAULT_PUBLIC_SEED,
    NOT_SAFETY_PERFORMANCE_LABEL,
    SYNTHETIC_CALIBRATION_LABEL,
    generate_curated_artifact,
    generate_public_benchmark,
    generate_sample_comparison_pair,
)
from app.ui import PUBLIC_BUDGET_MAX, PUBLIC_SEED_MAX

from edgecase_atlas.comparison import compare_run_documents
from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.serialization import canonical_json

PROPERTY_IDS = tuple(item.property_id for item in STARTER_PROPERTY_PACK)


@pytest.mark.parametrize("property_id", PROPERTY_IDS)
async def test_curated_artifact_supports_every_starter_property(property_id: str) -> None:
    artifact = await generate_curated_artifact(property_id)

    assert artifact["property_id"] == property_id
    assert artifact["adapter_id"] == "faulty_fixture"
    assert artifact["label"] == SYNTHETIC_CALIBRATION_LABEL
    assert artifact["disclaimer"] == NOT_SAFETY_PERFORMANCE_LABEL
    assert artifact["metrics"]["property_count"] == 1
    assert artifact["metrics"]["certificate_count"] == 1
    assert artifact["metrics"]["target_calls"] > 0
    assert artifact["metrics"]["coverage_cells"] > 0
    assert artifact["metrics"]["coverage_cell_ids"] == sorted(
        artifact["metrics"]["coverage_cell_ids"]
    )
    assert artifact["metrics"]["per_property_reproduction_rates"] == {
        property_id: {"reproductions": 5, "trials": 5, "rate": 1.0}
    }
    assert artifact["document"]["metadata"]["property_ids"] == [property_id]
    json.dumps(artifact, allow_nan=False)


async def test_showcase_artifacts_are_deterministic_and_content_addressed() -> None:
    first = await generate_curated_artifact(
        "hazard_non_aggression", seed=DEFAULT_PUBLIC_SEED, budget=1
    )
    second = await generate_curated_artifact(
        "hazard_non_aggression", seed=DEFAULT_PUBLIC_SEED, budget=1
    )

    assert first == second
    expected_digest = hashlib.sha256(canonical_json(first["document"]).encode("utf-8")).hexdigest()
    assert first["artifact_sha256"] == expected_digest
    assert len(first["artifact_sha256"]) == 64


async def test_public_benchmark_measures_all_five_properties() -> None:
    benchmark = await generate_public_benchmark()
    metrics = benchmark["metrics"]

    assert benchmark["label"] == SYNTHETIC_CALIBRATION_LABEL
    assert benchmark["disclaimer"] == NOT_SAFETY_PERFORMANCE_LABEL
    assert benchmark["adapter_id"] == "faulty_fixture"
    assert metrics["property_count"] == len(STARTER_PROPERTY_PACK) == 5
    assert metrics["certificate_count"] == 5
    assert metrics["target_calls"] > 0
    assert metrics["coverage_cells"] == len(metrics["coverage_cell_ids"])
    assert set(metrics["per_property_reproduction_rates"]) == set(PROPERTY_IDS)
    assert all(
        rate == {"reproductions": 5, "trials": 5, "rate": 1.0}
        for rate in metrics["per_property_reproduction_rates"].values()
    )
    assert (
        benchmark["artifact_sha256"]
        == hashlib.sha256(canonical_json(benchmark["document"]).encode("utf-8")).hexdigest()
    )
    json.dumps(benchmark, allow_nan=False)


@pytest.mark.parametrize(
    ("seed", "budget"),
    ((-1, 1), (PUBLIC_SEED_MAX + 1, 1), (True, 1), (0, 0), (0, 6), (0, True)),
)
async def test_curated_artifact_rejects_values_outside_hosted_bounds(
    seed: int, budget: int
) -> None:
    with pytest.raises(ValueError, match="public showcase range"):
        await generate_curated_artifact("red_signal_no_proceed", seed=seed, budget=budget)


async def test_public_benchmark_requires_the_documented_five_candidate_configuration() -> None:
    with pytest.raises(ValueError, match="one candidate per starter property"):
        await generate_public_benchmark(budget=PUBLIC_BUDGET_MAX - 1)
    with pytest.raises(ValueError, match="starter property"):
        await generate_curated_artifact("unknown-property")


async def test_sample_comparison_pair_is_compatible_and_deterministic() -> None:
    first = await generate_sample_comparison_pair()
    second = await generate_sample_comparison_pair()

    assert first == second
    assert first["label"] == SYNTHETIC_CALIBRATION_LABEL
    assert first["disclaimer"] == NOT_SAFETY_PERFORMANCE_LABEL
    assert first["comparison"] == compare_run_documents(first["run_a"], first["run_b"])
    compatibility = first["comparison"]["compatibility"]
    assert compatibility["property_ids"] == list(PROPERTY_IDS)
    assert (
        first["run_a_sha256"]
        == hashlib.sha256(canonical_json(first["run_a"]).encode("utf-8")).hexdigest()
    )
    assert (
        first["run_b_sha256"]
        == hashlib.sha256(canonical_json(first["run_b"]).encode("utf-8")).hexdigest()
    )
    json.dumps(first, allow_nan=False)
