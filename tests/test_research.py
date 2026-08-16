from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from edgecase_atlas.constraints import validate_scenario
from edgecase_atlas.models import Scenario

ROOT = Path(__file__).resolve().parents[1]
METHODS = (
    "random_valid_sampling",
    "fixed_metamorphic_templates",
    "unguided_llm_generation",
    "diversity_criticality_search",
    "atlas",
)
EXPERIMENT = {
    "campaign_design_id": "paired-12x5-v1",
    "experiment_id": "atlas-confirmatory-v1",
    "partition": "confirmatory",
    "property_pack_version": "starter-v0.1",
    "protocol_version": "1.0.0",
    "target_build_id": "frozen-target-v1",
}


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _target_call(method_id: str, call_kind: str, ordinal: int = 1) -> dict[str, object]:
    return {
        "call_kind": call_kind,
        "campaign_block_id": "block-01",
        "event_type": "target_call",
        "experiment": EXPERIMENT,
        "method_id": method_id,
        "ordinal": ordinal,
        "schema_version": "atlas-research-event-v1",
        "succeeded": True,
    }


def _signature() -> dict[str, object]:
    return {
        "applicability_stratum": "intersection-red-signal",
        "follow_up_action": "proceed",
        "follow_up_risk": "low",
        "property_pack_version": "starter-v0.1",
        "relation_id": "red_signal",
        "retained_changed_paths": ["signal"],
        "source_action": "stop",
        "source_risk": "high",
    }


def _certificate(method_id: str, *, research_confirmed: bool = True) -> dict[str, object]:
    return {
        "campaign_block_id": "block-01",
        "event_type": "certificate",
        "experiment": EXPERIMENT,
        "held_out_trials": 20 if research_confirmed else 0,
        "method_id": method_id,
        "minimization_status": "one_minimal",
        "research_confirmed": research_confirmed,
        "schema_version": "atlas-research-event-v1",
        "signature": _signature(),
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("".join(f"{_canonical(record)}\n" for record in records), encoding="utf-8")


def test_loader_rejects_missing_mixed_and_noncanonical_metadata(tmp_path: Path) -> None:
    from research.baselines import ResearchInputError, load_research_jsonl

    valid = _target_call("atlas", "search")
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, [valid])
    assert load_research_jsonl(path) == [valid]

    missing = dict(valid)
    missing.pop("experiment")
    _write_jsonl(path, [missing])
    with pytest.raises(ResearchInputError, match="experiment metadata"):
        load_research_jsonl(path)

    mixed = json.loads(_canonical(valid))
    mixed["experiment"]["target_build_id"] = "different-target"
    _write_jsonl(path, [valid, mixed])
    with pytest.raises(ResearchInputError, match="mixed experiment metadata"):
        load_research_jsonl(path)

    path.write_text(json.dumps(valid) + "\n", encoding="utf-8")
    with pytest.raises(ResearchInputError, match="canonical JSONL"):
        load_research_jsonl(path)


def test_loader_rejects_duplicate_charged_call_identity(tmp_path: Path) -> None:
    from research.baselines import ResearchInputError, load_research_jsonl

    call = _target_call("atlas", "search")
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, [call, call])
    with pytest.raises(ResearchInputError, match="duplicate charged call"):
        load_research_jsonl(path)


def test_call_ledger_counts_every_target_call_kind(tmp_path: Path) -> None:
    from research.baselines import load_research_jsonl, summarize_call_ledger

    records = [
        _target_call("atlas", "search", 1),
        _target_call("atlas", "retry", 2),
        _target_call("atlas", "confirmation", 3),
        _target_call("atlas", "shrink", 4),
        {
            "campaign_block_id": "block-01",
            "event_type": "generator_call",
            "experiment": EXPERIMENT,
            "method_id": "atlas",
            "ordinal": 5,
            "schema_version": "atlas-research-event-v1",
        },
    ]
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, records)
    summary = summarize_call_ledger(load_research_jsonl(path))

    assert summary["target_calls_total"] == 4
    assert summary["target_calls_by_kind"] == {
        "confirmation": 1,
        "retry": 1,
        "search": 1,
        "shrink": 1,
    }
    assert summary["generator_calls_total"] == 1


def test_analysis_uses_complete_campaign_blocks_and_held_out_confirmation(
    tmp_path: Path,
) -> None:
    from research.analysis import analyze_campaigns
    from research.baselines import load_research_jsonl

    records: list[dict[str, object]] = []
    for method_id in METHODS:
        records.extend(
            (
                _target_call(method_id, "search"),
                _certificate(method_id),
                _certificate(method_id),
                _certificate(method_id, research_confirmed=False),
                dict(
                    _certificate(method_id),
                    minimization_status="unreduced",
                    signature=dict(_signature(), retained_changed_paths=["speed_mph"]),
                ),
            )
        )
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, records)

    result = analyze_campaigns(load_research_jsonl(path), expected_campaign_blocks=1)

    assert result["inference_unit"] == "campaign_block"
    assert result["primary_comparator"] == "diversity_criticality_search"
    assert result["campaign_block_count"] == 1
    assert all(row["unique_confirmed_signatures"] == 1 for row in result["campaigns"])
    assert all(row["target_calls_total"] == 1 for row in result["campaigns"])


