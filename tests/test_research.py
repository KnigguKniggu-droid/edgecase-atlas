from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
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
    "confirmation_design_id": "fixed-20-unanimous-v1",
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


def _target_call(
    method_id: str,
    phase: str,
    ordinal: int = 1,
    *,
    evidence_id: str = "cert-01",
    pair_role: str = "source",
    seed: int = 1,
    outcome: str = "succeeded",
    trial_outcome: str = "violation",
    retry_of_attempt_id: str | None = None,
    retry_for_phase: str | None = None,
    reducer_operation: str | None = None,
) -> dict[str, object]:
    return {
        "attempt_id": f"{method_id}-{ordinal}",
        "campaign_block_id": "block-01",
        "evidence_id": evidence_id,
        "event_type": "target_call",
        "experiment": EXPERIMENT,
        "method_id": method_id,
        "outcome": outcome,
        "ordinal": ordinal,
        "pair_role": pair_role,
        "phase": phase,
        "property_id": "red_signal_no_proceed",
        "reducer_operation": reducer_operation,
        "relation_id": "red_signal",
        "retry_for_phase": retry_for_phase,
        "retry_of_attempt_id": retry_of_attempt_id,
        "schema_version": "atlas-research-event-v1",
        "seed": seed,
        "trial_outcome": trial_outcome,
    }


def _signature() -> dict[str, object]:
    from research.analysis import SIGNATURE_EQUIVALENCE_DIGEST

    return {
        "applicability_stratum": "intersection-red-signal",
        "equivalence_map_digest": SIGNATURE_EQUIVALENCE_DIGEST,
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
        "adaptive_successes": 4,
        "adaptive_trials": 5,
        "campaign_block_id": "block-01",
        "certificate_id": "cert-01",
        "event_type": "certificate",
        "experiment": EXPERIMENT,
        "held_out_successes": 20 if research_confirmed else 0,
        "held_out_trials": 20 if research_confirmed else 0,
        "method_id": method_id,
        "minimization_status": "one_minimal",
        "property_id": "red_signal_no_proceed",
        "reducer_vocabulary": ["remove_actor", "remove_attribute"],
        "relation_id": "red_signal",
        "research_confirmed": research_confirmed,
        "schema_version": "atlas-research-event-v1",
        "signature": _signature(),
        "terminal_audit_complete": True,
    }


def _confirmed_campaign(method_id: str) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []
    ordinal = 0

    def pair(
        phase: str,
        seed: int,
        trial_outcome: str = "violation",
        reducer_operation: str | None = None,
    ) -> None:
        nonlocal ordinal
        for role in ("source", "follow_up"):
            ordinal += 1
            calls.append(
                _target_call(
                    method_id,
                    phase,
                    ordinal,
                    pair_role=role,
                    seed=seed,
                    trial_outcome=trial_outcome,
                    reducer_operation=reducer_operation,
                )
            )

    pair("search", 1)
    for offset in range(5):
        pair("adaptive_gate", 100 + offset, "violation" if offset < 4 else "not_violation")
    pair("shrink", 200)
    pair("terminal_audit", 201, "not_violation", reducer_operation="remove_actor")
    pair("terminal_audit", 202, "not_violation", reducer_operation="remove_attribute")
    for offset in range(20):
        pair("held_out_confirmation", 300 + offset)
    summary = {
        "campaign_block_id": "block-01",
        "declared_target_calls": {
            "adaptive_gate": 10,
            "held_out_confirmation": 40,
            "retry": 0,
            "search": 2,
            "shrink": 2,
            "terminal_audit": 4,
            "total": 58,
        },
        "event_type": "campaign_summary",
        "experiment": EXPERIMENT,
        "method_id": method_id,
        "schema_version": "atlas-research-event-v1",
    }
    return [*calls, _certificate(method_id), summary]


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


