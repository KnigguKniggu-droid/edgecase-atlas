"""Curated, reproducible certificate gallery."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import cast

import streamlit as st

from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.serialization import canonical_json
from product_ui import (
    DownloadArtifact,
    render_counterfactual_faultline,
    render_download_controls,
    render_evidence_pipeline,
    render_failure_certificate,
    render_page_intro,
    render_privacy_footer,
)
from showcase import CuratedArtifact, generate_curated_artifact


@st.cache_data(show_spinner=False)  # type: ignore[untyped-decorator]
def _curated(property_id: str) -> CuratedArtifact:
    return asyncio.run(generate_curated_artifact(property_id))


render_page_intro(
    eyebrow="CERTIFICATE GALLERY / FIVE FAILURE MODES",
    title="Open a complete failure certificate, not a marketing screenshot.",
    lede=(
        "Each example is generated from the real engine and included synthetic flawed agent, "
        "then content-addressed for reproducibility."
    ),
    key="atlas_gallery_intro",
)

properties = {item.property_id: item for item in STARTER_PROPERTY_PACK}
property_id = st.pills(
    "Failure mode",
    options=tuple(properties),
    default="red_signal_no_proceed",
    selection_mode="single",
    format_func=lambda value: properties[value].title,
    key="atlas_gallery_property",
)

if property_id:
    with st.spinner("Assembling the selected certificate"):
        artifact = _curated(str(property_id))
    document = artifact["document"]
    certificates = cast(Sequence[Mapping[str, object]], document["certificates"])
    if certificates:
        certificate = certificates[0]
        metrics = artifact["metrics"]
        st.warning(artifact["disclaimer"], icon=":material/science:")
        first, second, third, fourth = st.columns(4)
        first.metric("Certificates", metrics["certificate_count"], border=True)
        second.metric("Target calls", metrics["target_calls"], border=True)
        third.metric("Coverage cells", metrics["coverage_cells"], border=True)
        rate = metrics["per_property_reproduction_rates"][str(property_id)]
        fourth.metric(
            "Reproduction",
            f"{rate['reproductions']}/{rate['trials']}",
            border=True,
        )

        with st.container(border=True, key="atlas_gallery_replay"):
            st.caption(
                "Replay and verify this exact failure locally. Download the certificate below, "
                "put it in a `certificates/` folder beside your `atlas.yaml`, then run:"
            )
            st.code(str(certificate["replay_command"]), language="shell", wrap_lines=True)

        # Index directly. A silent empty fallback here would render a blank fault line if the
        # certificate schema ever changed, instead of failing where the mismatch happened.
        source_scenario = cast(Mapping[str, object], certificate["source"])
        follow_up_scenario = cast(Mapping[str, object], certificate["minimized_follow_up"])
        changed_fields = cast(Sequence[Mapping[str, object]], certificate["changed_fields"])
        render_counterfactual_faultline(
            source_scenario,
            changed_fields,
            follow_up_scenario,
            key="atlas_gallery_faultline",
        )

        render_evidence_pipeline(certificate, key="atlas_gallery_pipeline")
        render_failure_certificate(
            certificate,
            call_ledger=cast(Mapping[str, object], document["call_ledger"]),
            key="atlas_gallery_certificate",
        )
        certificate_bytes = (canonical_json(dict(certificate)) + "\n").encode("utf-8")
        document_bytes = (canonical_json(document) + "\n").encode("utf-8")
        render_download_controls(
            (
                DownloadArtifact(
                    "Certificate JSON",
                    certificate_bytes,
                    f"{certificate['certificate_id']}.json",
                    "application/json",
                    ":material/verified:",
                ),
                DownloadArtifact(
                    "Complete run JSON",
                    document_bytes,
                    f"{property_id}-run.json",
                    "application/json",
                    ":material/data_object:",
                ),
            ),
            key="atlas_gallery_downloads",
        )
        with st.expander("Reproducibility identity"):
            st.code(f"SHA-256  {artifact['artifact_sha256']}", language=None)
    else:
        st.warning(
            "No reproducible failure certificate was produced for this mode under the current "
            "sampling budget. This is not evidence that the agent is safe.",
            icon=":material/info:",
        )
else:
    st.info(
        "A failure mode selection is required to inspect curated forensic artifacts. "
        "Select one of the available failure modes above:",
        icon=":material/touch_app:",
    )
    for item in STARTER_PROPERTY_PACK:
        st.markdown(f"- **{item.title}**: {item.description}")

render_privacy_footer(key="atlas_gallery_footer")
