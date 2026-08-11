from __future__ import annotations

import asyncio
import json
import sys
import time
import types
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

import edgecase_atlas.adapters as adapters_module
import edgecase_atlas.cli as cli_module
from edgecase_atlas.adapters import (
    AdapterError,
    AdapterHttpError,
    AdapterProcessError,
    AdapterTimeoutError,
    FunctionAdapter,
    JsonlSubprocessAdapter,
    OpenAICompatibleAdapter,
    UsageMetadataError,
)
from edgecase_atlas.cli import app
from edgecase_atlas.engine import AtlasEngine
from edgecase_atlas.evaluation import adapter_model_id, model_config_hash
from edgecase_atlas.fixtures import FaultyDemonstrationAgent
from edgecase_atlas.models import Decision, FailureCertificate, Scenario
from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.reporting import render_html_report
from edgecase_atlas.serialization import run_document, trace_events

runner = CliRunner()
FIXTURE = Path(__file__).parent / "fixtures" / "jsonl_review_agent.py"


def _scenario() -> Scenario:
    from edgecase_atlas.fixtures import known_violation_cases

    return known_violation_cases()[0].counterfactual.follow_up


def _network_adapter(**overrides: Any) -> OpenAICompatibleAdapter:
    values: dict[str, Any] = {
        "base_url": "https://models.invalid/v1",
        "model": "review-model",
        "api_key_env": "ATLAS_REVIEW_KEY",
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


@pytest.mark.asyncio
@respx.mock
async def test_serialized_request_bound_rejects_underreservation_before_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_REVIEW_KEY", "unit-test-secret")
    route = respx.post("https://models.invalid/v1/chat/completions").mock(
        return_value=httpx.Response(200)
    )
    adapter = _network_adapter(
        input_cost_per_million_tokens=1_000_000,
        output_cost_per_million_tokens=1_000_000,
        input_token_reservation=1,
        max_tokens=1,
        cost_cap_usd=2,
    )
    with pytest.raises(UsageMetadataError):
        await adapter.decide(_scenario(), 1)
    assert route.call_count == 0
    assert adapter.budget.reserved_usd == 0
    await adapter.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_each_retry_reserves_proven_exact_request_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_REVIEW_KEY", "unit-test-secret")
    route = respx.post("https://models.invalid/v1/chat/completions").mock(
        return_value=httpx.Response(503)
    )
    adapter = _network_adapter(max_retries=1)
    with pytest.raises(AdapterHttpError):
        await adapter.decide(_scenario(), 1)
    request_bytes = len(route.calls[0].request.content)
    expected_per_attempt = (request_bytes + adapter.max_tokens) / 1_000_000
    assert route.call_count == 2
    assert adapter.budget.reserved_usd == pytest.approx(2 * expected_per_attempt)
    await adapter.aclose()


@pytest.mark.asyncio
async def test_cancellation_during_process_creation_reaps_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = asyncio.create_subprocess_exec
    child_created = asyncio.Event()
    release_creation = asyncio.Event()
    processes: list[asyncio.subprocess.Process] = []

    async def delayed_create(*args: object, **kwargs: object) -> asyncio.subprocess.Process:
        process = await original(*args, **kwargs)
        processes.append(process)
        child_created.set()
        await release_creation.wait()
        return process

    monkeypatch.setattr(adapters_module.asyncio, "create_subprocess_exec", delayed_create)
    adapter = JsonlSubprocessAdapter(
        (sys.executable, str(FIXTURE), "eof-live"),
        timeout_seconds=2,
        shutdown_timeout_seconds=0.2,
    )
    task = asyncio.create_task(adapter.decide(_scenario(), 1))
    await asyncio.wait_for(child_created.wait(), timeout=2)
    task.cancel()
    release_creation.set()
    try:
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
        assert processes[0].returncode is not None
        assert adapter.process is None
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
                await process.wait()


@pytest.mark.asyncio
async def test_live_process_eof_is_bounded_and_reaped() -> None:
    adapter = JsonlSubprocessAdapter(
        (sys.executable, str(FIXTURE), "eof-live"),
        timeout_seconds=2,
        shutdown_timeout_seconds=0.1,
    )
    process = await adapter._ensure_process()
    started = time.perf_counter()
    with pytest.raises(AdapterProcessError):
        await adapter._exit_status_or_abort(process)
    assert time.perf_counter() - started < 1
    assert process.returncode is not None
    assert adapter.process is None


@pytest.mark.asyncio
async def test_mixed_cost_certificate_serializes_unknown_while_trace_keeps_known_sum() -> None:
    class MixedCostAgent:
        model_id = "mixed-cost-faulty"

        def __init__(self) -> None:
            self.delegate = FaultyDemonstrationAgent()
            self.calls = 0
            self.last_call_cost_usd: float | None = None

        async def decide(self, scenario: Scenario, seed: int) -> Decision:
            self.calls += 1
            self.last_call_cost_usd = 0.01 if self.calls % 2 else None
            return await self.delegate.decide(scenario, seed)

    run = await AtlasEngine().run(MixedCostAgent(), STARTER_PROPERTY_PACK, seed=42, budget=1)
    certificate = run.certificates[0].certificate
    assert certificate.cost_estimate_available is False
    assert certificate.estimated_cost_usd == 0.0
    assert run.call_ledger.estimated_cost_usd > 0
    call_events = [event for event in trace_events(run) if event["event_type"] == "target_call"]
    assert any(event["invocation"]["cost_estimate_available"] for event in call_events)
    assert any(not event["invocation"]["cost_estimate_available"] for event in call_events)


def _create_cli_certificate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(app, ["test", "--config", "atlas.yaml", "--budget", "1", "--seed", "42"])
    assert result.exit_code == 0, result.output
    return next((tmp_path / "certificates").glob("*.json"))


@pytest.mark.parametrize("field", ["source_decisions", "reducer_label"])
def test_replay_rejects_semantic_tamper_with_stale_certificate_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    certificate_path = _create_cli_certificate(tmp_path, monkeypatch)
    data = json.loads(certificate_path.read_text(encoding="utf-8"))
    if field == "source_decisions":
        data[field][0] = {"action": "proceed", "risk": "low", "explanation": "forged"}
    else:
        data[field] = "forged reducer claim"
    forged = tmp_path / f"forged-{field}.json"
    forged.write_text(json.dumps(data), encoding="utf-8")
    assert runner.invoke(app, ["replay", str(forged)]).exit_code == 2


def test_replay_binds_exact_model_id_even_with_recomputed_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from edgecase_atlas.engine import recompute_certificate_id

    certificate_path = _create_cli_certificate(tmp_path, monkeypatch)
    original = FailureCertificate.model_validate_json(certificate_path.read_text(encoding="utf-8"))
    changed = original.model_copy(update={"model_id": "forged-model"})
    changed = changed.model_copy(update={"certificate_id": recompute_certificate_id(changed)})
    forged = tmp_path / "forged-model.json"
    forged.write_text(changed.model_dump_json(), encoding="utf-8")
    assert runner.invoke(app, ["replay", str(forged)]).exit_code == 2


def test_public_certificate_digest_recomputes_original_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from edgecase_atlas.engine import recompute_certificate_id

    path = _create_cli_certificate(tmp_path, monkeypatch)
    certificate = FailureCertificate.model_validate_json(path.read_text(encoding="utf-8"))
    assert recompute_certificate_id(certificate) == certificate.certificate_id


def test_cli_sanitizes_yaml_jinja_target_and_filesystem_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("adapter: [unterminated", encoding="utf-8")
    yaml_result = runner.invoke(app, ["validate", str(malformed)])
    assert yaml_result.exit_code == 2
    assert "ParserError" not in yaml_result.output

    monkeypatch.chdir(tmp_path)
    crafted = tmp_path / "crafted.json"
    crafted.write_text(
        json.dumps({"metadata": {"run_id": "run-0123456789abcdef"}}),
        encoding="utf-8",
    )
    jinja_result = runner.invoke(app, ["report", str(crafted), "--format", "html"])
    assert jinja_result.exit_code == 2
    assert "UndefinedError" not in jinja_result.output

    module = types.ModuleType("atlas_review_target")

    def explode(_scenario: Scenario, _seed: int) -> Decision:
        raise RuntimeError("target-controlled-private-detail")

    module.explode = explode  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "atlas_review_target", module)
    python_config = tmp_path / "python.yaml"
    python_config.write_text(
        "schema_version: atlas-config-v1\nadapter:\n  kind: python\n"
        "  module: atlas_review_target\n  callable: explode\n"
        "property_ids: [red_signal_no_proceed]\n",
        encoding="utf-8",
    )
    target_result = runner.invoke(
        app, ["test", "--config", str(python_config), "--budget", "1", "--seed", "42"]
    )
    assert target_result.exit_code == 2
    assert "target-controlled-private-detail" not in target_result.output

    demo_config = tmp_path / "demo.yaml"
    demo_config.write_text(
        "schema_version: atlas-config-v1\nadapter: {kind: faulty}\n"
        "property_ids: [red_signal_no_proceed]\n",
        encoding="utf-8",
    )

    def fail_write(_path: Path, _value: object) -> Path:
        raise OSError("private-filesystem-detail")

    monkeypatch.setattr(cli_module, "write_canonical_json", fail_write)
    fs_result = runner.invoke(
        app, ["test", "--config", str(demo_config), "--budget", "1", "--seed", "42"]
    )
    assert fs_result.exit_code == 2
    assert "private-filesystem-detail" not in fs_result.output


