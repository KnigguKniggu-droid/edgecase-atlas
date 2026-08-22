"""Pure request validation and artifact assembly for the hosted demonstration."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from time import monotonic
from typing import Literal, NamedTuple

from edgecase_atlas.engine import AtlasEngine, RunResult
from edgecase_atlas.fixtures import FaultyDemonstrationAgent
from edgecase_atlas.properties import STARTER_PROPERTY_PACK, SafetyProperty
from edgecase_atlas.reporting import render_html_report
from edgecase_atlas.serialization import canonical_json, run_document, trace_events

PUBLIC_ADAPTER_ID = "faulty_fixture"
PUBLIC_BUDGET_MIN = 1
PUBLIC_BUDGET_MAX = 5
PUBLIC_TEXT_MAX_CHARS = 1_000
PUBLIC_SEED_MAX = 2**31 - 1
PUBLIC_TIMEOUT_SECONDS = 30
PUBLIC_ARTIFACT_MAX_BYTES = 2_000_000
PUBLIC_RUNS_PER_MINUTE = 10
_PUBLIC_RUN_TIMES: deque[float] = deque()
_PUBLIC_RUN_LOCK = Lock()

RunStatus = Literal["empty", "running", "success", "no_failure", "input_error", "adapter_error"]


class DemoRequest(NamedTuple):
    properties: tuple[SafetyProperty, ...]
    sample_property_id: str
    seed: int
    budget: int
    custom_text: str


class DemoArtifacts(NamedTuple):
    run: RunResult
    document: dict[str, object]
    json_bytes: bytes
    jsonl_bytes: bytes
    html_bytes: bytes


def validate_public_request(
    *,
    property_ids: Sequence[str],
    sample_property_id: str,
    seed: int,
    budget: int,
    custom_text: str,
) -> DemoRequest:
    """Revalidate every browser-supplied value before running the public fixture."""
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= PUBLIC_SEED_MAX:
        raise ValueError("Seed is outside the public demonstration range.")
    if (
        not isinstance(budget, int)
        or isinstance(budget, bool)
        or not PUBLIC_BUDGET_MIN <= budget <= PUBLIC_BUDGET_MAX
    ):
        raise ValueError("Test budget is outside the public demonstration range.")
    if not isinstance(custom_text, str) or len(custom_text) > PUBLIC_TEXT_MAX_CHARS:
        raise ValueError("Synthetic scenario context exceeds 1,000 characters.")

    by_id = {item.property_id: item for item in STARTER_PROPERTY_PACK}
    requested_ids = tuple(property_ids)
    if not isinstance(sample_property_id, str) or sample_property_id not in by_id:
        raise ValueError("Select a curated synthetic example from the public pack.")
    if not requested_ids:
        raise ValueError("Select at least one safety assumption.")
    if len(requested_ids) != len(set(requested_ids)):
        raise ValueError("Select unique safety assumptions.")
    if any(property_id not in by_id for property_id in requested_ids):
        raise ValueError("The public demonstration only supports the starter property pack.")
    ordered_ids = (
        sample_property_id,
        *(property_id for property_id in requested_ids if property_id != sample_property_id),
    )
    return DemoRequest(
        tuple(by_id[property_id] for property_id in ordered_ids),
        sample_property_id,
        seed,
        budget,
        custom_text.strip(),
    )


def claim_public_run(now: float | None = None) -> bool:
    """Enforce one process-wide rolling limit for hosted work."""
    current = monotonic() if now is None else now
    with _PUBLIC_RUN_LOCK:
        while _PUBLIC_RUN_TIMES and current - _PUBLIC_RUN_TIMES[0] >= 60:
            _PUBLIC_RUN_TIMES.popleft()
        if len(_PUBLIC_RUN_TIMES) >= PUBLIC_RUNS_PER_MINUTE:
            return False
        _PUBLIC_RUN_TIMES.append(current)
        return True


def public_adapter(adapter_id: str) -> FaultyDemonstrationAgent:
    """Return the only adapter allowed in the hosted no-key demonstration."""
    if adapter_id != PUBLIC_ADAPTER_ID:
        raise ValueError("The hosted demonstration only allows the synthetic faulty fixture.")
    return FaultyDemonstrationAgent()


async def build_demo_artifacts(request: DemoRequest) -> DemoArtifacts:
    """Run the real engine and create three self-contained download formats."""
    run = await AtlasEngine().run(
        public_adapter(PUBLIC_ADAPTER_ID),
        request.properties,
        seed=request.seed,
        budget=request.budget,
    )
    document = run_document(run)
    document["demo_input"] = {
        "adapter_id": PUBLIC_ADAPTER_ID,
        "sample_property_id": request.sample_property_id,
        "custom_text": request.custom_text,
        "note": (
            "Optional text is stored only as synthetic session context. "
            "The alpha generator remains typed and deterministic."
        ),
    }
    json_bytes = (canonical_json(document) + "\n").encode("utf-8")
    jsonl_bytes = ("\n".join(canonical_json(event) for event in trace_events(run)) + "\n").encode(
        "utf-8"
    )
    with TemporaryDirectory(prefix="edgecase-atlas-report-") as temporary_directory:
        output_path = Path(temporary_directory) / "report.html"
        render_html_report(document, output_path)
        html_bytes = output_path.read_bytes()
    if max(map(len, (json_bytes, jsonl_bytes, html_bytes))) > PUBLIC_ARTIFACT_MAX_BYTES:
        raise ValueError("Public artifact exceeds the hosted size limit")
    return DemoArtifacts(run, document, json_bytes, jsonl_bytes, html_bytes)


def status_copy(status: RunStatus | str, error: BaseException | None = None) -> tuple[str, str]:
    """Return complete public state copy without reflecting exception details."""
    del error
    messages = {
        "empty": (
            "Ready for a no-key demonstration.",
            "Select assumptions, then run the synthetic fixture.",
        ),
        "running": (
            "Running counterfactual checks.",
            "Atlas is generating, repeating, and reducing typed synthetic pairs.",
        ),
        "success": (
            "Reproducible failure found.",
            "The result met the adaptive 4-of-5 engineering gate.",
        ),
        "no_failure": (
            "No reproducible failure found.",
            "Try another assumption, seed, or larger budget. This is not evidence of safety.",
        ),
        "input_error": (
            "Check the demonstration inputs.",
            "Select at least one safety assumption and use the public bounds.",
        ),
        "adapter_error": (
            "The demonstration could not finish.",
            "No partial result was retained. Retry with the included fixture.",
        ),
    }
    if status not in messages:
        raise ValueError(f"Unknown public run state: {status!r}")
    return messages[status]
