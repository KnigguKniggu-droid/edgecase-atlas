from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from edgecase_atlas.config import (
    AtlasConfig,
    FaultyAdapterConfig,
    OpenAIAdapterConfig,
    load_config,
)


def test_faulty_config_is_strict_and_defaults_to_safe_demo() -> None:
    config = AtlasConfig()
    assert isinstance(config.adapter, FaultyAdapterConfig)
    assert config.adapter.kind == "faulty"
    with pytest.raises(ValidationError):
        AtlasConfig.model_validate({"adapter": {"kind": "faulty", "api_key": "secret"}})


def test_openai_config_requires_env_var_name_and_deliberate_network_enable() -> None:
    config = OpenAIAdapterConfig(
        base_url="https://models.invalid/v1",
        model="test-model",
        api_key_env="ATLAS_API_KEY",
    )
    assert config.network_enabled is False
    with pytest.raises(ValidationError):
        OpenAIAdapterConfig(
            base_url="https://models.invalid/v1",
            model="test-model",
            api_key_env="literal-secret-value!",
        )


def test_load_config_rejects_extra_keys_and_literal_secrets(tmp_path: Path) -> None:
    path = tmp_path / "atlas.yaml"
    path.write_text(
        "schema_version: atlas-config-v1\nadapter:\n  kind: openai\n"
        "  base_url: https://models.invalid/v1\n  model: target\n"
        "  api_key_env: ATLAS_KEY\n  api_key: should-not-be-here\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_config(path)


def test_load_config_parses_python_and_subprocess_variants(tmp_path: Path) -> None:
    python_path = tmp_path / "python.yaml"
    python_path.write_text(
        "schema_version: atlas-config-v1\nadapter:\n  kind: python\n"
        "  module: sample_agent\n  callable: decide\n",
        encoding="utf-8",
    )
    process_path = tmp_path / "process.yaml"
    process_path.write_text(
        "schema_version: atlas-config-v1\nadapter:\n  kind: subprocess\n"
        "  command: [python, agent.py]\n",
        encoding="utf-8",
    )
    assert load_config(python_path).adapter.kind == "python"
    assert load_config(process_path).adapter.kind == "subprocess"
