"""Executable synthetic calibration through the production engine."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from edgecase_atlas.engine import AtlasEngine  # noqa: E402
from edgecase_atlas.fixtures import FaultyDemonstrationAgent  # noqa: E402
from edgecase_atlas.properties import STARTER_PROPERTY_PACK  # noqa: E402


async def run_calibration(*, seed: int, budget: int) -> dict[str, object]:
    if budget < 1:
        raise ValueError("Budget must be positive")
    result = await AtlasEngine().run(
        FaultyDemonstrationAgent(), STARTER_PROPERTY_PACK, seed=seed, budget=budget
    )
    return {
        "schema_version": "atlas-calibration-result-v1",
        "results_status": "synthetic_fixture_calibration_not_confirmatory_research",
        "seed": seed,
        "budget": budget,
        "run_id": result.metadata.run_id,
        "target_calls_total": result.call_ledger.target_calls_total,
        "certificate_count": len(result.certificates),
        "certificate_ids": [item.certificate.certificate_id for item in result.certificates],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--budget", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = asyncio.run(run_calibration(seed=args.seed, budget=args.budget))
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
