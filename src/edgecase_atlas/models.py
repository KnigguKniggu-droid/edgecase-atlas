"""Strict, immutable domain contracts for simulated driving scenarios."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

type Action = Literal["stop", "prepare_stop", "reduce_speed", "increase_gap", "proceed"]
type Risk = Literal["low", "medium", "high", "critical"]
type ActorType = Literal["pedestrian", "vehicle", "cyclist", "hazard"]
type ActorRelevance = Literal["relevant", "background"]
type PedestrianState = Literal["standing", "crossing", "on_sidewalk", "running_toward_road"]
type LaneRelation = Literal[
    "ego_lane", "adjacent_lane", "oncoming_lane", "sidewalk", "off_road", "unknown"
]
type RoadType = Literal["residential", "urban", "highway", "intersection"]
type Signal = Literal["red", "yellow", "green", "none"]
type Surface = Literal["dry", "wet", "icy"]
type Visibility = Literal["clear", "reduced", "occluded"]
type SourceKind = Literal["synthetic", "public_record", "curated_sample"]
type JsonScalar = str | int | float | bool | None
type EventMetadataKey = Literal["movement", "intent", "state", "severity", "signal_phase", "source"]

_STARTER_PROPERTY_RELATIONS = {
    "red_signal_no_proceed": "red_signal",
    "hazard_non_aggression": "add_relevant_hazard",
    "overspeed_risk_monotonicity": "increase_speed",
    "crossing_pedestrian_caution": "pedestrian_crossing",
    "paraphrase_invariance": "semantic_paraphrase",
}

_PERSONAL_DATA_MARKERS = (
    "@",
    "name:",
    "email",
    "phone",
    "contact",
    "address",
    "latitude",
    "longitude",
    "location",
    "gps",
    "coordinate",
)
_PHONE_PATTERN = re.compile(r"(?:\+?\d[\d .()-]{6,}\d)")


class AtlasModel(BaseModel):
    """Base model that rejects undeclared fields, coercion, and attribute reassignment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, str_strip_whitespace=True)


