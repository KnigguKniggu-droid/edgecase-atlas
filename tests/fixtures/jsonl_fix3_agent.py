"""Real-child fixture for repeated subprocess-creation cancellation tests."""

from __future__ import annotations

import time


def main() -> None:
    time.sleep(2.0)


if __name__ == "__main__":
    main()