def test_call_ledger_counts_every_target_call_phase_and_retry(tmp_path: Path) -> None:
    from research.baselines import load_research_jsonl, summarize_call_ledger

    failed = _target_call("atlas", "search", 1, outcome="timeout", trial_outcome="unresolved")
    retry = _target_call(
        "atlas",
        "retry",
        2,
        retry_of_attempt_id="atlas-1",
        retry_for_phase="search",
    )
    records = [
        failed,
        retry,
        _target_call("atlas", "held_out_confirmation", 3),
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
    assert summary["target_calls_by_phase"] == {
        "held_out_confirmation": 1,
        "retry": 1,
        "search": 1,
        "shrink": 1,
    }
    assert summary["generator_calls_total"] == 1


def test_terminal_audit_retry_preserves_reducer_and_reconciles_campaign(
    tmp_path: Path,
) -> None:
    from research.analysis import analyze_campaigns
    from research.baselines import ResearchInputError, load_research_jsonl

    records: list[dict[str, object]] = []
    for method_id in METHODS:
        campaign = _confirmed_campaign(method_id)
        if method_id == "atlas":
            failed = next(
                record
                for record in campaign
                if record["event_type"] == "target_call"
                and record["phase"] == "terminal_audit"
                and record["pair_role"] == "source"
                and record["reducer_operation"] == "remove_actor"
            )
            failed["outcome"] = "timeout"
            failed["trial_outcome"] = "unresolved"
            retry = _target_call(
                "atlas",
                "retry",
                59,
                pair_role="source",
                seed=201,
                trial_outcome="not_violation",
                retry_of_attempt_id=str(failed["attempt_id"]),
                retry_for_phase="terminal_audit",
                reducer_operation="remove_actor",
            )
            campaign.insert(-2, retry)
            summary = campaign[-1]
            summary["declared_target_calls"] = dict(
                summary["declared_target_calls"], retry=1, total=59
            )
        records.extend(campaign)

    path = tmp_path / "events.jsonl"
    _write_jsonl(path, records)
    result = analyze_campaigns(load_research_jsonl(path), expected_campaign_blocks=1)

    atlas = next(row for row in result["campaigns"] if row["method_id"] == "atlas")
    assert atlas["target_calls_total"] == 59
    assert atlas["unique_confirmed_signatures"] == 1
    retry["reducer_operation"] = "remove_attribute"
    _write_jsonl(path, records)
    with pytest.raises(ResearchInputError, match="metadata differs"):
        load_research_jsonl(path)


def test_analysis_requires_ledger_proven_confirmation_and_reconciles_counts(
    tmp_path: Path,
) -> None:
    from research.analysis import AnalysisInputError, analyze_campaigns
    from research.baselines import load_research_jsonl

    records = [record for method_id in METHODS for record in _confirmed_campaign(method_id)]
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, records)

    result = analyze_campaigns(load_research_jsonl(path), expected_campaign_blocks=1)

    assert result["inference_unit"] == "campaign_block"
    assert result["primary_comparator"] == "diversity_criticality_search"
    assert result["campaign_block_count"] == 1
    assert all(row["unique_confirmed_signatures"] == 1 for row in result["campaigns"])
    assert all(row["target_calls_total"] == 58 for row in result["campaigns"])

    fake_records = [_target_call(method_id, "search") for method_id in METHODS] + [
        _certificate(method_id) for method_id in METHODS
    ]
    _write_jsonl(path, fake_records)
    with pytest.raises(AnalysisInputError, match=r"summary|evidence|phase"):
        analyze_campaigns(load_research_jsonl(path), expected_campaign_blocks=1)

    bad_counts = records.copy()
    summary = next(
        record
        for record in bad_counts
        if record["event_type"] == "campaign_summary" and record["method_id"] == "atlas"
    )
    summary["declared_target_calls"] = dict(summary["declared_target_calls"], total=57)
    _write_jsonl(path, bad_counts)
    with pytest.raises(ValueError, match="declared target call"):
        analyze_campaigns(load_research_jsonl(path), expected_campaign_blocks=1)


def test_held_out_confirmation_cannot_reuse_adaptive_four_of_five(
    tmp_path: Path,
) -> None:
    from research.analysis import AnalysisInputError, analyze_campaigns
    from research.baselines import load_research_jsonl

    records = [record for method_id in METHODS for record in _confirmed_campaign(method_id)]
    for record in records:
        if (
            record["method_id"] == "atlas"
            and record["event_type"] == "target_call"
            and record["phase"] == "held_out_confirmation"
            and record["seed"] == 300
        ):
            record["trial_outcome"] = "not_violation"
        if record["method_id"] == "atlas" and record["event_type"] == "certificate":
            record["held_out_successes"] = 19
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, records)
    with pytest.raises(AnalysisInputError, match="unanimous"):
        analyze_campaigns(load_research_jsonl(path), expected_campaign_blocks=1)


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
    for field, invalid in (
        ("source_action", "teleport"),
        ("follow_up_risk", "catastrophic"),
        ("relation_id", "unknown_relation"),
        ("applicability_stratum", "unknown-stratum"),
        ("equivalence_map_digest", "stale-map"),
    ):
        with pytest.raises(ValueError):
            failure_signature(dict(signature, **{field: invalid}))


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


def test_seed_pack_bytes_match_fresh_generator_and_git_archive(tmp_path: Path) -> None:
    from research.generate_seed_pack import write_seed_pack

    working = ROOT / "research" / "data" / "synthetic_seed_pack.jsonl"
    fresh = tmp_path / "fresh.jsonl"
    write_seed_pack(fresh)
    expected = fresh.read_bytes()
    assert b"\r\n" not in expected
    assert working.read_bytes() == expected
    assert (ROOT / ".gitattributes").read_text(encoding="utf-8") == (
        "research/data/*.jsonl text eol=lf\n"
    )

    repo = tmp_path / "archive-repo"
    archive_pack = repo / "research" / "data" / working.name
    archive_pack.parent.mkdir(parents=True)
    archive_pack.write_bytes(working.read_bytes())
    (repo / ".gitattributes").write_text(
        "research/data/*.jsonl text eol=lf\n", encoding="utf-8", newline="\n"
    )
    git = shutil.which("git")
    assert git is not None
    subprocess.run([git, "init", "-q"], cwd=repo, check=True)  # noqa: S603
    subprocess.run(  # noqa: S603
        [git, "add", ".gitattributes", "research/data/synthetic_seed_pack.jsonl"],
        cwd=repo,
        check=True,
    )
    subprocess.run(  # noqa: S603
        [
            git,
            "-c",
            "user.name=EdgeCase Atlas",
            "-c",
            "user.email=edgecase-atlas@users.noreply.github.com",
            "commit",
            "-qm",
            "archive fixture",
        ],
        cwd=repo,
        check=True,
    )
    archive = subprocess.check_output(  # noqa: S603
        [git, "archive", "--format=tar", "HEAD"], cwd=repo
    )
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        archived = bundle.extractfile("research/data/synthetic_seed_pack.jsonl")
        assert archived is not None
        assert archived.read() == expected


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
