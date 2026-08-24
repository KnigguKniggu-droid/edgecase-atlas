"""Public product architecture, copy, and security regression coverage."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

from edgecase_atlas.fixtures import known_violation_cases
from edgecase_atlas.properties import (
    CONFIRMATION_TRIALS,
    REQUIRED_REPRODUCTIONS,
    STARTER_PROPERTY_PACK,
)

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


def test_home_causal_chain_states_only_values_read_from_the_fixture() -> None:
    """The chain banner must describe the method, never assert a result before the run.

    A hardcoded outcome here would be a fabricated metric on the most-viewed public surface,
    and it would silently drift the moment the fixture or the reproduction gate changed.
    """
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=60).run()
    assert not app.exception

    case = next(
        item for item in known_violation_cases() if item.property_id == "red_signal_no_proceed"
    )
    tested_property = next(
        item for item in STARTER_PROPERTY_PACK if item.property_id == case.property_id
    )
    captions = [str(item.value) for item in app.caption]
    assert "THE CAUSAL EVIDENCE PIPELINE" in captions
    banner = next(caption for caption in captions if "assumption under test" in caption)
    assert tested_property.title in banner

    # Home spells the gate out rather than importing it, so assert the copy still matches.
    assert f"at least {REQUIRED_REPRODUCTIONS} of {CONFIRMATION_TRIALS} reruns" in banner

    # The published stat tiles must agree with the same sources, not restate them as literals.
    metrics = {str(item.label): str(item.value) for item in app.metric}
    assert metrics["editable assumptions"] == str(len(STARTER_PROPERTY_PACK))
    assert metrics["repeats required to count"] == f"{REQUIRED_REPRODUCTIONS}/{CONFIRMATION_TRIALS}"

    # The removed banner asserted an outcome before any run had happened.
    assert "Decision Flip" not in PAGES["home"].read_text(encoding="utf-8")


def test_a_page_test_passes_on_its_own_without_a_prior_entrypoint_load() -> None:
    """Page tests must not depend on another test having put ``app`` on ``sys.path``.

    Streamlit adds the entrypoint directory itself, so pages import ``product_ui`` and ``theme``
    bare. Before ``pythonpath`` was declared for pytest, a page test passed only in a full run
    and failed alone, which hides real breakage behind test ordering.
    """
    selected = (
        "tests/test_streamlit_app.py"
        "::test_test_lab_renders_local_agent_integration_onboarding"
    )
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", selected, "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_research_page_gate_copy_matches_the_published_constants() -> None:
    """The Research page spells the gate out, so hold that copy to the real constants.

    Home already has this guard. Without the same one here, changing the gate would leave the
    most research-facing page stating a number the engine no longer uses, with every test green.
    """
    source = PAGES["research"].read_text(encoding="utf-8")
    expected = f"{REQUIRED_REPRODUCTIONS}-of-{CONFIRMATION_TRIALS}"
    assert f'GATE_SUMMARY = "{expected}"' in source
    assert "4-of-5" not in source.replace(f'GATE_SUMMARY = "{expected}"', "")


def test_fault_line_text_wraps_on_the_narrowest_supported_screens() -> None:
    """The fault line must stay legible at 320 to 360px instead of overflowing.

    Its cards pack badges and metrics into horizontal rows, which run past the viewport on the
    smallest phones. This asserts the narrow-screen rules exist and are scoped to the fault
    line, so a later edit cannot quietly drop them or widen their blast radius.
    """
    theme_source = THEME_PATH.read_text(encoding="utf-8")
    query = "@media (max-width: 360px)"
    assert query in theme_source

    # Take just this query, up to whatever rule follows it.
    remainder = theme_source[theme_source.index(query) + len(query) :]
    block = remainder.split("@media")[0]

    assert "_faultline" in block
    assert "flex-wrap: wrap" in block
    assert "overflow-wrap: anywhere" in block or "word-break: break-word" in block


def test_mutation_card_renders_scenario_id_explanation_caption() -> None:
    """Mutation card must explain why scenario_id is not counted as a tested factor."""
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=30).run()
    assert not app.exception

    captions = [str(item.value) for item in app.caption]
    assert any(
        "scenario identifier changes with every follow-up scenario" in text
        for text in captions
    )


def test_completed_run_replaces_the_illustrative_fault_line_with_its_own() -> None:
    """After a run, the pair on screen must be the one that produced the certificate.

    Home renders an illustrative fixture pair so the page explains itself before anything is
    run. Leaving that pair up afterwards put a scenario comparison directly above a
    certificate it did not come from, which is the single most credibility-damaging thing
    this page could do.
    """
    app = AppTest.from_file(str(ENTRYPOINT), default_timeout=60).run()
    assert not app.exception

    def fault_lines(rendered: object) -> int:
        return sum(
            1
            for item in rendered.subheader  # type: ignore[attr-defined]
            if "fault line" in str(item.value).lower()
        )

    assert fault_lines(app) == 1

    run_button = next(item for item in app.button if item.key == "atlas_home_run")
    app = run_button.click().run(timeout=180)
    assert not app.exception

    # Exactly one, and it is the certificate's own pair rather than the fixture.
    assert fault_lines(app) == 1
    home_source = PAGES["home"].read_text(encoding="utf-8")
    assert 'key="atlas_home_result_faultline"' in home_source
    assert 'certificate["minimized_follow_up"]' in home_source
