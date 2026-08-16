from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

import edgecase_atlas.adapters as adapters_module
from edgecase_atlas.adapters import AdapterProcessError, JsonlSubprocessAdapter
from edgecase_atlas.models import Scenario

FIXTURE = Path(__file__).parent / "fixtures" / "jsonl_fix3_agent.py"


def _scenario() -> Scenario:
    from edgecase_atlas.fixtures import known_violation_cases

    return known_violation_cases()[0].counterfactual.follow_up


def test_repeated_aclose_cancellation_defers_until_real_child_is_reaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_create = asyncio.create_subprocess_exec
    original_reap = JsonlSubprocessAdapter._reap_detached_process
    processes: list[asyncio.subprocess.Process] = []

    async def probe() -> tuple[
        asyncio.subprocess.Process,
        asyncio.subprocess.Process | None,
        int,
        int,
        int,
    ]:
        child_created = asyncio.Event()
        release_creation = asyncio.Event()
        reaper_started = asyncio.Event()
        release_reaper = asyncio.Event()

        async def delayed_create(*args: object, **kwargs: object) -> asyncio.subprocess.Process:
            process = await original_create(*args, **kwargs)
            processes.append(process)
            child_created.set()
            await release_creation.wait()
            return process

        async def gated_reap(
            adapter: JsonlSubprocessAdapter,
            process: asyncio.subprocess.Process,
        ) -> None:
            reaper_started.set()
            await release_reaper.wait()
            await original_reap(adapter, process)

        monkeypatch.setattr(
            adapters_module.asyncio,
            "create_subprocess_exec",
            delayed_create,
        )
        monkeypatch.setattr(JsonlSubprocessAdapter, "_reap_detached_process", gated_reap)
        adapter = JsonlSubprocessAdapter(
            (sys.executable, str(FIXTURE)),
            timeout_seconds=2,
            shutdown_timeout_seconds=0.5,
        )
        decision_task = asyncio.create_task(adapter.decide(_scenario(), 1))
        await asyncio.wait_for(child_created.wait(), timeout=2)
        decision_task.cancel()
        await asyncio.sleep(0)
        decision_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await decision_task

        release_creation.set()
        close_task = asyncio.create_task(adapter.aclose())
        await asyncio.wait_for(reaper_started.wait(), timeout=1)
        close_task.cancel()
        await asyncio.sleep(0)
        close_task.cancel()
        release_reaper.set()
        with pytest.raises(asyncio.CancelledError):
            await close_task
        return (
            processes[0],
            adapter.process,
            len(adapter._pending_creations),
            len(adapter._creation_cleanup_futures),
            len(adapter._detached_cleanup_tasks),
        )

    process, registered, pending_count, lifecycle_count, detached_count = asyncio.run(probe())
    assert process.returncode is not None
    assert registered is None
    assert pending_count == 0
    assert lifecycle_count == 0
    assert detached_count == 0


@pytest.mark.asyncio
async def test_typed_cleanup_error_precedes_deferred_aclose_cancellation() -> None:
    adapter = JsonlSubprocessAdapter(
        (sys.executable, str(FIXTURE)),
        shutdown_timeout_seconds=0.02,
    )
    lifecycle = asyncio.get_running_loop().create_future()
    adapter._creation_cleanup_futures.add(lifecycle)
    close_task = asyncio.create_task(adapter.aclose())
    await asyncio.sleep(0)
    close_task.cancel()
    await asyncio.sleep(0)
    close_task.cancel()
    with pytest.raises(AdapterProcessError, match="lifecycle cleanup exceeded"):
        await close_task
    lifecycle.cancel()