class Provenance(AtlasModel):
    """Minimal, non-identifying origin metadata for a scenario.

    This structural guard rejects common contact, identity, and precise-location markers. It is not
    a complete detector for every possible personal identifier, so public datasets need a separate
    provenance and privacy review before inclusion.
    """

    source_kind: SourceKind
    source_reference: str = Field(min_length=1, max_length=240)
    license: str = Field(min_length=1, max_length=120)
    transformation_history: tuple[str, ...] = Field(default_factory=tuple, max_length=32)

    @field_validator("source_reference", "license")
    @classmethod
    def reject_personal_data(cls, value: str) -> str:
        cls._validate_non_identifying_text((value,))
        return value

    @field_validator("source_reference")
    @classmethod
    def validate_source_reference(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._:/-]{0,239}", value.casefold()):
            raise ValueError("source_reference must be a documented non-identifying identifier")
        return value

    @field_validator("transformation_history")
    @classmethod
    def validate_transformation_history(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(len(item) > 160 for item in value):
            raise ValueError("Each transformation history item must contain at most 160 characters")
        cls._validate_non_identifying_text(value)
        return value

    @staticmethod
    def _validate_non_identifying_text(values: Iterable[str]) -> None:
        for item in values:
            lowered = item.casefold()
            if any(marker in lowered for marker in _PERSONAL_DATA_MARKERS) or _PHONE_PATTERN.search(
                item
            ):
                raise ValueError(
                    "Provenance prohibits email, contact, identity, and precise-location data"
                )


class Actor(AtlasModel):
    """A structured road actor used only in synthetic text scenarios."""

    actor_id: str = Field(min_length=1, max_length=80)
    actor_type: ActorType
    relevance: ActorRelevance = "relevant"
    pedestrian_state: PedestrianState | None = None
    lane_relation: LaneRelation = "unknown"
    distance_m: float = Field(ge=0, le=10_000, allow_inf_nan=False)
    event_metadata: tuple[tuple[EventMetadataKey, str], ...] = Field(
        default_factory=tuple, max_length=16
    )

    @field_validator("event_metadata")
    @classmethod
    def validate_event_metadata(
        cls, value: tuple[tuple[EventMetadataKey, str], ...]
    ) -> tuple[tuple[EventMetadataKey, str], ...]:
        keys = [key for key, _ in value]
        if len(keys) != len(set(keys)):
            raise ValueError("event_metadata keys must be unique")
        for _key, item in value:
            if (
                len(item) > 240
                or any(marker in item.casefold() for marker in _PERSONAL_DATA_MARKERS)
                or _PHONE_PATTERN.search(item)
            ):
                raise ValueError("event_metadata only supports non-identifying event values")
        return value

    @model_validator(mode="after")
    def validate_type_state_compatibility(self) -> Actor:
        if self.actor_type != "pedestrian" and self.pedestrian_state is not None:
            raise ValueError("pedestrian_state is only valid for pedestrian actors")
        return self


class Scenario(AtlasModel):
    """Versioned AV-text-v1 scenario contract."""

    schema_version: Literal["av-text-v1"] = "av-text-v1"
    scenario_id: str = Field(min_length=1, max_length=100)
    seed: int = Field(ge=0, le=2**63 - 1)
    road_type: RoadType
    speed_mph: float = Field(ge=0, le=250, allow_inf_nan=False)
    speed_limit_mph: float = Field(gt=0, le=150, allow_inf_nan=False)
    signal: Signal
    surface: Surface
    visibility: Visibility
    actors: tuple[Actor, ...] = Field(default_factory=tuple, max_length=64)
    description: str = Field(min_length=1, max_length=1000)
    provenance: Provenance

    @model_validator(mode="after")
    def validate_actor_ids(self) -> Scenario:
        actor_ids = [actor.actor_id for actor in self.actors]
        if len(actor_ids) != len(set(actor_ids)):
            raise ValueError("Actor IDs must be unique within a scenario")
        return self


class Decision(AtlasModel):
    """Validated agent response independent of a particular model provider."""

    action: Action
    risk: Risk
    explanation: str = Field(min_length=1, max_length=2000)
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)


class FieldChange(AtlasModel):
    """One declared, canonical, retained difference, not a causal attribution."""

    path: str = Field(min_length=1, max_length=200)
    from_value: JsonScalar
    to_value: JsonScalar


class Counterfactual(AtlasModel):
    """An immutable paired relation with every declared retained difference recorded."""

    source: Scenario
    follow_up: Scenario
    changed_fields: tuple[FieldChange, ...] = Field(min_length=1, max_length=128)
    relation_id: str = Field(min_length=1, max_length=100)
    expected_actions: frozenset[Action] = Field(default_factory=frozenset)
    required_risk_floor: Risk | None = None

    @model_validator(mode="after")
    def validate_declared_differences(self) -> Counterfactual:
        canonical_differences = canonical_scenario_diffs(self.source, self.follow_up)
        if self.changed_fields != canonical_differences:
            raise ValueError(
                "changed_fields must equal the canonical declared retained differences"
            )
        return self


