from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from edgecase_atlas.fixtures import FaultyDemonstrationAgent, known_violation_cases
from edgecase_atlas.models import (
    Actor,
    Counterfactual,
    Decision,
    FailureCertificate,
    FieldChange,
    Provenance,
    Scenario,
    canonical_scenario_diffs,
)
from edgecase_atlas.properties import (
    STARTER_PROPERTY_PACK,
    action_becomes_more_aggressive,
    evaluate_property,
)


def scenario(**changes: object) -> Scenario:
    values: dict[str, object] = {
        "scenario_id": "review-source",
        "seed": 11,
        "road_type": "intersection",
        "speed_mph": 20.0,
        "speed_limit_mph": 35.0,
        "signal": "green",
        "surface": "dry",
        "visibility": "clear",
        "actors": (),
        "description": "A synthetic review scenario.",
        "provenance": Provenance(
            source_kind="synthetic",
            source_reference="edgecase-atlas-review",
            license="CC BY 4.0",
        ),
    }
    values.update(changes)
    return Scenario(**values)


def relation(source: Scenario, follow_up: Scenario, relation_id: str = "review") -> Counterfactual:
    return Counterfactual(
        source=source,
        follow_up=follow_up,
        changed_fields=canonical_scenario_diffs(source, follow_up),
        relation_id=relation_id,
    )


def decision(action: str, risk: str = "medium") -> Decision:
    return Decision(action=action, risk=risk, explanation="Synthetic regression decision.")  # type: ignore[arg-type]


def property_by_id(property_id: str):
    return next(item for item in STARTER_PROPERTY_PACK if item.property_id == property_id)


@pytest.mark.parametrize("red_on_source", [True, False])
def test_red_oracle_only_checks_the_red_member(red_on_source: bool) -> None:
    red = scenario(scenario_id="red", signal="red")
    green = scenario(scenario_id="green", signal="green")
    pair = relation(red, green) if red_on_source else relation(green, red)
    red_decision = decision("stop")
    green_decision = decision("proceed")
    source_decision, follow_up_decision = (
        (red_decision, green_decision) if red_on_source else (green_decision, red_decision)
    )

    result = evaluate_property(
        property_by_id("red_signal_no_proceed"), pair, source_decision, follow_up_decision
    )

    assert result.applicable
    assert not result.violated


@pytest.mark.parametrize("red_on_source", [True, False])
def test_red_oracle_detects_proceed_on_either_red_member(red_on_source: bool) -> None:
    red = scenario(scenario_id="red", signal="red")
    green = scenario(scenario_id="green", signal="green")
    pair = relation(red, green) if red_on_source else relation(green, red)
    source_decision, follow_up_decision = (
        (decision("proceed"), decision("stop"))
        if red_on_source
        else (decision("stop"), decision("proceed"))
    )

    assert evaluate_property(
        property_by_id("red_signal_no_proceed"), pair, source_decision, follow_up_decision
    ).violated


def test_non_applicable_property_has_distinct_reason() -> None:
    green = scenario()
    pair = relation(green, green.model_copy(update={"scenario_id": "green-follow-up"}))
    result = evaluate_property(
        property_by_id("red_signal_no_proceed"), pair, decision("proceed"), decision("proceed")
    )
    assert not result.applicable
    assert result.reason == "Not applicable"


def test_models_reject_coercion_and_unsupported_json_values() -> None:
    with pytest.raises(ValidationError):
        scenario(seed="11")
    with pytest.raises(ValidationError):
        scenario(speed_mph="20")
    with pytest.raises(ValidationError):
        FieldChange(path="x", from_value=object(), to_value="valid")


def test_all_public_models_round_trip_and_nested_metadata_is_immutable() -> None:
    actor = Actor(
        actor_id="pedestrian-1",
        actor_type="pedestrian",
        pedestrian_state="standing",
        distance_m=2.0,
        event_metadata=(("movement", "waiting"),),
    )
    source = scenario(actors=(actor,))
    follow_up = source.model_copy(update={"scenario_id": "review-follow-up", "speed_mph": 25.0})
    counterfactual = relation(source, follow_up)
    certificate = certificate_for(counterfactual)

    for model in (actor, source.provenance, source, counterfactual, certificate):
        assert type(model).model_validate_json(model.model_dump_json()) == model
    with pytest.raises(TypeError):
        actor.event_metadata[0] = ("movement", "moving")  # type: ignore[index]


def test_provenance_and_event_metadata_reject_contact_identity_and_location_data() -> None:
    with pytest.raises(ValidationError):
        Provenance(source_kind="synthetic", source_reference="name: someone", license="CC BY 4.0")
    with pytest.raises(ValidationError):
        Provenance(
            source_kind="synthetic",
            source_reference="edgecase-atlas",
            license="CC BY 4.0",
            transformation_history=("x" * 161,),
        )
    with pytest.raises(ValidationError):
        Actor(
            actor_id="a", actor_type="hazard", distance_m=1, event_metadata=(("phone", "555-0100"),)
        )


