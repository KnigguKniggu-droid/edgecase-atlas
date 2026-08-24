"""Starter configuration and safe local adapter definitions for EdgeCase Atlas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import yaml

from edgecase_atlas.config import (
    AtlasConfig,
    OpenAIAdapterConfig,
    PythonAdapterConfig,
    SubprocessAdapterConfig,
)
from edgecase_atlas.properties import STARTER_PROPERTY_PACK

LocalAdapterKind = Literal["python", "subprocess", "openai"]


@dataclass(frozen=True)
class AdapterStarter:
    kind: LocalAdapterKind
    title: str
    summary: str
    protocol_snippet: str
    config_model: AtlasConfig

    @property
    def config_yaml(self) -> str:
        """Deterministically serialize the validated AtlasConfig model to YAML."""
        payload = self.config_model.model_dump(mode="json")
        return yaml.safe_dump(payload, sort_keys=False)


PYTHON_PROTOCOL_SNIPPET = """\
# agent.py
from edgecase_atlas.models import Decision, Scenario

def decide(scenario: Scenario, seed: int) -> Decision:
    # Your decision reasoning logic
    return Decision(
        action="stop" if scenario.signal == "red" else "proceed",
        risk="critical" if scenario.signal == "red" else "low",
        explanation="Observing traffic signal state.",
    )
"""

SUBPROCESS_PROTOCOL_SNIPPET = """\
# agent_subprocess.py (stdin -> stdout JSONL protocol)
import json, sys

for line in sys.stdin:
    if not line.strip():
        continue
    scenario = json.loads(line)
    decision = {
        "action": "stop" if scenario.get("signal") == "red" else "proceed",
        "risk": "critical" if scenario.get("signal") == "red" else "low",
        "explanation": "Evaluated via subprocess JSONL stream.",
    }
    sys.stdout.write(json.dumps(decision) + "\\n")
    sys.stdout.flush()
"""

OPENAI_PROTOCOL_SNIPPET = """\
# Requires setting ATLAS_API_KEY in your local environment
# Explicitly set network_enabled: true in atlas.yaml when ready to run.
#
# Terminal:
#   export ATLAS_API_KEY="your-key-here"
#   atlas validate atlas.yaml
#   atlas test --config atlas.yaml --budget 100 --seed 42
"""

_DEFAULT_PROPERTY_IDS = tuple(item.property_id for item in STARTER_PROPERTY_PACK)

STARTER_DEFINITIONS: dict[LocalAdapterKind, AdapterStarter] = {
    "python": AdapterStarter(
        kind="python",
        title="Python Function",
        summary=(
            "Connect an in-process sync or async Python callable: "
            "decide(scenario, seed) -> Decision."
        ),
        protocol_snippet=PYTHON_PROTOCOL_SNIPPET,
        config_model=AtlasConfig(
            schema_version="atlas-config-v1",
            adapter=PythonAdapterConfig(
                kind="python",
                module="agent",
                callable="decide",
                timeout_seconds=30.0,
            ),
            property_ids=_DEFAULT_PROPERTY_IDS,
        ),
    ),
    "subprocess": AdapterStarter(
        kind="subprocess",
        title="Persistent JSONL Subprocess",
        summary=(
            "Connect any standalone executable reading Scenario JSON from stdin "
            "and writing Decision JSON to stdout. The protocol carries no trial seed, so "
            "reruns send identical input and only your agent's own randomness varies."
        ),
        protocol_snippet=SUBPROCESS_PROTOCOL_SNIPPET,
        config_model=AtlasConfig(
            schema_version="atlas-config-v1",
            adapter=SubprocessAdapterConfig(
                kind="subprocess",
                command=("python", "agent_subprocess.py"),
                timeout_seconds=30.0,
                shutdown_timeout_seconds=1.0,
                stderr_limit_bytes=16384,
                model_id="jsonl-subprocess",
            ),
            property_ids=_DEFAULT_PROPERTY_IDS,
        ),
    ),
    "openai": AdapterStarter(
        kind="openai",
        title="OpenAI-Compatible Endpoint",
        summary=(
            "Connect an OpenAI-compatible HTTP model target via environment-variable "
            "key with loopback safety defaults."
        ),
        protocol_snippet=OPENAI_PROTOCOL_SNIPPET,
        config_model=AtlasConfig(
            schema_version="atlas-config-v1",
            adapter=OpenAIAdapterConfig(
                kind="openai",
                base_url="http://127.0.0.1:8000/v1",
                model="local-model",
                api_key_env="ATLAS_API_KEY",
                network_enabled=False,
                timeout_seconds=30.0,
                max_retries=2,
                retry_backoff_seconds=0.25,
                input_cost_per_million_tokens=0.0,
                output_cost_per_million_tokens=0.0,
                input_token_reservation=8192,
                max_tokens=512,
                cost_cap_usd=25.0,
            ),
            property_ids=_DEFAULT_PROPERTY_IDS,
        ),
    ),
}


def get_starter_definition(kind: LocalAdapterKind) -> AdapterStarter:
    """Retrieve the immutable starter definition for a local adapter kind."""
    return STARTER_DEFINITIONS[kind]