class FailureCertificate(AtlasModel):
    """Portable evidence that an operational property violation reproduced.

    Historical provenance beyond structural consistency is an engine responsibility.
    """

    certificate_id: str = Field(min_length=1, max_length=100)
    relation_id: str = Field(min_length=1, max_length=100)
    property_id: str = Field(min_length=1, max_length=100)
    source: Scenario
    minimized_follow_up: Scenario
    changed_fields: tuple[FieldChange, ...] = Field(min_length=1, max_length=128)
    source_decisions: tuple[Decision, ...]
    follow_up_decisions: tuple[Decision, ...]
    reproduction_count: int = Field(ge=0)
    reproduction_trials: int = Field(gt=0)
    model_id: str = Field(min_length=1, max_length=200)
    model_config_hash: str = Field(min_length=1, max_length=128)
    software_version: str = Field(min_length=1, max_length=64)
    seed: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0, allow_inf_nan=False)
    cost_estimate_available: bool = False
    property_semantics_digest: str = Field(default="unknown", min_length=1, max_length=128)
    engine_config_hash: str = Field(default="unknown", min_length=1, max_length=128)
    reducer_label: str = Field(default="unreduced", min_length=1, max_length=200)
    reducer_vocabulary: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    terminal_audit_complete: bool = False
    replay_command: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_reproduction_evidence(self) -> FailureCertificate:
        if self.changed_fields != canonical_scenario_diffs(self.source, self.minimized_follow_up):
            raise ValueError(
                "changed_fields must equal canonical_scenario_diffs(source, minimized_follow_up)"
            )
        expected_relation = _STARTER_PROPERTY_RELATIONS.get(self.property_id)
        if expected_relation is not None and self.relation_id != expected_relation:
            raise ValueError("relation_id must match the starter property relation")
        if self.reproduction_count > self.reproduction_trials:
            raise ValueError("reproduction_count cannot exceed reproduction_trials")
        if len(self.source_decisions) != self.reproduction_trials:
            raise ValueError("source_decisions length must equal reproduction_trials")
        if len(self.follow_up_decisions) != self.reproduction_trials:
            raise ValueError("follow_up_decisions length must equal reproduction_trials")
        if not self.cost_estimate_available and self.estimated_cost_usd != 0:
            raise ValueError("Unknown cost estimates must serialize as unavailable and zero-valued")
        return self


def canonical_scenario_diffs(source: Scenario, follow_up: Scenario) -> tuple[FieldChange, ...]:
    """Return all actual retained scalar differences in stable path order.

    Scenario identifiers and descriptions are retained differences when they change. This function
    does not interpret any difference as causal.
    """
    differences: list[FieldChange] = []
    scalar_fields = (
        "schema_version",
        "scenario_id",
        "seed",
        "road_type",
        "speed_mph",
        "speed_limit_mph",
        "signal",
        "surface",
        "visibility",
        "description",
        "provenance",
    )
    for field_name in scalar_fields:
        source_value = getattr(source, field_name)
        follow_up_value = getattr(follow_up, field_name)
        if source_value != follow_up_value:
            differences.append(
                FieldChange(
                    path=field_name,
                    from_value=_canonical_scalar(source_value),
                    to_value=_canonical_scalar(follow_up_value),
                )
            )
    source_actors = {actor.actor_id: actor for actor in source.actors}
    follow_up_actors = {actor.actor_id: actor for actor in follow_up.actors}
    for actor_id in sorted(set(source_actors) | set(follow_up_actors)):
        differences.extend(
            _actor_diffs(actor_id, source_actors.get(actor_id), follow_up_actors.get(actor_id))
        )
    return tuple(sorted(differences, key=lambda difference: difference.path))


def _canonical_scalar(value: object) -> JsonScalar:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    if isinstance(value, tuple):
        return json.dumps(value, separators=(",", ":"))
    raise TypeError(f"Unsupported canonical scalar value: {type(value).__name__}")


def _actor_diffs(
    actor_id: str, source_actor: Actor | None, follow_up_actor: Actor | None
) -> tuple[FieldChange, ...]:
    differences: list[FieldChange] = []
    if source_actor is None or follow_up_actor is None:
        differences.append(
            FieldChange(
                path=f"actors.{actor_id}.present",
                from_value=source_actor is not None,
                to_value=follow_up_actor is not None,
            )
        )
    for field_name in (
        "actor_type",
        "relevance",
        "pedestrian_state",
        "lane_relation",
        "distance_m",
        "event_metadata",
    ):
        source_value = None if source_actor is None else getattr(source_actor, field_name)
        follow_up_value = None if follow_up_actor is None else getattr(follow_up_actor, field_name)
        if source_value != follow_up_value:
            differences.append(
                FieldChange(
                    path=f"actors.{actor_id}.{field_name}",
                    from_value=_canonical_scalar(source_value),
                    to_value=_canonical_scalar(follow_up_value),
                )
            )
    return tuple(differences)
