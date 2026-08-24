"""Contracts for reusable native Streamlit product renderers."""

from __future__ import annotations

import ast
import inspect
import runpy
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "app" / "product_ui.py"


def _module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def _streamlit_calls(node: ast.AST) -> list[ast.Call]:
    return [
        item
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and isinstance(item.func.value, ast.Name)
        and item.func.value.id == "st"
    ]


def test_product_ui_uses_native_streamlit_without_executable_markup() -> None:
    source = _module_source()
    lowered = source.casefold()
    tree = ast.parse(source)
    calls = {
        call.func.attr for call in _streamlit_calls(tree) if isinstance(call.func, ast.Attribute)
    }

    assert "unsafe_allow_html" not in source
    assert "unsafe_allow_javascript" not in source
    assert "<script" not in lowered
    assert "javascript:" not in lowered
    assert "st.html(" not in source
    assert "components" not in calls
    assert calls.isdisjoint({"iframe", "connection", "experimental_connection"})


def test_every_public_renderer_requires_a_caller_supplied_stable_key() -> None:
    namespace = runpy.run_path(str(MODULE_PATH))

    expected_renderers = {
        "render_page_intro",
        "render_scenario_card",
        "render_counterfactual_faultline",
        "render_evidence_pipeline",
        "render_failure_certificate",
        "render_download_controls",
        "render_run_comparison_delta",
        "render_benchmark_result",
        "render_privacy_footer",
    }
    assert expected_renderers.issubset(set(namespace["__all__"]))

    for name in expected_renderers:
        parameter = inspect.signature(namespace[name]).parameters["key"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is inspect.Parameter.empty


def test_scenario_visual_uses_chips_and_metrics_instead_of_tables() -> None:
    tree = ast.parse(_module_source())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "render_scenario_card"
    )
    calls = {
        call.func.attr
        for call in _streamlit_calls(function)
        if isinstance(call.func, ast.Attribute)
    }

    assert "badge" in calls
    assert "metric" in calls
    assert calls.isdisjoint({"table", "dataframe", "data_editor"})


def test_product_ui_never_builds_a_grid_wider_than_four_columns() -> None:
    tree = ast.parse(_module_source())
    for call in _streamlit_calls(tree):
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "columns":
            continue
        assert call.args
        argument = call.args[0]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, int):
            assert argument.value <= 4
        elif isinstance(argument, (ast.List, ast.Tuple)):
            assert len(argument.elts) <= 4
        else:
            raise AssertionError("st.columns width must be statically reviewable")


def test_representative_product_helpers_render_with_apptest(tmp_path: Path) -> None:
    script = tmp_path / "component_preview.py"
    script.write_text(
        "\n".join(
            (
                "import sys",
                f"sys.path.insert(0, {str(ROOT)!r})",
                "from app.product_ui import render_page_intro, render_scenario_card",
                "render_page_intro(",
                "    eyebrow='Live safety evidence',",
                "    title='Test one controlled change',",
                "    lede='See whether a simulated decision stays safe.',",
                "    key='test_intro',",
                ")",
                "render_scenario_card(",
                "    'Source scenario',",
                "    {",
                "        'description': 'A synthetic urban intersection.',",
                "        'road_type': 'urban',",
                "        'speed_mph': 22.0,",
                "        'speed_limit_mph': 30.0,",
                "        'signal': 'red',",
                "        'surface': 'wet',",
                "        'visibility': 'reduced',",
                "        'actors': [{'actor_type': 'pedestrian'}],",
                "    },",
                "    key='test_scenario',",
                ")",
            )
        ),
        encoding="utf-8",
    )

    app = AppTest.from_file(str(script), default_timeout=20).run()

    assert not app.exception
    assert app.title[0].value == "Test one controlled change"
    assert {metric.label for metric in app.metric} == {"Test car speed", "Speed limit", "Actors"}
    rendered = " ".join(
        str(getattr(item, "value", ""))
        for element_type in ("caption", "markdown", "subheader")
        for item in app.get(element_type)
    )
    assert "A synthetic urban intersection." in rendered


def test_download_controls_keep_accessible_labels_and_derived_widget_keys(
    tmp_path: Path,
) -> None:
    script = tmp_path / "download_preview.py"
    script.write_text(
        "\n".join(
            (
                "import sys",
                f"sys.path.insert(0, {str(ROOT)!r})",
                "from app.product_ui import DownloadArtifact, render_download_controls",
                "render_download_controls(",
                "    (",
                "        DownloadArtifact(",
                "            'JSON certificate', b'{}', 'run.json', 'application/json',",
                "            ':material/data_object:',",
                "        ),",
                "        DownloadArtifact(",
                "            'Offline report', b'<html></html>', 'run.html', 'text/html',",
                "            ':material/article:',",
                "        ),",
                "    ),",
                "    key='test_downloads',",
                ")",
            )
        ),
        encoding="utf-8",
    )

    app = AppTest.from_file(str(script), default_timeout=20).run()

    assert not app.exception
    buttons = app.get("download_button")
    assert [button.label for button in buttons] == ["JSON certificate", "Offline report"]
    assert [button.key for button in buttons] == ["test_downloads_0", "test_downloads_1"]
