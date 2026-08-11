"""Self-contained, escaped HTML reporting for canonical run artifacts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape


def render_html_report(document: Mapping[str, Any], output_path: Path | str) -> Path:
    """Render one offline report using only the artifact's immutable semantic snapshot."""
    environment = Environment(
        loader=PackageLoader("edgecase_atlas", "templates"),
        autoescape=select_autoescape(enabled_extensions=("html", "j2"), default=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        environment.get_template("report.html.j2").render(**_report_context(document)),
        encoding="utf-8",
        newline="\n",
    )
    return output


def _report_context(document: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _mapping(document.get("metadata"))
    call_ledger = _mapping(document.get("call_ledger"))
    property_pack = _sequence_of_mappings(document.get("property_pack"))
    properties = {str(item.get("property_id")): item for item in property_pack}
    certificates: list[dict[str, Any]] = []
    for raw in _sequence_of_mappings(document.get("certificates")):
        property_id = str(raw.get("property_id", "unknown"))
        property_snapshot = _mapping(raw.get("property")) or properties.get(property_id, {})
        source_decisions = _sequence_of_mappings(raw.get("source_decisions"))
        follow_decisions = _sequence_of_mappings(raw.get("follow_up_decisions"))
        distribution = _mapping(raw.get("output_distribution"))
        action_distribution = _distribution_items(
            distribution.get("actions"), source_decisions + follow_decisions, "action"
        )
        risk_distribution = _distribution_items(
            distribution.get("risks"), source_decisions + follow_decisions, "risk"
        )
        cost_available = raw.get("cost_estimate_available") is True
        certificates.append(
            {
                "raw": raw,
                "property_title": property_snapshot.get("title", property_id),
                "property_assumption": property_snapshot.get("description", "Unknown property"),
                "property_scope": property_snapshot.get("scope_note", "Unknown scope"),
                "changes": _sequence_of_mappings(raw.get("changed_fields")),
                "source_decisions": source_decisions,
                "follow_decisions": follow_decisions,
                "action_distribution": action_distribution,
                "risk_distribution": risk_distribution,
                "cost_display": (
                    f"${float(raw.get('estimated_cost_usd', 0.0)):.6f}"
                    if cost_available
                    else "unknown"
                ),
            }
        )
    run_cost_available = call_ledger.get("cost_estimate_available") is True
    return {
        "schema_version": document.get("schema_version", "unknown"),
        "metadata": metadata,
        "call_ledger": call_ledger,
        "coverage": _mapping(document.get("coverage")),
        "property_pack": property_pack,
        "certificates": certificates,
        "run_cost_display": (
            f"${float(call_ledger.get('estimated_cost_usd', 0.0)):.6f}"
            if run_cost_available
            else "unknown"
        ),
    }


def _distribution_items(
    snapshot: object, decisions: list[Mapping[str, Any]], field_name: str
) -> list[tuple[str, int]]:
    if isinstance(snapshot, Mapping):
        return sorted((str(label), int(count)) for label, count in snapshot.items())
    counts = Counter(str(item.get(field_name, "unknown")) for item in decisions)
    return sorted(counts.items())


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence_of_mappings(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]
