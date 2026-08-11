"""Deterministic end-to-end discovery of minimal reproducing certificates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from edgecase_atlas import __version__
from edgecase_atlas.coverage import CoveragePoint, CoverageTracker
from edgecase_atlas.evaluation import (
    AgentAdapter,
    CallLedger,
    SeedStreams,
    adapter_model_id,
    evaluate_pair,
    evaluate_suspected_violation,
    model_config_hash,
)
from edgecase_atlas.generation import generate_corpus
from edgecase_atlas.minimizer import HierarchicalMinimizer, MinimizationResult
from edgecase_atlas.models import Counterfactual, FailureCertificate
from edgecase_atlas.properties import SafetyProperty


@dataclass(frozen=True, slots=True)
class RunMetadata:
    """Run-level reproducibility metadata without claiming research confirmation."""

    run_id: str
    seed: int
    candidate_budget: int
    held_out_confirmation_seed_stream: str
    executed_seed_streams: tuple[str, ...]
    confirmation_note: str


@dataclass(frozen=True, slots=True)
class MinimalReproducingCertificate:
    """A 1-minimal reproducing certificate under the declared reducer set."""

    certificate: FailureCertificate
    label: str
    minimization: MinimizationResult


@dataclass(frozen=True, slots=True)
class RunResult:
    """Deterministic discovery output and complete charged-call accounting."""

    metadata: RunMetadata
    certificates: tuple[MinimalReproducingCertificate, ...]
    call_ledger: CallLedger
    coverage_cells: frozenset[str]
    coverage_trajectory: tuple[CoveragePoint, ...]


class AtlasEngine:
    """Run a candidate budget with paired search, an engineering gate, and reduction."""

    async def run(
        self,
        adapter: AgentAdapter,
        properties: tuple[SafetyProperty, ...],
        *,
        seed: int,
        budget: int,
    ) -> RunResult:
        ledger = CallLedger()
        streams = SeedStreams(seed)
        tracker = CoverageTracker()
        certificates: list[MinimalReproducingCertificate] = []
        executed_streams: list[str] = []
        corpus = generate_corpus(properties, seed=seed, budget=budget)
        search_seeds = streams.search_seeds(len(corpus))
        if corpus:
            executed_streams.append("search")
        for generated, search_seed in zip(corpus, search_seeds, strict=True):
            search_trial = await evaluate_pair(
                adapter,
                generated.property,
                generated.counterfactual,
                search_seed,
                ledger,
                phase="search",
            )
            tracker.observe(
                generated.property,
                generated.counterfactual,
                search_trial.source_decision,
                search_trial.follow_up_decision,
                charged_target_calls=ledger.target_calls_total,
            )
            if not (
                search_trial.property_result.applicable and search_trial.property_result.violated
            ):
                continue
            if "engineering-gate" not in executed_streams:
                executed_streams.append("engineering-gate")
            confirmation = await evaluate_suspected_violation(
                adapter,
                generated.property,
                generated.counterfactual,
                streams.engineering_gate_seeds(5),
                ledger,
                phase="confirmation",
                required_reproductions=4,
            )
            confirmation_start_calls = ledger.target_calls_total - (2 * len(confirmation.trials))
            for index, trial in enumerate(confirmation.trials, start=1):
                tracker.observe(
                    generated.property,
                    generated.counterfactual,
                    trial.source_decision,
                    trial.follow_up_decision,
                    charged_target_calls=confirmation_start_calls + (2 * index),
                )
            if not confirmation.accepted:
                continue
            if "shrink" not in executed_streams:
                executed_streams.append("shrink")
            minimization = await HierarchicalMinimizer().minimize(
                adapter, generated.property, generated.counterfactual, streams, ledger
            )
            if not minimization.accepted:
                continue
            certificate = _certificate(adapter, generated.property.property_id, minimization, seed)
            certificates.append(
                MinimalReproducingCertificate(certificate, minimization.label, minimization)
            )
        return RunResult(
            metadata=RunMetadata(
                run_id=_run_id(seed, budget, properties),
                seed=seed,
                candidate_budget=budget,
                held_out_confirmation_seed_stream="held-out-confirmation",
                executed_seed_streams=tuple(executed_streams),
                confirmation_note=(
                    "The held-out confirmation stream is reserved and unexecuted by the alpha run. "
                    "The alpha 4-of-5 result is only an engineering discovery and reduction "
                    "heuristic."
                ),
            ),
            certificates=tuple(certificates),
            call_ledger=ledger,
            coverage_cells=tracker.cells,
            coverage_trajectory=tuple(tracker.trajectory),
        )


def _certificate(
    adapter: AgentAdapter,
    property_id: str,
    minimization: MinimizationResult,
    seed: int,
) -> FailureCertificate:
    relation = minimization.counterfactual
    certificate_id = _certificate_id(
        property_id,
        relation,
        adapter_model_id(adapter),
        model_config_hash(adapter),
        seed,
    )
    return FailureCertificate(
        certificate_id=certificate_id,
        relation_id=relation.relation_id,
        property_id=property_id,
        source=relation.source,
        minimized_follow_up=relation.follow_up,
        changed_fields=relation.changed_fields,
        source_decisions=minimization.reproduction.source_decisions,
        follow_up_decisions=minimization.reproduction.follow_up_decisions,
        reproduction_count=minimization.reproduction_count,
        reproduction_trials=minimization.reproduction_trials,
        model_id=adapter_model_id(adapter),
        model_config_hash=model_config_hash(adapter),
        software_version=__version__,
        seed=seed,
        latency_ms=minimization.reproduction.latency_ms,
        estimated_cost_usd=minimization.reproduction.estimated_cost_usd,
        replay_command=f"atlas replay certificates/{certificate_id}.json --seed {seed}",
    )


def _run_id(seed: int, budget: int, properties: tuple[SafetyProperty, ...]) -> str:
    property_ids = ",".join(property_.property_id for property_ in properties)
    return f"run-{_digest(f'{seed}:{budget}:{property_ids}')[:16]}"


def _certificate_id(
    property_id: str,
    relation: Counterfactual,
    model_id: str,
    config_hash: str,
    seed: int,
) -> str:
    content = {
        "property_id": property_id,
        "relation": relation.model_dump(mode="json"),
        "model_id": model_id,
        "model_config_hash": config_hash,
        "seed": seed,
        "software_version": __version__,
    }
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return f"case-{_digest(canonical)[:20]}"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
