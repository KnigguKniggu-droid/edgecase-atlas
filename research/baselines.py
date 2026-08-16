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
CALL_KINDS = ("search", "retry", "confirmation", "shrink")
_EXPERIMENT_FIELDS = frozenset(
    {
        "campaign_design_id",
        "experiment_id",
        "partition",
        "property_pack_version",
        "protocol_version",
        "target_build_id",
    }
)


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
            ordinal = record.get("ordinal")
            if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
                raise ResearchInputError(f"Line {line_number} has an invalid charged call ordinal")
            identity = (
                str(record["campaign_block_id"]),
                str(record["method_id"]),
                str(record["event_type"]),
                ordinal,
            )
            if identity in charged_identities:
                raise ResearchInputError("Input contains a duplicate charged call identity")
            charged_identities.add(identity)
        records.append(record)
    if not records:
        raise ResearchInputError("Research JSONL must contain at least one event")
    return records


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"Non-finite number is prohibited: {value}")


def _validate_record(value: dict[str, Any], line_number: int) -> dict[str, object]:
    experiment = value.get("experiment")
    if not isinstance(experiment, dict) or frozenset(experiment) != _EXPERIMENT_FIELDS:
        raise ResearchInputError(f"Line {line_number} has missing experiment metadata")
    if any(not isinstance(experiment[field], str) or not experiment[field] for field in experiment):
        raise ResearchInputError(f"Line {line_number} has invalid experiment metadata")
    if experiment["partition"] not in {"development", "pilot", "confirmatory"}:
        raise ResearchInputError(f"Line {line_number} has invalid experiment partition")
    required = {
        "campaign_block_id",
        "event_type",
        "experiment",
        "method_id",
        "schema_version",
    }
    if not required.issubset(value):
        raise ResearchInputError(f"Line {line_number} is missing research event fields")
    if value["schema_version"] != "atlas-research-event-v1":
        raise ResearchInputError(f"Line {line_number} has an unsupported schema version")
    if value["method_id"] not in METHODS:
        raise ResearchInputError(f"Line {line_number} has an unknown method")
    if not isinstance(value["campaign_block_id"], str) or not value["campaign_block_id"]:
        raise ResearchInputError(f"Line {line_number} has an invalid campaign block")
    event_type = value["event_type"]
    if event_type == "target_call":
        if value.get("call_kind") not in CALL_KINDS:
            raise ResearchInputError(f"Line {line_number} has an invalid target call kind")
    elif event_type not in {"generator_call", "certificate", "coverage"}:
        raise ResearchInputError(f"Line {line_number} has an unknown event type")
    return value


def summarize_call_ledger(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Count each attempted target call, including retries, confirmation, and shrinking."""
    target_kinds = Counter(
        str(record["call_kind"]) for record in records if record.get("event_type") == "target_call"
    )
    return {
        "generator_calls_total": sum(
            record.get("event_type") == "generator_call" for record in records
        ),
        "target_calls_by_kind": dict(sorted(target_kinds.items())),
        "target_calls_total": sum(target_kinds.values()),
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
