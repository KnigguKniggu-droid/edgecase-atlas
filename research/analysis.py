"""Campaign-block analysis entry point for frozen EdgeCase Atlas evidence."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from research.baselines import METHODS, PRIMARY_COMPARATOR, load_research_jsonl

_SIGNATURE_FIELDS = frozenset(
    {
        "applicability_stratum",
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
    scalar_fields = (
        "property_pack_version",
        "relation_id",
        "source_action",
        "follow_up_action",
        "source_risk",
        "follow_up_risk",
    )
    if any(not isinstance(value[field], str) or not value[field] for field in scalar_fields):
        raise ValueError("Failure signature scalar fields must be nonempty strings")
    stratum = value["applicability_stratum"]
    if not isinstance(stratum, str) or not stratum:
        raise ValueError("Failure signature applicability stratum must be nonempty")
    return (
        *(value[field] for field in scalar_fields),
        tuple(sorted(set(paths))),
        stratum,
    )


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
            signatures: set[tuple[object, ...]] = set()
            for record in method_records:
                if record.get("event_type") != "certificate":
                    continue
                if record.get("research_confirmed") is not True:
                    continue
                if record.get("minimization_status") != "one_minimal":
                    continue
                trials = record.get("held_out_trials")
                if not isinstance(trials, int) or isinstance(trials, bool) or trials < 20:
                    raise AnalysisInputError(
                        "Research-confirmed certificates require at least 20 held-out trials"
                    )
                signature = record.get("signature")
                if not isinstance(signature, Mapping):
                    raise AnalysisInputError("Research-confirmed certificate lacks a signature")
                normalized_signature = failure_signature(signature)
                if normalized_signature[0] != experiment["property_pack_version"]:
                    raise AnalysisInputError(
                        "Certificate signature property pack differs from experiment metadata"
                    )
                signatures.add(normalized_signature)
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
