"""Adversarial tests for the public artifact-ingestion boundary."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import FrozenInstanceError

import pytest
from app import artifact_io

from edgecase_atlas.engine import AtlasEngine
from edgecase_atlas.fixtures import FaultyDemonstrationAgent
from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.serialization import canonical_json, run_document, trace_events


@pytest.fixture(scope="module")
def artifacts() -> tuple[dict[str, object], list[dict[str, object]]]:
    run = asyncio.run(
        AtlasEngine().run(FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=1)
    )
    return run_document(run), trace_events(run)


def _json_bytes(value: object) -> bytes:
    return (canonical_json(value) + "\n").encode()


def _jsonl_bytes(events: list[dict[str, object]]) -> bytes:
    return ("\n".join(canonical_json(event) for event in events) + "\n").encode()


def test_json_run_is_validated_by_the_canonical_validator(
    artifacts: tuple[dict[str, object], list[dict[str, object]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document, _events = artifacts
    calls: list[object] = []

    def validate(value: object) -> Mapping[str, object]:
        calls.append(value)
        assert isinstance(value, Mapping)
        return value

    monkeypatch.setattr(artifact_io, "validate_run_document", validate)

    result = artifact_io.ingest_artifact(
        _json_bytes(document), filename="run.json", media_type="application/json"
    )

    assert result is calls[0]


def test_jsonl_returns_an_immutable_public_summary(
    artifacts: tuple[dict[str, object], list[dict[str, object]]],
) -> None:
    _document, events = artifacts

    summary = artifact_io.ingest_artifact(
        _jsonl_bytes(events), filename="trace.jsonl", media_type="application/x-ndjson"
    )

    assert isinstance(summary, artifact_io.TraceSummary)
    assert summary.run_id == events[0]["run_id"]
    assert summary.event_counts == {
        "run_started": 1,
        "target_call": sum(event["event_type"] == "target_call" for event in events),
        "certificate": sum(event["event_type"] == "certificate" for event in events),
        "run_completed": 1,
    }
    assert summary.target_call_count == summary.event_counts["target_call"]
    assert summary.certificate_count == summary.event_counts["certificate"]
    assert summary.completion_status == "complete"
    assert summary.completed is True
    assert summary.property_ids == tuple(events[0]["metadata"]["property_ids"])
    with pytest.raises(TypeError):
        summary.event_counts["target_call"] = 0  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        summary.run_id = "run-0000000000000000"  # type: ignore[misc]


def test_incomplete_trace_has_explicit_status(
    artifacts: tuple[dict[str, object], list[dict[str, object]]],
) -> None:
    _document, events = artifacts

    summary = artifact_io.ingest_trace(_jsonl_bytes(events[:-1]))

    assert summary.completion_status == "incomplete"
    assert summary.completed is False
    assert summary.event_counts["run_completed"] == 0


@pytest.mark.parametrize(
    ("payload", "message"),
    (
        (b"", "Artifact is empty."),
        (b" \r\n\t", "Artifact is empty."),
        (b"\xff", "Artifact must be valid UTF-8."),
        (
            b'{"schema_version":"atlas-run-v1","schema_version":"duplicate"}',
            "Artifact contains duplicate JSON object keys.",
        ),
        (b'{"value":NaN}', "Artifact contains a non-finite JSON number."),
        (b'{"value":Infinity}', "Artifact contains a non-finite JSON number."),
        (b'{"value":-Infinity}', "Artifact contains a non-finite JSON number."),
        (b'{"broken":', "Artifact contains malformed JSON."),
    ),
)
def test_json_rejects_invalid_encoding_and_grammar(payload: bytes, message: str) -> None:
    with pytest.raises(ValueError) as captured:
        artifact_io.ingest_run_document(payload)

    assert str(captured.value) == message


def test_json_rejects_excessive_nesting_before_decoding() -> None:
    payload = (
        "[" * (artifact_io.MAX_JSON_DEPTH + 1) + "0" + "]" * (artifact_io.MAX_JSON_DEPTH + 1)
    ).encode()

    with pytest.raises(ValueError) as captured:
        artifact_io.ingest_run_document(payload)

    assert str(captured.value) == (
        f"Artifact JSON nesting exceeds {artifact_io.MAX_JSON_DEPTH} levels."
    )


def test_input_size_limit_is_measured_in_bytes() -> None:
    payload = b" " * (artifact_io.MAX_ARTIFACT_BYTES + 1)

    with pytest.raises(ValueError) as captured:
        artifact_io.ingest_run_document(payload)

    assert str(captured.value) == (
        f"Artifact exceeds the {artifact_io.MAX_ARTIFACT_BYTES:,}-byte limit."
    )


@pytest.mark.parametrize(
    ("filename", "media_type", "message"),
    (
        ("run.txt", "application/json", "Artifact filename must end in .json or .jsonl."),
        ("run.json", "text/html", "Artifact media type is unsupported."),
        ("run.json", "application/x-ndjson", "Artifact filename and media type do not match."),
        ("trace.jsonl", "application/json", "Artifact filename and media type do not match."),
    ),
)
def test_dispatch_rejects_unsupported_or_mismatched_formats(
    filename: str, media_type: str, message: str
) -> None:
    with pytest.raises(ValueError) as captured:
        artifact_io.ingest_artifact(b"{}", filename=filename, media_type=media_type)

    assert str(captured.value) == message


def test_dispatch_allows_an_unspecified_media_type(
    artifacts: tuple[dict[str, object], list[dict[str, object]]],
) -> None:
    document, _events = artifacts

    assert isinstance(
        artifact_io.ingest_artifact(_json_bytes(document), filename="RUN.JSON"), Mapping
    )


def test_trace_rejects_excess_record_count() -> None:
    record = b'{"schema_version":"atlas-trace-v1"}'
    payload = b"\n".join([record] * (artifact_io.MAX_JSONL_LINES + 1))

    with pytest.raises(ValueError) as captured:
        artifact_io.ingest_trace(payload)

    assert str(captured.value) == (
        f"Trace exceeds the {artifact_io.MAX_JSONL_LINES:,}-record limit."
    )


def test_trace_rejects_empty_and_non_object_records() -> None:
    with pytest.raises(ValueError, match=r"^Trace contains an empty record\.$"):
        artifact_io.ingest_trace(b"{}\n\n{}")
    with pytest.raises(ValueError, match=r"^Every trace record must be a JSON object\.$"):
        artifact_io.ingest_trace(b"[]")


def test_trace_rejects_duplicate_keys_and_non_finite_numbers() -> None:
    with pytest.raises(ValueError, match=r"^Artifact contains duplicate JSON object keys\.$"):
        artifact_io.ingest_trace(b'{"run_id":"first","run_id":"second"}')
    with pytest.raises(ValueError, match=r"^Artifact contains a non-finite JSON number\.$"):
        artifact_io.ingest_trace(b'{"value":NaN}')


def test_trace_rejects_mixed_run_ids(
    artifacts: tuple[dict[str, object], list[dict[str, object]]],
) -> None:
    _document, events = artifacts
    changed = json.loads(json.dumps(events))
    changed[1]["run_id"] = "run-0000000000000000"

    with pytest.raises(ValueError, match=r"^Trace records must use one canonical run ID\.$"):
        artifact_io.ingest_trace(_jsonl_bytes(changed))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("schema_version", "atlas-trace-v2", "Trace schema version is unsupported."),
        ("event_type", "command", "Trace event type is unsupported."),
    ),
)
def test_trace_rejects_unknown_schema_and_event_types(
    artifacts: tuple[dict[str, object], list[dict[str, object]]],
    field: str,
    value: str,
    message: str,
) -> None:
    _document, events = artifacts
    changed = json.loads(json.dumps(events))
    changed[1][field] = value

    with pytest.raises(ValueError) as captured:
        artifact_io.ingest_trace(_jsonl_bytes(changed))

    assert str(captured.value) == message


def test_trace_rejects_oversized_nested_fields_without_reflecting_them(
    artifacts: tuple[dict[str, object], list[dict[str, object]]],
) -> None:
    _document, events = artifacts
    sentinel = "PRIVATE-SENTINEL-" + "x" * artifact_io.MAX_FIELD_CHARS
    changed = json.loads(json.dumps(events))
    changed[1]["invocation"]["error_type"] = sentinel

    with pytest.raises(ValueError) as captured:
        artifact_io.ingest_trace(_jsonl_bytes(changed))

    assert str(captured.value) == (
        f"Artifact field exceeds the {artifact_io.MAX_FIELD_CHARS:,}-character limit."
    )
    assert sentinel not in str(captured.value)


def test_run_rejects_oversized_unknown_fields_before_validation(
    artifacts: tuple[dict[str, object], list[dict[str, object]]],
) -> None:
    document, _events = artifacts
    changed = json.loads(json.dumps(document))
    changed["untrusted"] = "x" * (artifact_io.MAX_FIELD_CHARS + 1)

    with pytest.raises(ValueError, match="field exceeds"):
        artifact_io.ingest_run_document(_json_bytes(changed))


def test_trace_requires_one_canonical_first_start_event(
    artifacts: tuple[dict[str, object], list[dict[str, object]]],
) -> None:
    _document, events = artifacts
    with pytest.raises(
        ValueError, match=r"^Trace must begin with one canonical run_started event\.$"
    ):
        artifact_io.ingest_trace(_jsonl_bytes(events[1:]))
    with pytest.raises(ValueError, match=r"^Trace must contain exactly one run_started event\.$"):
        artifact_io.ingest_trace(_jsonl_bytes([events[0], *events]))


def test_trace_rejects_noncanonical_start_and_mismatched_completion_totals(
    artifacts: tuple[dict[str, object], list[dict[str, object]]],
) -> None:
    _document, events = artifacts
    changed = json.loads(json.dumps(events))
    changed[0]["unexpected"] = "field"
    with pytest.raises(ValueError, match=r"^Trace run_started event is not canonical\.$"):
        artifact_io.ingest_trace(_jsonl_bytes(changed))

    changed = json.loads(json.dumps(events))
    changed[-1]["target_calls_total"] += 1
    with pytest.raises(ValueError, match=r"^Trace completion totals are inconsistent\.$"):
        artifact_io.ingest_trace(_jsonl_bytes(changed))


def test_trace_rejects_noncanonical_event_order(
    artifacts: tuple[dict[str, object], list[dict[str, object]]],
) -> None:
    _document, events = artifacts
    changed = [events[0], events[-1], *events[1:-1]]

    with pytest.raises(ValueError, match=r"^Trace event order is not canonical\.$"):
        artifact_io.ingest_trace(_jsonl_bytes(changed))


def test_all_parse_failures_are_public_safe() -> None:
    sentinel = "PRIVATE-SENTINEL"
    payload = f'{{"{sentinel}":'.encode()

    with pytest.raises(ValueError) as captured:
        artifact_io.ingest_run_document(payload)

    assert sentinel not in str(captured.value)
