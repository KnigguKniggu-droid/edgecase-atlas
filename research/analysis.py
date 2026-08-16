"""Campaign-block analysis entry point for frozen EdgeCase Atlas evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from itertools import combinations
from pathlib import Path
from typing import get_args

from research.baselines import (
    METHODS,
    PRIMARY_COMPARATOR,
    TARGET_PHASES,
    load_research_jsonl,
)

from edgecase_atlas.models import Action, Risk


def _literal_values(alias: object) -> tuple[str, ...]:
    literal = getattr(alias, "__value__", alias)
    return tuple(str(value) for value in get_args(literal))


_ACTIONS = frozenset(_literal_values(Action))
_RISKS = frozenset(_literal_values(Risk))
_EQUIVALENCE_MAP = {
    "actions": sorted(_ACTIONS),
    "risks": sorted(_RISKS),
    "version": "normalized-decision-labels-v1",
}
SIGNATURE_EQUIVALENCE_DIGEST = hashlib.sha256(
    json.dumps(
        _EQUIVALENCE_MAP,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
).hexdigest()
_RELATION_TO_PROPERTY = {
    "red_signal": "red_signal_no_proceed",
    "add_relevant_hazard": "hazard_non_aggression",
    "increase_speed": "overspeed_risk_monotonicity",
    "pedestrian_crossing": "crossing_pedestrian_caution",
    "semantic_paraphrase": "paraphrase_invariance",
}
_RELATION_TO_STRATUM = {
    "red_signal": "intersection-red-signal",
    "add_relevant_hazard": "relevant-hazard-added",
    "increase_speed": "overspeed-increase",
    "pedestrian_crossing": "pedestrian-sidewalk-to-crossing",
    "semantic_paraphrase": "semantic-paraphrase",
}
_SIGNATURE_FIELDS = frozenset(
    {
        "applicability_stratum",
        "equivalence_map_digest",
        "follow_up_action",
        "follow_up_risk",
        "property_pack_version",
        "relation_id",
        "retained_changed_paths",
        "source_action",
        "source_risk",
    }
)


class AnalysisInputError(ValueError):
    """Raised when campaign evidence violates the frozen analysis contract."""


def failure_signature(value: Mapping[str, object]) -> tuple[object, ...]:
    """Return the preregistered canonical failure-signature tuple."""
    if frozenset(value) != _SIGNATURE_FIELDS:
        raise ValueError("Failure signature fields do not match the frozen signature")
    paths = value["retained_changed_paths"]
    if not isinstance(paths, list) or not paths or any(not isinstance(path, str) for path in paths):
        raise ValueError("Failure signature retained paths must be a nonempty string list")
    if paths != sorted(set(paths)):
        raise ValueError("Failure signature retained paths must be sorted and unique")
    if value["source_action"] not in _ACTIONS or value["follow_up_action"] not in _ACTIONS:
        raise ValueError("Failure signature contains an unknown normalized action")
    if value["source_risk"] not in _RISKS or value["follow_up_risk"] not in _RISKS:
        raise ValueError("Failure signature contains an unknown normalized risk")
    relation_id = value["relation_id"]
    if relation_id not in _RELATION_TO_PROPERTY:
        raise ValueError("Failure signature contains an unknown relation")
    if value["applicability_stratum"] != _RELATION_TO_STRATUM[relation_id]:
        raise ValueError("Failure signature contains an unknown applicability stratum")
    if value["equivalence_map_digest"] != SIGNATURE_EQUIVALENCE_DIGEST:
        raise ValueError("Failure signature equivalence map is not frozen")
    property_pack = value["property_pack_version"]
    if not isinstance(property_pack, str) or not property_pack:
        raise ValueError("Failure signature property pack must be a nonempty string")
    return (
        property_pack,
        relation_id,
        value["source_action"],
        value["follow_up_action"],
        value["source_risk"],
        value["follow_up_risk"],
        tuple(paths),
        value["applicability_stratum"],
    )


def _effective_phase(record: Mapping[str, object]) -> str:
    phase = str(record["phase"])
    return str(record["retry_for_phase"]) if phase == "retry" else phase


def _resolve_pairs(
    calls: Sequence[Mapping[str, object]],
) -> dict[str, list[tuple[int, str, str | None]]]:
    attempts: dict[tuple[str, int, str, str | None], list[Mapping[str, object]]] = defaultdict(list)
    for call in calls:
        seed = call["seed"]
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise AnalysisInputError("Evidence seed must be an integer")
        key = (
            _effective_phase(call),
            seed,
            str(call["pair_role"]),
            None if call["reducer_operation"] is None else str(call["reducer_operation"]),
        )
        attempts[key].append(call)

    resolved: dict[tuple[str, int, str | None], dict[str, str]] = defaultdict(dict)
    for (phase, seed, role, reducer), group in attempts.items():
        successes = [call for call in group if call["outcome"] == "succeeded"]
        if len(successes) != 1:
            raise AnalysisInputError(
                "Each evidence role requires exactly one successful call after retries"
            )
        resolved[(phase, seed, reducer)][role] = str(successes[0]["trial_outcome"])

    pairs: dict[str, list[tuple[int, str, str | None]]] = defaultdict(list)
    for (phase, seed, reducer), roles in resolved.items():
        if set(roles) != {"source", "follow_up"}:
            raise AnalysisInputError("Evidence requires matching source and follow-up roles")
        if roles["source"] != roles["follow_up"]:
            raise AnalysisInputError("Source and follow-up roles disagree on trial outcome")
        pairs[phase].append((seed, roles["source"], reducer))
    return {phase: sorted(values) for phase, values in pairs.items()}


def _validated_certificate_signature(
    certificate: Mapping[str, object],
    experiment: Mapping[str, object],
    method_calls: Sequence[Mapping[str, object]],
) -> tuple[object, ...] | None:
    signature = certificate["signature"]
    assert isinstance(signature, Mapping)
    normalized = failure_signature(signature)
    if normalized[0] != experiment["property_pack_version"]:
        raise AnalysisInputError(
            "Certificate signature property pack differs from experiment metadata"
        )
    relation_id = str(certificate["relation_id"])
    property_id = str(certificate["property_id"])
    if normalized[1] != relation_id or _RELATION_TO_PROPERTY.get(relation_id) != property_id:
        raise AnalysisInputError("Certificate property, relation, and signature do not match")

    claims_minimized = certificate["minimization_status"] == "one_minimal"
    claims_confirmed = certificate["research_confirmed"] is True
    if not claims_minimized and not claims_confirmed:
        return None
    if claims_confirmed and not claims_minimized:
        raise AnalysisInputError("Research confirmation requires a one-minimal certificate")

    certificate_id = str(certificate["certificate_id"])
    evidence = [
        call
        for call in method_calls
        if call.get("event_type") == "target_call"
        and call["evidence_id"] == certificate_id
        and call["property_id"] == property_id
        and call["relation_id"] == relation_id
    ]
    if not evidence:
        raise AnalysisInputError("Certificate has no matching invocation-ledger evidence")
    pairs = _resolve_pairs(evidence)

    search = pairs.get("search", [])
    adaptive = pairs.get("adaptive_gate", [])
    shrink = pairs.get("shrink", [])
    terminal = pairs.get("terminal_audit", [])
    held_out = pairs.get("held_out_confirmation", [])
    if not search or not any(outcome == "violation" for _, outcome, _ in search):
        raise AnalysisInputError("Certificate lacks search-phase failure evidence")
    if len(adaptive) != 5:
        raise AnalysisInputError("Adaptive gate must contain exactly five paired trials")
    adaptive_successes = sum(outcome == "violation" for _, outcome, _ in adaptive)
    if adaptive_successes < 4:
        raise AnalysisInputError("Adaptive 4-of-5 heuristic was not met")
    if not shrink or not any(outcome == "violation" for _, outcome, _ in shrink):
        raise AnalysisInputError("One-minimal claim lacks shrink-phase failure evidence")
    reducers = certificate["reducer_vocabulary"]
    assert isinstance(reducers, list)
    audited = {
        reducer
        for _, outcome, reducer in terminal
        if outcome == "not_violation" and reducer is not None
    }
    if audited != set(reducers) or len(terminal) != len(reducers):
        raise AnalysisInputError("One-minimal claim lacks complete terminal audit evidence")
    if certificate["terminal_audit_complete"] is not True:
        raise AnalysisInputError("One-minimal certificate must declare terminal audit completion")

    phase_seeds = {
        "search": {seed for seed, _, _ in search},
        "adaptive_gate": {seed for seed, _, _ in adaptive},
        "shrink": {seed for seed, _, _ in shrink},
        "terminal_audit": {seed for seed, _, _ in terminal},
        "held_out_confirmation": {seed for seed, _, _ in held_out},
    }
    for left, right in combinations(phase_seeds, 2):
        if phase_seeds[left] & phase_seeds[right]:
            raise AnalysisInputError(f"Evidence phases {left} and {right} must use disjoint seeds")
    held_out_successes = sum(outcome == "violation" for _, outcome, _ in held_out)
    if claims_confirmed:
        if experiment["confirmation_design_id"] != "fixed-20-unanimous-v1":
            raise AnalysisInputError("Unsupported held-out confirmation design")
        if len(held_out) < 20:
            raise AnalysisInputError(
                "Research-confirmed certificates require at least 20 held-out trials"
            )
        if held_out_successes != len(held_out):
            raise AnalysisInputError(
                "Fixed held-out confirmation requires unanimous reproduced failures"
            )

    declared = (
        ("adaptive_trials", len(adaptive)),
        ("adaptive_successes", adaptive_successes),
        ("held_out_trials", len(held_out)),
        ("held_out_successes", held_out_successes),
    )
    if any(certificate[field] != observed for field, observed in declared):
        raise AnalysisInputError("Certificate phase counts differ from invocation ledger")
    return normalized if claims_confirmed else None


def _reconcile_summary(method_records: Sequence[Mapping[str, object]]) -> None:
    summaries = [
        record for record in method_records if record.get("event_type") == "campaign_summary"
    ]
    if len(summaries) != 1:
        raise AnalysisInputError("Each method and campaign block requires one campaign summary")
    declared = summaries[0]["declared_target_calls"]
    assert isinstance(declared, Mapping)
    observed = Counter(
        str(record["phase"])
        for record in method_records
        if record.get("event_type") == "target_call"
    )
    for phase in TARGET_PHASES:
        if declared[phase] != observed[phase]:
            raise AnalysisInputError("Declared target call phase count differs from ledger")
    if declared["total"] != sum(observed.values()):
        raise AnalysisInputError("Declared target call total differs from ledger")


def analyze_campaigns(
    records: Sequence[Mapping[str, object]], *, expected_campaign_blocks: int = 12
) -> dict[str, object]:
    """Reduce adaptive events to one row per method and independent campaign block."""
    if expected_campaign_blocks < 1:
        raise AnalysisInputError("Expected campaign block count must be positive")
    experiment = records[0].get("experiment") if records else None
    if not isinstance(experiment, Mapping):
        raise AnalysisInputError("Experiment metadata is required")
    if experiment.get("partition") != "confirmatory":
        raise AnalysisInputError("pilot and development rows cannot enter confirmatory analysis")
    block_ids = sorted({str(record["campaign_block_id"]) for record in records})
    if len(block_ids) != expected_campaign_blocks:
        raise AnalysisInputError(
            f"Expected {expected_campaign_blocks} campaign blocks, found {len(block_ids)}"
        )

    campaigns: list[dict[str, object]] = []
    for block_id in block_ids:
        block_records = [record for record in records if record["campaign_block_id"] == block_id]
        methods = {str(record["method_id"]) for record in block_records}
        if methods != set(METHODS):
            raise AnalysisInputError("Each campaign block must contain all five methods")
        for method_id in METHODS:
            method_records = [
                record for record in block_records if record["method_id"] == method_id
            ]
            _reconcile_summary(method_records)
            signatures: set[tuple[object, ...]] = set()
            certificate_ids: set[str] = set()
            for record in method_records:
                if record.get("event_type") != "certificate":
                    continue
                certificate_id = str(record["certificate_id"])
                if certificate_id in certificate_ids:
                    raise AnalysisInputError("Duplicate certificate identity in campaign method")
                certificate_ids.add(certificate_id)
                normalized = _validated_certificate_signature(record, experiment, method_records)
                if normalized is not None:
                    signatures.add(normalized)
            campaigns.append(
                {
                    "campaign_block_id": block_id,
                    "method_id": method_id,
                    "target_calls_total": sum(
                        record.get("event_type") == "target_call" for record in method_records
                    ),
                    "unique_confirmed_signatures": len(signatures),
                }
            )
    return {
        "campaign_block_count": len(block_ids),
        "campaigns": campaigns,
        "h1_preregistered_margin_rate_ratio": 1.30,
        "inference_unit": "campaign_block",
        "primary_comparator": PRIMARY_COMPARATOR,
        "results_status": "computed_from_input_not_public_launch_metrics",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and reduce confirmatory JSONL at the campaign-block level."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--expected-campaign-blocks", type=int, default=12)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = analyze_campaigns(
            load_research_jsonl(args.input),
            expected_campaign_blocks=args.expected_campaign_blocks,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    text = (
        json.dumps(
            result,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
    if args.output is None:
        print(text, end="")
    else:
        args.output.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
