"""Z3-backed validity checks for cross-field scenario constraints."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from z3 import Real, RealVal, Solver, sat  # type: ignore[import-untyped]

from edgecase_atlas.models import Scenario


@dataclass(frozen=True, slots=True)
class ConstraintViolation:
    """A stable, machine-readable validity failure."""

    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ConstraintResult:
    """Outcome of checking every cross-field validity rule."""

    violations: tuple[ConstraintViolation, ...]

    @property
    def valid(self) -> bool:
        return not self.violations


class ScenarioConstraintError(ValueError):
    """Raised when a scenario is invalid for generation or minimization."""

    def __init__(self, result: ConstraintResult) -> None:
        self.result = result
        super().__init__("; ".join(issue.code for issue in result.violations))


def _satisfies(*conditions: object) -> bool:
    solver = Solver()
    solver.add(*conditions)
    return bool(solver.check() == sat)


def validate_scenario(scenario: Scenario) -> ConstraintResult:
    """Validate semantic constraints, including ones Pydantic guards at input boundaries."""
    violations: list[ConstraintViolation] = []
    speed = Real("speed")
    speed_limit = Real("speed_limit")
    if not isfinite(scenario.speed_mph) or not _satisfies(
        speed == RealVal(str(scenario.speed_mph)), speed >= 0
    ):
        violations.append(
            ConstraintViolation(
                "speed.nonnegative", "speed_mph", "speed_mph must be finite and nonnegative"
            )
        )
    if not isfinite(scenario.speed_limit_mph) or not _satisfies(
        speed_limit == RealVal(str(scenario.speed_limit_mph)), speed_limit > 0
    ):
        violations.append(
            ConstraintViolation(
                "speed_limit.positive",
                "speed_limit_mph",
                "speed_limit_mph must be finite and positive",
            )
        )
    if scenario.signal != "none" and scenario.road_type not in {"intersection", "urban"}:
        violations.append(
            ConstraintViolation(
                "signal.road_incompatible",
                "signal",
                "A colored signal requires an intersection or urban road type",
            )
        )
    for index, actor in enumerate(scenario.actors):
        distance = Real(f"distance_{index}")
        if not isfinite(actor.distance_m) or not _satisfies(
            distance == RealVal(str(actor.distance_m)), distance >= 0
        ):
            violations.append(
                ConstraintViolation(
                    "actor.distance_nonnegative",
                    f"actors.{index}.distance_m",
                    "Actor distance must be finite and nonnegative",
                )
            )
        if actor.pedestrian_state is not None and actor.actor_type != "pedestrian":
            violations.append(
                ConstraintViolation(
                    "actor.pedestrian_state_incompatible",
                    f"actors.{index}.pedestrian_state",
                    "A pedestrian state can only be assigned to a pedestrian actor",
                )
            )
    return ConstraintResult(tuple(violations))


def assert_valid_scenario(scenario: Scenario) -> None:
    """Raise a typed exception if a scenario fails semantic validation."""
    result = validate_scenario(scenario)
    if not result.valid:
        raise ScenarioConstraintError(result)
