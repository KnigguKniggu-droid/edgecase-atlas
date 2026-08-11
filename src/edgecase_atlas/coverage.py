"""Method-agnostic observable coverage for paired decision testing."""

from __future__ import annotations

from dataclasses import dataclass, field

from edgecase_atlas.models import Counterfactual, Decision
from edgecase_atlas.properties import SafetyProperty, evaluate_property


@dataclass(frozen=True, slots=True)
class CoverageSnapshot:
    cells: frozenset[str]
    charged_target_calls: int


@dataclass(frozen=True, slots=True)
class CoveragePoint:
    charged_target_calls: int
    observed_cells: int


@dataclass(slots=True)
class CoverageTracker:
    """Accumulate method-agnostic cells and honestly extend a charged-call trajectory."""

    _cells: set[str] = field(default_factory=set)
    trajectory: list[CoveragePoint] = field(default_factory=list)

    @property
    def cells(self) -> frozenset[str]:
        return frozenset(self._cells)

    def observe(
        self,
        property_: SafetyProperty,
        counterfactual: Counterfactual,
        source_decision: Decision,
        follow_up_decision: Decision,
        *,
        charged_target_calls: int,
    ) -> CoverageSnapshot:
        if charged_target_calls < 0:
            raise ValueError("charged_target_calls must be nonnegative")
        for scenario in (counterfactual.source, counterfactual.follow_up):
            self._cells.update(
                {
                    f"factor:road_type:{scenario.road_type}",
                    f"factor:signal:{scenario.signal}",
                    f"factor:surface:{scenario.surface}",
                    f"factor:visibility:{scenario.visibility}",
                    "factor:speed_band:"
                    + _speed_band(scenario.speed_mph, scenario.speed_limit_mph),
                }
            )
        result = evaluate_property(property_, counterfactual, source_decision, follow_up_decision)
        applicability = "applicable" if result.applicable else "not_applicable"
        predicate = (
            "not_evaluated"
            if not result.applicable
            else ("violated" if result.violated else "satisfied")
        )
        self._cells.update(
            {
                f"relation:{counterfactual.relation_id}",
                f"applicability:{property_.property_id}:{applicability}",
                f"predicate:{property_.property_id}:{predicate}",
                f"action_transition:{source_decision.action}->{follow_up_decision.action}",
                f"risk_transition:{source_decision.risk}->{follow_up_decision.risk}",
            }
        )
        return self._append(charged_target_calls)

    def extend_constant_to(self, charged_target_calls: int) -> CoverageSnapshot:
        """Append no-new-cell points for excluded minimization calls on the charged-call axis."""
        if charged_target_calls < 0:
            raise ValueError("charged_target_calls must be nonnegative")
        start = self.trajectory[-1].charged_target_calls if self.trajectory else 0
        for point in range(start + 1, charged_target_calls + 1):
            self._append(point)
        return CoverageSnapshot(self.cells, charged_target_calls)

    def _append(self, charged_target_calls: int) -> CoverageSnapshot:
        self.trajectory.append(CoveragePoint(charged_target_calls, len(self._cells)))
        return CoverageSnapshot(self.cells, charged_target_calls)


def _speed_band(speed_mph: float, speed_limit_mph: float) -> str:
    if speed_mph > speed_limit_mph:
        return "over_limit"
    if speed_mph < 25:
        return "slow"
    if speed_mph <= 45:
        return "moderate"
    return "fast"
