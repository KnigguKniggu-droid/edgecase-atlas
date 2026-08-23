"""No-key public demonstration for simulated EdgeCase Atlas research."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Mapping, Sequence
from typing import Literal, cast

import streamlit as st

from edgecase_atlas import __version__
from edgecase_atlas.fixtures import known_violation_cases
from edgecase_atlas.models import Counterfactual
from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.serialization import canonical_json
from theme import APP_CSS
from ui import (
    PUBLIC_ADAPTER_ID,
    PUBLIC_BUDGET_MAX,
    PUBLIC_BUDGET_MIN,
    PUBLIC_SEED_MAX,
    PUBLIC_TEXT_MAX_CHARS,
    PUBLIC_TIMEOUT_SECONDS,
    DemoArtifacts,
    RunStatus,
    build_demo_artifacts,
    claim_public_run,
    status_copy,
    validate_public_request,
)

_PUBLIC_RUN_SLOTS = threading.BoundedSemaphore(2)

st.set_page_config(
    page_title="EdgeCase Atlas",
    page_icon="\U0001F9ED",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get help": "https://github.com/KnigguKniggu-droid/edgecase-atlas/issues",
        "Report a bug": "https://github.com/KnigguKniggu-droid/edgecase-atlas/issues/new",
        "About": "EdgeCase Atlas v0.1. Constraint-guided counterfactual testing.",
    },
)
st.html(APP_CSS)


def _humanize(value: object) -> str:
    return str(value).replace("_", " ")


def _scenario_rows(scenario: Mapping[str, object]) -> list[dict[str, object]]:
    return [
        {"Field": "Road type", "Value": _humanize(scenario.get("road_type", "unknown"))},
        {"Field": "Speed", "Value": f"{scenario.get('speed_mph', 'unknown')} mph"},
        {
            "Field": "Speed limit",
            "Value": f"{scenario.get('speed_limit_mph', 'unknown')} mph",
        },
        {"Field": "Signal", "Value": _humanize(scenario.get("signal", "unknown"))},
        {"Field": "Surface", "Value": _humanize(scenario.get("surface", "unknown"))},
        {"Field": "Visibility", "Value": _humanize(scenario.get("visibility", "unknown"))},
        {
            "Field": "Actors",
            "Value": str(len(cast(Sequence[object], scenario.get("actors", ())))),
        },
    ]


def _render_scenario(label: str, scenario: Mapping[str, object], *, key: str) -> None:
    with st.container(key=key):
        st.badge(label, icon=":material/route:", color="gray")
        st.markdown(f"**{scenario.get('description', 'No description available.')}**")
        st.table(
            _scenario_rows(scenario),
            border="horizontal",
            width="stretch",
            hide_index=True,
            hide_header=True,
        )


def _meaningful_changes(changes: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    meaningful = [change for change in changes if change.get("path") != "scenario_id"]
    return meaningful or list(changes)


def _render_mutation(changes: Sequence[Mapping[str, object]], *, key: str) -> None:
    with st.container(key=key, vertical_alignment="center"):
        st.badge("Controlled mutation", icon=":material/difference:", color="orange")
        for change in _meaningful_changes(changes):
            st.code(
                f"{_humanize(change['path'])}\n"
                f"{_humanize(change['from_value'])}  ->  {_humanize(change['to_value'])}",
                language=None,
                wrap_lines=True,
            )


def _render_preview(counterfactual: Counterfactual) -> None:
    source = cast(Mapping[str, object], counterfactual.source.model_dump(mode="json"))
    follow_up = cast(Mapping[str, object], counterfactual.follow_up.model_dump(mode="json"))
    changes = cast(
        Sequence[Mapping[str, object]],
        [item.model_dump(mode="json") for item in counterfactual.changed_fields],
    )
    source_column, mutation_column, follow_column = st.columns(
        [1.15, 0.72, 1.15], vertical_alignment="center"
    )
    with source_column:
        _render_scenario("Source", source, key="atlas_source_panel")
    with mutation_column:
        _render_mutation(changes, key="atlas_mutation_panel")
    with follow_column:
        _render_scenario("Counterfactual", follow_up, key="atlas_follow_panel")


def _render_downloads(artifacts: DemoArtifacts, run_id: str) -> None:
    st.subheader("Portable evidence")
    st.caption("Every format is self-contained and can be reproduced outside this browser session.")
    with st.container(horizontal=True, key="atlas_downloads"):
        st.download_button(
            "JSON certificate",
            artifacts.json_bytes,
            file_name=f"{run_id}.json",
            mime="application/json",
            icon=":material/data_object:",
            key="atlas_download_json",
        )
        st.download_button(
            "JSONL trace",
            artifacts.jsonl_bytes,
            file_name=f"{run_id}.jsonl",
            mime="application/x-ndjson",
            icon=":material/format_list_bulleted:",
            key="atlas_download_jsonl",
        )
        st.download_button(
            "Offline HTML report",
            artifacts.html_bytes,
            file_name=f"{run_id}.html",
            mime="text/html",
            icon=":material/article:",
            key="atlas_download_html",
        )


def _render_decision(
    label: str,
    decision: Mapping[str, object],
    *,
    key: str,
    badge_color: Literal["green", "red"],
) -> None:
    with st.container(key=key):
        st.badge(label, icon=":material/psychology:", color=badge_color)
        st.subheader(_humanize(decision["action"]).upper())
        st.markdown(f"Risk assessment: **{_humanize(decision['risk'])}**")
        st.caption(str(decision.get("explanation", "No explanation supplied.")))


def _render_faultline(certificate: Mapping[str, object]) -> None:
    source_decisions = cast(Sequence[Mapping[str, object]], certificate["source_decisions"])
    follow_decisions = cast(Sequence[Mapping[str, object]], certificate["follow_up_decisions"])
    changes = cast(Sequence[Mapping[str, object]], certificate["changed_fields"])
    with st.container(key="atlas_faultline"):
        st.subheader("The fault line")
        st.caption(
            "Atlas reduced the failure to the retained field change below, then reproduced it."
        )
        source_column, delta_column, failure_column = st.columns(
            [1, 0.78, 1], vertical_alignment="top"
        )
        with source_column:
            _render_decision(
                "Source decision",
                source_decisions[0],
                key="atlas_source_decision",
                badge_color="green",
            )
        with delta_column:
            _render_mutation(changes, key="atlas_delta")
        with failure_column:
            _render_decision(
                "Failing decision",
                follow_decisions[0],
                key="atlas_failure_decision",
                badge_color="red",
            )


def _render_evidence_tab(certificate: Mapping[str, object], coverage: Mapping[str, object]) -> None:
    st.subheader("Retained changes")
    changes = cast(Sequence[Mapping[str, object]], certificate["changed_fields"])
    st.dataframe(
        [
            {
                "Field": _humanize(change["path"]),
                "Source value": canonical_json(change["from_value"]),
                "Follow-up value": canonical_json(change["to_value"]),
            }
            for change in changes
        ],
        hide_index=True,
        key="atlas_changed_fields",
    )

    trajectory = cast(Sequence[Mapping[str, object]], coverage["trajectory"])
    st.subheader("Coverage by charged target call")
    if trajectory:
        st.line_chart(
            trajectory,
            x="charged_target_calls",
            y="observed_cells",
            x_label="Charged target calls",
            y_label="Observed coverage cells",
            color="#66D9D0",
        )
    else:
        st.caption("No coverage points were recorded for this run.")


def _render_distributions_tab(certificate: Mapping[str, object]) -> None:
    distribution = cast(Mapping[str, Mapping[str, int]], certificate["output_distribution"])
    action_column, risk_column = st.columns(2)
    with action_column:
        st.subheader("Action distribution")
        st.bar_chart(
            [
                {"Action": _humanize(label), "Count": count}
                for label, count in distribution["actions"].items()
            ],
            x="Action",
            y="Count",
            horizontal=True,
            color="#66D9D0",
        )
    with risk_column:
        st.subheader("Risk distribution")
        st.bar_chart(
            [
                {"Risk": _humanize(label), "Count": count}
                for label, count in distribution["risks"].items()
            ],
            x="Risk",
            y="Count",
            horizontal=True,
            color="#E4544B",
        )


def _render_scenarios_tab(certificate: Mapping[str, object]) -> None:
    source_column, follow_column = st.columns(2)
    with source_column:
        _render_scenario(
            "Full source scenario",
            cast(Mapping[str, object], certificate["source"]),
            key="atlas_result_source_scenario",
        )
    with follow_column:
        _render_scenario(
            "Minimized follow-up",
            cast(Mapping[str, object], certificate["minimized_follow_up"]),
            key="atlas_result_follow_scenario",
        )


def _render_results(artifacts: DemoArtifacts) -> None:
    document = artifacts.document
    metadata = cast(Mapping[str, object], document["metadata"])
    ledger = cast(Mapping[str, object], document["call_ledger"])
    coverage = cast(Mapping[str, object], document["coverage"])
    certificates = cast(Sequence[Mapping[str, object]], document["certificates"])
    run_id = str(metadata["run_id"])

    title, detail = status_copy("success" if certificates else "no_failure")
    if not certificates:
        st.warning(f"{title} {detail}", icon=":material/search_off:")
        st.caption(f"Run ID: {run_id}")
        _render_downloads(artifacts, run_id)
        return

    with st.container(key="atlas_violation_banner"):
        st.error(f"{title} {detail}", icon=":material/gpp_bad:")
        st.caption(f"Run {run_id} | deterministic public fixture | no API key")

    certificate_index = 0
    if len(certificates) > 1:
        certificate_index = st.selectbox(
            "Failure certificate",
            options=range(len(certificates)),
            format_func=lambda index: (
                f"{cast(Mapping[str, object], certificates[index]['property'])['title']} "
                f"({certificates[index]['certificate_id']})"
            ),
            key="atlas_certificate_input",
            help="Inspect each independently reproduced property violation.",
        )
    certificate = certificates[certificate_index]
    property_snapshot = cast(Mapping[str, object], certificate["property"])
    st.subheader(str(property_snapshot["title"]))
    st.caption(str(property_snapshot["scope_note"]))

    _render_faultline(certificate)

    cost_display = (
        f"${cast(float, ledger['estimated_cost_usd']):.6f}"
        if ledger.get("cost_estimate_available") is True
        else "Unknown"
    )
    metric_columns = st.columns(4)
    with metric_columns[0]:
        st.metric(
            "Reproduction",
            f"{certificate['reproduction_count']}/{certificate['reproduction_trials']}",
            border=True,
        )
    with metric_columns[1]:
        st.metric("Charged target calls", cast(int, ledger["target_calls_total"]), border=True)
    with metric_columns[2]:
        st.metric("Estimated cost", cost_display, border=True)
    with metric_columns[3]:
        st.metric("Certificate latency", f"{certificate['latency_ms']} ms", border=True)

    evidence_tab, outputs_tab, scenarios_tab = st.tabs(
        [
            ":material/biotech: Evidence",
            ":material/monitoring: Repeated outputs",
            ":material/route: Full scenarios",
        ]
    )
    with evidence_tab:
        _render_evidence_tab(certificate, coverage)
    with outputs_tab:
        _render_distributions_tab(certificate)
    with scenarios_tab:
        _render_scenarios_tab(certificate)

    st.subheader("Replay exactly")
    st.code(str(certificate["replay_command"]), language="shell", wrap_lines=True)
    st.caption(
        "This certificate is local 1-minimal under the declared reducer set. "
        "It is not a causal proof or a global-smallest claim."
    )
    _render_downloads(artifacts, run_id)


st.session_state.setdefault("atlas_run_status", "empty")
st.session_state.setdefault("atlas_run_artifacts", None)
st.session_state.setdefault("atlas_run_error", None)

with st.container(key="atlas_hero"):
    with st.container(key="atlas_brandline"):
        st.markdown(f"EDGECASE ATLAS / ALPHA {__version__} / SYNTHETIC RESEARCH MODE")
    st.title("EdgeCase Atlas")
    with st.container(key="atlas_thesis"):
        st.markdown("Find the one scenario change that breaks an AI driving decision.")
    st.caption(
        "For simulated research: generate valid counterfactuals, rerun stochastic failures, "
        "shrink the evidence, "
        "and export a replayable certificate."
    )
    with st.container(horizontal=True):
        st.badge("No API key", icon=":material/key_off:", color="green")
        st.badge("Deterministic fixture", icon=":material/replay:", color="blue")
        st.badge("Simulated only", icon=":material/science:", color="gray")
    with st.container(key="atlas_process"):
        st.caption("EVIDENCE PIPELINE")
        with st.container(horizontal=True, key="atlas_process_steps"):
            st.badge("01 GENERATE", color="blue")
            st.badge("02 REPEAT 5x", color="gray")
            st.badge("03 SHRINK", color="orange")
            st.badge("04 REPLAY", color="green")

with st.container(key="atlas_workbench_title"):
    st.header("Counterfactual workbench")
    st.caption(
        "Choose an operational assumption and inspect the controlled pair before running it."
    )

property_titles = {item.property_id: item.title for item in STARTER_PROPERTY_PACK}
curated_cases = {item.property_id: item for item in known_violation_cases()}
default_sample_property_id = next(iter(curated_cases))
stored_sample_property_id = st.session_state.get("atlas_sample_input")
sample_state_was_reset = stored_sample_property_id is not None and not (
    isinstance(stored_sample_property_id, str) and stored_sample_property_id in curated_cases
)
if sample_state_was_reset:
    st.session_state["atlas_sample_input"] = default_sample_property_id
    st.warning(
        "The curated example selection was reset to a safe default.",
        icon=":material/shield:",
    )

control_column, specimen_column = st.columns([0.86, 1.44], vertical_alignment="top")
with control_column:
    with st.container(key="atlas_controls"):
        st.subheader("Configure the test")
        st.badge("Faulty fixture", icon=":material/bug_report:", color="orange")
        st.caption(
            "A synthetic flawed benchmark agent enables deterministic, key-free testing."
        )
        st.selectbox(
            "Agent adapter",
            options=(PUBLIC_ADAPTER_ID,),
            format_func=lambda _value: "Faulty fixture (no API key)",
            key="atlas_adapter_input",
            help="Hosted mode permits only the included deterministic synthetic fixture.",
            disabled=True,
        )
        sample_property_id = st.selectbox(
            "Curated synthetic example",
            options=tuple(curated_cases),
            format_func=lambda value: property_titles[value],
            key="atlas_sample_input",
            help="Changing this selection immediately updates the pair on the right.",
        )
        selected_property_ids = st.multiselect(
            "Safety assumptions",
            options=tuple(property_titles),
            default=("red_signal_no_proceed",),
            format_func=lambda value: property_titles[value],
            key="atlas_properties_input",
            help="Editable operational assumptions, not universal safety laws.",
        )
        with st.expander("Run controls", icon=":material/tune:"):
            seed = st.number_input(
                "Seed",
                min_value=0,
                max_value=PUBLIC_SEED_MAX,
                value=42,
                step=1,
                key="atlas_seed_input",
            )
            budget = st.number_input(
                "Test budget",
                min_value=PUBLIC_BUDGET_MIN,
                max_value=PUBLIC_BUDGET_MAX,
                value=1,
                step=1,
                key="atlas_budget_input",
                help="Public runs are capped at five generated candidates.",
            )
            custom_text = st.text_area(
                "Optional synthetic scenario context",
                max_chars=PUBLIC_TEXT_MAX_CHARS,
                key="atlas_context_input",
                help="Stored only in your downloaded artifact. Never executed or sent remotely.",
            )
        submitted = st.button(
            "Run counterfactual test",
            type="primary",
            icon=":material/radar:",
            key="atlas_run_submit",
        )
        st.caption("Five reruns | 4-of-5 reproduction gate | 30 second hosted limit")

with specimen_column:
    with st.container(key="atlas_specimen"):
        st.subheader("Controlled scenario pair")
        st.caption(
            "Only the declared mutation should change. Atlas validates the pair before testing."
        )
        preview = curated_cases[sample_property_id]
        _render_preview(preview.counterfactual)

if submitted:
    try:
        request = validate_public_request(
            property_ids=selected_property_ids,
            sample_property_id=sample_property_id,
            seed=seed,
            budget=budget,
            custom_text=custom_text,
        )
    except ValueError:
        st.session_state["atlas_run_artifacts"] = None
        st.session_state["atlas_run_status"] = "input_error"
        st.session_state["atlas_run_error"] = None
    else:
        try:
            st.session_state["atlas_run_status"] = "running"
            st.session_state["atlas_run_error"] = None
            running_title, running_detail = status_copy("running")
            with st.status(running_title, expanded=True, state="running") as run_status:
                st.write(running_detail)
                st.write("Validating operational constraints")
                if not claim_public_run():
                    raise RuntimeError("Public demonstration rate limit reached")
                if not _PUBLIC_RUN_SLOTS.acquire(blocking=False):
                    raise RuntimeError("Public demonstration is busy")
                try:
                    artifacts = asyncio.run(
                        asyncio.wait_for(build_demo_artifacts(request), PUBLIC_TIMEOUT_SECONDS)
                    )
                finally:
                    _PUBLIC_RUN_SLOTS.release()
                run_status.update(
                    label="Certificate assembled",
                    state="complete",
                    expanded=False,
                )
            st.session_state["atlas_run_artifacts"] = artifacts
            st.session_state["atlas_run_status"] = (
                "success" if artifacts.run.certificates else "no_failure"
            )
        except Exception:
            st.session_state["atlas_run_artifacts"] = None
            st.session_state["atlas_run_status"] = "adapter_error"
            st.session_state["atlas_run_error"] = None

current_status = cast(RunStatus, st.session_state["atlas_run_status"])
stored_artifacts = st.session_state["atlas_run_artifacts"]
if current_status == "empty":
    with st.container(key="atlas_empty_state"):
        st.info(
            "Ready. Inspect the controlled pair above, then run the no-key test.",
            icon=":material/radar:",
        )
elif current_status == "input_error":
    input_title, input_detail = status_copy("input_error")
    st.error(f"{input_title} {input_detail}", icon=":material/warning:")
elif current_status == "adapter_error":
    error_title, error_detail = status_copy("adapter_error")
    st.error(f"{error_title} {error_detail}", icon=":material/error:")
elif stored_artifacts is not None:
    _render_results(cast(DemoArtifacts, stored_artifacts))

with st.container(key="atlas_footer"):
    st.caption(
        "EdgeCase Atlas tests structured simulated decisions. It does not control vehicles, "
        "certify safety, establish legal compliance, or prove real-world causality. "
        "No uploads, endpoints, code execution, personal data collection, or remote model calls."
    )
