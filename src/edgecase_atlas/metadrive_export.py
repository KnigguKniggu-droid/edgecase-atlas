"""Deterministic abstract exports for later MetaDrive scenario construction."""

from __future__ import annotations

from typing import Final

from edgecase_atlas.engine import recompute_certificate_id
from edgecase_atlas.models import FailureCertificate, Scenario

_MPS_PER_MPH: Final = 0.44704
_SUPPORTED_ROAD_TYPES: Final = {"residential", "urban", "highway", "intersection"}

ACTION_TO_CONTROLLER: Final = {
    "stop": {"target_speed_ratio": 0.0, "minimum_gap_seconds": None},
    "prepare_stop": {"target_speed_ratio": 0.5, "minimum_gap_seconds": None},
    "reduce_speed": {"target_speed_ratio": 0.7, "minimum_gap_seconds": None},
    "increase_gap": {"target_speed_ratio": 0.85, "minimum_gap_seconds": 3.0},
    "proceed": {"target_speed_ratio": 1.0, "minimum_gap_seconds": None},
}


def export_metadrive_abstract(certificate: FailureCertificate) -> dict[str, object]:
    """Map a verified certificate to a geometry-free, simulator-neutral bridge artifact."""
    canonical_replay = f"atlas replay certificates/{certificate.certificate_id}.json"
    if certificate.replay_command != canonical_replay:
        raise ValueError("Certificate replay command is not canonical")
    if recompute_certificate_id(certificate) != certificate.certificate_id:
        raise ValueError("Certificate content digest does not match its identifier")

    return {
        "schema_version": "edgecase-atlas-metadrive-abstract-v1",
        "status": "abstract_export_not_simulator_validation",
        "certificate_id": certificate.certificate_id,
        "relation_id": certificate.relation_id,
        "property_id": certificate.property_id,
        "paired_seeds": {
            "certificate": certificate.seed,
            "source_scenario": certificate.source.seed,
            "follow_up_scenario": certificate.minimized_follow_up.seed,
        },
        "scenarios": {
            "source": _scenario(certificate.source),
            "follow_up": _scenario(certificate.minimized_follow_up),
        },
        "action_to_controller_mapping": ACTION_TO_CONTROLLER,
        "limitations": [
            "No road geometry, lane coordinates, routes, dynamics, or traffic "
            "placement are inferred.",
            "Controller values are fixed abstract targets, not tuned MetaDrive control parameters.",
            "A separate reviewed scenario builder must supply geometry before simulator execution.",
        ],
    }


def _scenario(scenario: Scenario) -> dict[str, object]:
    if scenario.road_type not in _SUPPORTED_ROAD_TYPES:
        raise ValueError(f"Unsupported road_type abstraction: {scenario.road_type}")
    actors: list[dict[str, object]] = []
    for actor in scenario.actors:
        if actor.lane_relation == "unknown":
            raise ValueError(f"Actor {actor.actor_id} has unsupported unknown lane relation")
        actors.append(
            {
                "actor_id": actor.actor_id,
                "actor_type": actor.actor_type,
                "relevance": actor.relevance,
                "pedestrian_state": actor.pedestrian_state,
                "lane_relation": actor.lane_relation,
                "distance_m": actor.distance_m,
                "event_metadata": dict(actor.event_metadata),
            }
        )
    return {
        "scenario_id": scenario.scenario_id,
        "seed": scenario.seed,
        "road_type": scenario.road_type,
        "signal": scenario.signal,
        "surface": scenario.surface,
        "visibility": scenario.visibility,
        "ego_speed_mps": scenario.speed_mph * _MPS_PER_MPH,
        "speed_limit_mps": scenario.speed_limit_mph * _MPS_PER_MPH,
        "actors": actors,
    }
