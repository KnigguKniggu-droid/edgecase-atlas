"""Public Streamlit demo contracts and no-key integration coverage."""

from __future__ import annotations

import ast
import asyncio
import importlib
import json
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).parents[1] / "app" / "streamlit_app.py"
UI_PATH = Path(__file__).parents[1] / "app" / "ui.py"
STREAMLIT_CONFIG_PATH = Path(__file__).parents[1] / ".streamlit" / "config.toml"
PYPROJECT_PATH = Path(__file__).parents[1] / "pyproject.toml"
THEME_PATH = Path(__file__).parents[1] / "app" / "theme.py"
FONT_DIRECTORY = Path(__file__).parents[1] / "app" / "static" / "fonts"
PAGE_DIRECTORY = Path(__file__).parents[1] / "app" / "app_pages"
PRODUCT_UI_PATH = Path(__file__).parents[1] / "app" / "product_ui.py"
ARTIFACT_IO_PATH = Path(__file__).parents[1] / "app" / "artifact_io.py"


def _load_app_module() -> ModuleType:
    return importlib.import_module("app.ui")


def _relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_streamlit_config_disables_telemetry_hides_errors_and_meets_button_contrast() -> None:
    """Regressing privacy settings or button contrast must fail deployment configuration."""
    config = tomllib.loads(STREAMLIT_CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["browser"]["gatherUsageStats"] is False
    assert config["client"]["showErrorDetails"] == "none"
    assert _contrast_ratio(config["theme"]["primaryColor"], "#FFFFFF") >= 4.5
    assert config["server"]["enableStaticServing"] is True
    project = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert "streamlit==1.61.1" in project["project"]["dependencies"]
    assert config["theme"]["font"] == "'IBM Plex Sans', sans-serif"
    assert config["theme"]["headingFont"] == "'IBM Plex Sans', sans-serif"
    assert config["theme"]["codeFont"] == "'IBM Plex Mono', monospace"
    assert "http" not in STREAMLIT_CONFIG_PATH.read_text(encoding="utf-8").lower()

    font_files = tuple(FONT_DIRECTORY.glob("*.woff2"))
    assert len(font_files) == 6
    assert all(path.stat().st_size > 10_000 for path in font_files)
    assert (FONT_DIRECTORY / "OFL.txt").is_file()


def test_public_entrypoint_excludes_execution_and_network_capabilities() -> None:
    """Hosted uploads must remain inert and every page must avoid arbitrary networking."""
    page_paths = tuple(sorted(PAGE_DIRECTORY.glob("*.py")))
    reviewed_paths = (APP_PATH, UI_PATH, PRODUCT_UI_PATH, ARTIFACT_IO_PATH, *page_paths)
    sources = {path: path.read_text(encoding="utf-8") for path in reviewed_paths}
    trees = {path: ast.parse(source) for path, source in sources.items()}
    nodes = [node for tree in trees.values() for node in ast.walk(tree)]
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in nodes
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", 1)[0]
        for node in nodes
        if isinstance(node, ast.ImportFrom) and node.module
    )
    calls = {
        node.func.attr
        for node in nodes
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    direct_calls = {
        node.func.id
        for node in nodes
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert imported_roots.isdisjoint({"httpx", "requests", "socket", "subprocess", "urllib"})
    assert calls.isdisjoint({"iframe", "connection", "experimental_connection"})
    assert direct_calls.isdisjoint({"eval", "exec", "compile"})
    # The hosted app takes no files at all. Evidence arrives as pasted text through the
    # same bounded parser, so there is no upload surface on the public deployment.
    assert "file_uploader" not in calls
    joined = "".join(sources.values())
    assert "st.file_uploader(" not in joined
    compare_source = sources[PAGE_DIRECTORY / "compare_runs.py"]
    assert compare_source.count("ingest_run_document(") == 2
    assert compare_source.count("ingest_trace(") == 1

    app_source = sources[APP_PATH]
    theme_source = THEME_PATH.read_text(encoding="utf-8").lower()
    assert 'page_icon=":material/' not in app_source
    assert app_source.count("st.html(APP_CSS)") == 1
    assert app_source.count("st.navigation(") == 1
    assert 'position="hidden"' in app_source
    assert app_source.count("st.Page(") == 1
    assert app_source.count("st.page_link(") == 1
    assert "<script" not in theme_source
    assert "javascript:" not in theme_source
    assert "fonts.googleapis.com" not in theme_source
    assert "#mainmenu" in theme_source
    assert "visibility: hidden" in theme_source
    assert "text-transform: uppercase" in theme_source
    assert "letter-spacing" in theme_source
    assert "st.table(" not in "\n".join(sources.values())
    assert not any(
        keyword.arg == "unsafe_allow_html"
        for node in nodes
        if isinstance(node, ast.Call)
        for keyword in node.keywords
    )


def test_public_request_revalidates_text_budget_seed_and_property_allowlist() -> None:
    """Removing any server-side boundary must expose an invalid request."""
    app = _load_app_module()

    request = app.validate_public_request(
        property_ids=("red_signal_no_proceed",),
        sample_property_id="red_signal_no_proceed",
        seed=42,
        budget=1,
        custom_text="  Synthetic context only.  ",
    )
    assert request.custom_text == "Synthetic context only."
    assert tuple(item.property_id for item in request.properties) == ("red_signal_no_proceed",)
    assert request.sample_property_id == "red_signal_no_proceed"

    invalid_requests = (
        {
            "property_ids": (),
            "sample_property_id": "red_signal_no_proceed",
            "seed": 42,
            "budget": 1,
            "custom_text": "",
        },
        {
            "property_ids": ("unknown",),
            "sample_property_id": "red_signal_no_proceed",
            "seed": 42,
            "budget": 1,
            "custom_text": "",
        },
        {
            "property_ids": ("red_signal_no_proceed",),
            "sample_property_id": "C:\\private\\sample",
            "seed": 42,
            "budget": 1,
            "custom_text": "",
        },
        {
            "property_ids": ("red_signal_no_proceed",),
            "sample_property_id": "red_signal_no_proceed",
            "seed": -1,
            "budget": 1,
            "custom_text": "",
        },
        {
            "property_ids": ("red_signal_no_proceed",),
            "sample_property_id": "red_signal_no_proceed",
            "seed": 42,
            "budget": 0,
            "custom_text": "",
        },
        {
            "property_ids": ("red_signal_no_proceed",),
            "sample_property_id": "red_signal_no_proceed",
            "seed": 42,
            "budget": 26,
            "custom_text": "",
        },
        {
            "property_ids": ("red_signal_no_proceed",),
            "sample_property_id": "red_signal_no_proceed",
            "seed": 42,
            "budget": 1,
            "custom_text": "x" * 1001,
        },
    )
    for values in invalid_requests:
        with pytest.raises(ValueError):
            app.validate_public_request(**values)


def test_public_adapter_allowlist_contains_only_no_key_fixture() -> None:
    """Registering any external adapter must fail the hosted allowlist contract."""
    app = _load_app_module()

    adapter = app.public_adapter("faulty_fixture")
    assert adapter.model_id == "faulty-demonstration-agent-v1"
    with pytest.raises(ValueError):
        app.public_adapter("subprocess")
    with pytest.raises(ValueError):
        app.public_adapter("https://example.test/v1")


def test_no_key_demo_builds_json_jsonl_and_standalone_html_downloads() -> None:
    """Breaking the real engine-to-download path must fail one no-key run."""
    app = _load_app_module()
    request = app.validate_public_request(
        property_ids=("red_signal_no_proceed",),
        sample_property_id="hazard_non_aggression",
        seed=42,
        budget=1,
        custom_text="A synthetic intersection context.",
    )

    artifacts = asyncio.run(app.build_demo_artifacts(request))
    document = json.loads(artifacts.json_bytes)
    events = [json.loads(line) for line in artifacts.jsonl_bytes.splitlines()]

    assert document["schema_version"] == "atlas-run-v1"
    assert document["demo_input"]["custom_text"] == "A synthetic intersection context."
    assert document["demo_input"]["sample_property_id"] == "hazard_non_aggression"
    assert document["certificates"][0]["property"]["property_id"] == "hazard_non_aggression"
    assert len(document["certificates"]) >= 1
    assert events[0]["event_type"] == "run_started"
    assert events[-1]["event_type"] == "run_completed"
    assert b"<!doctype html>" in artifacts.html_bytes.lower()
    assert document["metadata"]["run_id"].encode() in artifacts.html_bytes
    assert b"<script" not in artifacts.html_bytes.lower()


def test_status_copy_covers_every_public_run_state_without_leaking_errors() -> None:
    """Deleting a state or echoing an adapter exception must fail safe status copy."""
    app = _load_app_module()

    assert app.status_copy("empty") == (
        "Ready for a no-key demonstration.",
        "Select assumptions, then run the synthetic fixture.",
    )
    assert app.status_copy("running")[0] == "Running counterfactual checks."
    assert app.status_copy("success")[0] == "Reproducible failure found."
    assert app.status_copy("no_failure")[0] == "No reproducible failure found."
    assert app.status_copy("input_error")[0] == "Check the demonstration inputs."
    title, detail = app.status_copy("adapter_error", RuntimeError("secret-token"))
    assert title == "The demonstration could not finish."
    assert "secret-token" not in detail
    with pytest.raises(ValueError):
        app.status_copy("unknown")


def test_initial_app_is_accessible_and_uses_unique_stable_widget_keys() -> None:
    """The default product thesis and primary action must load without credentials."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=20).run()

    assert not app.exception
    assert app.header[0].value == "Catch the decision change before it becomes a driving failure."
    assert any("synthetic" in item.value.lower() for item in app.caption)
    widgets = [*app.button]
    keys = [item.key for item in widgets]
    assert all(keys)
    assert len(keys) == len(set(keys))
    assert any(item.label == "Run the live safety break" for item in app.button)


def test_submit_runs_no_key_demo_and_renders_certificate() -> None:
    """The home action must run the real engine and create three portable artifacts."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

    run_button = next(item for item in app.button if item.label == "Run the live safety break")
    app = run_button.click().run(timeout=30)

    assert not app.exception
    assert any("Reproducible failure found" in item.value for item in app.error)
    metric_labels = {item.label for item in app.metric}
    assert {
        "Reruns that failed",
        "Times the agent was asked",
        "Estimated cost",
        "Time the agent took",
    }.issubset(metric_labels)
    assert any("atlas replay certificates/" in item.value for item in app.code)
    assert len(app.get("download_button")) == 3


def test_certificate_gallery_exposes_all_five_curated_failure_modes() -> None:
    """Every starter assumption must have a first-class gallery artifact."""
    from edgecase_atlas.properties import STARTER_PROPERTY_PACK

    source = (PAGE_DIRECTORY / "certificates.py").read_text(encoding="utf-8")
    assert "generate_curated_artifact" in source
    assert "options=tuple(properties)" in source
    assert len(STARTER_PROPERTY_PACK) == 5

    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/certificates.py").run(timeout=30)
    assert not app.exception
    assert app.title[0].value.startswith("Open a complete failure certificate")
    assert len(app.get("download_button")) == 2


def test_test_lab_exposes_bounded_accessible_controls() -> None:
    """The configurable workflow must keep bounded, labeled, stable controls."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/test_lab.py").run(timeout=30)

    assert not app.exception
    assert app.selectbox[0].label == "Scenario to mutate"
    assert {item.label for item in app.number_input} == {
        "Repeat number",
        "How many scenarios to try",
    }
    assert app.text_area[0].label == "Optional synthetic context"
    assert any(item.label == "Run counterfactual test" for item in app.button)
    widget_keys = [
        item.key for item in (*app.selectbox, *app.number_input, *app.text_area, *app.button)
    ]
    assert all(widget_keys)
    assert len(widget_keys) == len(set(widget_keys))


def test_tampered_session_artifact_is_ignored_without_value_leak() -> None:
    """A forged result object must not be rendered or reflected into the page."""
    injected_value = r"C:\private\fixture-secret"
    app = AppTest.from_file(str(APP_PATH), default_timeout=30)
    app.session_state["atlas_home_artifacts"] = injected_value

    app = app.run(timeout=30)

    assert not app.exception
    rendered = " ".join(
        str(getattr(item, "value", ""))
        for element_type in ("warning", "error", "caption", "info", "exception", "markdown")
        for item in app.get(element_type)
    )
    assert injected_value not in rendered
    assert "streamlit_app.py" not in rendered


def test_curated_sample_selection_changes_the_executed_property() -> None:
    """The Test Lab selector must control the real fixture run."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/test_lab.py").run(timeout=30)
    sample_picker = next(item for item in app.selectbox if item.label == "Scenario to mutate")
    sample_picker.set_value("hazard_non_aggression")

    run_button = next(item for item in app.button if item.label == "Run counterfactual test")
    app = run_button.click().run(timeout=30)

    assert not app.exception
    assert any(
        item.value == "Relevant hazards cannot increase aggression" for item in app.subheader
    )


def test_test_lab_renders_local_agent_integration_onboarding() -> None:
    """The Test Lab page must provide a safe, zero-credential local onboarding bridge."""
    app = AppTest.from_file(str(PAGE_DIRECTORY / "test_lab.py"), default_timeout=30).run()
    assert not app.exception

    rendered = " ".join(
        str(getattr(item, "value", ""))
        for element_type in ("caption", "markdown", "subheader", "header", "info")
        for item in app.get(element_type)
    )
    assert "Runs on your machine, never in this hosted app" in rendered
    assert "Python Function" in rendered
    assert any(b.key == "atlas_lab_download_starter_yaml" for b in app.download_button)
    assert any("atlas validate atlas.yaml" in item.value for item in app.code)

    # Test selecting each adapter kind via pills
    adapter_pills = next(item for item in app.pills if item.key == "atlas_lab_adapter_choice")
    expected_options = {"Python Function", "JSONL Subprocess", "OpenAI-Compatible"}
    assert set(adapter_pills.options) == expected_options

    adapter_pills.set_value("JSONL Subprocess").run()
    assert not app.exception
    assert any("agent_subprocess.py" in item.value for item in app.code)

    adapter_pills.set_value("OpenAI-Compatible").run()
    assert not app.exception
    assert any("ATLAS_API_KEY" in item.value for item in app.code)
    assert any("network_enabled: false" in item.value for item in app.code)


def test_test_lab_post_run_promotes_local_agent_bridge_as_step_two() -> None:
    """After running a live demo test, Test Lab must present Step 2 onboarding directly."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/test_lab.py").run(timeout=30)
    assert not app.exception

    run_button = next(item for item in app.button if item.label == "Run counterfactual test")
    app = run_button.click().run(timeout=30)
    assert not app.exception

    # Confirm certificate rendered
    assert any(item.value == "Reproducible failure found." for item in app.error)

    # Confirm Step 2 heading and onboarding elements are visibly present post-run
    assert any(
        item.value == "Step 2: Test your own agent against this failure mode"
        for item in app.subheader
    )
    assert any(b.key == "atlas_lab_download_starter_yaml" for b in app.download_button)
    assert any("atlas test --config atlas.yaml" in item.value for item in app.code)


def test_certificates_page_renders_complete_faultline_evidence() -> None:
    """The Certificates page must render the source, mutation, and counterfactual cards."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/certificates.py").run(timeout=30)

    assert not app.exception
    assert any(item.value == "The decision fault line" for item in app.subheader)
    assert any("Certificate JSON" in item.label for item in app.download_button)
    assert any("Complete run JSON" in item.label for item in app.download_button)




