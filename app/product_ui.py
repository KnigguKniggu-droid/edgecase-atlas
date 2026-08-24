"""Reusable native Streamlit renderers for the public product surface."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

import streamlit as st

__all__ = (
    "DownloadArtifact",
    "render_benchmark_result",
    "render_counterfactual_faultline",
    "render_download_controls",
    "render_evidence_pipeline",
    "render_failure_certificate",
    "render_page_intro",
    "render_privacy_footer",
    "render_run_comparison_delta",
    "render_scenario_card",
)

type BadgeColor = Literal[
    "red",
    "orange",
    "yellow",
    "blue",
    "green",
    "violet",
    "gray",
    "grey",
    "primary",
]

_UNKNOWN: Final = "Not recorded"


@dataclass(frozen=True, slots=True)
class DownloadArtifact:
    """One caller-prepared, inert artifact exposed through a download button."""

    label: str
    data: bytes
    file_name: str
    mime: str
    icon: str


def render_page_intro(*, eyebrow: str, title: str, lede: str, key: str) -> None:
    """Render a compact page thesis with clear information hierarchy."""
    with st.container(key=key):
        st.caption(eyebrow)
        st.title(title)
        st.markdown(lede)


def render_scenario_card(
    label: str,
    scenario: Mapping[str, object],
    *,
    key: str,
) -> None:
    """Render a scenario as scannable factors and metrics, never as a table."""
    actors = _sequence(scenario.get("actors"))
    description = str(scenario.get("description") or "No description available.")
    with st.container(border=True, key=key):
        st.badge(label, icon=":material/route:", color="gray")
        st.markdown(f"**{description}**")
        with st.container(horizontal=True, key=f"{key}_factors"):
            st.badge(
                f"Road: {_display(scenario.get('road_type'))}",
                icon=":material/alt_route:",
                color="blue",
            )
            st.badge(
                f"Signal: {_display(scenario.get('signal'))}",
                icon=":material/traffic:",
                color=_signal_color(scenario.get("signal")),
            )
            st.badge(
                f"Surface: {_display(scenario.get('surface'))}",
                icon=_surface_icon(scenario.get("surface")),
                color="gray",
            )
            st.badge(
                f"Visibility: {_display(scenario.get('visibility'))}",
                icon=":material/visibility:",
                color="gray",
            )
        with st.container(horizontal=True, key=f"{key}_metrics"):
            st.metric("Ego speed", _with_unit(scenario.get("speed_mph"), "mph"), border=True)
            st.metric(
                "Speed limit",
                _with_unit(scenario.get("speed_limit_mph"), "mph"),
                border=True,
            )
            st.metric("Actors", str(len(actors)), border=True)
        actor_counts = Counter(
            _display(actor.get("actor_type")) for actor in actors if isinstance(actor, Mapping)
        )
        if actor_counts:
            with st.container(horizontal=True, key=f"{key}_actors"):
                for actor_type, count in sorted(actor_counts.items()):
                    st.badge(
                        f"{count} {actor_type}",
                        icon=_actor_icon(actor_type),
                        color="gray",
                    )
        else:
            st.caption("No road actors are recorded in this scenario.")


def render_counterfactual_faultline(
    source: Mapping[str, object],
    changes: Sequence[Mapping[str, object]],
    follow_up: Mapping[str, object],
    *,
    key: str,
) -> None:
    """Show the source, retained mutation, and counterfactual as one visual sequence."""
    with st.container(key=key):
        st.subheader("The decision fault line")
        st.caption(
            "Read left to right. The center card is the retained change between two valid "
            "simulated scenarios."
        )
        with st.container(horizontal=True, key=f"{key}_sequence"):
            render_scenario_card("Source scenario", source, key=f"{key}_source")
            _render_mutation_card(changes, key=f"{key}_mutation")
            render_scenario_card("Counterfactual", follow_up, key=f"{key}_follow_up")


def render_evidence_pipeline(certificate: Mapping[str, object], *, key: str) -> None:
    """Render the sequential evidence stages represented by one certificate."""
    property_snapshot = _mapping(certificate.get("property"))
    property_title = str(
        property_snapshot.get("title")
        or certificate.get("property_id")
        or "Selected safety assumption"
    )
    changes = _meaningful_changes(_mappings(certificate.get("changed_fields")))
    reproduction_count = _integer(certificate.get("reproduction_count"))
    reproduction_trials = _integer(certificate.get("reproduction_trials"))
    certificate_id = str(certificate.get("certificate_id") or _UNKNOWN)

    with st.container(key=key):
        st.subheader("Evidence pipeline")
        st.caption("Each stage contributes distinct evidence to the final replayable result.")
        with st.container(horizontal=True, key=f"{key}_stages"):
            _render_pipeline_stage(
                "1",
                "Frame the assumption",
                property_title,
                color="blue",
                key=f"{key}_stage_1",
            )
            _render_pipeline_stage(
                "2",
                "Apply one controlled change",
                f"{len(changes)} retained factor change{_plural(len(changes))}",
                color="orange",
                key=f"{key}_stage_2",
            )
            _render_pipeline_stage(
                "3",
                "Repeat the decision",
                f"{reproduction_count} of {reproduction_trials} trials reproduced the failure",
                color="red",
                key=f"{key}_stage_3",
            )
            _render_pipeline_stage(
                "4",
                "Shrink and package",
                f"Replayable certificate {certificate_id}",
                color="green",
                key=f"{key}_stage_4",
            )


def render_failure_certificate(
    certificate: Mapping[str, object],
    *,
    call_ledger: Mapping[str, object] | None = None,
    key: str,
) -> None:
    """Render the high-signal result summary for one failure certificate."""
    property_snapshot = _mapping(certificate.get("property"))
    title = str(
        property_snapshot.get("title") or certificate.get("property_id") or "Safety assumption"
    )
    scope_note = str(property_snapshot.get("scope_note") or "")
    source_decision = _first_mapping(certificate.get("source_decisions"))
    follow_up_decision = _first_mapping(certificate.get("follow_up_decisions"))
    ledger = call_ledger or {}
    cost_available = bool(
        ledger.get("cost_estimate_available", certificate.get("cost_estimate_available", False))
    )
    estimated_cost = ledger.get("estimated_cost_usd", certificate.get("estimated_cost_usd", 0.0))

    with st.container(border=True, key=key):
        st.error("Reproducible decision failure found", icon=":material/gpp_bad:")
        st.subheader(title)
        if scope_note:
            st.caption(scope_note)
        st.caption(f"Certificate {certificate.get('certificate_id', _UNKNOWN)}")
        with st.container(horizontal=True, key=f"{key}_transition"):
            st.badge(
                f"Source: {_decision_label(source_decision)}",
                icon=":material/check_circle:",
                color="green",
            )
            st.badge(
                "Controlled change",
                icon=":material/arrow_forward:",
                color="orange",
            )
            st.badge(
                f"Counterfactual: {_decision_label(follow_up_decision)}",
                icon=":material/error:",
                color="red",
            )
        with st.container(horizontal=True, key=f"{key}_metrics"):
            st.metric(
                "Reruns that failed",
                f"{_integer(certificate.get('reproduction_count'))}/"
                f"{_integer(certificate.get('reproduction_trials'))}",
                border=True,
            )
            st.metric(
                "Certificate latency",
                _with_unit(certificate.get("latency_ms"), "ms"),
                border=True,
            )
            st.metric(
                "Charged target calls",
                _display(ledger.get("target_calls_total")),
                border=True,
            )
            st.metric(
                "Estimated cost",
                _format_cost(estimated_cost) if cost_available else "Unknown",
                border=True,
            )
        replay_command = certificate.get("replay_command")
        if replay_command:
            st.caption("Replay exactly")
            st.code(str(replay_command), language="shell", wrap_lines=True)
        st.caption(
            "This is minimized evidence under the declared reducer set, not a causal proof "
            "or a certification claim."
        )


def render_download_controls(
    downloads: Sequence[DownloadArtifact],
    *,
    key: str,
    heading: str = "Download evidence",
) -> None:
    """Render a responsive row of caller-prepared artifact downloads."""
    with st.container(key=key):
        st.subheader(heading)
        st.caption("Each file is portable and can be inspected outside this browser session.")
        with st.container(horizontal=True, key=f"{key}_actions"):
            for index, artifact in enumerate(downloads):
                st.download_button(
                    artifact.label,
                    artifact.data,
                    file_name=artifact.file_name,
                    mime=artifact.mime,
                    icon=artifact.icon,
                    key=f"{key}_{index}",
                )


def render_run_comparison_delta(comparison: Mapping[str, object], *, key: str) -> None:
    """Render a compact B-minus-A comparison without a dense data table."""
    runs = _mapping(comparison.get("runs"))
    certificates = _mapping(comparison.get("certificates"))
    call_totals = _mapping(comparison.get("call_totals"))
    coverage = _mapping(comparison.get("coverage"))
    trajectory_auc = _mapping(coverage.get("trajectory_auc"))
    added = _sequence(certificates.get("added"))
    removed = _sequence(certificates.get("removed"))
    cells_added = _sequence(coverage.get("cells_added"))
    cells_removed = _sequence(coverage.get("cells_removed"))

    with st.container(border=True, key=key):
        st.subheader("What changed between runs")
        st.caption(f"Run A: {runs.get('a', _UNKNOWN)} | Run B: {runs.get('b', _UNKNOWN)}")
        with st.container(horizontal=True, key=f"{key}_metrics"):
            st.metric("Failures added", str(len(added)), border=True)
            st.metric("Failures removed", str(len(removed)), border=True)
            st.metric(
                "Target calls in run B",
                _display(call_totals.get("b")),
                _signed_delta(call_totals.get("delta"), "vs run A"),
                delta_color="off",
                border=True,
            )
            st.metric(
                "Coverage AUC in run B",
                _format_number(trajectory_auc.get("b")),
                _signed_delta(trajectory_auc.get("delta"), "vs run A"),
                delta_color="off",
                border=True,
            )
        with st.container(horizontal=True, key=f"{key}_coverage"):
            st.badge(
                f"{len(cells_added)} coverage cells added",
                icon=":material/add_circle:",
                color="green",
            )
            st.badge(
                f"{len(cells_removed)} coverage cells removed",
                icon=":material/remove_circle:",
                color="orange",
            )


def render_benchmark_result(result: Mapping[str, object], *, key: str) -> None:
    """Render a benchmark summary and per-property detection status."""
    metrics = _mapping(result.get("metrics"))
    summary = _mapping(result.get("summary")) or metrics or result
    rows = _benchmark_rows(result)
    property_count = _first_integer(
        summary,
        ("property_count", "properties_tested", "total_properties"),
        fallback=len(rows),
    )
    certificate_count = _first_integer(
        summary,
        ("certificate_count", "failures_found", "reproducible_failures"),
        fallback=_detected_count(rows),
    )
    target_calls = _first_integer(summary, ("target_calls",), fallback=0)
    detection_rate = 0.0 if property_count == 0 else certificate_count / property_count

    with st.container(border=True, key=key):
        st.success("Synthetic benchmark complete", icon=":material/task_alt:")
        st.caption("Measured results from the included deterministic fixture.")
        with st.container(horizontal=True, key=f"{key}_metrics"):
            st.metric("Properties tested", str(property_count), border=True)
            st.metric("Failures detected", str(certificate_count), border=True)
            st.metric("Detection rate", f"{detection_rate:.0%}", border=True)
            st.metric("Target calls", str(target_calls), border=True)
        if rows:
            st.markdown("**Property results**")
            with st.container(horizontal=True, key=f"{key}_properties"):
                for row in rows:
                    detected = _row_detected(row)
                    label = _humanize(
                        row.get("title") or row.get("property_id") or "Property check"
                    )
                    st.badge(
                        f"{label}: {'failure detected' if detected else 'no failure detected'}",
                        icon=(":material/bug_report:" if detected else ":material/search_off:"),
                        color="red" if detected else "gray",
                    )


def render_privacy_footer(*, key: str) -> None:
    """Render the public privacy and research-scope boundary."""
    with st.container(key=key):
        with st.container(horizontal=True, key=f"{key}_badges"):
            st.badge("Simulated research only", icon=":material/science:", color="gray")
            st.badge("No file uploads", icon=":material/code_off:", color="green")
            st.badge("No remote model calls", icon=":material/cloud_off:", color="blue")
        st.caption(
            "The hosted app accepts no file uploads. Pasted evidence text is parsed as inert "
            "data and never retained. The app contacts no remote endpoint. Safety assumptions "
            "remain editable operational checks, not "
            "universal laws or certification claims."
        )


def _render_mutation_card(
    changes: Sequence[Mapping[str, object]],
    *,
    key: str,
) -> None:
    retained = _meaningful_changes(changes)
    with st.container(border=True, key=key):
        st.badge(
            "Controlled mutation",
            icon=":material/difference:",
            color="orange",
        )
        if not retained:
            st.caption("No retained factor change was recorded.")
        for change in retained:
            st.metric(
                _humanize(change.get("path")),
                _display(change.get("to_value")),
                f"From {_display(change.get('from_value'))}",
                delta_color="off",
                border=True,
            )
        st.caption(
            "The scenario identifier changes with every follow-up scenario and is not "
            "counted as a tested factor."
        )


def _render_pipeline_stage(
    number: str,
    title: str,
    detail: str,
    *,
    color: BadgeColor,
    key: str,
) -> None:
    with st.container(border=True, key=key):
        st.badge(f"Stage {number}", color=color)
        st.markdown(f"**{title}**")
        st.caption(detail)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> list[Mapping[str, object]]:
    return [item for item in _sequence(value) if isinstance(item, Mapping)]


def _sequence(value: object) -> list[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _first_mapping(value: object) -> Mapping[str, object]:
    items = _mappings(value)
    return items[0] if items else {}


def _meaningful_changes(
    changes: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    meaningful = [change for change in changes if change.get("path") != "scenario_id"]
    return meaningful or list(changes)


def _humanize(value: object) -> str:
    return str(value or _UNKNOWN).replace("_", " ").replace(".", " / ")


def _display(value: object) -> str:
    if value is None:
        return _UNKNOWN
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, str):
        return value.replace("_", " ")
    if isinstance(value, (Mapping, Sequence)) and not isinstance(value, (bytes, bytearray)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return str(value)


def _with_unit(value: object, unit: str) -> str:
    displayed = _display(value)
    return displayed if displayed == _UNKNOWN else f"{displayed} {unit}"


def _surface_icon(value: object) -> str:
    surface = str(value or "").casefold()
    if any(term in surface for term in ("wet", "rain", "puddle", "flood")):
        return ":material/water_drop:"
    if any(term in surface for term in ("snow", "ice", "icy", "frost", "slush")):
        return ":material/ac_unit:"
    if "dry" in surface:
        return ":material/wb_sunny:"
    return ":material/texture:"


def _visibility_icon(value: object) -> str:
    visibility = str(value or "").casefold()
    if any(term in visibility for term in ("fog", "mist", "smoke", "haze", "reduced")):
        return ":material/foggy:"
    if any(term in visibility for term in ("occluded", "blocked", "blind")):
        return ":material/visibility_off:"
    if any(term in visibility for term in ("night", "dark", "dusk", "dawn")):
        return ":material/dark_mode:"
    return ":material/visibility:"


def _actor_icon(value: object) -> str:
    actor = str(value or "").casefold()
    if any(term in actor for term in ("vehicle", "car", "truck", "bus", "auto", "van")):
        return ":material/directions_car:"
    if any(term in actor for term in ("bike", "bicycle", "cyclist", "motorcycle", "scooter")):
        return ":material/two_wheeler:"
    if any(term in actor for term in ("pedestrian", "walker", "person", "child")):
        return ":material/directions_walk:"
    if any(term in actor for term in ("hazard", "obstacle", "debris", "cone", "barrier")):
        return ":material/warning:"
    return ":material/directions_walk:"


def _signal_color(value: object) -> BadgeColor:
    signal = str(value).casefold()
    if signal == "red":
        return "red"
    if signal == "yellow":
        return "orange"
    if signal == "green":
        return "green"
    return "gray"


def _integer(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _number(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _format_number(value: object) -> str:
    number = _number(value)
    return f"{number:,.1f}" if not number.is_integer() else f"{int(number):,}"


def _signed_delta(value: object, suffix: str) -> str:
    number = _number(value)
    formatted = f"{number:+.1f}" if not number.is_integer() else f"{int(number):+d}"
    return f"{formatted} {suffix}"


def _format_cost(value: object) -> str:
    return f"${_number(value):.6f}"


def _decision_label(decision: Mapping[str, object]) -> str:
    action = _display(decision.get("action"))
    risk = _display(decision.get("risk"))
    return f"{action}, {risk} risk"


def _plural(count: int) -> str:
    return "" if count == 1 else "s"


def _benchmark_rows(result: Mapping[str, object]) -> list[Mapping[str, object]]:
    for field in ("results", "properties", "property_results"):
        rows = _mappings(result.get(field))
        if rows:
            return rows
    metrics = _mapping(result.get("metrics"))
    rates = _mapping(metrics.get("per_property_reproduction_rates"))
    if rates:
        rows = []
        for property_id, value in rates.items():
            rate = _mapping(value)
            rows.append(
                {
                    "property_id": property_id,
                    "detected": _integer(rate.get("reproductions")) > 0,
                }
            )
        return rows
    return []


def _row_detected(row: Mapping[str, object]) -> bool:
    if "detected" in row:
        return bool(row["detected"])
    if "certificate_count" in row:
        return _integer(row["certificate_count"]) > 0
    return str(row.get("status", "")).casefold() in {
        "detected",
        "failure",
        "failed",
        "reproduced",
    }


def _detected_count(rows: Sequence[Mapping[str, object]]) -> int:
    return sum(_row_detected(row) for row in rows)


def _first_integer(
    values: Mapping[str, object],
    fields: Sequence[str],
    *,
    fallback: int,
) -> int:
    for field in fields:
        if field in values:
            return _integer(values[field])
    return fallback


def _first_number(
    values: Mapping[str, object],
    fields: Sequence[str],
    *,
    fallback: float,
) -> float:
    for field in fields:
        if field in values:
            return _number(values[field])
    return fallback
