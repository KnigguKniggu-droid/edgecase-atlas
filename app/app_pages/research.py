"""Measured synthetic calibration and research-method page."""

from __future__ import annotations

import asyncio

import streamlit as st

from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from product_ui import render_benchmark_result, render_page_intro, render_privacy_footer
from showcase import PublicBenchmark, generate_public_benchmark

# Spelled out rather than imported, because app files deploy straight from the
# repository while the hosted environment resolves the installed package separately.
# tests/test_product_surface.py holds this to REQUIRED_REPRODUCTIONS and
# CONFIRMATION_TRIALS so it cannot drift.
GATE_SUMMARY = "4-of-5"


@st.cache_data(show_spinner=False)  # type: ignore[untyped-decorator]
def _benchmark() -> PublicBenchmark:
    return asyncio.run(generate_public_benchmark())


render_page_intro(
    eyebrow="RESEARCH / MEASURED SYNTHETIC CALIBRATION",
    title="Measure the testing method before claiming anything about safety.",
    lede=(
        "This public calibration checks whether the included flawed fixture triggers all five "
        "operational assumptions under a fixed seed and budget."
    ),
    key="atlas_research_intro",
)

with st.container(key="atlas_research_method"):
    st.subheader("What this public result can establish")
    left, right = st.columns(2)
    with left:
        st.markdown(
            "**It can establish** that the deterministic generator, repeated evaluator, "
            "constraint checks, minimizer, and serialization path work together on controlled "
            "synthetic failures."
        )
    with right:
        st.markdown(
            "**It cannot establish** real-world safety, model ranking, commercial readiness, "
            "or statistical superiority over research baselines."
        )

if st.button(
    "Run the five-property calibration",
    type="primary",
    icon=":material/biotech:",
    key="atlas_research_run",
):
    with st.status("Running five controlled candidates", expanded=True) as status:
        st.write("Use seed 42 and one candidate per property")
        st.write(f"Apply the {GATE_SUMMARY} repeatability gate")
        st.write("Measure calls, certificates, and observed coverage")
        st.session_state["atlas_benchmark"] = _benchmark()
        status.update(label="Synthetic calibration complete", state="complete", expanded=False)

benchmark = st.session_state.get("atlas_benchmark")
if isinstance(benchmark, dict):
    render_benchmark_result(benchmark, key="atlas_research_benchmark")
    labels = {item.property_id: item.title for item in STARTER_PROPERTY_PACK}
    rates = benchmark["metrics"]["per_property_reproduction_rates"]
    chart_data = {
        labels[property_id]: float(rate["rate"] or 0.0) for property_id, rate in rates.items()
    }
    st.subheader("Observed reproduction rate by assumption")
    st.bar_chart(chart_data, horizontal=True, x_label="Reproduction rate", y_label="Assumption")
    with st.expander("Artifact identity and fixed configuration"):
        st.code(
            "Seed      42\n"
            "Budget    5 valid candidates\n"
            "Reruns    5 per candidate\n"
            "Gate      at least 4 matching failures\n"
            f"SHA-256  {benchmark['artifact_sha256']}",
            language=None,
        )

with st.container(key="atlas_research_ledger"):
    st.subheader("Evidence Ledger")
    st.caption("Explicit accounting of demonstrated capabilities vs planned and out-of-scope work.")

    unrun_note = (
        "Calibration has not been run yet. Click 'Run the five-property calibration' above."
    )
    has_benchmark = isinstance(benchmark, dict)
    metrics_map = benchmark["metrics"] if has_benchmark else None

    if (
        metrics_map is not None
        and "certificate_count" in metrics_map
        and "property_count" in metrics_map
    ):
        cert_count = metrics_map["certificate_count"]
        prop_count = metrics_map["property_count"]
        status_1 = ("Measured", "green")
        ev_1 = f"{cert_count} of {prop_count} triggered"
    else:
        status_1 = ("Not yet measured", "gray")
        ev_1 = unrun_note

    if metrics_map is not None and "target_calls" in metrics_map:
        target_calls = metrics_map["target_calls"]
        status_2 = ("Measured", "green")
        ev_2 = f"{target_calls} target model invocations"
    else:
        status_2 = ("Not yet measured", "gray")
        ev_2 = unrun_note

    if metrics_map is not None and "coverage_cells" in metrics_map:
        cov_cells = metrics_map["coverage_cells"]
        status_3 = ("Measured", "green")
        ev_3 = f"{cov_cells} coverage cells explored"
    else:
        status_3 = ("Not yet measured", "gray")
        ev_3 = unrun_note

    if has_benchmark and "artifact_sha256" in benchmark and benchmark["artifact_sha256"]:
        sha = benchmark["artifact_sha256"][:12]
        status_4 = ("Measured", "green")
        ev_4 = f"SHA-256 prefix {sha} verified"
    else:
        status_4 = ("Not yet measured", "gray")
        ev_4 = unrun_note

    rows = [
        ("Synthetic failure trigger", status_1, ev_1),
        ("Target invocation efficiency", status_2, ev_2),
        ("Discrete behavioral coverage", status_3, ev_3),
        ("Deterministic artifact identity", status_4, ev_4),
        (
            "Comparative baseline superiority",
            ("Planned", "blue"),
            "Matched-budget study unexecuted",
        ),
        (
            "Real-world autonomous vehicle safety",
            ("Out of scope", "gray"),
            "Synthetic domain only; no vehicle claims",
        ),
    ]

    for claim, (status_text, status_color), evidence in rows:
        with st.container(key=f"atlas_ledger_row_{claim.lower().replace(' ', '_')}"):
            col_status, col_claim, col_evidence = st.columns(
                [1.8, 3.2, 5.0], vertical_alignment="center"
            )
            with col_status:
                st.badge(status_text, color=status_color)
            with col_claim:
                st.markdown(f"**{claim}**")
            with col_evidence:
                st.caption(evidence)

with st.container(key="atlas_research_next"):
    st.subheader("The defensible research step")
    st.markdown(
        "The planned study compares constraint-guided counterfactual search with random, fixed "
        "template, unguided language-model, and diversity-guided baselines under matched call "
        "budgets. No superiority claim appears here because those campaigns have not been run."
    )
    st.caption(
        "All scenarios shown in this public application are simulated and synthetic. "
        "Atlas is for research and debugging, not for controlling any vehicle or "
        "issuing certification."
    )

render_privacy_footer(key="atlas_research_footer")