def test_compare_runs_page_handles_sample_and_paste_states() -> None:
    """Compare Runs must guide the empty and partial paste states and compute sample deltas."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/compare_runs.py").run(timeout=30)

    assert not app.exception
    assert any("No comparison loaded yet" in item.value for item in app.caption)

    # Click build sample comparison
    build_button = next(item for item in app.button if item.label == "Build the sample comparison")
    app = build_button.click().run(timeout=30)
    assert not app.exception
    assert any("Compatible run pair verified locally." in item.value for item in app.success)
    assert any(item.value == "What changed between runs" for item in app.subheader)

    # Switch to paste mode and verify empty state guidance
    mode_selector = next(item for item in app.segmented_control if item.key == "atlas_compare_mode")
    mode_selector.set_value("Paste runs").run()
    assert not app.exception
    assert any("Paste both Run A and Run B" in item.value for item in app.caption)




def test_research_page_renders_evidence_ledger_before_and_after_calibration() -> None:
    """Research page must provide an explicit Evidence Ledger tracking measured claims."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/research.py").run(timeout=30)

    assert not app.exception
    assert any(item.value == "Evidence Ledger" for item in app.subheader)
    rendered_md = [str(item.value) for item in app.markdown]
    assert any("Not yet measured" in text for text in rendered_md)
    assert any("Planned" in text for text in rendered_md)
    assert any("Out of scope" in text for text in rendered_md)
    assert not any(":green-badge[Measured]" in text for text in rendered_md)
    assert any(
        "deliberate starting state" in str(item.value) for item in app.info
    )

    # Run the 5-property calibration
    calib_button = next(
        item for item in app.button if item.label == "Run the five-property calibration"
    )
    app = calib_button.click().run(timeout=30)
    assert not app.exception
    assert not any(
        "deliberate starting state" in str(item.value) for item in app.info
    )
    assert any(
        item.value == "How often each failure repeated" for item in app.subheader
    )
    calibrated_md = [str(item.value) for item in app.markdown]
    assert any(":green-badge[Measured]" in text for text in calibrated_md)
    assert any("Planned" in text for text in calibrated_md)
    assert any("Out of scope" in text for text in calibrated_md)



