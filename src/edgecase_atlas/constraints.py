"""Z3-backed validity checks for cross-field scenario constraints."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from z3 import Implies, Int, Or, Real, RealVal, Solver, sat  # type: ignore[import-untyped]

from edgecase_atlas.models import ActorType, RoadType, Scenario, Signal

_ROAD_CODES: dict[RoadType, int] = {
    "residential": 0,
    "urban": 1,
    "highway": 2,
    "intersection": 3,
}
_SIGNAL_CODES: dict[Signal, int] = {"none": 0, "red": 1, "yellow": 2, "green": 3}
_ACTOR_TYPE_CODES: dict[ActorType, int] = {
    "pedestrian": 0,
    "vehicle": 1,
    "cyclist": 2,
    "hazard": 3,
}
_PEDESTRIAN_STATE_CODES = {
    None: 0,
    "standing": 1,
    "crossing": 2,
    "on_sidewalk": 3,
    "running_toward_road": 4,
}


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


def _predicate_holds(solver: Solver, predicate: object) -> bool:
    solver.push()
    solver.add(predicate)
    result = bool(solver.check() == sat)
    solver.pop()
    return result


def validate_scenario(scenario: Scenario) -> ConstraintResult:
    """Evaluate every documented semantic predicate with one Z3 scenario model.

    Overspeed is intentionally valid. The speed-limit relation constrains only nonnegative speed
    and a positive legal limit because overspeed is an input to a starter property.
    """
    violations: list[ConstraintViolation] = []
    solver = Solver()
    speed = Real("speed_mph")
    speed_limit = Real("speed_limit_mph")
    road_type = Int("road_type")
    signal = Int("signal")

    if isfinite(scenario.speed_mph):
        solver.add(speed == RealVal(str(scenario.speed_mph)))
    else:
        violations.append(
            ConstraintViolation(
                "speed.nonnegative", "speed_mph", "speed_mph must be finite and nonnegative"
            )
        )
    if isfinite(scenario.speed_limit_mph):
        solver.add(speed_limit == RealVal(str(scenario.speed_limit_mph)))
    else:
        violations.append(
            ConstraintViolation(
                "speed_limit.positive",
                "speed_limit_mph",
                "speed_limit_mph must be finite and positive",
            )
        )
    solver.add(road_type == _ROAD_CODES[scenario.road_type])
    solver.add(signal == _SIGNAL_CODES[scenario.signal])

    predicates: list[tuple[str, str, str, object]] = [
        ("speed.nonnegative", "speed_mph", "speed_mph must be finite and nonnegative", speed >= 0),
        (
            "speed_limit.positive",
            "speed_limit_mph",
            "speed_limit_mph must be finite and positive",
            speed_limit > 0,
        ),
        (
            "signal.road_incompatible",
            "signal",
            "A colored signal requires an intersection or urban road type",
            Implies(
                signal != _SIGNAL_CODES["none"],
                Or(road_type == _ROAD_CODES["intersection"], road_type == _ROAD_CODES["urban"]),
            ),
        ),
    ]
    for index, actor in enumerate(scenario.actors):
        distance = Real(f"actor_distance_{index}")
        actor_type = Int(f"actor_type_{index}")
        pedestrian_state = Int(f"pedestrian_state_{index}")
        if isfinite(actor.distance_m):
            solver.add(distance == RealVal(str(actor.distance_m)))
        else:
            violations.append(
                ConstraintViolation(
                    "actor.distance_nonnegative",
                    f"actors.{index}.distance_m",
                    "Actor distance must be finite and nonnegative",
                )
            )
        solver.add(actor_type == _ACTOR_TYPE_CODES[actor.actor_type])
        solver.add(pedestrian_state == _PEDESTRIAN_STATE_CODES[actor.pedestrian_state])
        predicates.extend(
            (
                (
                    "actor.distance_nonnegative",
                    f"actors.{index}.distance_m",
                    "Actor distance must be finite and nonnegative",
                    distance >= 0,
                ),
                (
                    "actor.pedestrian_state_incompatible",
                    f"actors.{index}.pedestrian_state",
                    "A pedestrian state can only be assigned to a pedestrian actor",
                    Implies(pedestrian_state != 0, actor_type == _ACTOR_TYPE_CODES["pedestrian"]),
                ),
            )
        )
    for code, path, message, predicate in predicates:
        if not _predicate_holds(solver, predicate):
            violation = ConstraintViolation(code, path, message)
            if violation not in violations:
                violations.append(violation)
    return ConstraintResult(tuple(violations))


def assert_valid_scenario(scenario: Scenario) -> None:
    """Raise a typed exception if a scenario fails semantic validation."""
    result = validate_scenario(scenario)
    if not result.valid:
        raise ScenarioConstraintError(result)
