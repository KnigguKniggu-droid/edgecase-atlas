from __future__ import annotations

import asyncio
import sys
import time
import types
from pathlib import Path

import pytest
from typer.testing import CliRunner

import edgecase_atlas.adapters as adapters_module
import edgecase_atlas.cli as cli_module
from edgecase_atlas.adapters import JsonlSubprocessAdapter
from edgecase_atlas.cli import app
from edgecase_atlas.engine import recompute_certificate_id
from edgecase_atlas.models import Decision, FailureCertificate, Scenario

runner = CliRunner()
FIXTURE = Path(__file__).parent / "fixtures" / "jsonl_fix3_agent.py"


def _scenario() -> Scenario:
    from edgecase_atlas.fixtures import known_violation_cases

    return known_violation_cases()[0].counterfactual.follow_up


async def _wait_until_reaped(process: asyncio.subprocess.Process) -> None:
    await process.wait()


@pytest.mark.asyncio
async def test_repeated_creation_cancellation_has_independent_real_child_cleanup(
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
        (sys.executable, str(FIXTURE)),
        timeout_seconds=2,
        shutdown_timeout_seconds=0.2,
    )
    task = asyncio.create_task(adapter.decide(_scenario(), 1))
    await asyncio.wait_for(child_created.wait(), timeout=2)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    release_creation.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(_wait_until_reaped(processes[0]), timeout=0.75)
    assert processes[0].returncode is not None
    assert adapter.process is None


def _create_certificate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(
        app,
        ["test", "--config", "atlas.yaml", "--budget", "1", "--seed", "42"],
    )
    assert result.exit_code == 0, result.output
    return next((tmp_path / "certificates").glob("*.json"))


@pytest.mark.parametrize("recompute_id", [False, True])
def test_replay_rejects_noncanonical_command_before_adapter_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recompute_id: bool,
) -> None:
    certificate_path = _create_certificate(tmp_path, monkeypatch)
    certificate = FailureCertificate.model_validate_json(
        certificate_path.read_text(encoding="utf-8")
    )
    certificate = certificate.model_copy(update={"replay_command": "forged local command"})
    if recompute_id:
        certificate = certificate.model_copy(
            update={"certificate_id": recompute_certificate_id(certificate)}
        )
    forged = tmp_path / f"forged-command-{recompute_id}.json"
    forged.write_text(certificate.model_dump_json(), encoding="utf-8")
    constructed = False

    def forbidden_adapter_construction(_config: object) -> object:
        nonlocal constructed
        constructed = True
        raise AssertionError("adapter construction must not occur")

    monkeypatch.setattr(cli_module, "_build_adapter", forbidden_adapter_construction)
    result = runner.invoke(app, ["replay", str(forged)])
    assert result.exit_code == 2
    assert constructed is False


def test_cli_sync_python_timeout_is_observable_at_command_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = types.ModuleType("atlas_fix3_sync_target")

    def slow_target(_scenario: Scenario, _seed: int) -> Decision:
        time.sleep(0.6)
        return Decision(action="stop", risk="high", explanation="late trusted result")

    module.slow_target = slow_target  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "atlas_fix3_sync_target", module)
    config = tmp_path / "atlas.yaml"
    config.write_text(
        "schema_version: atlas-config-v1\n"
        "adapter:\n"
        "  kind: python\n"
        "  module: atlas_fix3_sync_target\n"
        "  callable: slow_target\n"
        "  timeout_seconds: 0.05\n"
        "property_ids: [red_signal_no_proceed]\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    started = time.perf_counter()
    result = runner.invoke(
        app,
        ["test", "--config", str(config), "--budget", "1", "--seed", "42"],
    )
    elapsed = time.perf_counter() - started
    assert result.exit_code == 2
    assert elapsed < 0.25
    assert "late trusted result" not in result.output
