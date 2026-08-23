"""Safe run comparison and trace-inspection page."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import cast

import streamlit as st

from artifact_io import TraceSummary, ingest_artifact
from edgecase_atlas.comparison import compare_run_documents
from product_ui import (
    render_page_intro,
    render_privacy_footer,
    render_run_comparison_delta,
)
from showcase import ComparisonPair, generate_sample_comparison_pair


@st.cache_data(show_spinner=False)  # type: ignore[untyped-decorator]
def _sample_pair() -> ComparisonPair:
    return asyncio.run(generate_sample_comparison_pair())


def _run_document(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("The uploaded file is not an Atlas run document.")
    return cast(Mapping[str, object], value)


render_page_intro(
    eyebrow="COMPARE RUNS / EVIDENCE DELTAS",
    title="See what changed between two compatible test campaigns.",
    lede=(
        "Compare certificates, charged calls, and observed coverage without sending either "
        "artifact to a remote service."
    ),
    key="atlas_compare_intro",
)

mode = st.segmented_control(
    "Comparison source",
    options=("Sample pair", "Upload runs", "Inspect trace"),
    default="Sample pair",
    selection_mode="single",
    key="atlas_compare_mode",
)

if mode == "Sample pair":
    st.info(
        "The sample compares one evaluation with five evaluations of the same synthetic fixture. "
        "It is a product demonstration, not a safety result.",
        icon=":material/science:",
    )
    if st.button(
        "Build the sample comparison",
        type="primary",
        icon=":material/compare_arrows:",
        key="atlas_compare_sample",
    ):
        with st.spinner("Generating two compatible runs"):
            st.session_state["atlas_comparison"] = _sample_pair()
    pair = st.session_state.get("atlas_comparison")
    if isinstance(pair, dict) and isinstance(pair.get("comparison"), Mapping):
        st.success("Compatible run pair verified locally.")
        render_run_comparison_delta(
            cast(Mapping[str, object], pair["comparison"]),
            key="atlas_compare_sample_result",
        )
        with st.expander("Artifact identity"):
            st.code(
                f"Run A  {pair['run_a_sha256']}\nRun B  {pair['run_b_sha256']}",
                language=None,
            )

elif mode == "Upload runs":
    st.warning(
        "Uploads are parsed as data only. Atlas never imports, executes, or forwards file content.",
        icon=":material/shield:",
    )
    left, right = st.columns(2)
    with left:
        run_a_file = st.file_uploader(
            "Run A JSON",
            type=("json",),
            max_upload_size=2,
            key="atlas_compare_run_a",
        )
    with right:
        run_b_file = st.file_uploader(
            "Run B JSON",
            type=("json",),
            max_upload_size=2,
            key="atlas_compare_run_b",
        )
    if st.button(
        "Compare validated runs",
        type="primary",
        disabled=run_a_file is None or run_b_file is None,
        icon=":material/difference:",
        key="atlas_compare_uploaded",
    ):
        try:
            assert run_a_file is not None and run_b_file is not None
            run_a = _run_document(
                ingest_artifact(
                    run_a_file.getvalue(), filename=run_a_file.name, media_type=run_a_file.type
                )
            )
            run_b = _run_document(
                ingest_artifact(
                    run_b_file.getvalue(), filename=run_b_file.name, media_type=run_b_file.type
                )
            )
            comparison = compare_run_documents(run_a, run_b)
        except (TypeError, ValueError):
            st.error("The files are invalid or incompatible Atlas runs. No content was retained.")
        else:
            st.session_state["atlas_uploaded_comparison"] = comparison
    uploaded = st.session_state.get("atlas_uploaded_comparison")
    if isinstance(uploaded, Mapping):
        render_run_comparison_delta(uploaded, key="atlas_compare_uploaded_result")

else:
    st.info(
        "Inspect the structure of a JSONL trace without displaying scenario text or model output.",
        icon=":material/privacy_tip:",
    )
    trace_file = st.file_uploader(
        "Atlas JSONL trace",
        type=("jsonl", "ndjson"),
        max_upload_size=2,
        key="atlas_compare_trace",
    )
    if trace_file is not None:
        try:
            parsed_trace = ingest_artifact(
                trace_file.getvalue(), filename=trace_file.name, media_type=trace_file.type
            )
        except (TypeError, ValueError):
            st.error("The trace is invalid. No content was retained.")
        else:
            if isinstance(parsed_trace, TraceSummary):
                st.session_state["atlas_trace_summary"] = parsed_trace
    stored_trace = st.session_state.get("atlas_trace_summary")
    if isinstance(stored_trace, TraceSummary):
        first, second, third = st.columns(3)
        first.metric("Events", sum(stored_trace.event_counts.values()), border=True)
        second.metric("Run ID", stored_trace.run_id, border=True)
        third.metric("Event types", len(stored_trace.event_counts), border=True)
        st.bar_chart(stored_trace.event_counts, horizontal=True)

render_privacy_footer(key="atlas_compare_footer")