def test_certificates_page_handles_deselection_with_recovery_content() -> None:
    """Deselecting the failure mode pill must render clear recovery guidance."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/certificates.py").run(timeout=30)

    assert not app.exception
    pills = next(item for item in app.pills if item.key == "atlas_gallery_property")
    assert pills.value == "red_signal_no_proceed"

    # Deselect the pill via session state
    app.session_state["atlas_gallery_property"] = None
    app = app.run(timeout=30)
    assert not app.exception
    assert any("A failure mode selection is required" in item.value for item in app.info)
    assert any(
        "Red signal requires a non-proceed action" in item.value
        for item in app.markdown
    )




def test_home_page_handles_empty_certificates_safely() -> None:
    """Home page must render honest warning copy when certificates list is empty."""
    from edgecase_atlas.engine import RunMetadata, RunResult
    from edgecase_atlas.evaluation import CallLedger
    from ui import DemoArtifacts

    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

    fake_doc = {
        "schema_version": "atlas-run-v1",
        "metadata": {
            "run_id": "run-empty-test",
            "seed": 42,
            "candidate_budget": 1,
            "property_ids": ["red_signal_no_proceed"],
        },
        "property_pack": [],
        "call_ledger": {
            "target_calls_total": 5,
            "search_calls": 5,
            "confirmation_calls": 0,
            "minimization_calls": 0,
            "estimated_cost_usd": 0.0,
            "cost_estimate_available": False,
            "invocations": [],
        },
        "coverage": {"estimand": "test", "cells": [], "trajectory": []},
        "certificates": [],
    }
    dummy_meta = RunMetadata(
        run_id="run-empty-test",
        seed=42,
        candidate_budget=1,
        held_out_confirmation_seed_stream="1",
        executed_seed_streams=("1",),
        property_ids=("red_signal_no_proceed",),
        property_pack_digest="digest",
        engine_config_hash="hash",
        confirmation_note="",
    )
    dummy_result = RunResult(
        metadata=dummy_meta,
        call_ledger=CallLedger(),
        coverage_estimand="test",
        coverage_cells=frozenset(),
        coverage_trajectory=(),
        certificates=(),
    )
    artifacts = DemoArtifacts(
        run=dummy_result,
        document=fake_doc,
        json_bytes=b"{}",
        jsonl_bytes=b"",
        html_bytes=b"<html></html>",
    )
    app.session_state["atlas_home_artifacts"] = artifacts
    app = app.run(timeout=30)

    assert not app.exception
    assert any("No reproducible failure was found." in item.value for item in app.warning)
    assert any(
        "This is not evidence that the agent is safe." in item.value
        for item in app.warning
    )




def test_test_lab_in_progress_running_state_displays_request_parameters() -> None:
    """Test Lab status block must display assumption count, budget, and seed from request."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/test_lab.py").run(timeout=30)

    assert not app.exception

    # Submit form with default inputs (1 property, budget=1, seed=42)
    submit_button = next(item for item in app.button if item.label == "Run counterfactual test")
    app = submit_button.click().run(timeout=30)

    assert not app.exception
    rendered_writes = [str(item.value) for item in app.get("markdown") if hasattr(item, "value")]
    # Verify the status step messages reflect real request parameters
    assert any("Validating 1 safety assumption(s)" in text for text in rendered_writes)
    assert any("1 scenario variation" in text for text in rendered_writes)
    assert any("repeat number 42" in text for text in rendered_writes)




