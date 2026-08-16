"""Generate the deterministic, newly written 100-scenario synthetic seed pack."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from edgecase_atlas.models import (
    Actor,
    ActorType,
    LaneRelation,
    PedestrianState,
    Provenance,
    RoadType,
    Scenario,
    Signal,
    Surface,
    Visibility,
)

_ROADS: tuple[RoadType, ...] = ("residential", "urban", "highway", "intersection")
_SURFACES: tuple[Surface, ...] = ("dry", "wet", "icy")
_VISIBILITY: tuple[Visibility, ...] = ("clear", "reduced", "occluded")
_LIMITS = (20.0, 25.0, 30.0, 35.0, 45.0, 55.0, 65.0)


def generate_scenarios() -> tuple[Scenario, ...]:
    """Construct the fixed taxonomy without private or downloaded source material."""
    return tuple(_scenario(index) for index in range(100))


def _scenario(index: int) -> Scenario:
    road = _ROADS[index % len(_ROADS)]
    surface = _SURFACES[(index // len(_ROADS)) % len(_SURFACES)]
    visibility = _VISIBILITY[(index // (len(_ROADS) * len(_SURFACES))) % len(_VISIBILITY)]
    limit = _LIMITS[index % len(_LIMITS)]
    signal: Signal = "none"
    if road in {"urban", "intersection"}:
        signal = ("red", "yellow", "green", "none")[(index // 4) % 4]
    actors = _actors(index)
    return Scenario(
        scenario_id=f"synthetic-seed-{index + 1:03d}",
        seed=10_000 + index,
        road_type=road,
        speed_mph=max(5.0, limit + float((index % 5) - 2) * 5.0),
        speed_limit_mph=limit,
        signal=signal,
        surface=surface,
        visibility=visibility,
        actors=actors,
        description=(
            f"A newly written synthetic {road} scenario with {surface} surface and "
            f"{visibility} visibility."
        ),
        provenance=Provenance(
            source_kind="synthetic",
            source_reference=f"edgecase-atlas-synthetic-seed-{index + 1:03d}",
            license="CC BY 4.0",
            transformation_history=(
                "newly written deterministic seed taxonomy",
                f"taxonomy-stratum-{index % 20:02d}",
            ),
        ),
    )


def _actors(index: int) -> tuple[Actor, ...]:
    variant = index % 5
    if variant == 0:
        return ()
    if variant == 1:
        pedestrian_states: tuple[PedestrianState, ...] = (
            "standing",
            "crossing",
            "on_sidewalk",
            "running_toward_road",
        )
        pedestrian_state = pedestrian_states[(index // 5) % 4]
        lane: LaneRelation = "sidewalk" if pedestrian_state == "on_sidewalk" else "ego_lane"
        return (
            Actor(
                actor_id=f"pedestrian-{index + 1:03d}",
                actor_type="pedestrian",
                pedestrian_state=pedestrian_state,
                lane_relation=lane,
                distance_m=float(3 + index % 18),
            ),
        )
    actor_types: tuple[ActorType, ...] = ("hazard", "vehicle", "cyclist")
    actor_type = actor_types[variant - 2]
    return (
        Actor(
            actor_id=f"{actor_type}-{index + 1:03d}",
            actor_type=actor_type,
            lane_relation="ego_lane" if variant != 4 else "adjacent_lane",
            distance_m=float(5 + index % 40),
        ),
    )


def write_seed_pack(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = (
        json.dumps(
            scenario.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        for scenario in generate_scenarios()
    )
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "data" / "synthetic_seed_pack.jsonl",
    )
    args = parser.parse_args(argv)
    write_seed_pack(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
