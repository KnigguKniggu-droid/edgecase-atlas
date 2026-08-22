"""Canonical JSON, research JSONL traces, and artifact-safe file helpers."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from edgecase_atlas.engine import (
    _COVERAGE_ESTIMAND,
    RunResult,
    _digest_json,
    _engine_config_hash,
    _property_pack_digest,
    recompute_certificate_id,
)
from edgecase_atlas.models import FailureCertificate
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


def write_jsonl(path: Path | str, events: Sequence[Mapping[str, object]]) -> Path:
    """Atomically replace one execution trace so deterministic run IDs never mix runs."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for event in events:
            stream.write(canonical_json(event) + "\n")
        stream.flush()
    temporary.replace(output)
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


def validate_run_document(value: object) -> Mapping[str, object]:
    """Reject forged or internally inconsistent evidence before report rendering."""
    if not isinstance(value, Mapping) or value.get("schema_version") != "atlas-run-v1":
        raise ValueError("Unsupported Atlas run artifact")
    metadata = value.get("metadata")
    property_pack = value.get("property_pack")
    ledger = value.get("call_ledger")
    certificates = value.get("certificates")
    if not isinstance(metadata, Mapping) or not isinstance(ledger, Mapping):
        raise ValueError("Run metadata and ledger must be objects")
    if not isinstance(property_pack, list) or not isinstance(certificates, list):
        raise ValueError("Property pack and certificates must be arrays")
    property_ids = metadata.get("property_ids")
    if not isinstance(property_ids, list) or not all(
        isinstance(item, str) for item in property_ids
    ):
        raise ValueError("Run property IDs are invalid")
    if set(metadata) != {
        "run_id",
        "seed",
        "candidate_budget",
        "held_out_confirmation_seed_stream",
        "executed_seed_streams",
        "property_ids",
        "property_pack_digest",
        "engine_config_hash",
        "confirmation_note",
    }:
        raise ValueError("Run metadata fields are not canonical")
    if not isinstance(metadata["run_id"], str) or not re.fullmatch(
        r"run-[0-9a-f]{16}", metadata["run_id"]
    ):
        raise ValueError("Run ID is not canonical")
    if (
        not isinstance(metadata["seed"], int)
        or isinstance(metadata["seed"], bool)
        or metadata["seed"] < 0
    ):
        raise ValueError("Run seed is invalid")
    if (
        not isinstance(metadata["candidate_budget"], int)
        or not 1 <= metadata["candidate_budget"] <= 100_000
    ):
        raise ValueError("Run budget is invalid")
    properties = tuple(
        _PROPERTIES[property_id] for property_id in property_ids if property_id in _PROPERTIES
    )
    if metadata["property_pack_digest"] != _property_pack_digest(properties):
        raise ValueError("Run property-pack digest is inconsistent")
    if metadata["engine_config_hash"] != _engine_config_hash():
        raise ValueError("Run engine configuration is inconsistent")
    expected_pack = []
    for property_id in property_ids:
        item = _PROPERTIES.get(property_id)
        if item is None:
            raise ValueError("Run references an unknown property")
        expected_pack.append(
            {
                "property_id": item.property_id,
                "title": item.title,
                "description": item.description,
                "scope_note": item.scope_note,
            }
        )
    if property_pack != expected_pack:
        raise ValueError("Property pack does not match installed assumptions")
    invocations = ledger.get("invocations")
    if not isinstance(invocations, list):
        raise ValueError("Call ledger invocations must be an array")
    phases = {"search": 0, "confirmation": 0, "minimization": 0}
    for ordinal, invocation in enumerate(invocations, start=1):
        if not isinstance(invocation, Mapping) or invocation.get("ordinal") != ordinal:
            raise ValueError("Call ledger ordinals are not canonical")
        phase = invocation.get("phase")
        if phase not in phases:
            raise ValueError("Call ledger phase is invalid")
        phases[str(phase)] += 1
    if ledger.get("target_calls_total") != len(invocations):
        raise ValueError("Call ledger total is inconsistent")
    if any(ledger.get(f"{phase}_calls") != count for phase, count in phases.items()):
        raise ValueError("Call ledger phase totals are inconsistent")
    if phases["search"] != 2 * metadata["candidate_budget"]:
        raise ValueError("Run budget is inconsistent with charged search calls")
    costs = [invocation.get("estimated_cost_usd") for invocation in invocations]
    if not all(isinstance(cost, (int, float)) and not isinstance(cost, bool) for cost in costs):
        raise ValueError("Call ledger costs are invalid")
    if not math.isclose(float(ledger.get("estimated_cost_usd", -1)), sum(costs)):
        raise ValueError("Call ledger cost total is inconsistent")
    cost_available = bool(invocations) and all(
        invocation.get("cost_estimate_available") is True for invocation in invocations
    )
    if ledger.get("cost_estimate_available") is not cost_available:
        raise ValueError("Call ledger cost availability is inconsistent")
    coverage = value.get("coverage")
    if not isinstance(coverage, Mapping) or set(coverage) != {"estimand", "cells", "trajectory"}:
        raise ValueError("Run coverage is invalid")
    cells = coverage["cells"]
    trajectory = coverage["trajectory"]
    if coverage["estimand"] != _COVERAGE_ESTIMAND:
        raise ValueError("Run coverage estimand is inconsistent")
    if (
        not isinstance(cells, list)
        or cells != sorted(set(cells))
        or not all(isinstance(cell, str) and len(cell) <= 300 for cell in cells)
    ):
        raise ValueError("Run coverage cells are invalid")
    if not isinstance(trajectory, list) or len(trajectory) > int(ledger["target_calls_total"]):
        raise ValueError("Run coverage trajectory is invalid")
    previous_calls = 0
    previous_cells = 0
    for point in trajectory:
        if not isinstance(point, Mapping) or set(point) != {
            "charged_target_calls",
            "observed_cells",
        }:
            raise ValueError("Run coverage point is invalid")
        calls = point["charged_target_calls"]
        observed = point["observed_cells"]
        if (
            not isinstance(calls, int)
            or not isinstance(observed, int)
            or calls < previous_calls
            or observed < previous_cells
            or observed > len(cells)
        ):
            raise ValueError("Run coverage trajectory is inconsistent")
        previous_calls, previous_cells = calls, observed
    if trajectory and (
        previous_calls > int(ledger["target_calls_total"]) or previous_cells != len(cells)
    ):
        raise ValueError("Run coverage terminal point is inconsistent")
    for item in certificates:
        if not isinstance(item, Mapping):
            raise ValueError("Certificate must be an object")
        data = {
            key: field_value
            for key, field_value in item.items()
            if key not in {"property", "output_distribution", "minimization_evidence"}
        }
        certificate = FailureCertificate.model_validate_json(canonical_json(data))
        if recompute_certificate_id(certificate) != certificate.certificate_id:
            raise ValueError("Certificate digest does not match its content")
        if certificate.property_id not in property_ids:
            raise ValueError("Certificate property is not in run property pack")
        if (
            certificate.seed != metadata["seed"]
            or certificate.engine_config_hash != metadata["engine_config_hash"]
        ):
            raise ValueError("Certificate metadata is inconsistent with the run")
        identity = {
            "seed": metadata["seed"],
            "candidate_budget": metadata["candidate_budget"],
            "property_pack_digest": metadata["property_pack_digest"],
            "model_id": certificate.model_id,
            "model_config_hash": certificate.model_config_hash,
            "engine_config_hash": metadata["engine_config_hash"],
        }
        if metadata["run_id"] != f"run-{_digest_json(identity)[:16]}":
            raise ValueError("Run ID does not match certificate metadata")
        if (
            certificate.replay_command
            != f"atlas replay certificates/{certificate.certificate_id}.json"
        ):
            raise ValueError("Certificate replay command is not canonical")
        if item.get("property") != expected_pack[property_ids.index(certificate.property_id)]:
            raise ValueError("Certificate property snapshot is inconsistent")
        if item.get("output_distribution") != _distribution(certificate):
            raise ValueError("Certificate output distribution is inconsistent")
        evidence = item.get("minimization_evidence")
        if (
            not isinstance(evidence, Mapping)
            or set(evidence)
            != {
                "label",
                "accepted",
                "attempts",
                "terminal_audit_attempts",
                "terminal_audit_complete",
            }
            or evidence.get("label") != certificate.reducer_label
            or evidence.get("accepted") is not True
            or evidence.get("terminal_audit_complete") is not certificate.terminal_audit_complete
        ):
            raise ValueError("Certificate minimization evidence is inconsistent")
        for attempts_name in ("attempts", "terminal_audit_attempts"):
            attempts = evidence[attempts_name]
            if not isinstance(attempts, list) or len(attempts) > 128:
                raise ValueError("Certificate minimization attempts are invalid")
            for attempt in attempts:
                if not isinstance(attempt, Mapping) or set(attempt) != {
                    "operation",
                    "accepted",
                    "reason",
                }:
                    raise ValueError("Certificate minimization attempt is invalid")
                if (
                    not isinstance(attempt["operation"], str)
                    or len(attempt["operation"]) > 200
                    or not isinstance(attempt["accepted"], bool)
                    or not isinstance(attempt["reason"], str)
                    or len(attempt["reason"]) > 500
                ):
                    raise ValueError("Certificate minimization attempt fields are invalid")
    return value


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
