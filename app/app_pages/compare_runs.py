"""Safe run comparison and trace-inspection page."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import cast

import streamlit as st

from artifact_io import MAX_ARTIFACT_BYTES, TraceSummary, ingest_run_document, ingest_trace
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
        raise ValueError("The pasted text is not an Atlas run document.")
    return cast(Mapping[str, object], value)


def _as_payload(text: str) -> bytes:
    """Encode pasted text for the same parser the CLI artifacts go through.

    The 2 MB ceiling and every structural check live in artifact_io, so pasted evidence is
    bounded and validated exactly like any other artifact rather than on a second code path.
    """
    if not text.strip():
        raise ValueError("Paste an Atlas artifact first.")
    return text.encode("utf-8")


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
    options=("Sample pair", "Paste runs", "Inspect trace"),
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
    else:
        st.caption(
            "No comparison loaded yet. Click 'Build the sample comparison' to generate a "
            "compatible demonstration pair."
        )

elif mode == "Paste runs":
    st.info(
        "Paste the contents of two run JSON files. The hosted app accepts no file uploads. "
        "Text is parsed as inert data and never imported, executed, forwarded, or retained.",
        icon=":material/shield:",
    )
    left, right = st.columns(2)
    with left:
        run_a_text = st.text_area(
            "Run A JSON",
            height=170,
            placeholder="Paste the contents of runs/RUN.json",
            key="atlas_compare_run_a",
        )
    with right:
        run_b_text = st.text_area(
            "Run B JSON",
            height=170,
            placeholder="Paste the contents of a second runs/RUN.json",
            key="atlas_compare_run_b",
        )

    has_a = bool(run_a_text and run_a_text.strip())
    has_b = bool(run_b_text and run_b_text.strip())

    if not has_a and not has_b:
        st.caption(
            f"Paste both Run A and Run B above to compute the delta. Each is capped at "
            f"{MAX_ARTIFACT_BYTES:,} bytes."
        )
    elif has_a and not has_b:
        st.info("Run A ready. Paste Run B to proceed with the comparison.")
    elif not has_a and has_b:
        st.info("Run B ready. Paste Run A to proceed with the comparison.")

    if st.button(
        "Compare validated runs",
        type="primary",
        disabled=not (has_a and has_b),
        icon=":material/difference:",
        key="atlas_compare_pasted",
    ):
        try:
            run_a = _run_document(ingest_run_document(_as_payload(run_a_text)))
            run_b = _run_document(ingest_run_document(_as_payload(run_b_text)))
            comparison = compare_run_documents(run_a, run_b)
        except (TypeError, ValueError):
            st.error("The text is not a pair of valid, compatible Atlas runs. Nothing was kept.")
        else:
            st.session_state["atlas_uploaded_comparison"] = comparison
    pasted = st.session_state.get("atlas_uploaded_comparison")
    if isinstance(pasted, Mapping):
        render_run_comparison_delta(pasted, key="atlas_compare_uploaded_result")

else:
    st.info(
        "Inspect the structure of a JSONL trace without displaying scenario text or model output.",
        icon=":material/privacy_tip:",
    )
    trace_text = st.text_area(
        "Atlas JSONL trace",
        height=170,
        placeholder="Paste the contents of traces/RUN.jsonl",
        key="atlas_compare_trace",
    )
    if trace_text and trace_text.strip():
        try:
            parsed_trace = ingest_trace(_as_payload(trace_text))
        except (TypeError, ValueError):
            st.error("The trace is invalid. No content was retained.")
        else:
            st.session_state["atlas_trace_summary"] = parsed_trace
    stored_trace = st.session_state.get("atlas_trace_summary")
    if isinstance(stored_trace, TraceSummary):
        first, second, third = st.columns(3)
        first.metric("Events", sum(stored_trace.event_counts.values()), border=True)
        second.metric("Run ID", stored_trace.run_id, border=True)
        third.metric("Event types", len(stored_trace.event_counts), border=True)
        st.subheader("Event distribution")
        st.caption("Event types observed across the trace sequence.")
        for event_name, count in sorted(stored_trace.event_counts.items()):
            st.write(f"- `{event_name}`: {count}")
    else:
        st.caption("No trace loaded yet. Paste an Atlas .jsonl trace to inspect event metrics.")

render_privacy_footer(key="atlas_compare_footer")
