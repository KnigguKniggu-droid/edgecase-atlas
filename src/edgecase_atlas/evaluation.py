"""Paired agent evaluation, charged-call accounting, and seed-stream isolation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol, runtime_checkable

from edgecase_atlas.models import Counterfactual, Decision, Scenario
from edgecase_atlas.properties import PropertyResult, SafetyProperty, evaluate_property

EvaluationPhase = Literal["search", "confirmation", "minimization"]


@runtime_checkable
class AgentAdapter(Protocol):
    """Stable target interface implemented by concrete adapters in Task 3."""

    async def decide(self, scenario: Scenario, seed: int) -> Decision: ...


@dataclass(frozen=True, slots=True)
class SeedStreams:
    """Deterministically derived, mutually disjoint streams for adaptive and future work."""

    root_seed: int

    def search_seeds(self, count: int) -> tuple[int, ...]:
        return self._seeds("search", count)

    def engineering_gate_seeds(self, count: int) -> tuple[int, ...]:
        """Return adaptive 4-of-5 engineering-gate seeds, never held-out research seeds."""
        return self._seeds("engineering-gate", count)

    def confirmation_seeds(self, count: int) -> tuple[int, ...]:
        """Compatibility alias for the alpha engineering gate, not research confirmation."""
        return self.engineering_gate_seeds(count)

    def shrink_seeds(self, count: int) -> tuple[int, ...]:
        return self._seeds("shrink", count)

    def held_out_confirmation_seeds(self, count: int) -> tuple[int, ...]:
        """Reserve unexecuted seeds for a future non-adaptive confirmation protocol."""
        return self._seeds("held-out-confirmation", count)

    def _seeds(self, stream: str, count: int) -> tuple[int, ...]:
        if count < 0:
            raise ValueError("count must be nonnegative")
        return tuple(
            int.from_bytes(
                hashlib.sha256(
                    f"edgecase-atlas:{self.root_seed}:{stream}:{index}".encode()
                ).digest()[:8],
                "big",
            )
            & ((2**63) - 1)
            for index in range(count)
        )


@dataclass(slots=True)
class CallLedger:
    """Every attempted target invocation is charged exactly once to an operational phase."""

    target_calls_total: int = 0
    search_calls: int = 0
    confirmation_calls: int = 0
    minimization_calls: int = 0
    estimated_cost_usd: float = 0.0
    cost_estimate_available: bool = False

    def record(self, phase: EvaluationPhase, estimated_cost_usd: float | None) -> None:
        self.target_calls_total += 1
        if phase == "search":
            self.search_calls += 1
        elif phase == "confirmation":
            self.confirmation_calls += 1
        else:
            self.minimization_calls += 1
        if estimated_cost_usd is not None:
            self.estimated_cost_usd += estimated_cost_usd
            self.cost_estimate_available = True


@dataclass(frozen=True, slots=True)
class PairTrial:
    """One source/follow-up evaluation pair, charged as two calls when both complete."""

    seed: int
    source_decision: Decision
    follow_up_decision: Decision
    property_result: PropertyResult
    latency_ms: int
    estimated_cost_usd: float
    cost_estimate_available: bool


@dataclass(frozen=True, slots=True)
class ReproductionResult:
    """A repeated engineering gate, not independent research confirmation."""

    trials: tuple[PairTrial, ...]
    reproduction_count: int
    reproduction_trials: int
    accepted: bool
    phase: EvaluationPhase

    @property
    def source_decisions(self) -> tuple[Decision, ...]:
        return tuple(trial.source_decision for trial in self.trials)

    @property
    def follow_up_decisions(self) -> tuple[Decision, ...]:
        return tuple(trial.follow_up_decision for trial in self.trials)

    @property
    def latency_ms(self) -> int:
        return sum(trial.latency_ms for trial in self.trials)

    @property
    def estimated_cost_usd(self) -> float:
        return sum(trial.estimated_cost_usd for trial in self.trials)

    @property
    def cost_estimate_available(self) -> bool:
        return bool(self.trials) and all(trial.cost_estimate_available for trial in self.trials)


async def evaluate_pair(
    adapter: AgentAdapter,
    property_: SafetyProperty,
    counterfactual: Counterfactual,
    seed: int,
    ledger: CallLedger,
    *,
    phase: EvaluationPhase,
) -> PairTrial:
    """Evaluate both sides and preserve the paired decisions used by the operational oracle."""
    source_decision, source_latency = await _decide(
        adapter, counterfactual.source, seed, ledger, phase
    )
    follow_up_decision, follow_up_latency = await _decide(
        adapter, counterfactual.follow_up, seed, ledger, phase
    )
    estimate = _cost_estimate(adapter)
    return PairTrial(
        seed=seed,
        source_decision=source_decision,
        follow_up_decision=follow_up_decision,
        property_result=evaluate_property(
            property_, counterfactual, source_decision, follow_up_decision
        ),
        latency_ms=source_latency + follow_up_latency,
        estimated_cost_usd=0.0 if estimate is None else estimate * 2,
        cost_estimate_available=estimate is not None,
    )


async def evaluate_suspected_violation(
    adapter: AgentAdapter,
    property_: SafetyProperty,
    counterfactual: Counterfactual,
    seeds: tuple[int, ...],
    ledger: CallLedger,
    *,
    phase: EvaluationPhase,
    required_reproductions: int = 4,
) -> ReproductionResult:
    """Apply a declared repeated-evaluation engineering gate to a suspected violation."""
    if not seeds:
        raise ValueError("At least one trial seed is required")
    if required_reproductions < 1 or required_reproductions > len(seeds):
        raise ValueError("required_reproductions must be between one and the trial count")
    trials: list[PairTrial] = []
    for seed in seeds:
        trials.append(
            await evaluate_pair(adapter, property_, counterfactual, seed, ledger, phase=phase)
        )
    reproduction_count = sum(
        trial.property_result.applicable and trial.property_result.violated for trial in trials
    )
    return ReproductionResult(
        trials=tuple(trials),
        reproduction_count=reproduction_count,
        reproduction_trials=len(trials),
        accepted=reproduction_count >= required_reproductions,
        phase=phase,
    )


def adapter_model_id(adapter: AgentAdapter) -> str:
    """Return a stable nonempty target identifier without assuming a provider."""
    value = getattr(adapter, "model_id", adapter.__class__.__name__)
    return value if isinstance(value, str) and value else adapter.__class__.__name__


def model_config_hash(adapter: AgentAdapter) -> str:
    """Hash public adapter configuration while excluding undeclared secrets."""
    config = getattr(adapter, "model_config", {})
    serializable = config if isinstance(config, dict) else {}
    canonical = json.dumps(serializable, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]


async def _decide(
    adapter: AgentAdapter,
    scenario: Scenario,
    seed: int,
    ledger: CallLedger,
    phase: EvaluationPhase,
) -> tuple[Decision, int]:
    started = perf_counter()
    try:
        decision = await adapter.decide(scenario, seed)
    finally:
        ledger.record(phase, _cost_estimate(adapter))
    return decision, int((perf_counter() - started) * 1000)


def _cost_estimate(adapter: AgentAdapter) -> float | None:
    value = getattr(adapter, "estimated_cost_per_call_usd", None)
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    return None