@pytest.mark.asyncio
async def test_function_adapter_uses_one_end_to_end_deadline() -> None:
    def two_stage(_scenario: Scenario, _seed: int):
        time.sleep(0.08)

        async def finish() -> Decision:
            await asyncio.sleep(0.08)
            return Decision(action="stop", risk="high", explanation="too late")

        return finish()

    adapter = FunctionAdapter(two_stage, timeout_seconds=0.1)
    started = time.perf_counter()
    with pytest.raises(AdapterTimeoutError):
        await adapter.decide(_scenario(), 1)
    assert time.perf_counter() - started < 0.14
    assert "cannot be forcibly terminated" in (FunctionAdapter.__doc__ or "")


@pytest.mark.asyncio
async def test_report_lists_selected_property_when_no_certificate(tmp_path: Path) -> None:
    class SafeAgent:
        async def decide(self, _scenario: Scenario, _seed: int) -> Decision:
            return Decision(action="stop", risk="high", explanation="safe")

    selected = (STARTER_PROPERTY_PACK[0],)
    run = await AtlasEngine().run(SafeAgent(), selected, seed=42, budget=1)
    assert not run.certificates
    output = tmp_path / "no-certificates.html"
    render_html_report(run_document(run), output)
    html = output.read_text(encoding="utf-8")
    assert selected[0].title in html
    assert selected[0].description in html
    assert selected[0].scope_note in html


