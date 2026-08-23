"""Bounded synchronous bridge for public Streamlit demonstration runs."""

from __future__ import annotations

import asyncio
import threading

from ui import (
    PUBLIC_TIMEOUT_SECONDS,
    DemoArtifacts,
    DemoRequest,
    build_demo_artifacts,
    claim_public_run,
)

_PUBLIC_RUN_SLOTS = threading.BoundedSemaphore(2)


class PublicRunUnavailable(RuntimeError):
    """Safe public error whose message contains no adapter or user data."""


def execute_public_demo(request: DemoRequest) -> DemoArtifacts:
    """Run one bounded no-key demonstration without exposing arbitrary execution."""
    if not claim_public_run():
        raise PublicRunUnavailable("Public demonstration rate limit reached.")
    if not _PUBLIC_RUN_SLOTS.acquire(blocking=False):
        raise PublicRunUnavailable("Public demonstration is busy.")
    try:
        return asyncio.run(asyncio.wait_for(build_demo_artifacts(request), PUBLIC_TIMEOUT_SECONDS))
    except TimeoutError as error:
        raise PublicRunUnavailable("Public demonstration timed out.") from error
    finally:
        _PUBLIC_RUN_SLOTS.release()
