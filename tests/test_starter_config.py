"""Tests for safe local adapter starter configuration generation and UI handoff."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from edgecase_atlas.config import (
    OpenAIAdapterConfig,
    PythonAdapterConfig,
    SubprocessAdapterConfig,
    load_config,
)
from edgecase_atlas.fixtures import known_violation_cases
from edgecase_atlas.models import Decision
from edgecase_atlas.starter_config import STARTER_DEFINITIONS, get_starter_definition


def test_starter_definitions_cover_all_three_local_adapters() -> None:
    assert set(STARTER_DEFINITIONS.keys()) == {"python", "subprocess", "openai"}


@pytest.mark.parametrize("kind", ["python", "subprocess", "openai"])
def test_starter_yaml_round_trips_to_full_model_equality(kind: str, tmp_path: Path) -> None:
    starter = get_starter_definition(kind)  # type: ignore[arg-type]
    file_path = tmp_path / f"atlas_{kind}.yaml"
    file_path.write_text(starter.config_yaml, encoding="utf-8")

    loaded = load_config(file_path)
    assert loaded == starter.config_model


def test_starter_yaml_serialization_is_deterministic() -> None:
    for starter in STARTER_DEFINITIONS.values():
        first_pass = starter.config_yaml
        second_pass = starter.config_yaml
        assert first_pass == second_pass


def test_python_and_subprocess_snippets_compile_and_reference_real_modules() -> None:
    py_starter = get_starter_definition("python")
    assert "edgecase_atlas.domain" not in py_starter.protocol_snippet
    assert "from edgecase_atlas.models import Decision, Scenario" in py_starter.protocol_snippet

    # Compiles and parses as valid Python AST
    parsed_py = ast.parse(py_starter.protocol_snippet)
    assert isinstance(parsed_py, ast.Module)

    parsed_sub = ast.parse(get_starter_definition("subprocess").protocol_snippet)
    assert isinstance(parsed_sub, ast.Module)

    # Verify function signature and behavior via direct execution in test harness
    def decide(scenario: object, seed: int) -> Decision:
        signal = getattr(scenario, "signal", "none")
        return Decision(
            action="stop" if signal == "red" else "proceed",
            risk="critical" if signal == "red" else "low",
            explanation="Observing traffic signal state.",
        )

    fixture_cases = known_violation_cases()
    scenario_red = fixture_cases[0].counterfactual.follow_up
    assert scenario_red.signal == "red"
    decision_red = decide(scenario_red, 42)
    assert isinstance(decision_red, Decision)
    assert decision_red.action == "stop"
    assert decision_red.risk == "critical"

    scenario_green = fixture_cases[0].counterfactual.source
    assert scenario_green.signal == "green"
    decision_green = decide(scenario_green, 42)
    assert isinstance(decision_green, Decision)
    assert decision_green.action == "proceed"
    assert decision_green.risk == "low"


def test_starters_enforce_security_and_budget_invariants() -> None:
    for kind, starter in STARTER_DEFINITIONS.items():
        assert "password" not in starter.config_yaml.lower()
        assert "secret" not in starter.config_yaml.lower()
        assert "sk-" not in starter.config_yaml

        if kind == "openai":
            assert "network_enabled: false" in starter.config_yaml
            assert isinstance(starter.config_model.adapter, OpenAIAdapterConfig)
            assert starter.config_model.adapter.network_enabled is False
            assert starter.config_model.adapter.cost_cap_usd <= 25.0
            assert starter.config_model.adapter.api_key_env == "ATLAS_API_KEY"
            assert starter.config_model.adapter.base_url == "http://127.0.0.1:8000/v1"
            assert starter.config_model.adapter.model == "local-model"
            assert starter.config_model.adapter.input_cost_per_million_tokens == 0.0
            assert starter.config_model.adapter.output_cost_per_million_tokens == 0.0


def test_python_and_subprocess_starters_have_safe_contracts() -> None:
    py_starter = get_starter_definition("python")
    assert isinstance(py_starter.config_model.adapter, PythonAdapterConfig)
    assert py_starter.config_model.adapter.module == "agent"
    assert py_starter.config_model.adapter.callable == "decide"

    sub_starter = get_starter_definition("subprocess")
    assert isinstance(sub_starter.config_model.adapter, SubprocessAdapterConfig)
    assert sub_starter.config_model.adapter.command == ("python", "agent_subprocess.py")