def test_model_config_hash_covers_every_public_execution_parameter() -> None:
    command = (sys.executable, str(FIXTURE), "eof-live")
    base_process = JsonlSubprocessAdapter(command)
    process_variants = (
        JsonlSubprocessAdapter(command, model_id="other"),
        JsonlSubprocessAdapter(command, shutdown_timeout_seconds=2),
        JsonlSubprocessAdapter(command, stderr_limit_bytes=99),
    )
    assert all(
        model_config_hash(item) != model_config_hash(base_process) for item in process_variants
    )

    base_network = _network_adapter(retry_backoff_seconds=0.1)
    changed_network = _network_adapter(retry_backoff_seconds=9)
    assert model_config_hash(base_network) != model_config_hash(changed_network)
    assert adapter_model_id(base_process) != adapter_model_id(process_variants[0])


@pytest.mark.asyncio
@respx.mock
async def test_openai_resets_cost_before_early_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_REVIEW_KEY", "unit-test-secret")
    respx.post("https://models.invalid/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"action":"stop","risk":"high","explanation":"ok"}'}}
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
    )
    adapter = _network_adapter()
    await adapter.decide(_scenario(), 1)
    assert adapter.last_call_cost_usd is not None
    monkeypatch.delenv("ATLAS_REVIEW_KEY")
    with pytest.raises(AdapterError):
        await adapter.decide(_scenario(), 2)
    assert adapter.last_call_cost_usd is None
    await adapter.aclose()
