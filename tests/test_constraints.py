from __future__ import annotations

from edgecase_atlas.constraints import assert_valid_scenario, validate_scenario
from edgecase_atlas.models import Actor, Provenance, Scenario


def unchecked_scenario(**changes: object) -> Scenario:
    values: dict[str, object] = {
        "schema_version": "av-text-v1",
        "scenario_id": "unchecked",
        "seed": 1,
        "road_type": "intersection",
        "speed_mph": 20.0,
        "speed_limit_mph": 30.0,
        "signal": "green",
        "surface": "dry",
        "visibility": "clear",
        "actors": (),
        "description": "Synthetic constraint test.",
        "provenance": Provenance(
            source_kind="synthetic", source_reference="test", license="CC BY 4.0"
        ),
    }
    values.update(changes)
    return Scenario.model_construct(**values)


def test_constraints_accept_valid_scenario() -> None:
    result = validate_scenario(unchecked_scenario())
    assert result.valid
    assert result.violations == ()
    assert_valid_scenario(unchecked_scenario())


def test_constraints_return_machine_readable_speed_and_signal_violations() -> None:
    scenario = unchecked_scenario(
        speed_mph=-1.0,
        speed_limit_mph=0.0,
        road_type="highway",
        signal="red",
    )
    result = validate_scenario(scenario)

    assert not result.valid
    assert {issue.code for issue in result.violations} == {
        "speed.nonnegative",
        "speed_limit.positive",
        "signal.road_incompatible",
    }
    assert all(issue.path for issue in result.violations)


def test_constraints_detect_actor_distance_and_state_type_mismatches() -> None:
    actor = Actor.model_construct(
        actor_id="car-1",
        actor_type="vehicle",
        relevance="relevant",
        pedestrian_state="crossing",
        lane_relation="ego_lane",
        distance_m=-0.5,
        event_metadata={},
    )
    result = validate_scenario(unchecked_scenario(actors=(actor,)))

    assert {issue.code for issue in result.violations} == {
        "actor.distance_nonnegative",
        "actor.pedestrian_state_incompatible",
    }
