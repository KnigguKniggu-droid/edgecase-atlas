"""Outcome-first home page for the public product."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, cast

import streamlit as st

from edgecase_atlas.fixtures import known_violation_cases
from edgecase_atlas.properties import STARTER_PROPERTY_PACK

if TYPE_CHECKING:
    # Annotation only. Keeping this out of the runtime import graph narrows what this page
    # needs from the installed package, which the hosted environment resolves separately
    # from the app files it serves straight out of the repository.
    from edgecase_atlas.models import Counterfactual
from product_ui import (
    DownloadArtifact,
    render_counterfactual_faultline,
    render_download_controls,
    render_evidence_pipeline,
    render_failure_certificate,
    render_privacy_footer,
)
from runtime import PublicRunUnavailable, execute_public_demo
from ui import DemoArtifacts, validate_public_request


def _counterfactual_payload(
    counterfactual: Counterfactual,
) -> tuple[
    Mapping[str, object],
    Sequence[Mapping[str, object]],
    Mapping[str, object],
]:
    source = cast(Mapping[str, object], counterfactual.source.model_dump(mode="json"))
    changes = cast(
        Sequence[Mapping[str, object]],
        [change.model_dump(mode="json") for change in counterfactual.changed_fields],
    )
    follow_up = cast(Mapping[str, object], counterfactual.follow_up.model_dump(mode="json"))
    return source, changes, follow_up


with st.container(key="atlas_home_hero"):
    st.caption("AI DECISION SAFETY / LIVE SYNTHETIC DEMONSTRATION")
    st.header("Catch the decision change before it becomes a driving failure.")
    st.markdown(
        "EdgeCase Atlas makes one controlled change to a scenario, reruns the agent, "
        "and reduces a repeatable failure into evidence another developer can replay."
    )
    with st.container(horizontal=True, key="atlas_home_trust"):
        st.badge("No API key", color="green")
        st.badge("No uploaded code", color="gray")
        st.badge("Five reruns", color="blue")
        st.badge("Replayable evidence", color="orange")

with st.container(horizontal=True, vertical_alignment="center", key="atlas_home_action"):
    run_live = st.button(
        "Run the live safety break",
        type="primary",
        icon=":material/play_arrow:",
        key="atlas_home_run",
    )
    st.caption("One click runs the real engine against the included synthetic flawed agent.")

case = next(item for item in known_violation_cases() if item.property_id == "red_signal_no_proceed")
source, changes, follow_up = _counterfactual_payload(case.counterfactual)
tested_property = next(
    item for item in STARTER_PROPERTY_PACK if item.property_id == case.property_id
)

# The gate is written as text rather than imported from edgecase_atlas.properties. Files under
# app deploy live from the repository while the hosted environment installs the package, so an
# app module must never import a symbol added in the same commit. Drift is caught instead by
# test_home_causal_chain_states_only_values_read_from_the_fixture, which compares this copy
# against REQUIRED_REPRODUCTIONS and CONFIRMATION_TRIALS.
GATE_SUMMARY = "at least 4 of 5 reruns"
GATE_TILE = "4/5"

# Nothing about the outcome is stated in advance, because the run below has not happened yet.
with st.container(key="atlas_home_chain"):
    st.caption("THE CAUSAL EVIDENCE PIPELINE")
    st.markdown(
        "**1. Source scenario** &rarr; **2. One controlled change** &rarr; "
        "**3. Decision change** &rarr; **4. Repeated evidence** &rarr; "
        "**5. Replayable certificate**"
    )
    st.caption(
        f"The assumption under test is: {tested_property.title}. Atlas changes one field below, "
        f"holds every other factor constant, and accepts a failure only when it reproduces in "
        f"{GATE_SUMMARY}."
    )

if run_live:
    request = validate_public_request(
        property_ids=("red_signal_no_proceed",),
        sample_property_id="red_signal_no_proceed",
        seed=42,
        budget=1,
        custom_text="",
    )
    try:
        with st.status("Testing the controlled change", expanded=True) as status:
            st.write("Generate a valid pair")
            st.write("Repeat the decisions five times")
            st.write("Shrink retained factors")
            artifacts = execute_public_demo(request)
            status.update(label="Replayable evidence assembled", state="complete", expanded=False)
    except PublicRunUnavailable:
        st.error("The public demonstration is busy. Retry in a moment.")
    else:
        st.session_state["atlas_home_artifacts"] = artifacts

stored = st.session_state.get("atlas_home_artifacts")

# Illustrative pair, shown only until a real run produces its own. Leaving it up after a
# run would put a scenario pair above a certificate that did not come from it.
if not isinstance(stored, DemoArtifacts):
    render_counterfactual_faultline(source, changes, follow_up, key="atlas_home_faultline")
if isinstance(stored, DemoArtifacts):
    document = stored.document
    certificates = cast(Sequence[Mapping[str, object]], document["certificates"])
    if certificates:
        certificate = certificates[0]
        st.error(
            f"Reproducible failure found. The red-signal decision was wrong in {GATE_SUMMARY}.",
            icon=":material/gpp_bad:",
        )
        # The pair this certificate was actually built from, not the illustrative fixture.
        render_counterfactual_faultline(
            cast(Mapping[str, object], certificate["source"]),
            cast(Sequence[Mapping[str, object]], certificate["changed_fields"]),
            cast(Mapping[str, object], certificate["minimized_follow_up"]),
            key="atlas_home_result_faultline",
        )

        first, second, third = st.columns(3)
        # Read the run's actual reproduction count. Showing the gate threshold here instead
        # would present a fixed number as this run's measured result.
        first.metric(
            "Reproduction",
            f"{certificate['reproduction_count']}/{certificate['reproduction_trials']} reruns",
            border=True,
        )
        call_ledger = cast(Mapping[str, object], document["call_ledger"])
        second.metric(
            "Times the agent was asked",
            call_ledger["target_calls_total"],
            border=True,
        )
        third.metric("Certificate latency", f"{certificate['latency_ms']} ms", border=True)

        render_evidence_pipeline(certificate, key="atlas_home_pipeline")
        render_failure_certificate(
            certificate,
            call_ledger=call_ledger,
            key="atlas_home_certificate",
        )
        run_id = str(cast(Mapping[str, object], document["metadata"])["run_id"])
        render_download_controls(
            (
                DownloadArtifact(
                    "JSON certificate",
                    stored.json_bytes,
                    f"{run_id}.json",
                    "application/json",
                    ":material/data_object:",
                ),
                DownloadArtifact(
                    "JSONL trace",
                    stored.jsonl_bytes,
                    f"{run_id}.jsonl",
                    "application/x-ndjson",
                    ":material/format_list_bulleted:",
                ),
                DownloadArtifact(
                    "Offline HTML report",
                    stored.html_bytes,
                    f"{run_id}.html",
                    "text/html",
                    ":material/article:",
                ),
            ),
            key="atlas_home_downloads",
        )
    else:
        st.warning(
            "No reproducible failure was found. This is not evidence that the agent is safe.",
            icon=":material/info:",
        )

with st.container(key="atlas_home_proof"):
    st.subheader("One failure becomes a portable debugging artifact")
    columns = st.columns(4)
    # The first two are read from the pack and the engine gate so they cannot drift into a
    # false claim. The last two describe fixed structural facts of the hosted surface.
    facts = (
        (str(len(STARTER_PROPERTY_PACK)), "editable assumptions"),
        (GATE_TILE, "repeats required to count"),
        ("3", "export formats"),
        ("0", "remote model calls"),
    )
    for column, (value, label) in zip(columns, facts, strict=True):
        with column:
            st.metric(label, value, border=True)

with st.container(key="atlas_home_value"):
    st.subheader("Built for the handoff after a surprising model answer")
    first, second, third = st.columns(3)
    with first:
        with st.container(border=True, height="stretch"):
            st.badge("CONTROL", color="blue")
            st.markdown("**Freeze everything except the factor under test.**")
            st.caption("Typed constraints keep the source and follow-up pair valid.")
    with second:
        with st.container(border=True, height="stretch"):
            st.badge("REPRODUCE", color="orange")
            st.markdown("**Distinguish one-off model noise from a repeatable break.**")
            st.caption("A certificate requires at least four matching failures in five reruns.")
    with third:
        with st.container(border=True, height="stretch"):
            st.badge("REPLAY", color="green")
            st.markdown("**Give the next developer evidence they can rerun.**")
            st.caption("Every result includes the changed field, outputs, seed, and command.")

render_privacy_footer(key="atlas_home_footer")
