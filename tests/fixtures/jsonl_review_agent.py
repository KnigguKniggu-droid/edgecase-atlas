"""Subprocess fixture for Task 3 lifecycle review regressions."""

from __future__ import annotations

import os
import sys
import time


def main() -> None:
    mode = sys.argv[1]
    for _line in sys.stdin:
        if mode == "eof-live":
            os.close(sys.stdout.fileno())
            time.sleep(5)


if __name__ == "__main__":
    main()
