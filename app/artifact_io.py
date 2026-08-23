"""Strict, non-executing ingestion for public Atlas JSON and JSONL artifacts."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePath
from types import MappingProxyType
from typing import Literal, cast

from edgecase_atlas.engine import recompute_certificate_id
from edgecase_atlas.models import Decision, FailureCertificate, Scenario
from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.serialization import canonical_json, validate_run_document

MAX_ARTIFACT_BYTES = 2_000_000
MAX_JSONL_LINES = 10_000
MAX_JSON_DEPTH = 64
MAX_FIELD_CHARS = 10_000

_RUN_ID = re.compile(r"run-[0-9a-f]{16}")
_TRACE_SCHEMA = "atlas-trace-v1"
_EVENT_TYPES = ("run_started", "target_call", "certificate", "run_completed")
_JSON_MEDIA_TYPES = frozenset({"application/json"})
_JSONL_MEDIA_TYPES = frozenset(
    {"application/jsonl", "application/ndjson", "application/x-ndjson", "text/jsonl"}
)
_START_KEYS = frozenset({"schema_version", "event_type", "run_id", "metadata", "property_pack"})
_METADATA_KEYS = frozenset(
    {
        "run_id",
        "seed",
        "candidate_budget",
        "held_out_confirmation_seed_stream",
        "executed_seed_streams",
        "property_ids",
        "property_pack_digest",
        "engine_config_hash",
        "confirmation_note",
    }
)
_TARGET_KEYS = frozenset({"schema_version", "event_type", "run_id", "invocation"})
_INVOCATION_KEYS = frozenset(
    {
        "phase",
        "ordinal",
        "property_id",
        "relation_id",
        "pair_role",
        "scenario",
        "seed",
        "decision",
        "succeeded",
        "latency_ms",
        "estimated_cost_usd",
        "cost_estimate_available",
        "error_type",
    }
)
_CERTIFICATE_KEYS = frozenset(
    {
        "schema_version",
        "event_type",
        "run_id",
        "property",
        "certificate",
        "output_distribution",
        "minimization_evidence",
    }
)
_COMPLETED_KEYS = frozenset(
    {
        "schema_version",
        "event_type",
        "run_id",
        "target_calls_total",
        "certificate_count",
        "coverage_cell_count",
        "cost_estimate_available",
        "estimated_cost_usd",
    }
)
_PROPERTY_SNAPSHOTS = {
    item.property_id: {
        "property_id": item.property_id,
        "title": item.title,
        "description": item.description,
        "scope_note": item.scope_note,
    }
    for item in STARTER_PROPERTY_PACK
}


@dataclass(frozen=True, slots=True)
class TraceSummary:
    """Immutable, display-safe facts derived from a validated Atlas trace."""

    run_id: str
    event_counts: Mapping[str, int]
    target_call_count: int
    certificate_count: int
    completion_status: Literal["complete", "incomplete"]
    property_ids: tuple[str, ...]

    @property
    def completed(self) -> bool:
        """Return whether the canonical terminal event was present."""
        return self.completion_status == "complete"


type Artifact = Mapping[str, object] | TraceSummary


class _DuplicateKeyError(Exception):
    pass


class _NonFiniteNumberError(Exception):
    pass


def ingest_artifact(
    payload: bytes | bytearray | memoryview,
    *,
    filename: str,
    media_type: str | None = None,
) -> Artifact:
    """Dispatch a bounded upload by an allowlisted suffix and media type."""
    if not isinstance(filename, str):
        raise ValueError("Artifact filename must end in .json or .jsonl.")
    suffix = PurePath(filename).suffix.casefold()
    if suffix not in {".json", ".jsonl"}:
        raise ValueError("Artifact filename must end in .json or .jsonl.")

    normalized_media_type = _normalize_media_type(media_type)
    if normalized_media_type is not None:
        supported = _JSON_MEDIA_TYPES | _JSONL_MEDIA_TYPES
        if normalized_media_type not in supported:
            raise ValueError("Artifact media type is unsupported.")
        expected = _JSON_MEDIA_TYPES if suffix == ".json" else _JSONL_MEDIA_TYPES
        if normalized_media_type not in expected:
            raise ValueError("Artifact filename and media type do not match.")

    if suffix == ".json":
        return ingest_run_document(payload)
    return ingest_trace(payload)


def ingest_run_document(payload: bytes | bytearray | memoryview) -> Mapping[str, object]:
    """Parse and canonically validate one Atlas run document without executing it."""
    value = _parse_json(_decode_payload(payload))
    _validate_field_bounds(value)
    try:
        return cast(Mapping[str, object], validate_run_document(value))
    except Exception:
        raise ValueError("Atlas run document failed canonical validation.") from None


def ingest_trace(payload: bytes | bytearray | memoryview) -> TraceSummary:
    """Validate an Atlas JSONL trace and expose only an immutable summary."""
    text = _decode_payload(payload)
    lines = text.splitlines()
    if len(lines) > MAX_JSONL_LINES:
        raise ValueError(f"Trace exceeds the {MAX_JSONL_LINES:,}-record limit.")
    if any(not line.strip() for line in lines):
        raise ValueError("Trace contains an empty record.")

    records: list[Mapping[str, object]] = []
    for line in lines:
        value = _parse_json(line)
        _validate_field_bounds(value)
        if not isinstance(value, Mapping):
            raise ValueError("Every trace record must be a JSON object.")
        records.append(cast(Mapping[str, object], value))

    return _summarize_trace(records)


def _normalize_media_type(media_type: str | None) -> str | None:
    if media_type is None or not media_type.strip():
        return None
    return media_type.partition(";")[0].strip().casefold()


def _decode_payload(payload: bytes | bytearray | memoryview) -> str:
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise ValueError("Artifact must be provided as bytes.")
    raw = bytes(payload)
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError(f"Artifact exceeds the {MAX_ARTIFACT_BYTES:,}-byte limit.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Artifact must be valid UTF-8.") from None
    if not text.strip():
        raise ValueError("Artifact is empty.")
    return text


def _parse_json(text: str) -> object:
    _check_json_depth(text)
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
        )
    except _DuplicateKeyError:
        raise ValueError("Artifact contains duplicate JSON object keys.") from None
    except _NonFiniteNumberError:
        raise ValueError("Artifact contains a non-finite JSON number.") from None
    except (json.JSONDecodeError, RecursionError, ValueError):
        raise ValueError("Artifact contains malformed JSON.") from None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise _NonFiniteNumberError


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _NonFiniteNumberError
    return parsed


def _check_json_depth(text: str) -> None:
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ValueError(f"Artifact JSON nesting exceeds {MAX_JSON_DEPTH} levels.")
        elif character in "]}":
            depth -= 1


def _validate_field_bounds(value: object) -> None:
    if isinstance(value, str):
        if len(value) > MAX_FIELD_CHARS:
            raise ValueError(f"Artifact field exceeds the {MAX_FIELD_CHARS:,}-character limit.")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _validate_field_bounds(key)
            _validate_field_bounds(item)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _validate_field_bounds(item)
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Artifact contains a non-finite JSON number.")


def _summarize_trace(records: list[Mapping[str, object]]) -> TraceSummary:
    event_types: list[str] = []
    run_ids: list[str] = []
    for record in records:
        if record.get("schema_version") != _TRACE_SCHEMA:
            raise ValueError("Trace schema version is unsupported.")
        event_type = record.get("event_type")
        if event_type not in _EVENT_TYPES:
            raise ValueError("Trace event type is unsupported.")
        event_types.append(event_type)
        run_id = record.get("run_id")
        if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
            raise ValueError("Trace records must use one canonical run ID.")
        run_ids.append(run_id)

    if len(set(run_ids)) != 1:
        raise ValueError("Trace records must use one canonical run ID.")
    if not event_types or event_types[0] != "run_started":
        raise ValueError("Trace must begin with one canonical run_started event.")
    if event_types.count("run_started") != 1:
        raise ValueError("Trace must contain exactly one run_started event.")
    _validate_event_order(event_types)

    run_id = run_ids[0]
    property_ids = _validate_run_started(records[0], run_id)
    target_call_count = 0
    certificate_count = 0
    for record, event_type in zip(records[1:], event_types[1:], strict=True):
        if event_type == "target_call":
            target_call_count += 1
            _validate_target_call(record, property_ids, target_call_count)
        elif event_type == "certificate":
            certificate_count += 1
            _validate_certificate(record, property_ids, records[0])
        elif event_type == "run_completed":
            _validate_completed(record, target_call_count, certificate_count)

    counts = Counter(event_types)
    immutable_counts = MappingProxyType(
        {event_type: counts[event_type] for event_type in _EVENT_TYPES}
    )
    completed = counts["run_completed"] == 1
    return TraceSummary(
        run_id=run_id,
        event_counts=immutable_counts,
        target_call_count=target_call_count,
        certificate_count=certificate_count,
        completion_status="complete" if completed else "incomplete",
        property_ids=property_ids,
    )


def _validate_event_order(event_types: list[str]) -> None:
    order = {"run_started": 0, "target_call": 1, "certificate": 2, "run_completed": 3}
    positions = [order[event_type] for event_type in event_types]
    if positions != sorted(positions) or event_types.count("run_completed") > 1:
        raise ValueError("Trace event order is not canonical.")
    if "run_completed" in event_types and event_types[-1] != "run_completed":
        raise ValueError("Trace event order is not canonical.")


def _validate_run_started(record: Mapping[str, object], run_id: str) -> tuple[str, ...]:
    if set(record) != _START_KEYS:
        raise ValueError("Trace run_started event is not canonical.")
    metadata = record.get("metadata")
    property_pack = record.get("property_pack")
    if (
        not isinstance(metadata, Mapping)
        or set(metadata) != _METADATA_KEYS
        or metadata.get("run_id") != run_id
        or not isinstance(property_pack, list)
    ):
        raise ValueError("Trace run_started event is not canonical.")

    metadata_property_ids = metadata.get("property_ids")
    if not isinstance(metadata_property_ids, list) or not metadata_property_ids:
        raise ValueError("Trace run_started event is not canonical.")
    if not all(isinstance(item, str) for item in metadata_property_ids):
        raise ValueError("Trace run_started event is not canonical.")
    property_ids = tuple(cast(list[str], metadata_property_ids))
    if len(property_ids) != len(set(property_ids)):
        raise ValueError("Trace run_started event is not canonical.")
    expected_pack = [_PROPERTY_SNAPSHOTS.get(property_id) for property_id in property_ids]
    if None in expected_pack or property_pack != expected_pack:
        raise ValueError("Trace run_started event is not canonical.")
    if not _valid_metadata_scalars(metadata):
        raise ValueError("Trace run_started event is not canonical.")
    return property_ids


def _valid_metadata_scalars(metadata: Mapping[str, object]) -> bool:
    seed = metadata.get("seed")
    budget = metadata.get("candidate_budget")
    streams = metadata.get("executed_seed_streams")
    return (
        isinstance(seed, int)
        and not isinstance(seed, bool)
        and seed >= 0
        and isinstance(budget, int)
        and not isinstance(budget, bool)
        and 1 <= budget <= 100_000
        and isinstance(metadata.get("held_out_confirmation_seed_stream"), str)
        and isinstance(streams, list)
        and all(isinstance(item, str) for item in streams)
        and isinstance(metadata.get("property_pack_digest"), str)
        and isinstance(metadata.get("engine_config_hash"), str)
        and isinstance(metadata.get("confirmation_note"), str)
    )


def _validate_target_call(
    record: Mapping[str, object], property_ids: tuple[str, ...], ordinal: int
) -> None:
    invocation = record.get("invocation")
    if not isinstance(invocation, Mapping) or set(record) != _TARGET_KEYS:
        raise ValueError("Trace target_call event is not canonical.")
    if set(invocation) != _INVOCATION_KEYS:
        raise ValueError("Trace target_call event is not canonical.")
    if (
        invocation.get("ordinal") != ordinal
        or invocation.get("phase") not in {"search", "confirmation", "minimization"}
        or invocation.get("property_id") not in property_ids
        or invocation.get("pair_role") not in {"source", "follow_up"}
        or not _valid_nonnegative_int(invocation.get("seed"))
        or not _valid_nonnegative_int(invocation.get("latency_ms"))
        or not _valid_finite_number(invocation.get("estimated_cost_usd"))
        or not isinstance(invocation.get("cost_estimate_available"), bool)
        or not isinstance(invocation.get("succeeded"), bool)
        or not isinstance(invocation.get("relation_id"), str)
    ):
        raise ValueError("Trace target_call event is not canonical.")
    try:
        Scenario.model_validate_json(canonical_json(invocation.get("scenario")))
        decision = invocation.get("decision")
        if decision is not None:
            Decision.model_validate_json(canonical_json(decision))
    except Exception:
        raise ValueError("Trace target_call event is not canonical.") from None
    succeeded = invocation.get("succeeded") is True
    error_type = invocation.get("error_type")
    if succeeded != (invocation.get("decision") is not None) or (
        error_type is not None and not isinstance(error_type, str)
    ):
        raise ValueError("Trace target_call event is not canonical.")


def _validate_certificate(
    record: Mapping[str, object],
    property_ids: tuple[str, ...],
    started: Mapping[str, object],
) -> None:
    if set(record) != _CERTIFICATE_KEYS:
        raise ValueError("Trace certificate event is not canonical.")
    try:
        certificate = FailureCertificate.model_validate_json(
            canonical_json(record.get("certificate"))
        )
    except Exception:
        raise ValueError("Trace certificate event is not canonical.") from None
    if (
        certificate.property_id not in property_ids
        or record.get("property") != _PROPERTY_SNAPSHOTS[certificate.property_id]
        or recompute_certificate_id(certificate) != certificate.certificate_id
    ):
        raise ValueError("Trace certificate event is not canonical.")
    metadata = cast(Mapping[str, object], started["metadata"])
    if (
        certificate.seed != metadata["seed"]
        or certificate.engine_config_hash != metadata["engine_config_hash"]
        or not isinstance(record.get("output_distribution"), Mapping)
        or not isinstance(record.get("minimization_evidence"), Mapping)
    ):
        raise ValueError("Trace certificate event is not canonical.")


def _validate_completed(
    record: Mapping[str, object], target_call_count: int, certificate_count: int
) -> None:
    if set(record) != _COMPLETED_KEYS:
        raise ValueError("Trace run_completed event is not canonical.")
    if (
        record.get("target_calls_total") != target_call_count
        or record.get("certificate_count") != certificate_count
        or not _valid_nonnegative_int(record.get("coverage_cell_count"))
        or not isinstance(record.get("cost_estimate_available"), bool)
        or not _valid_finite_number(record.get("estimated_cost_usd"))
    ):
        raise ValueError("Trace completion totals are inconsistent.")


def _valid_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    )
