"""Deterministic comparison of validated Atlas run artifacts."""

from __future__ import annotations

import hashlib
import html
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from edgecase_atlas.serialization import canonical_json, validate_run_document


def compare_run_documents(run_a: object, run_b: object) -> dict[str, object]:
    """Validate two compatible runs and return stable B-minus-A evidence deltas."""
    a = validate_run_document(run_a)
    b = validate_run_document(run_b)
    _require_compatible(a, b)
    metadata_a, metadata_b = _mapping(a["metadata"]), _mapping(b["metadata"])
    ledger_a, ledger_b = _mapping(a["call_ledger"]), _mapping(b["call_ledger"])
    coverage_a, coverage_b = _mapping(a["coverage"]), _mapping(b["coverage"])
    signatures_a = {_certificate_signature(item) for item in _mappings(a["certificates"])}
    signatures_b = {_certificate_signature(item) for item in _mappings(b["certificates"])}
    cells_a = set(_strings(coverage_a["cells"]))
    cells_b = set(_strings(coverage_b["cells"]))
    calls_a = int(ledger_a["target_calls_total"])
    calls_b = int(ledger_b["target_calls_total"])
    auc_a = coverage_trajectory_auc(_mappings(coverage_a["trajectory"]))
    auc_b = coverage_trajectory_auc(_mappings(coverage_b["trajectory"]))
    return {
        "schema_version": "atlas-comparison-v1",
        "runs": {"a": metadata_a["run_id"], "b": metadata_b["run_id"]},
        "compatibility": {
            "engine_config_hash": metadata_a["engine_config_hash"],
            "property_pack_digest": metadata_a["property_pack_digest"],
            "property_ids": list(metadata_a["property_ids"]),
            "coverage_estimand": coverage_a["estimand"],
        },
        "certificates": {
            "added": sorted(signatures_b - signatures_a),
            "removed": sorted(signatures_a - signatures_b),
            "unchanged": sorted(signatures_a & signatures_b),
        },
        "call_totals": {"a": calls_a, "b": calls_b, "delta": calls_b - calls_a},
        "coverage": {
            "cells_added": sorted(cells_b - cells_a),
            "cells_removed": sorted(cells_a - cells_b),
            "trajectory_auc": {"a": auc_a, "b": auc_b, "delta": auc_b - auc_a},
        },
    }


def coverage_trajectory_auc(trajectory: Sequence[Mapping[str, object]]) -> float:
    """Return raw observed-cell by charged-call AUC, anchored at the zero-call origin."""
    area = 0.0
    previous_calls = 0
    previous_cells = 0
    for point in trajectory:
        calls = cast(int, point["charged_target_calls"])
        cells = cast(int, point["observed_cells"])
        area += (calls - previous_calls) * (previous_cells + cells) / 2
        previous_calls, previous_cells = calls, cells
    return area


def render_comparison_html(comparison: Mapping[str, object], output_path: Path | str) -> Path:
    """Write one escaped, dependency-free standalone comparison report."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = html.escape(json.dumps(comparison, indent=2, sort_keys=True, ensure_ascii=False))
    output.write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        "<title>EdgeCase Atlas run comparison</title>"
        "<style>body{font:16px system-ui;max-width:72rem;margin:2rem auto;padding:0 1rem;}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f4f4;padding:1rem;}</style>"
        f"<h1>EdgeCase Atlas run comparison</h1><pre>{payload}</pre></html>\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def _require_compatible(a: Mapping[str, object], b: Mapping[str, object]) -> None:
    metadata_a, metadata_b = _mapping(a["metadata"]), _mapping(b["metadata"])
    coverage_a, coverage_b = _mapping(a["coverage"]), _mapping(b["coverage"])
    checks = (
        (a["schema_version"], b["schema_version"], "schema version"),
        (a["property_pack"], b["property_pack"], "property pack"),
        (metadata_a["property_ids"], metadata_b["property_ids"], "property IDs"),
        (
            metadata_a["property_pack_digest"],
            metadata_b["property_pack_digest"],
            "property-pack digest",
        ),
        (
            metadata_a["engine_config_hash"],
            metadata_b["engine_config_hash"],
            "engine configuration",
        ),
        (coverage_a["estimand"], coverage_b["estimand"], "coverage estimand"),
    )
    for left, right, label in checks:
        if left != right:
            raise ValueError(f"Runs have incompatible {label}")


def _certificate_signature(certificate: Mapping[str, object]) -> str:
    source = _mappings(certificate["source_decisions"])
    follow_up = _mappings(certificate["follow_up_decisions"])
    transitions = sorted(
        f"{left['action']}:{left['risk']}->{right['action']}:{right['risk']}"
        for left, right in zip(source, follow_up, strict=True)
    )
    evidence = {
        "relation_id": certificate["relation_id"],
        "property_id": certificate["property_id"],
        "changed_fields": certificate["changed_fields"],
        "decision_transitions": transitions,
    }
    digest = hashlib.sha256(canonical_json(evidence).encode("utf-8")).hexdigest()
    return f"failure-{digest[:20]}"


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("Validated run field must be an object")
    return value


def _mappings(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise TypeError("Validated run field must be an array of objects")
    return list(value)


def _strings(value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("Validated run field must be an array of strings")
    return value