def test_counterfactual_rejects_missing_or_false_declared_differences() -> None:
    source = scenario()
    follow_up = source.model_copy(update={"scenario_id": "review-follow-up", "speed_mph": 30.0})
    with pytest.raises(ValidationError, match="canonical"):
        Counterfactual(
            source=source,
            follow_up=follow_up,
            changed_fields=(
                FieldChange(
                    path="scenario_id", from_value="review-source", to_value="review-follow-up"
                ),
            ),
            relation_id="speed-change",
        )
    with pytest.raises(ValidationError, match="canonical"):
        Counterfactual(
            source=source,
            follow_up=follow_up,
            changed_fields=(
                FieldChange(path="scenario_id", from_value="wrong", to_value="review-follow-up"),
                FieldChange(path="speed_mph", from_value=20.0, to_value=30.0),
            ),
            relation_id="speed-change",
        )


def test_canonical_diffs_include_all_retained_actor_differences() -> None:
    source = scenario(
        actors=(
            Actor(
                actor_id="pedestrian-1",
                actor_type="pedestrian",
                pedestrian_state="on_sidewalk",
                lane_relation="sidewalk",
                distance_m=5,
            ),
        )
    )
    follow_up = source.model_copy(
        update={
            "scenario_id": "review-follow-up",
            "actors": (
                source.actors[0].model_copy(
                    update={"pedestrian_state": "crossing", "lane_relation": "ego_lane"}
                ),
            ),
        }
    )
    paths = {change.path for change in canonical_scenario_diffs(source, follow_up)}
    assert {
        "scenario_id",
        "actors.pedestrian-1.pedestrian_state",
        "actors.pedestrian-1.lane_relation",
    } <= paths


def certificate_for(counterfactual: Counterfactual, **changes: object) -> FailureCertificate:
    values: dict[str, object] = {
        "certificate_id": "review-certificate",
        "relation_id": counterfactual.relation_id,
        "property_id": "red_signal_no_proceed",
        "source": counterfactual.source,
        "minimized_follow_up": counterfactual.follow_up,
        "changed_fields": counterfactual.changed_fields,
        "source_decisions": (decision("stop"),) * 5,
        "follow_up_decisions": (decision("proceed"),) * 5,
        "reproduction_count": 4,
        "reproduction_trials": 5,
        "model_id": "fixture",
        "model_config_hash": "a" * 64,
        "software_version": "0.1.0",
        "seed": 11,
        "latency_ms": 1,
        "estimated_cost_usd": 0.0,
        "replay_command": "atlas replay synthetic.json",
    }
    values.update(changes)
    return FailureCertificate(**values)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"reproduction_count": 6}, "reproduction_count"),
        ({"source_decisions": ()}, "source_decisions"),
        ({"follow_up_decisions": (decision("stop"),) * 4}, "reproduction_trials"),
    ],
)
def test_certificate_rejects_impossible_evidence(changes: dict[str, object], match: str) -> None:
    pair = known_violation_cases()[0].counterfactual
    with pytest.raises(ValidationError, match=match):
        certificate_for(pair, **changes)


def test_faulty_agent_is_the_source_of_every_known_property_violation() -> None:
    agent = FaultyDemonstrationAgent()
    for case in known_violation_cases():
        source_decision = asyncio.run(agent.decide(case.counterfactual.source, seed=1))
        follow_up_decision = asyncio.run(agent.decide(case.counterfactual.follow_up, seed=1))
        result = evaluate_property(
            case.property, case.counterfactual, source_decision, follow_up_decision
        )
        assert result.applicable
        assert result.violated


@pytest.mark.parametrize(
    ("source", "follow_up", "expected"),
    [
        ("stop", "stop", False),
        ("stop", "prepare_stop", True),
        ("stop", "reduce_speed", True),
        ("stop", "increase_gap", True),
        ("stop", "proceed", True),
        ("prepare_stop", "stop", False),
        ("prepare_stop", "prepare_stop", False),
        ("prepare_stop", "reduce_speed", True),
        ("prepare_stop", "increase_gap", True),
        ("prepare_stop", "proceed", True),
        ("reduce_speed", "stop", False),
        ("reduce_speed", "prepare_stop", False),
        ("reduce_speed", "reduce_speed", False),
        ("reduce_speed", "increase_gap", False),
        ("reduce_speed", "proceed", True),
        ("increase_gap", "stop", False),
        ("increase_gap", "prepare_stop", False),
        ("increase_gap", "reduce_speed", False),
        ("increase_gap", "increase_gap", False),
        ("increase_gap", "proceed", True),
        ("proceed", "stop", False),
        ("proceed", "prepare_stop", False),
        ("proceed", "reduce_speed", False),
        ("proceed", "increase_gap", False),
        ("proceed", "proceed", False),
    ],
)
def test_action_aggression_uses_a_documented_partial_order(
    source: str, follow_up: str, expected: bool
) -> None:
    assert action_becomes_more_aggressive(source, follow_up) is expected  # type: ignore[arg-type]
