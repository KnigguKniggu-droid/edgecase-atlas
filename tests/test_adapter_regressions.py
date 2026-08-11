from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import ValidationError

from edgecase_atlas.adapters import (
    AdapterHttpError,
    AdapterProcessError,
    AdapterSchemaError,
    AdapterTimeoutError,
    JsonlSubprocessAdapter,
    OpenAICompatibleAdapter,
)
from edgecase_atlas.config import OpenAIAdapterConfig
from edgecase_atlas.fixtures import known_violation_cases

FIXTURE = Path(__file__).parent / "fixtures" / "jsonl_edge_agent.py"


def _scenario():
    return known_violation_cases()[0].counterfactual.follow_up


def _adapter(**overrides: Any) -> OpenAICompatibleAdapter:
    values: dict[str, Any] = {
        "base_url": "https://models.invalid/v1",
        "model": "target",
        "api_key_env": "ATLAS_TEST_KEY",
        "network_enabled": True,
        "input_cost_per_million_tokens": 1.0,
        "output_cost_per_million_tokens": 1.0,
        "input_token_reservation": 10_000,
        "max_tokens": 100,
        "max_retries": 0,
        "retry_backoff_seconds": 0,
    }
    values.update(overrides)
    return OpenAICompatibleAdapter(**values)


@pytest.mark.parametrize(
    "url",
    [
        "http://models.invalid/v1",
        "https://user:password@models.invalid/v1",
        "https://models.invalid/v1?api_key=secret",
    ],
)
def test_remote_cleartext_userinfo_and_query_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        OpenAIAdapterConfig(base_url=url, model="target", api_key_env="ATLAS_TEST_KEY")
    with pytest.raises(ValueError):
        _adapter(base_url=url)


@pytest.mark.parametrize("url", ["http://localhost:8000/v1", "http://127.0.0.1:8000/v1"])
def test_loopback_http_is_allowed_for_local_servers(url: str) -> None:
    assert (
        OpenAIAdapterConfig(base_url=url, model="target", api_key_env="ATLAS_TEST_KEY").base_url
        == url
    )
    adapter = _adapter(base_url=url)
    assert adapter.base_url == url


def test_literal_secret_is_not_accepted_as_an_environment_name() -> None:
    with pytest.raises(ValidationError):
        OpenAIAdapterConfig(
            base_url="https://models.invalid/v1",
            model="target",
            api_key_env="literal-secret-value!",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (httpx.ReadTimeout("timeout"), AdapterTimeoutError),
        (httpx.ConnectError("transport"), AdapterHttpError),
    ],
)
@respx.mock
async def test_openai_transport_failures_are_typed_and_bounded(
    monkeypatch: pytest.MonkeyPatch, failure: Exception, error: type[Exception]
) -> None:
    monkeypatch.setenv("ATLAS_TEST_KEY", "unit-test-secret")
    route = respx.post("https://models.invalid/v1/chat/completions").mock(side_effect=failure)
    adapter = _adapter()
    with pytest.raises(error):
        await adapter.decide(_scenario(), 1)
    assert route.call_count == 1
    await adapter.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        json.dumps({"action": "swerve", "risk": "low", "explanation": "unknown"}),
    ],
)
@respx.mock
async def test_openai_malformed_and_unknown_decisions_are_schema_failures(
    monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    monkeypatch.setenv("ATLAS_TEST_KEY", "unit-test-secret")
    respx.post("https://models.invalid/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
    )
    adapter = _adapter()
    with pytest.raises(AdapterSchemaError):
        await adapter.decide(_scenario(), 1)
    await adapter.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_retry_stops_exactly_after_configured_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_TEST_KEY", "unit-test-secret")
    route = respx.post("https://models.invalid/v1/chat/completions").mock(
        return_value=httpx.Response(503)
    )
    adapter = _adapter(max_retries=1)
    with pytest.raises(AdapterHttpError):
        await adapter.decide(_scenario(), 1)
    assert route.call_count == 2
    await adapter.aclose()


@pytest.mark.asyncio
async def test_subprocess_crash_diagnostic_is_bounded() -> None:
    adapter = JsonlSubprocessAdapter(
        (sys.executable, str(FIXTURE), "stderr-crash"),
        timeout_seconds=2,
        stderr_limit_bytes=64,
    )
    with pytest.raises(AdapterProcessError) as caught:
        await adapter.decide(_scenario(), 1)
    assert len(str(caught.value)) < 200
    assert adapter.process is None


@pytest.mark.asyncio
async def test_subprocess_overlong_stdout_is_typed_and_cleaned() -> None:
    adapter = JsonlSubprocessAdapter((sys.executable, str(FIXTURE), "overlong"), timeout_seconds=2)
    with pytest.raises(AdapterSchemaError):
        await adapter.decide(_scenario(), 1)
    assert adapter.process is None


@pytest.mark.asyncio
async def test_subprocess_cancellation_cleans_up_without_orphan() -> None:
    adapter = JsonlSubprocessAdapter(
        (
            sys.executable,
            str(Path(__file__).parent / "fixtures" / "jsonl_agent.py"),
            "slow",
        ),
        timeout_seconds=5,
    )
    task = asyncio.create_task(adapter.decide(_scenario(), 1))
    for _ in range(100):
        if adapter.process_id is not None:
            break
        await asyncio.sleep(0.01)
    process = adapter.process
    assert process is not None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert process.returncode is not None
    assert adapter.process is None
