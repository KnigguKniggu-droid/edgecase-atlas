"""Configurable no-key counterfactual test laboratory."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

import streamlit as st

from edgecase_atlas.fixtures import known_violation_cases
from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.starter_config import LocalAdapterKind, get_starter_definition
from product_ui import (
    DownloadArtifact,
    render_counterfactual_faultline,
    render_download_controls,
    render_evidence_pipeline,
    render_failure_certificate,
    render_page_intro,
    render_privacy_footer,
)
from runtime import PublicRunUnavailable, execute_public_demo
from ui import (
    PUBLIC_BUDGET_MAX,
    PUBLIC_BUDGET_MIN,
    PUBLIC_SEED_MAX,
    PUBLIC_TEXT_MAX_CHARS,
    DemoArtifacts,
    validate_public_request,
)


def _render_local_agent_onboarding(*, is_post_run: bool) -> None:
    """Render a dedicated, prominent bridge connecting the demo to local agent testing."""
    with st.container(key="atlas_lab_onboarding_section"):
        st.divider()
        if is_post_run:
            st.subheader("Step 2: Test your own agent against this failure mode", anchor=False)
            st.markdown(
                "Now that you have observed the synthetic counterfactual break, connect your "
                "own driving agent locally to discover if it shares the same blind spot. "
                "**Runs on your machine, never in this hosted app.**"
            )
        else:
            st.subheader("Connect your own agent locally (CLI & SDK)", anchor=False)
            st.markdown(
                "**Runs on your machine, never in this hosted app.** "
                "Atlas connects to your driving agent locally via Python functions, "
                "JSONL subprocesses, or OpenAI-compatible endpoints."
            )

        adapter_choice = st.pills(
            "Integration mode",
            options=cast(tuple[LocalAdapterKind, ...], ("python", "subprocess", "openai")),
            default="python",
            selection_mode="single",
            format_func=lambda k: {
                "python": "Python Function",
                "subprocess": "JSONL Subprocess",
                "openai": "OpenAI-Compatible",
            }[k],
            key="atlas_lab_adapter_choice",
        )
        starter = get_starter_definition(adapter_choice or "python")

        st.markdown(f"**{starter.title}**")
        st.caption(starter.summary)

        col_proto, col_yaml = st.columns(2)
        with col_proto:
            st.markdown("**Adapter Protocol Contract**")
            st.code(starter.protocol_snippet, language="python")
        with col_yaml:
            st.markdown("**Validated `atlas.yaml` Starter**")
            st.code(starter.config_yaml, language="yaml")
            st.download_button(
                label="Download atlas.yaml",
                data=starter.config_yaml.encode("utf-8"),
                file_name="atlas.yaml",
                mime="application/x-yaml",
                icon=":material/download:",
                key="atlas_lab_download_starter_yaml",
            )

        st.markdown("**Run locally with the Atlas CLI:**")
        st.code(
            "atlas validate atlas.yaml\n"
            "atlas test --config atlas.yaml --budget 100 --seed 42\n"
            "atlas report runs/RUN.json --format html",
            language="powershell",
        )


render_page_intro(
    eyebrow="TEST LAB / ONE CHANGE AT A TIME",
    title="Test one operational assumption at a time.",
    lede=(
        "Choose a synthetic scenario, freeze non-target factors, and let Atlas reproduce and "
        "shrink the failure."
    ),
    key="atlas_lab_intro",
)

properties = {item.property_id: item for item in STARTER_PROPERTY_PACK}
cases = {item.property_id: item for item in known_violation_cases()}

with st.form("atlas_lab_form", border=False):
    sample_property_id = st.selectbox(
        "Scenario to mutate",
        options=tuple(cases),
        format_func=lambda value: properties[value].title,
        key="atlas_lab_sample",
    )
    selected_property_ids = st.pills(
        "Safety assumptions",
        options=tuple(properties),
        default=("red_signal_no_proceed",),
        selection_mode="multi",
        format_func=lambda value: properties[value].title,
        key="atlas_lab_properties",
    )
    controls = st.columns(2)
    with controls[0]:
        seed = st.number_input(
            "Seed",
            min_value=0,
            max_value=PUBLIC_SEED_MAX,
            value=42,
            step=1,
            key="atlas_lab_seed",
            help="Starting number that makes simulated randomness exactly repeatable.",
        )
    with controls[1]:
        budget = st.number_input(
            "Test budget",
            min_value=PUBLIC_BUDGET_MIN,
            max_value=PUBLIC_BUDGET_MAX,
            value=1,
            step=1,
            key="atlas_lab_budget",
            help="Maximum number of scenario variations to generate and evaluate.",
        )
    custom_text = st.text_area(
        "Optional synthetic context",
        max_chars=PUBLIC_TEXT_MAX_CHARS,
        key="atlas_lab_context",
        help="This text is stored in the download only. It is never executed or sent remotely.",
    )
    submitted = st.form_submit_button(
        "Run counterfactual test",
        type="primary",
        icon=":material/radar:",
    )

preview = cases[str(sample_property_id)]
source = cast(Mapping[str, object], preview.counterfactual.source.model_dump(mode="json"))
changes = cast(
    Sequence[Mapping[str, object]],
    [change.model_dump(mode="json") for change in preview.counterfactual.changed_fields],
)
follow_up = cast(Mapping[str, object], preview.counterfactual.follow_up.model_dump(mode="json"))
render_counterfactual_faultline(source, changes, follow_up, key="atlas_lab_preview")

if submitted:
    try:
        request = validate_public_request(
            property_ids=cast(Sequence[str], selected_property_ids or ()),
            sample_property_id=str(sample_property_id),
            seed=seed,
            budget=budget,
            custom_text=custom_text,
        )
        with st.container(key="atlas_lab_status"):
            with st.status("Running the evidence pipeline", expanded=True) as status:
                st.write(
                    f"Validating {len(request.properties)} safety assumption(s) "
                    "against the scenario pair"
                )
                st.write(
                    f"Collecting repeated decisions with mutation budget {request.budget}"
                )
                st.write(f"Reducing retained factors with seed {request.seed}")
                artifacts = execute_public_demo(request)
                status.update(label="Test complete", state="complete", expanded=False)
    except ValueError:
        st.error("Select at least one allowed safety assumption and stay within public limits.")
    except PublicRunUnavailable:
        st.error("The public demonstration is busy. Retry in a moment.")
    else:
        st.session_state["atlas_lab_artifacts"] = artifacts

stored = st.session_state.get("atlas_lab_artifacts")
has_completed_run = False

if isinstance(stored, DemoArtifacts):
    document = stored.document
    certificates = cast(Sequence[Mapping[str, object]], document["certificates"])
    if not certificates:
        st.warning("No repeatable failure was found. This is not evidence that the agent is safe.")
    else:
        has_completed_run = True
        titles = [
            str(cast(Mapping[str, object], certificate["property"])["title"])
            for certificate in certificates
        ]
        selected_index = 0
        if len(certificates) > 1:
            selected_title = st.selectbox(
                "Failure certificate",
                options=titles,
                key="atlas_lab_certificate",
            )
            selected_index = titles.index(selected_title)
        certificate = certificates[selected_index]
        st.error("Reproducible failure found.", icon=":material/gpp_bad:")
        render_evidence_pipeline(certificate, key="atlas_lab_pipeline")
        render_failure_certificate(
            certificate,
            call_ledger=cast(Mapping[str, object], document["call_ledger"]),
            key="atlas_lab_result",
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
            key="atlas_lab_downloads",
        )

_render_local_agent_onboarding(is_post_run=has_completed_run)

render_privacy_footer(key="atlas_lab_footer")

