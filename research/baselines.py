"""Validate canonical research JSONL and reconcile charged call ledgers."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

METHODS = (
    "random_valid_sampling",
    "fixed_metamorphic_templates",
    "unguided_llm_generation",
    "diversity_criticality_search",
    "atlas",
)
PRIMARY_COMPARATOR = "diversity_criticality_search"
TARGET_PHASES = (
    "search",
    "retry",
    "adaptive_gate",
    "shrink",
    "terminal_audit",
    "held_out_confirmation",
)
_EFFECTIVE_PHASES = frozenset(TARGET_PHASES) - {"retry"}
_OUTCOMES = frozenset({"succeeded", "timeout", "crash", "malformed_output", "schema_error"})
_TRIAL_OUTCOMES = frozenset({"violation", "not_violation", "unresolved"})
_EXPERIMENT_FIELDS = frozenset(
    {
        "campaign_design_id",
        "confirmation_design_id",
        "experiment_id",
        "partition",
        "property_pack_version",
        "protocol_version",
        "target_build_id",
    }
)
_BASE_FIELDS = frozenset(
    {"campaign_block_id", "event_type", "experiment", "method_id", "schema_version"}
)
_TARGET_FIELDS = _BASE_FIELDS | {
    "attempt_id",
    "evidence_id",
    "ordinal",
    "outcome",
    "pair_role",
    "phase",
    "property_id",
    "reducer_operation",
    "relation_id",
    "retry_for_phase",
    "retry_of_attempt_id",
    "seed",
    "trial_outcome",
}
_GENERATOR_FIELDS = _BASE_FIELDS | {"ordinal"}
_SUMMARY_FIELDS = _BASE_FIELDS | {"declared_target_calls"}
_CERTIFICATE_FIELDS = _BASE_FIELDS | {
    "adaptive_successes",
    "adaptive_trials",
    "certificate_id",
    "held_out_successes",
    "held_out_trials",
    "minimization_status",
    "property_id",
    "reducer_vocabulary",
    "relation_id",
    "research_confirmed",
    "signature",
    "terminal_audit_complete",
}


class ResearchInputError(ValueError):
    """Raised when evidence cannot belong to one frozen experiment."""


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def load_research_jsonl(path: Path | str) -> list[dict[str, object]]:
    """Load one canonical stream and reject missing or mixed experiment metadata."""
    records: list[dict[str, object]] = []
    frozen_experiment: dict[str, object] | None = None
    charged_identities: set[tuple[str, str, str, int]] = set()
    attempt_ids: set[str] = set()
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            raise ResearchInputError(f"Blank line {line_number} is not canonical JSONL")
        try:
            value = json.loads(line, parse_constant=_reject_nonfinite)
        except (json.JSONDecodeError, ValueError) as error:
            raise ResearchInputError(f"Line {line_number} is not valid JSON") from error
        if not isinstance(value, dict) or line != _canonical(value):
            raise ResearchInputError(f"Line {line_number} is not canonical JSONL")
        record = _validate_record(value, line_number)
        experiment = record["experiment"]
        assert isinstance(experiment, dict)
        if frozen_experiment is None:
            frozen_experiment = experiment
        elif experiment != frozen_experiment:
            raise ResearchInputError("Input contains mixed experiment metadata")
        if record["event_type"] in {"target_call", "generator_call"}:
            ordinal = record["ordinal"]
            assert isinstance(ordinal, int)
            identity = (
                str(record["campaign_block_id"]),
                str(record["method_id"]),
                str(record["event_type"]),
                ordinal,
            )
            if identity in charged_identities:
                raise ResearchInputError("Input contains a duplicate charged call identity")
            charged_identities.add(identity)
        if record["event_type"] == "target_call":
            attempt_id = str(record["attempt_id"])
            if attempt_id in attempt_ids:
                raise ResearchInputError("Input contains a duplicate target attempt identity")
            attempt_ids.add(attempt_id)
        records.append(record)
    if not records:
        raise ResearchInputError("Research JSONL must contain at least one event")
    _validate_retries(records)
    return records


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Non-finite number is prohibited: {value}")


def _positive_ordinal(value: object, line_number: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ResearchInputError(f"Line {line_number} has an invalid charged call ordinal")
    return value


def _nonempty_string(value: object, line_number: int, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ResearchInputError(f"Line {line_number} has an invalid {field}")
    return value


def _validate_record(value: dict[str, Any], line_number: int) -> dict[str, object]:
    experiment = value.get("experiment")
    if not isinstance(experiment, dict) or frozenset(experiment) != _EXPERIMENT_FIELDS:
        raise ResearchInputError(f"Line {line_number} has missing experiment metadata")
    if any(not isinstance(experiment[field], str) or not experiment[field] for field in experiment):
        raise ResearchInputError(f"Line {line_number} has invalid experiment metadata")
    if experiment["partition"] not in {"development", "pilot", "confirmatory"}:
        raise ResearchInputError(f"Line {line_number} has invalid experiment partition")
    if experiment["confirmation_design_id"] != "fixed-20-unanimous-v1":
        raise ResearchInputError(f"Line {line_number} has an unsupported confirmation design")
    if not _BASE_FIELDS.issubset(value):
        raise ResearchInputError(f"Line {line_number} is missing research event fields")
    if value["schema_version"] != "atlas-research-event-v1":
        raise ResearchInputError(f"Line {line_number} has an unsupported schema version")
    if value["method_id"] not in METHODS:
        raise ResearchInputError(f"Line {line_number} has an unknown method")
    _nonempty_string(value["campaign_block_id"], line_number, "campaign block")

    event_type = value["event_type"]
    if event_type == "target_call":
        _validate_target_call(value, line_number)
    elif event_type == "generator_call":
        if frozenset(value) != _GENERATOR_FIELDS:
            raise ResearchInputError(f"Line {line_number} has invalid generator-call fields")
        _positive_ordinal(value["ordinal"], line_number)
    elif event_type == "campaign_summary":
        _validate_summary(value, line_number)
    elif event_type == "certificate":
        _validate_certificate(value, line_number)
    elif event_type == "coverage":
        if frozenset(value) != _BASE_FIELDS:
            raise ResearchInputError(f"Line {line_number} has invalid coverage fields")
    else:
        raise ResearchInputError(f"Line {line_number} has an unknown event type")
    return value


def _validate_target_call(value: dict[str, Any], line_number: int) -> None:
    if frozenset(value) != _TARGET_FIELDS:
        raise ResearchInputError(f"Line {line_number} has invalid target-call fields")
    _positive_ordinal(value["ordinal"], line_number)
    for field in ("attempt_id", "evidence_id", "property_id", "relation_id"):
        _nonempty_string(value[field], line_number, field.replace("_", " "))
    if value["phase"] not in TARGET_PHASES:
        raise ResearchInputError(f"Line {line_number} has an invalid target-call phase")
    if value["pair_role"] not in {"source", "follow_up"}:
        raise ResearchInputError(f"Line {line_number} has an invalid pair role")
    if not isinstance(value["seed"], int) or isinstance(value["seed"], bool) or value["seed"] < 0:
        raise ResearchInputError(f"Line {line_number} has an invalid seed")
    if value["outcome"] not in _OUTCOMES:
        raise ResearchInputError(f"Line {line_number} has an invalid target-call outcome")
    if value["trial_outcome"] not in _TRIAL_OUTCOMES:
        raise ResearchInputError(f"Line {line_number} has an invalid trial outcome")
    if value["outcome"] == "succeeded" and value["trial_outcome"] == "unresolved":
        raise ResearchInputError(f"Line {line_number} has an unresolved successful call")
    if value["outcome"] != "succeeded" and value["trial_outcome"] != "unresolved":
        raise ResearchInputError(f"Line {line_number} gives a failed call a trial result")
    if value["phase"] == "retry":
        _nonempty_string(value["retry_of_attempt_id"], line_number, "retry reference")
        if value["retry_for_phase"] not in _EFFECTIVE_PHASES:
            raise ResearchInputError(f"Line {line_number} has an invalid retry phase")
    elif value["retry_of_attempt_id"] is not None or value["retry_for_phase"] is not None:
        raise ResearchInputError(f"Line {line_number} has retry fields on a non-retry call")
    reducer = value["reducer_operation"]
    effective_phase = value["retry_for_phase"] if value["phase"] == "retry" else value["phase"]
    if effective_phase == "terminal_audit":
        _nonempty_string(reducer, line_number, "reducer operation")
    elif reducer is not None:
        raise ResearchInputError(f"Line {line_number} has an unexpected reducer operation")


def _validate_summary(value: dict[str, Any], line_number: int) -> None:
    if frozenset(value) != _SUMMARY_FIELDS:
        raise ResearchInputError(f"Line {line_number} has invalid campaign-summary fields")
    counts = value["declared_target_calls"]
    expected_fields = frozenset(TARGET_PHASES) | {"total"}
    if not isinstance(counts, dict) or frozenset(counts) != expected_fields:
        raise ResearchInputError(f"Line {line_number} has invalid declared target call fields")
    if any(
        not isinstance(count, int) or isinstance(count, bool) or count < 0
        for count in counts.values()
    ):
        raise ResearchInputError(f"Line {line_number} has invalid declared target call count")
    if counts["total"] != sum(counts[phase] for phase in TARGET_PHASES):
        raise ResearchInputError(f"Line {line_number} has inconsistent declared target call total")


def _validate_certificate(value: dict[str, Any], line_number: int) -> None:
    if frozenset(value) != _CERTIFICATE_FIELDS:
        raise ResearchInputError(f"Line {line_number} has invalid certificate fields")
    for field in ("certificate_id", "property_id", "relation_id", "minimization_status"):
        _nonempty_string(value[field], line_number, field.replace("_", " "))
    for field in (
        "adaptive_successes",
        "adaptive_trials",
        "held_out_successes",
        "held_out_trials",
    ):
        count = value[field]
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ResearchInputError(f"Line {line_number} has an invalid {field}")
    if value["adaptive_successes"] > value["adaptive_trials"]:
        raise ResearchInputError(f"Line {line_number} has impossible adaptive counts")
    if value["held_out_successes"] > value["held_out_trials"]:
        raise ResearchInputError(f"Line {line_number} has impossible held-out counts")
    if not isinstance(value["research_confirmed"], bool):
        raise ResearchInputError(f"Line {line_number} has invalid confirmation status")
    if not isinstance(value["terminal_audit_complete"], bool):
        raise ResearchInputError(f"Line {line_number} has invalid terminal audit status")
    reducers = value["reducer_vocabulary"]
    if (
        not isinstance(reducers, list)
        or not reducers
        or any(not isinstance(item, str) or not item for item in reducers)
        or reducers != sorted(set(reducers))
    ):
        raise ResearchInputError(f"Line {line_number} has invalid reducer vocabulary")
    if not isinstance(value["signature"], dict):
        raise ResearchInputError(f"Line {line_number} has invalid signature")


def _validate_retries(records: Sequence[Mapping[str, object]]) -> None:
    attempts: dict[str, tuple[int, Mapping[str, object]]] = {}
    for position, record in enumerate(records):
        if record["event_type"] != "target_call":
            continue
        attempt_id = str(record["attempt_id"])
        if record["phase"] == "retry":
            reference = str(record["retry_of_attempt_id"])
            prior = attempts.get(reference)
            if prior is None or prior[0] >= position:
                raise ResearchInputError("Retry must reference an earlier target attempt")
            original = prior[1]
            if original["phase"] == "retry" or original["outcome"] == "succeeded":
                raise ResearchInputError("Retry must reference a failed non-retry attempt")
            matching_fields = (
                "campaign_block_id",
                "reducer_operation",
                "method_id",
                "evidence_id",
                "property_id",
                "relation_id",
                "pair_role",
                "seed",
            )
            if any(record[field] != original[field] for field in matching_fields):
                raise ResearchInputError("Retry metadata differs from its original attempt")
            if record["retry_for_phase"] != original["phase"]:
                raise ResearchInputError("Retry phase differs from its original attempt")
        attempts[attempt_id] = (position, record)


def summarize_call_ledger(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Count every attempted target call, including failures, retries, and reductions."""
    target_phases = Counter(
        str(record["phase"]) for record in records if record.get("event_type") == "target_call"
    )
    return {
        "generator_calls_total": sum(
            record.get("event_type") == "generator_call" for record in records
        ),
        "target_calls_by_phase": dict(sorted(target_phases.items())),
        "target_calls_total": sum(target_phases.values()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate canonical baseline JSONL and reconcile all charged calls."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = summarize_call_ledger(load_research_jsonl(args.input))
    except (OSError, ResearchInputError) as error:
        parser.error(str(error))
    text = _canonical(summary) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
