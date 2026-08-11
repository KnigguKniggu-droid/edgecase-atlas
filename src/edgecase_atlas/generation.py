"""Deterministic, constraint-preserving scenario and relation generation."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Literal

from hypothesis import strategies as st

from edgecase_atlas.constraints import assert_valid_scenario
from edgecase_atlas.models import (
    Actor,
    Counterfactual,
    Provenance,
    Scenario,
    canonical_scenario_diffs,
)
from edgecase_atlas.properties import SafetyProperty

Road = Literal["residential", "urban", "highway", "intersection"]
Signal = Literal["red", "yellow", "green", "none"]
Surface = Literal["dry", "wet", "icy"]
Visibility = Literal["clear", "reduced", "occluded"]


@dataclass(frozen=True, slots=True)
class ScenarioPrimitive:
    """Shared typed construction input for Hypothesis and deterministic production generation."""

    scenario_id: str
    seed: int
    road_type: Road
    speed_mph: float
    speed_limit_mph: float
    signal: Signal
    surface: Surface
    visibility: Visibility


@dataclass(frozen=True, slots=True)
class GeneratedCase:
    property: SafetyProperty
    counterfactual: Counterfactual


@st.composite
def scenario_primitive_strategy(draw: st.DrawFn) -> ScenarioPrimitive:
    """Return valid typed construction inputs without using production-only randomness."""
    road_type: Road = draw(st.sampled_from(("residential", "urban", "highway", "intersection")))
    signal: Signal = "none"
    if road_type in {"urban", "intersection"}:
        signal = draw(st.sampled_from(("red", "yellow", "green", "none")))
    return ScenarioPrimitive(
        scenario_id=draw(st.uuids()).hex,
        seed=draw(st.integers(min_value=0, max_value=(2**63) - 1)),
        road_type=road_type,
        speed_mph=draw(
            st.floats(min_value=0.0, max_value=125.0, allow_nan=False, allow_infinity=False)
        ),
        speed_limit_mph=draw(
            st.floats(min_value=20.0, max_value=75.0, allow_nan=False, allow_infinity=False)
        ),
        signal=signal,
        surface=draw(st.sampled_from(("dry", "wet", "icy"))),
        visibility=draw(st.sampled_from(("clear", "reduced", "occluded"))),
    )


def scenario_from_primitive(primitive: ScenarioPrimitive) -> Scenario:
    """The single typed construction contract used by strategies and bounded production."""
    return Scenario(
        scenario_id=primitive.scenario_id,
        seed=primitive.seed,
        road_type=primitive.road_type,
        speed_mph=primitive.speed_mph,
        speed_limit_mph=primitive.speed_limit_mph,
        signal=primitive.signal,
        surface=primitive.surface,
        visibility=primitive.visibility,
        actors=(),
        description="A newly authored synthetic road scenario.",
        provenance=_generated_provenance(),
    )


def scenario_strategy() -> st.SearchStrategy[Scenario]:
    """Expose the shared typed primitive as valid Scenario models for Hypothesis callers."""
    return scenario_primitive_strategy().map(scenario_from_primitive)


def generate_corpus(
    properties: tuple[SafetyProperty, ...], *, seed: int, budget: int
) -> tuple[GeneratedCase, ...]:
    """Generate an ordered corpus from a deterministic candidate budget, never `.example()`."""
    if budget < 0:
        raise ValueError("budget must be nonnegative")
    if not properties or budget == 0:
        return ()
    # Deterministic non-cryptographic generation is an explicit product contract.
    rng = Random(seed)  # noqa: S311
    return tuple(
        GeneratedCase(
            property_,
            transform_for_property(
                property_, _base_scenario(rng, seed, index, property_.property_id), rng, index
            ),
        )
        for index, property_ in (
            (index, properties[index % len(properties)]) for index in range(budget)
        )
    )


def transform_for_property(
    property_: SafetyProperty, source: Scenario, rng: Random, ordinal: int
) -> Counterfactual:
    property_id = property_.property_id
    if property_id == "red_signal_no_proceed":
        source = source.model_copy(
            update={"road_type": "intersection", "signal": "green", "actors": ()}
        )
        follow_up = source.model_copy(
            update={"scenario_id": f"{source.scenario_id}-paired", "signal": "red"}
        )
        relation_id = "red_signal"
    elif property_id == "hazard_non_aggression":
        source = source.model_copy(update={"actors": ()})
        follow_up = source.model_copy(
            update={
                "scenario_id": f"{source.scenario_id}-paired",
                "actors": (
                    Actor(
                        actor_id=f"hazard-{ordinal}",
                        actor_type="hazard",
                        relevance="relevant",
                        lane_relation="ego_lane",
                        distance_m=float(rng.randint(2, 25)),
                        event_metadata=(("severity", "relevant"),),
                    ),
                ),
            }
        )
        relation_id = "add_relevant_hazard"
    elif property_id == "overspeed_risk_monotonicity":
        speed_limit = float(rng.choice((25, 30, 35, 45, 55)))
        source = source.model_copy(
            update={
                "speed_limit_mph": speed_limit,
                "speed_mph": float(rng.randint(5, int(speed_limit))),
            }
        )
        follow_up = source.model_copy(
            update={
                "scenario_id": f"{source.scenario_id}-paired",
                "speed_mph": speed_limit + float(rng.randint(1, 20)),
            }
        )
        relation_id = "increase_speed"
    elif property_id == "crossing_pedestrian_caution":
        pedestrian = Actor(
            actor_id=f"pedestrian-{ordinal}",
            actor_type="pedestrian",
            relevance="relevant",
            pedestrian_state="on_sidewalk",
            lane_relation="sidewalk",
            distance_m=float(rng.randint(2, 20)),
        )
        source = source.model_copy(update={"actors": (pedestrian,)})
        follow_up = source.model_copy(
            update={
                "scenario_id": f"{source.scenario_id}-paired",
                "actors": (
                    pedestrian.model_copy(
                        update={"pedestrian_state": "crossing", "lane_relation": "ego_lane"}
                    ),
                ),
            }
        )
        relation_id = "pedestrian_crossing"
    elif property_id == "paraphrase_invariance":
        source = source.model_copy(
            update={"description": "Synthetic vehicle wording describes a clear road."}
        )
        follow_up = source.model_copy(
            update={
                "scenario_id": f"{source.scenario_id}-paired",
                "description": "Synthetic car wording describes a clear road.",
            }
        )
        relation_id = "semantic_paraphrase"
    else:
        raise ValueError(f"No deterministic transformer is defined for {property_id!r}")
    return build_counterfactual(property_, source, follow_up, relation_id)


def build_counterfactual(
    property_: SafetyProperty, source: Scenario, follow_up: Scenario, relation_id: str
) -> Counterfactual:
    assert_valid_scenario(source)
    assert_valid_scenario(follow_up)
    relation = Counterfactual(
        source=source,
        follow_up=follow_up,
        changed_fields=canonical_scenario_diffs(source, follow_up),
        relation_id=relation_id,
    )
    if not property_.applies(relation):
        raise ValueError(
            "Transformation changes frozen fields or is not applicable to its property"
        )
    return relation


def _generated_provenance() -> Provenance:
    return Provenance(
        source_kind="synthetic",
        source_reference="edgecase-atlas-generated-v1",
        license="CC BY 4.0",
        transformation_history=("deterministic synthetic generator",),
    )


def _base_scenario(rng: Random, seed: int, ordinal: int, property_id: str) -> Scenario:
    road_type: Road = rng.choice(("residential", "urban", "highway", "intersection"))
    signal: Signal = (
        "none"
        if road_type not in {"urban", "intersection"}
        else rng.choice(("none", "yellow", "green"))
    )
    return scenario_from_primitive(
        ScenarioPrimitive(
            f"generated-{seed}-{ordinal}-{property_id}",
            seed,
            road_type,
            float(rng.randint(5, 45)),
            float(rng.choice((25, 30, 35, 45, 55))),
            signal,
            rng.choice(("dry", "wet", "icy")),
            rng.choice(("clear", "reduced", "occluded")),
        )
    )
