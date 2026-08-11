"""Subprocess fixture for bounded stderr and overlong stdout tests."""

from __future__ import annotations

import sys


def main() -> None:
    mode = sys.argv[1]
    for _line in sys.stdin:
        if mode == "stderr-crash":
            print("x" * 100_000, file=sys.stderr, flush=True)
            raise SystemExit(9)
        if mode == "overlong":
            print("x" * 100_000, flush=True)


if __name__ == "__main__":
    main()
