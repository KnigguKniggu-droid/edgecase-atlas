"""Canonical JSON, research JSONL traces, and artifact-safe file helpers."""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from edgecase_atlas.engine import RunResult
from edgecase_atlas.properties import STARTER_PROPERTY_PACK

_PROPERTIES = {item.property_id: item for item in STARTER_PROPERTY_PACK}


def jsonable(value: object) -> object:
    """Convert supported Atlas evidence to stable, JSON-safe primitive structures."""
    if isinstance(value, BaseModel):
        return jsonable(value.model_dump(mode="json"))
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        converted = [jsonable(item) for item in value]
        return sorted(converted, key=_sort_key)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Canonical JSON prohibits NaN and infinite values")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported canonical JSON value: {type(value).__name__}")


def _sort_key(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_json(value: object) -> str:
    """Return deterministic UTF-8 JSON text without non-standard numeric values."""
    return json.dumps(
        jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def write_canonical_json(path: Path | str, value: object) -> Path:
    """Atomically replace one canonical JSON artifact."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(output)
    return output


def append_jsonl(path: Path | str, events: Sequence[Mapping[str, object]]) -> Path:
    """Append complete canonical events without truncating prior research evidence."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8", newline="\n") as stream:
        for event in events:
            stream.write(canonical_json(event))
            stream.write("\n")
        stream.flush()
    return output


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _property_pack(run: RunResult) -> list[dict[str, str]]:
    snapshots: list[dict[str, str]] = []
    for property_id in run.metadata.property_ids:
        property_ = _PROPERTIES.get(property_id)
        if property_ is None:
            raise ValueError(f"No serializable property snapshot exists for {property_id!r}")
        snapshots.append(
            {
                "property_id": property_.property_id,
                "title": property_.title,
                "description": property_.description,
                "scope_note": property_.scope_note,
            }
        )
    return snapshots


def _distribution(certificate: BaseModel) -> dict[str, dict[str, int]]:
    data = certificate.model_dump(mode="json")
    decisions = data["source_decisions"] + data["follow_up_decisions"]
    actions = Counter(str(item["action"]) for item in decisions)
    risks = Counter(str(item["risk"]) for item in decisions)
    return {
        "actions": dict(sorted(actions.items())),
        "risks": dict(sorted(risks.items())),
    }


def run_document(run: RunResult) -> dict[str, object]:
    """Build the stable standalone run artifact consumed by reports and research tooling."""
    property_pack = _property_pack(run)
    properties = {item["property_id"]: item for item in property_pack}
    certificates: list[dict[str, object]] = []
    for item in run.certificates:
        certificate = item.certificate.model_dump(mode="json")
        certificate["property"] = dict(properties[item.certificate.property_id])
        certificate["output_distribution"] = _distribution(item.certificate)
        certificate["minimization_evidence"] = {
            "label": item.label,
            "accepted": item.minimization.accepted,
            "attempts": jsonable(item.minimization.attempts),
            "terminal_audit_attempts": jsonable(item.minimization.terminal_audit_attempts),
            "terminal_audit_complete": item.minimization.terminal_audit_complete,
        }
        certificates.append(certificate)
    return {
        "schema_version": "atlas-run-v1",
        "metadata": jsonable(run.metadata),
        "property_pack": property_pack,
        "call_ledger": {
            "target_calls_total": run.call_ledger.target_calls_total,
            "search_calls": run.call_ledger.search_calls,
            "confirmation_calls": run.call_ledger.confirmation_calls,
            "minimization_calls": run.call_ledger.minimization_calls,
            "estimated_cost_usd": run.call_ledger.estimated_cost_usd,
            "cost_estimate_available": run.call_ledger.cost_estimate_available,
            "invocations": jsonable(run.call_ledger.invocations),
        },
        "coverage": {
            "estimand": run.coverage_estimand,
            "cells": sorted(run.coverage_cells),
            "trajectory": jsonable(run.coverage_trajectory),
        },
        "certificates": certificates,
    }


def trace_events(run: RunResult) -> list[dict[str, object]]:
    """Return append-only event records with complete per-call and certificate evidence."""
    run_id = run.metadata.run_id
    property_pack = _property_pack(run)
    properties = {item["property_id"]: item for item in property_pack}
    events: list[dict[str, object]] = [
        {
            "schema_version": "atlas-trace-v1",
            "event_type": "run_started",
            "run_id": run_id,
            "metadata": jsonable(run.metadata),
            "property_pack": property_pack,
        }
    ]
    for invocation in run.call_ledger.invocations:
        events.append(
            {
                "schema_version": "atlas-trace-v1",
                "event_type": "target_call",
                "run_id": run_id,
                "invocation": jsonable(invocation),
            }
        )
    for item in run.certificates:
        events.append(
            {
                "schema_version": "atlas-trace-v1",
                "event_type": "certificate",
                "run_id": run_id,
                "property": properties[item.certificate.property_id],
                "certificate": item.certificate.model_dump(mode="json"),
                "output_distribution": _distribution(item.certificate),
                "minimization_evidence": jsonable(item.minimization),
            }
        )
    events.append(
        {
            "schema_version": "atlas-trace-v1",
            "event_type": "run_completed",
            "run_id": run_id,
            "target_calls_total": run.call_ledger.target_calls_total,
            "certificate_count": len(run.certificates),
            "coverage_cell_count": len(run.coverage_cells),
            "cost_estimate_available": run.call_ledger.cost_estimate_available,
            "estimated_cost_usd": run.call_ledger.estimated_cost_usd,
        }
    )
    return events
