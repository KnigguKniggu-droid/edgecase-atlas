"""Persistent JSONL subprocess fixture used only by adapter contract tests."""

from __future__ import annotations

import json
import os
import sys
import time


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "valid"
    for line in sys.stdin:
        scenario = json.loads(line)
        if mode == "crash":
            print("fixture crash", file=sys.stderr, flush=True)
            raise SystemExit(7)
        if mode == "slow":
            time.sleep(2)
        if mode == "malformed":
            print("not-json", flush=True)
            continue
        if mode == "unknown":
            print(
                json.dumps({"action": "swerve", "risk": "low", "explanation": "invalid label"}),
                flush=True,
            )
            continue
        print(
            json.dumps(
                {
                    "action": "stop" if scenario["signal"] == "red" else "reduce_speed",
                    "risk": "high",
                    "explanation": f"fixture-pid:{os.getpid()}",
                    "confidence": 1.0,
                },
                sort_keys=True,
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
