from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from edgecase_atlas.models import (
    Actor,
    Decision,
    FieldChange,
    Provenance,
    Scenario,
)


def make_scenario(**changes: object) -> Scenario:
    values: dict[str, object] = {
        "scenario_id": "synthetic-round-trip",
        "seed": 42,
        "road_type": "intersection",
        "speed_mph": 25.0,
        "speed_limit_mph": 35.0,
        "signal": "green",
        "surface": "dry",
        "visibility": "clear",
        "actors": (
            Actor(
                actor_id="ped-1",
                actor_type="pedestrian",
                relevance="relevant",
                pedestrian_state="on_sidewalk",
                lane_relation="sidewalk",
                distance_m=12.5,
            ),
        ),
        "description": "A synthetic intersection scenario.",
        "provenance": Provenance(
            source_kind="synthetic",
            source_reference="edgecase-atlas-fixture",
            license="CC BY 4.0",
            transformation_history=("authored",),
        ),
    }
    values.update(changes)
    return Scenario(**values)


def test_scenario_json_round_trip_is_stable_and_frozen() -> None:
    scenario = make_scenario()
    restored = Scenario.model_validate_json(scenario.model_dump_json())

    assert restored == scenario
    assert isinstance(scenario.actors, tuple)
    with pytest.raises(ValidationError):
        scenario.speed_mph = 12.0  # type: ignore[misc]


@pytest.mark.parametrize("speed", [-0.1, math.inf, math.nan])
def test_scenario_rejects_non_finite_or_negative_speed(speed: float) -> None:
    with pytest.raises(ValidationError):
        make_scenario(speed_mph=speed)


def test_scenario_rejects_duplicate_actor_ids() -> None:
    first = Actor(actor_id="same", actor_type="vehicle", distance_m=4)
    second = Actor(actor_id="same", actor_type="cyclist", distance_m=8)

    with pytest.raises(ValidationError, match="unique"):
        make_scenario(actors=(first, second))


def test_actor_rejects_incompatible_pedestrian_state() -> None:
    with pytest.raises(ValidationError, match="pedestrian_state"):
        Actor(
            actor_id="vehicle-1",
            actor_type="vehicle",
            pedestrian_state="crossing",
            distance_m=2,
        )


def test_provenance_rejects_personal_email() -> None:
    with pytest.raises(ValidationError, match="email"):
        Provenance(
            source_kind="synthetic",
            source_reference="contact someone@example.com",
            license="CC BY 4.0",
        )


def test_decision_confidence_is_bounded() -> None:
    assert (
        Decision(action="stop", risk="high", explanation="Synthetic test.", confidence=1).confidence
        == 1
    )
    with pytest.raises(ValidationError):
        Decision(action="stop", risk="high", explanation="Synthetic test.", confidence=1.01)


def test_field_change_is_frozen_and_serializable() -> None:
    change = FieldChange(path="speed_mph", from_value=20.0, to_value=45.0)
    assert FieldChange.model_validate_json(change.model_dump_json()) == change
    with pytest.raises(ValidationError):
        change.path = "signal"  # type: ignore[misc]
