"""Strict YAML configuration with secret-by-environment references only."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator

from edgecase_atlas.adapters import validate_openai_base_url
from edgecase_atlas.properties import STARTER_PROPERTY_PACK

_ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]{1,127}$")
_DOTTED_NAME = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
_PROPERTY_IDS = frozenset(item.property_id for item in STARTER_PROPERTY_PACK)


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, str_strip_whitespace=True)


class FaultyAdapterConfig(ConfigModel):
    kind: Literal["faulty"] = "faulty"


class PythonAdapterConfig(ConfigModel):
    kind: Literal["python"] = "python"
    module: str = Field(min_length=1, max_length=240)
    callable: str = Field(min_length=1, max_length=120)
    timeout_seconds: float = Field(default=30.0, gt=0, le=600)

    @field_validator("module", "callable")
    @classmethod
    def validate_python_name(cls, value: str) -> str:
        if not _DOTTED_NAME.fullmatch(value):
            raise ValueError("Python module and callable must be dotted identifiers")
        return value


class SubprocessAdapterConfig(ConfigModel):
    kind: Literal["subprocess"] = "subprocess"
    command: tuple[str, ...] = Field(min_length=1, max_length=64)
    timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    shutdown_timeout_seconds: float = Field(default=1.0, gt=0, le=30)
    stderr_limit_bytes: int = Field(default=16_384, ge=0, le=1_048_576)
    model_id: str = Field(default="jsonl-subprocess", min_length=1, max_length=200)

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or len(item) > 1_000 for item in value):
            raise ValueError("command arguments must be nonempty and bounded")
        return value


class OpenAIAdapterConfig(ConfigModel):
    kind: Literal["openai"] = "openai"
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    api_key_env: str = Field(min_length=2, max_length=128)
    network_enabled: bool = False
    timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    max_retries: int = Field(default=2, ge=0, le=5)
    retry_backoff_seconds: float = Field(default=0.25, ge=0, le=30)
    input_cost_per_million_tokens: float = Field(default=0.0, ge=0)
    output_cost_per_million_tokens: float = Field(default=0.0, ge=0)
    input_token_reservation: int = Field(default=8_192, gt=0, le=1_000_000)
    max_tokens: int = Field(default=512, gt=0, le=100_000)
    cost_cap_usd: float = Field(default=25.0, gt=0, le=25.0)

    @field_validator("api_key_env")
    @classmethod
    def validate_api_key_environment_name(cls, value: str) -> str:
        if not _ENV_NAME.fullmatch(value):
            raise ValueError("api_key_env must be an uppercase environment-variable name")
        return value

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return validate_openai_base_url(value)


AdapterConfig = Annotated[
    FaultyAdapterConfig | PythonAdapterConfig | SubprocessAdapterConfig | OpenAIAdapterConfig,
    Field(discriminator="kind"),
]


class AtlasConfig(ConfigModel):
    schema_version: Literal["atlas-config-v1"] = "atlas-config-v1"
    adapter: AdapterConfig = Field(default_factory=FaultyAdapterConfig)
    property_ids: tuple[str, ...] = tuple(item.property_id for item in STARTER_PROPERTY_PACK)

    @field_validator("property_ids")
    @classmethod
    def validate_property_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("property_ids must be nonempty and unique")
        unknown = set(value) - _PROPERTY_IDS
        if unknown:
            raise ValueError(f"Unknown starter property IDs: {sorted(unknown)}")
        return value


def load_config(path: Path | str) -> AtlasConfig:
    """Load one strict YAML document without resolving or persisting secrets."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("Atlas configuration must be a YAML mapping")
    return AtlasConfig.model_validate(_normalize_yaml_collections(raw))


def _normalize_yaml_collections(raw: dict[object, object]) -> dict[object, object]:
    result = dict(raw)
    adapter = result.get("adapter")
    if isinstance(adapter, dict):
        normalized_adapter = dict(adapter)
        command = normalized_adapter.get("command")
        if isinstance(command, list):
            normalized_adapter["command"] = tuple(command)
        result["adapter"] = normalized_adapter
    property_ids = result.get("property_ids")
    if isinstance(property_ids, list):
        result["property_ids"] = tuple(property_ids)
    return result


DEFAULT_CONFIG_YAML = """\
schema_version: atlas-config-v1
adapter:
  kind: faulty
property_ids:
  - red_signal_no_proceed
  - hazard_non_aggression
  - overspeed_risk_monotonicity
  - crossing_pedestrian_caution
  - paraphrase_invariance
"""
