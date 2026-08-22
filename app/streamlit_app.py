"""No-key public demonstration for simulated EdgeCase Atlas research."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Mapping, Sequence
from typing import cast

import streamlit as st
from app.ui import (
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

from edgecase_atlas import __version__
from edgecase_atlas.fixtures import known_violation_cases
from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.serialization import canonical_json

_PUBLIC_RUN_SLOTS = threading.BoundedSemaphore(2)

st.set_page_config(
    page_title="EdgeCase Atlas",
    page_icon=":material/experiment:",
    layout="wide",
    initial_sidebar_state="auto",
)


def _scenario_rows(scenario: Mapping[str, object]) -> list[dict[str, object]]:
    return [
        {"Field": "Road type", "Value": scenario.get("road_type", "unknown")},
        {"Field": "Speed", "Value": f"{scenario.get('speed_mph', 'unknown')} mph"},
        {
            "Field": "Speed limit",
            "Value": f"{scenario.get('speed_limit_mph', 'unknown')} mph",
        },
        {"Field": "Signal", "Value": scenario.get("signal", "unknown")},
        {"Field": "Surface", "Value": scenario.get("surface", "unknown")},
        {"Field": "Visibility", "Value": scenario.get("visibility", "unknown")},
        {
            "Field": "Actors",
            "Value": str(len(cast(Sequence[object], scenario.get("actors", ())))),
        },
    ]


def _render_scenario(label: str, scenario: Mapping[str, object], *, key: str) -> None:
    with st.container(border=True):
        st.subheader(label)
        st.caption(str(scenario.get("description", "No description available.")))
        st.dataframe(
            _scenario_rows(scenario),
            hide_index=True,
            key=key,
            column_config={
                "Field": st.column_config.TextColumn("Field"),
                "Value": st.column_config.TextColumn("Value"),
            },
        )


def _render_downloads(artifacts: DemoArtifacts, run_id: str) -> None:
    st.subheader("Download research artifacts")
    with st.container(horizontal=True):
        st.download_button(
            "Download JSON",
            artifacts.json_bytes,
            file_name=f"{run_id}.json",
            mime="application/json",
            icon=":material/download:",
            key="atlas_download_json",
        )
        st.download_button(
            "Download JSONL trace",
            artifacts.jsonl_bytes,
            file_name=f"{run_id}.jsonl",
            mime="application/x-ndjson",
            icon=":material/download:",
            key="atlas_download_jsonl",
        )
        st.download_button(
            "Download HTML report",
            artifacts.html_bytes,
            file_name=f"{run_id}.html",
            mime="text/html",
            icon=":material/download:",
            key="atlas_download_html",
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

    st.success(f"{title} {detail}", icon=":material/check_circle:")
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
            help="Each selected assumption can produce a separate reproducible certificate.",
        )
    certificate = certificates[certificate_index]
    property_snapshot = cast(Mapping[str, object], certificate["property"])
    st.subheader(str(property_snapshot["title"]))
    st.caption(str(property_snapshot["scope_note"]))

    with st.container(horizontal=True):
        _render_scenario(
            "Source scenario",
            cast(Mapping[str, object], certificate["source"]),
            key="atlas_source_scenario",
        )
        _render_scenario(
            "Minimized follow-up",
            cast(Mapping[str, object], certificate["minimized_follow_up"]),
            key="atlas_follow_up_scenario",
        )

    st.subheader("Canonical retained changes")
    changes = cast(Sequence[Mapping[str, object]], certificate["changed_fields"])
    st.dataframe(
        [
            {
                "Field": change["path"],
                "Source value": canonical_json(change["from_value"]),
                "Follow-up value": canonical_json(change["to_value"]),
            }
            for change in changes
        ],
        hide_index=True,
        key="atlas_changed_fields",
    )

    cost_display = (
        f"${cast(float, ledger['estimated_cost_usd']):.6f}"
        if ledger.get("cost_estimate_available") is True
        else "Unknown"
    )
    with st.container(horizontal=True):
        st.metric(
            "Reproduction",
            f"{certificate['reproduction_count']}/{certificate['reproduction_trials']}",
            border=True,
        )
        st.metric("Charged target calls", cast(int, ledger["target_calls_total"]), border=True)
        st.metric("Estimated cost", cost_display, border=True)
        st.metric("Certificate latency", f"{certificate['latency_ms']} ms", border=True)

    trajectory = cast(Sequence[Mapping[str, object]], coverage["trajectory"])
    st.subheader("Observed coverage by charged target call")
    if trajectory:
        st.line_chart(
            trajectory,
            x="charged_target_calls",
            y="observed_cells",
            x_label="Charged target calls",
            y_label="Observed coverage cells",
        )
    else:
        st.caption("No coverage points were recorded for this run.")

    distribution = cast(Mapping[str, Mapping[str, int]], certificate["output_distribution"])
    with st.container(horizontal=True):
        with st.container(border=True):
            st.subheader("Action distribution")
            st.bar_chart(
                [
                    {"Action": label, "Count": count}
                    for label, count in distribution["actions"].items()
                ],
                x="Action",
                y="Count",
                horizontal=True,
            )
        with st.container(border=True):
            st.subheader("Risk distribution")
            st.bar_chart(
                [{"Risk": label, "Count": count} for label, count in distribution["risks"].items()],
                x="Risk",
                y="Count",
                horizontal=True,
            )

    st.subheader("Replay command")
    st.code(str(certificate["replay_command"]), language="shell", wrap_lines=True)
    st.caption(
        "This certificate is local 1-minimal under the declared reducer set. "
        "It is not a causal proof or a global-smallest claim."
    )
    _render_downloads(artifacts, run_id)


st.session_state.setdefault("atlas_run_status", "empty")
st.session_state.setdefault("atlas_run_artifacts", None)
st.session_state.setdefault("atlas_run_error", None)

with st.sidebar:
    st.subheader("Demonstration settings")
    st.selectbox(
        "Agent adapter",
        options=(PUBLIC_ADAPTER_ID,),
        format_func=lambda _value: "Faulty fixture (no API key)",
        key="atlas_adapter_input",
        help="Hosted mode permits only the included deterministic synthetic fixture.",
    )
    st.caption(f"EdgeCase Atlas {__version__}")
    st.caption("Five editable operational assumptions. Synthetic content only.")

st.title("EdgeCase Atlas")
st.caption(
    "Property-based counterfactual testing for simulated research and debugging. "
    "Not vehicle control, certification, or legal compliance."
)
st.info(
    "This hosted demonstration accepts no files, endpoints, subprocesses, or code. "
    "Inputs and results stay in this browser session and are not collected.",
    icon=":material/privacy_tip:",
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

with st.form("atlas_demo_form", border=True):
    st.subheader("Configure one bounded demonstration")
    sample_property_id = st.selectbox(
        "Curated synthetic example",
        options=tuple(curated_cases),
        format_func=lambda value: property_titles[value],
        key="atlas_sample_input",
        help=(
            "Preview a newly authored synthetic pair. "
            "Its matching assumption is run first within the selected budget."
        ),
    )
    selected_property_ids = st.multiselect(
        "Safety assumptions",
        options=tuple(property_titles),
        default=("red_signal_no_proceed",),
        format_func=lambda value: property_titles[value],
        key="atlas_properties_input",
        help="These are editable operational assumptions, not universal safety laws.",
    )
    with st.container(horizontal=True):
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
            help="Public runs are capped at 5 generated candidates.",
        )
    custom_text = st.text_area(
        "Optional synthetic scenario context",
        max_chars=PUBLIC_TEXT_MAX_CHARS,
        key="atlas_context_input",
        help=(
            "Stored only in your downloaded run artifact as session context. "
            "It is never executed or sent to a remote service."
        ),
    )
    submitted = st.form_submit_button(
        "Run demonstration",
        type="primary",
        icon=":material/play_arrow:",
        key="atlas_run_submit",
    )

preview = curated_cases[sample_property_id]
with st.expander("Preview the curated synthetic pair", icon=":material/compare_arrows:"):
    with st.container(horizontal=True):
        _render_scenario(
            "Source scenario",
            preview.counterfactual.source.model_dump(mode="json"),
            key="atlas_preview_source",
        )
        _render_scenario(
            "Follow-up scenario",
            preview.counterfactual.follow_up.model_dump(mode="json"),
            key="atlas_preview_follow_up",
        )

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
            with st.status(
                running_title,
                expanded=True,
                state="running",
            ) as run_status:
                st.write(running_detail)
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
                run_status.update(label="Demonstration complete", state="complete", expanded=False)
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
    empty_title, empty_detail = status_copy("empty")
    st.info(f"{empty_title} {empty_detail}", icon=":material/science:")
elif current_status == "input_error":
    input_title, input_detail = status_copy("input_error")
    st.error(f"{input_title} {input_detail}", icon=":material/warning:")
elif current_status == "adapter_error":
    error_title, error_detail = status_copy("adapter_error")
    st.error(f"{error_title} {error_detail}", icon=":material/error:")
elif stored_artifacts is not None:
    _render_results(cast(DemoArtifacts, stored_artifacts))
