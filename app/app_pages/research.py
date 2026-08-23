"""Measured synthetic calibration and research-method page."""

from __future__ import annotations

import asyncio

import streamlit as st

from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from product_ui import render_benchmark_result, render_page_intro, render_privacy_footer
from showcase import PublicBenchmark, generate_public_benchmark


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
        st.write("Apply the 4-of-5 repeatability gate")
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