def test_certificates_page_renders_prominent_replay_command() -> None:
    """Certificates page must display a dedicated replay command block before the fault line.

    Replayability is the core product promise, so the command has to be the visible takeaway
    rather than something a reviewer scrolls past. The ordering is asserted against the source,
    because a rendered-element search alone would still pass if the block moved to the bottom.
    """
    source = (PAGE_DIRECTORY / "certificates.py").read_text(encoding="utf-8")
    assert source.index('key="atlas_gallery_replay"') < source.index(
        "render_counterfactual_faultline("
    )

    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/certificates.py").run(timeout=30)

    assert not app.exception
    # Verify replay code block contains the replay CLI command
    code_blocks = [str(item.value) for item in app.code if hasattr(item, "value")]
    assert any("atlas replay certificates/" in block for block in code_blocks)


def test_rejected_paste_leaves_no_stale_comparison_on_screen() -> None:
    """A failure banner must never sit above a result panel from a different pair of runs.

    The delta lives in session state, so an invalid paste used to render the previous
    comparison directly beneath the error, with no indication which runs the numbers
    described.
    """
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/compare_runs.py").run(timeout=30)

    mode = next(item for item in app.segmented_control if item.key == "atlas_compare_mode")
    mode.set_value("Paste runs")
    app = app.run(timeout=30)

    for area in app.text_area:
        if area.key in ("atlas_compare_run_a", "atlas_compare_run_b"):
            area.set_value("this is not an atlas run document")
    app = app.run(timeout=30)

    app = next(b for b in app.button if b.key == "atlas_compare_pasted").click().run(timeout=30)

    assert not app.exception
    assert any("Run A is invalid:" in str(item.value) for item in app.error)
    assert not any(str(item.value) == "What changed between runs" for item in app.subheader)


def test_compare_runs_trace_paste_rejection_names_specific_error() -> None:
    """Trace inspection rejection must report the specific validation error message."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app = app.switch_page("app_pages/compare_runs.py").run(timeout=30)

    mode = next(item for item in app.segmented_control if item.key == "atlas_compare_mode")
    mode.set_value("Inspect trace")
    app = app.run(timeout=30)

    for area in app.text_area:
        if area.key == "atlas_compare_trace":
            area.set_value("this is not a jsonl trace")
    app = app.run(timeout=30)

    assert not app.exception
    assert any("Trace is invalid:" in str(item.value) for item in app.error)


def test_certificates_page_renders_empty_state_recovery_guidance() -> None:
    """Unselected failure mode state must render recovery guidance and starter properties."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app.session_state["atlas_gallery_property"] = None
    app = app.switch_page("app_pages/certificates.py").run(timeout=30)
    assert not app.exception

    assert any(
        "A failure mode selection is required" in str(item.value)
        for item in app.info
    )
    rendered_md = [str(item.value) for item in app.markdown]
    assert any("Red signal requires a non-proceed action" in text for text in rendered_md)
