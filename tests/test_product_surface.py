"""Public product architecture, copy, and security regression coverage."""

from __future__ import annotations

import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parents[1]
ENTRYPOINT = ROOT / "app" / "streamlit_app.py"
THEME_PATH = ROOT / "app" / "theme.py"
PAGES = {
    "home": ROOT / "app" / "app_pages" / "home.py",
    "test_lab": ROOT / "app" / "app_pages" / "test_lab.py",
    "compare_runs": ROOT / "app" / "app_pages" / "compare_runs.py",
    "certificates": ROOT / "app" / "app_pages" / "certificates.py",
    "research": ROOT / "app" / "app_pages" / "research.py",
}


def test_public_surface_has_five_real_top_level_workflows() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8")

    assert source.count("st.navigation(") == 1
    assert 'position="hidden"' in source
    assert 'key="atlas_shell_nav"' in source
    assert set(PAGES) == {"home", "test_lab", "compare_runs", "certificates", "research"}
    assert all(path.is_file() for path in PAGES.values())

    # Routes and the visible bar must render from one PAGE_SPECS tuple, so each page path and
    # title appears exactly once and a page cannot be registered without also being reachable.
    assert source.count("st.Page(") == 1
    assert source.count("st.page_link(") == 1
    for path in PAGES.values():
        assert source.count(f'"app_pages/{path.name}"') == 1
    for title in ("Home", "Test Lab", "Compare Runs", "Certificates", "Research"):
        assert source.count(f'"{title}"') == 1


def test_app_modules_never_mutate_the_import_path() -> None:
    """Module ownership must hold without sys.path or PYTHONPATH rewriting.

    Streamlit prepends the entrypoint directory automatically, and shared domain code lives in
    the installed ``edgecase_atlas`` package, so any path mutation here would mask a broken
    import contract for CLI users, packaged installs, and repository-root test runs.
    """
    for path in (ENTRYPOINT, *PAGES.values(), *sorted((ROOT / "app").glob("*.py"))):
        source = path.read_text(encoding="utf-8")
        assert "sys.path" not in source, f"{path.name} mutates sys.path"
        assert "PYTHONPATH" not in source, f"{path.name} depends on PYTHONPATH"
    assert not (ROOT / "app" / "starter_config.py").exists()


def test_page_sources_keep_uploads_inert_and_avoid_unsafe_html() -> None:
    for path in PAGES.values():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        imported_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }

        assert "unsafe_allow_html" not in source
        assert "<script" not in source.lower()
        assert imported_roots.isdisjoint({"subprocess", "socket", "requests", "httpx", "urllib"})
        assert calls.isdisjoint({"iframe", "connection", "experimental_connection"})


def test_home_renders_product_thesis_and_one_click_demo() -> None:
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=30).run()

    assert not app.exception
    assert any(
        item.value == "Catch the decision change before it becomes a driving failure."
        for item in app.header
    )
    assert any(item.label == "Run the live safety break" for item in app.button)
    rendered = " ".join(
        str(getattr(item, "value", ""))
        for element_type in ("caption", "markdown", "subheader", "header", "info")
        for item in app.get(element_type)
    )
    assert "No API key" in rendered
    assert "synthetic" in rendered.lower()


def test_all_public_pages_use_plain_product_language() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in PAGES.values()).lower()

    assert "constraint-guided counterfactual fuzzing" not in combined
    assert "reason-responsive" not in combined
    assert "universal safety law" not in combined
    assert "vehicle controller" not in combined
    assert "one controlled change" in combined
    assert "simulated" in combined


def test_responsive_theme_rules_stack_narrow_layouts_and_prevent_horizontal_body_overflow() -> None:
    """Narrow viewports (< 640px) must stack two-column layouts and prevent page overflow."""
    theme_source = THEME_PATH.read_text(encoding="utf-8")

    assert "@media (max-width: 640px)" in theme_source
    assert ".st-key-atlas_lab_onboarding_section" in theme_source
    assert "flex-direction: column" in theme_source
    assert "-webkit-overflow-scrolling: touch" in theme_source
