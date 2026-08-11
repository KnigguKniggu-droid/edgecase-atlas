"""Strict, immutable domain contracts for simulated driving scenarios."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

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


class AtlasModel(BaseModel):
    """Base model that rejects undeclared fields and freezes values."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Provenance(AtlasModel):
    """Minimal, non-identifying origin metadata for a scenario."""

    source_kind: SourceKind
    source_reference: str = Field(min_length=1, max_length=240)
    license: str = Field(min_length=1, max_length=120)
    transformation_history: tuple[str, ...] = Field(default_factory=tuple, max_length=32)

    @field_validator("source_reference", "license", "transformation_history")
    @classmethod
    def reject_personal_data(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        values = (value,) if isinstance(value, str) else value
        for item in values:
            if "@" in item:
                raise ValueError("Provenance must not include email addresses or personal data")
        return value


class Actor(AtlasModel):
    """A structured road actor used only in synthetic text scenarios."""

    actor_id: str = Field(min_length=1, max_length=80)
    actor_type: ActorType
    relevance: ActorRelevance = "relevant"
    pedestrian_state: PedestrianState | None = None
    lane_relation: LaneRelation = "unknown"
    distance_m: float = Field(ge=0, le=10_000, allow_inf_nan=False)
    event_metadata: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("event_metadata")
    @classmethod
    def validate_event_metadata(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        if len(value) > 16:
            raise ValueError("event_metadata supports at most 16 entries")
        for key, item in value.items():
            if not key or len(key) > 64 or len(item) > 240 or "@" in item:
                raise ValueError("event_metadata must be compact and non-identifying")
        return dict(value)

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
    """One explicitly recorded source-to-follow-up difference."""

    path: str = Field(min_length=1, max_length=200)
    from_value: Any
    to_value: Any


class Counterfactual(AtlasModel):
    """An immutable paired scenario relation and required outcome constraints."""

    source: Scenario
    follow_up: Scenario
    changed_fields: tuple[FieldChange, ...] = Field(min_length=1, max_length=32)
    relation_id: str = Field(min_length=1, max_length=100)
    expected_actions: frozenset[Action] = Field(default_factory=frozenset)
    required_risk_floor: Risk | None = None


class FailureCertificate(AtlasModel):
    """Portable evidence that a paired safety-property failure reproduced."""

    certificate_id: str = Field(min_length=1, max_length=100)
    relation_id: str = Field(min_length=1, max_length=100)
    source: Scenario
    minimized_follow_up: Scenario
    changed_fields: tuple[FieldChange, ...]
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
    replay_command: str = Field(min_length=1, max_length=1000)
