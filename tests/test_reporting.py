from __future__ import annotations

import json
from pathlib import Path

import pytest

from edgecase_atlas.engine import AtlasEngine
from edgecase_atlas.fixtures import FaultyDemonstrationAgent
from edgecase_atlas.properties import STARTER_PROPERTY_PACK
from edgecase_atlas.reporting import render_html_report
from edgecase_atlas.serialization import canonical_json, run_document, trace_events


@pytest.mark.asyncio
async def test_canonical_run_and_trace_are_stable_and_research_complete() -> None:
    run = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=1
    )
    document = run_document(run)
    assert canonical_json(document) == canonical_json(json.loads(canonical_json(document)))
    events = trace_events(run)
    assert events[0]["event_type"] == "run_started"
    assert any(event["event_type"] == "target_call" for event in events)
    assert any(event["event_type"] == "certificate" for event in events)
    assert events[-1]["event_type"] == "run_completed"


@pytest.mark.asyncio
async def test_offline_report_escapes_text_and_labels_unknown_cost(tmp_path: Path) -> None:
    run = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=42, budget=1
    )
    document = run_document(run)
    document["certificates"][0]["source_decisions"][0]["explanation"] = "<script>x</script>"
    output = tmp_path / "report.html"
    render_html_report(document, output)
    html = output.read_text(encoding="utf-8")
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "<script src=" not in html
    assert "http://" not in html and "https://" not in html
    assert "unknown" in html
    assert "1-minimal under the declared reducer set" in html
    assert "simulated research and debugging" in html
    assert "not vehicle control, certification, or legal compliance" in html
