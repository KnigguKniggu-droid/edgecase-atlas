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
THEME_PATH = Path(__file__).parents[1] / "app" / "theme.py"
FONT_DIRECTORY = Path(__file__).parents[1] / "app" / "static" / "fonts"


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
    assert config["theme"]["font"] == "'IBM Plex Sans', sans-serif"
    assert config["theme"]["headingFont"] == "'IBM Plex Sans', sans-serif"
    assert config["theme"]["codeFont"] == "'IBM Plex Mono', monospace"
    assert "http" not in STREAMLIT_CONFIG_PATH.read_text(encoding="utf-8").lower()

    font_files = tuple(FONT_DIRECTORY.glob("*.woff2"))
    assert len(font_files) == 6
    assert all(path.stat().st_size > 10_000 for path in font_files)
    assert (FONT_DIRECTORY / "OFL.txt").is_file()


def test_public_entrypoint_excludes_execution_and_network_capabilities() -> None:
    """Adding a hosted execution or arbitrary-network surface must fail this test."""
    trees = [ast.parse(path.read_text(encoding="utf-8")) for path in (APP_PATH, UI_PATH)]
    nodes = [node for tree in trees for node in ast.walk(tree)]
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

    assert imported_roots.isdisjoint({"httpx", "requests", "socket", "subprocess", "urllib"})
    assert calls.isdisjoint({"file_uploader", "iframe", "connection", "experimental_connection"})
    app_source = APP_PATH.read_text(encoding="utf-8")
    theme_source = THEME_PATH.read_text(encoding="utf-8").lower()
    assert app_source.count("st.html(APP_CSS)") == 1
    assert "<script" not in theme_source
    assert "javascript:" not in theme_source
    assert "fonts.googleapis.com" not in theme_source
    assert "unsafe_allow_javascript" not in app_source
    assert "#mainmenu" in theme_source
    assert "visibility: hidden" in theme_source
    assert "text-transform: uppercase" in theme_source
    assert "letter-spacing" in theme_source
    assert "st.table(" in app_source
    assert "01 generate" in app_source.lower()
    assert "04 replay" in app_source.lower()
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
    """Removing labels, state choices, or unique keys must break the rendered app."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=20).run()

    assert not app.exception
    assert app.title[0].value == "EdgeCase Atlas"
    assert any("simulated research" in item.value.lower() for item in app.caption)
    assert len(app.multiselect) == 1
    assert app.multiselect[0].label == "Safety assumptions"
    assert len(app.number_input) == 2
    assert {item.label for item in app.number_input} == {"Seed", "Test budget"}
    assert len(app.text_area) == 1
    assert app.text_area[0].label == "Optional synthetic scenario context"

    widgets = [
        *app.selectbox,
        *app.multiselect,
        *app.number_input,
        *app.text_area,
        *app.button,
    ]
    keys = [item.key for item in widgets]
    assert all(keys)
    assert len(keys) == len(set(keys))
    assert any(item.label == "Run counterfactual test" for item in app.button)


def test_submit_runs_no_key_demo_and_renders_certificate() -> None:
    """Breaking the rendered no-key result path must surface an AppTest exception."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

    run_button = next(item for item in app.button if item.label == "Run counterfactual test")
    app = run_button.click().run(timeout=30)

    assert not app.exception
    assert any("Reproducible failure found" in item.value for item in app.error)
    assert {item.label for item in app.metric} == {
        "Reproduction",
        "Charged target calls",
        "Estimated cost",
        "Certificate latency",
    }
    assert any("atlas replay certificates/" in item.value for item in app.code)
    assert len(app.get("download_button")) == 3


def test_multiple_certificates_remain_individually_inspectable() -> None:
    """Hiding all but the first selected-property failure must fail this workflow."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app.multiselect[0].set_value(["red_signal_no_proceed", "hazard_non_aggression"])
    next(item for item in app.number_input if item.label == "Test budget").set_value(2)

    run_button = next(item for item in app.button if item.label == "Run counterfactual test")
    app = run_button.click().run(timeout=30)

    assert not app.exception
    certificate_picker = next(item for item in app.selectbox if item.label == "Failure certificate")
    assert len(certificate_picker.options) == 2


def test_empty_property_selection_is_reported_as_input_validation() -> None:
    """Submitting no safety assumptions must not be mislabeled as an adapter failure."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    app.multiselect[0].set_value([])

    run_button = next(item for item in app.button if item.label == "Run counterfactual test")
    app = run_button.click().run(timeout=30)

    assert not app.exception
    assert any("Select at least one safety assumption" in item.value for item in app.error)
    assert all("could not finish" not in item.value.lower() for item in app.error)


def test_tampered_preview_state_is_reset_without_traceback_or_value_leak() -> None:
    """A forged session-state preview ID must be validated before dictionary indexing."""
    injected_value = r"C:\private\fixture-secret"
    app = AppTest.from_file(str(APP_PATH), default_timeout=30)
    app.session_state["atlas_sample_input"] = injected_value

    app = app.run(timeout=30)

    assert not app.exception
    assert any("reset to a safe default" in item.value for item in app.warning)
    rendered = " ".join(
        str(getattr(item, "value", ""))
        for element_type in ("warning", "error", "caption", "info", "exception")
        for item in app.get(element_type)
    )
    assert injected_value not in rendered
    assert "streamlit_app.py" not in rendered


def test_curated_sample_selection_changes_the_executed_property() -> None:
    """The curated selector must affect the real run rather than only its preview."""
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
    sample_picker = next(
        item for item in app.selectbox if item.label == "Curated synthetic example"
    )
    sample_picker.set_value("hazard_non_aggression")

    run_button = next(item for item in app.button if item.label == "Run counterfactual test")
    app = run_button.click().run(timeout=30)

    assert not app.exception
    assert any(
        item.value == "Relevant hazards cannot increase aggression" for item in app.subheader
    )
