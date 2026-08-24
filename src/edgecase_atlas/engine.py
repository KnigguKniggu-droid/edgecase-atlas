"""Deterministic end-to-end discovery of minimal reproducing certificates."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from edgecase_atlas import __version__
from edgecase_atlas.adapters import AdapterError
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
from edgecase_atlas.models import FailureCertificate
from edgecase_atlas.properties import (
    CONFIRMATION_TRIALS,
    REQUIRED_REPRODUCTIONS,
    SafetyProperty,
)

_COVERAGE_ESTIMAND = "search-and-engineering-gate observable coverage"


@dataclass(frozen=True, slots=True)
class RunMetadata:
    run_id: str
    seed: int
    candidate_budget: int
    held_out_confirmation_seed_stream: str
    executed_seed_streams: tuple[str, ...]
    property_ids: tuple[str, ...]
    property_pack_digest: str
    engine_config_hash: str
    confirmation_note: str


@dataclass(frozen=True, slots=True)
class MinimalReproducingCertificate:
    certificate: FailureCertificate
    label: str
    minimization: MinimizationResult


@dataclass(frozen=True, slots=True)
class RunResult:
    metadata: RunMetadata
    certificates: tuple[MinimalReproducingCertificate, ...]
    call_ledger: CallLedger
    coverage_cells: frozenset[str]
    coverage_trajectory: tuple[CoveragePoint, ...]
    coverage_estimand: str


class AtlasEngine:
    """Use the 4-of-5 result only as an adaptive engineering gate."""

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
        property_pack_digest = _property_pack_digest(properties)
        engine_config_hash = _engine_config_hash()
        corpus = generate_corpus(properties, seed=seed, budget=budget)
        if corpus:
            executed_streams.append("search")
        for generated, search_seed in zip(corpus, streams.search_seeds(len(corpus)), strict=True):
            try:
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
                outcome = search_trial.property_result
                if not (outcome.applicable and outcome.violated):
                    continue
                if "engineering-gate" not in executed_streams:
                    executed_streams.append("engineering-gate")
                confirmation = await evaluate_suspected_violation(
                    adapter,
                    generated.property,
                    generated.counterfactual,
                    streams.engineering_gate_seeds(CONFIRMATION_TRIALS),
                    ledger,
                    phase="confirmation",
                    required_reproductions=REQUIRED_REPRODUCTIONS,
                )
                start = ledger.target_calls_total - 2 * len(confirmation.trials)
                for index, trial in enumerate(confirmation.trials, start=1):
                    tracker.observe(
                        generated.property,
                        generated.counterfactual,
                        trial.source_decision,
                        trial.follow_up_decision,
                        charged_target_calls=start + 2 * index,
                    )
                if not confirmation.accepted:
                    continue
                if "shrink" not in executed_streams:
                    executed_streams.append("shrink")
                minimization = await HierarchicalMinimizer().minimize(
                    adapter, generated.property, generated.counterfactual, streams, ledger
                )
                tracker.extend_constant_to(ledger.target_calls_total)
                if minimization.accepted:
                    certificate = _certificate(
                        adapter,
                        generated.property,
                        minimization,
                        seed,
                        _property_digest(generated.property),
                        engine_config_hash,
                    )
                    certificates.append(
                        MinimalReproducingCertificate(certificate, minimization.label, minimization)
                    )
            except AdapterError:
                # A target that fails on one candidate must not discard the certificates
                # already found. But a target that has produced nothing is simply broken,
                # and hiding that would let a misconfigured agent look like a clean run,
                # so the error still propagates until there is evidence worth keeping.
                if not certificates:
                    raise
                continue
        return RunResult(
            RunMetadata(
                _run_id(seed, budget, adapter, property_pack_digest, engine_config_hash),
                seed,
                budget,
                "held-out-confirmation",
                tuple(executed_streams),
                tuple(property_.property_id for property_ in properties),
                property_pack_digest,
                engine_config_hash,
                (
                    "The held-out confirmation stream is reserved and unexecuted. "
                    "The alpha 4-of-5 result is an engineering discovery and reduction heuristic."
                ),
            ),
            tuple(certificates),
            ledger,
            tracker.cells,
            tuple(tracker.trajectory),
            _COVERAGE_ESTIMAND,
        )


def _certificate(
    adapter: AgentAdapter,
    property_: SafetyProperty,
    minimization: MinimizationResult,
    seed: int,
    property_semantics_digest: str,
    engine_config_hash: str,
) -> FailureCertificate:
    relation = minimization.counterfactual
    cost_available = minimization.reproduction.cost_estimate_available
    provisional = FailureCertificate(
        certificate_id="pending",
        relation_id=relation.relation_id,
        property_id=property_.property_id,
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
        estimated_cost_usd=(
            minimization.reproduction.estimated_cost_usd if cost_available else 0.0
        ),
        cost_estimate_available=cost_available,
        property_semantics_digest=property_semantics_digest,
        engine_config_hash=engine_config_hash,
        reducer_label=minimization.label,
        reducer_vocabulary=minimization.reducer_vocabulary,
        terminal_audit_complete=minimization.terminal_audit_complete,
        replay_command="pending",
    )
    certificate_id = recompute_certificate_id(provisional)
    return provisional.model_copy(
        update={
            "certificate_id": certificate_id,
            "replay_command": f"atlas replay certificates/{certificate_id}.json",
        }
    )


def _certificate_id(
    adapter: AgentAdapter,
    property_: SafetyProperty,
    minimization: MinimizationResult,
    seed: int,
    property_semantics_digest: str,
    engine_config_hash: str,
) -> str:
    """Retain the Task 2 helper while delegating to the public evidence digest."""
    return _certificate(
        adapter,
        property_,
        minimization,
        seed,
        property_semantics_digest,
        engine_config_hash,
    ).certificate_id


def recompute_certificate_id(certificate: FailureCertificate) -> str:
    """Recompute the public, deterministic digest over stable certificate evidence."""
    evidence = {
        "relation_id": certificate.relation_id,
        "property_id": certificate.property_id,
        "source": certificate.source.model_dump(mode="json"),
        "minimized_follow_up": certificate.minimized_follow_up.model_dump(mode="json"),
        "changed_fields": [change.model_dump(mode="json") for change in certificate.changed_fields],
        "source_decisions": [
            decision.model_dump(mode="json") for decision in certificate.source_decisions
        ],
        "follow_up_decisions": [
            decision.model_dump(mode="json") for decision in certificate.follow_up_decisions
        ],
        "reproduction_count": certificate.reproduction_count,
        "reproduction_trials": certificate.reproduction_trials,
        "model_id": certificate.model_id,
        "model_config_hash": certificate.model_config_hash,
        "software_version": certificate.software_version,
        "seed": certificate.seed,
        "property_semantics_digest": certificate.property_semantics_digest,
        "engine_config_hash": certificate.engine_config_hash,
        "reducer_label": certificate.reducer_label,
        "reducer_vocabulary": certificate.reducer_vocabulary,
        "terminal_audit_complete": certificate.terminal_audit_complete,
    }
    return f"case-{_digest_json(evidence)[:20]}"


def _run_id(
    seed: int,
    budget: int,
    adapter: AgentAdapter,
    property_pack_digest: str,
    engine_config_hash: str,
) -> str:
    identity = {
        "seed": seed,
        "candidate_budget": budget,
        "property_pack_digest": property_pack_digest,
        "model_id": adapter_model_id(adapter),
        "model_config_hash": model_config_hash(adapter),
        "engine_config_hash": engine_config_hash,
    }
    return f"run-{_digest_json(identity)[:16]}"


def _property_digest(property_: SafetyProperty) -> str:
    return _digest_json(
        {
            "property_id": property_.property_id,
            "title": property_.title,
            "description": property_.description,
            "scope_note": property_.scope_note,
        }
    )


def _property_pack_digest(properties: tuple[SafetyProperty, ...]) -> str:
    return _digest_json([_property_digest(property_) for property_ in properties])


def _engine_config_hash() -> str:
    return _digest_json(
        {
            "software_version": __version__,
            "confirmation_trials": CONFIRMATION_TRIALS,
            "required_reproductions": REQUIRED_REPRODUCTIONS,
            "coverage_estimand": _COVERAGE_ESTIMAND,
            "reducer": HierarchicalMinimizer.reducer_vocabulary,
        }
    )


def _digest_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=list).encode()
    ).hexdigest()