def test_analysis_rejects_pilot_rows_and_incomplete_method_blocks(tmp_path: Path) -> None:
    from research.analysis import AnalysisInputError, analyze_campaigns
    from research.baselines import load_research_jsonl

    pilot_experiment = dict(EXPERIMENT, partition="pilot")
    pilot = _target_call("atlas", "search")
    pilot["experiment"] = pilot_experiment
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, [pilot])
    with pytest.raises(AnalysisInputError, match="pilot"):
        analyze_campaigns(load_research_jsonl(path), expected_campaign_blocks=1)

    _write_jsonl(path, [_target_call("atlas", "search")])
    with pytest.raises(AnalysisInputError, match="five methods"):
        analyze_campaigns(load_research_jsonl(path), expected_campaign_blocks=1)


def test_failure_signature_is_canonical_and_predefined() -> None:
    from research.analysis import failure_signature

    signature = _signature()
    assert failure_signature(signature) == (
        "starter-v0.1",
        "red_signal",
        "stop",
        "proceed",
        "high",
        "low",
        ("signal",),
        "intersection-red-signal",
    )
    with pytest.raises(ValueError, match="signature"):
        failure_signature({"relation_id": "red_signal"})
    with pytest.raises(ValueError, match="sorted and unique"):
        failure_signature(dict(signature, retained_changed_paths=["speed_mph", "signal", "signal"]))


def test_synthetic_seed_pack_is_canonical_valid_deterministic_and_anonymous() -> None:
    path = ROOT / "research" / "data" / "synthetic_seed_pack.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 100

    scenarios = [Scenario.model_validate_json(line) for line in lines]
    assert all(line == _canonical(json.loads(line)) for line in lines)
    assert all(validate_scenario(scenario).valid for scenario in scenarios)
    assert len({scenario.scenario_id for scenario in scenarios}) == 100
    assert {scenario.provenance.source_kind for scenario in scenarios} == {"synthetic"}
    assert {scenario.provenance.license for scenario in scenarios} == {"CC BY 4.0"}
    assert all("synthetic" in scenario.description.casefold() for scenario in scenarios)
    assert {scenario.road_type for scenario in scenarios} == {
        "highway",
        "intersection",
        "residential",
        "urban",
    }
    assert {scenario.surface for scenario in scenarios} == {"dry", "icy", "wet"}
    assert {scenario.visibility for scenario in scenarios} == {"clear", "occluded", "reduced"}

    manifest = yaml.safe_load(
        (ROOT / "research" / "reproducibility-manifest.yaml").read_text(encoding="utf-8")
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert manifest["synthetic_seed_pack"]["records"] == 100
    assert manifest["synthetic_seed_pack"]["sha256"] == digest
    assert manifest["results_status"] == "TBD"


def test_research_and_launch_documents_freeze_required_boundaries() -> None:
    files = {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in (
            ROOT / "research" / "README.md",
            ROOT / "research" / "protocol.md",
            ROOT / "research" / "preregistration.md",
            ROOT / "docs" / "threat-model.md",
            ROOT / "docs" / "dataset-card.md",
            ROOT / "docs" / "model-card.md",
            ROOT / "docs" / "launch" / "quickstart.md",
            ROOT / "docs" / "launch" / "video-storyboard.md",
            ROOT / "docs" / "launch" / "competition-story-template.md",
            ROOT / "docs" / "launch" / "pilot-feedback-template.md",
        )
    }
    joined = "\n".join(files.values())
    title = "Constraint-Guided Counterfactual Fuzzing for Reason-Responsive Driving Agents"
    assert title in files["research/protocol.md"]
    assert title in files["research/preregistration.md"]
    for label in ("H1", "H2", "H3", "H4", "H5"):
        assert label in files["research/preregistration.md"]
    for method_id in METHODS:
        assert method_id in files["research/protocol.md"]
    for required in (
        "12 paired campaign",
        "6,000",
        "primary search calls only",
        "4 of 5",
        "at least 20",
        "campaign block",
        "diversity_criticality_search",
        "paired randomization",
        "negative-binomial",
        "paired permutation",
        "Kaplan-Meier",
        "stratified log-rank",
        "exact McNemar",
        "paired Wilcoxon",
        "bootstrap",
        "Holm",
        "TBD",
    ):
        assert required.casefold() in joined.casefold()
    for future_boundary in ("OSMO", "AnomalyGen", "Kubernetes", "GPU pool"):
        assert future_boundary in files["research/protocol.md"]
    assert "not executed" in files["research/protocol.md"].casefold()


def test_competition_story_template_is_at_most_150_words_and_has_no_claimed_metrics() -> None:
    story = (ROOT / "docs" / "launch" / "competition-story-template.md").read_text(encoding="utf-8")
    body = story.split("## Story", maxsplit=1)[1]
    words = body.replace("[", "").replace("]", "").split()
    assert len(words) <= 150
    assert body.count("TBD") >= 3
    assert "1,000" not in body
    assert "30 users" not in body.casefold()
