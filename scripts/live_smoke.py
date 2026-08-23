"""Check every public page of the deployed app for a Streamlit error screen.

Local gates cannot catch this class of failure. Files under ``app`` are served straight from
the repository while the hosted environment resolves the installed package separately, so an
app module can import a name that exists locally and not in the deployment. That renders a
redacted error screen while every local test still passes.

Streamlit Cloud renders the app inside a child iframe, so the outer document is an empty
shell. ``DOM.getDocument`` with ``pierce`` is what actually reaches the rendered content.

Usage::

    python scripts/live_smoke.py
    python scripts/live_smoke.py --base-url https://example.streamlit.app --wait 45

Requires a local Chrome or Edge. Exits non-zero if any page shows an error screen.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://edgecase-atlas.streamlit.app"
PAGE_PATHS: tuple[str, ...] = ("", "test_lab", "compare_runs", "certificates", "research")

# Text Streamlit renders when a page raises. Error details are redacted in this deployment,
# so the wrapper copy is the only reliable signal.
ERROR_MARKERS: tuple[str, ...] = ("encountered an error", "Traceback")
# Proves the app shell booted rather than the request failing outright.
SHELL_MARKER = "EDGECASE ATLAS"

_PROGRAM_FILES = os.environ.get("ProgramFiles", "")
_PROGRAM_FILES_X86 = os.environ.get("ProgramFiles(x86)", "")
_CANDIDATES: tuple[str, ...] = (
    f"{_PROGRAM_FILES}/Google/Chrome/Application/chrome.exe",
    f"{_PROGRAM_FILES_X86}/Google/Chrome/Application/chrome.exe",
    f"{_PROGRAM_FILES_X86}/Microsoft/Edge/Application/msedge.exe",
    f"{_PROGRAM_FILES}/Microsoft/Edge/Application/msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
)


def find_browser() -> str:
    for candidate in _CANDIDATES:
        if candidate and not candidate.startswith("/") and Path(candidate).exists():
            return candidate
        if candidate.startswith("/") and Path(candidate).exists():
            return candidate
    raise SystemExit("live smoke needs a local Chrome or Edge and found none")


def _devtools_raw(port: int, path: str, method: str = "GET") -> str:
    """Call the local DevTools HTTP endpoint. Loopback only, so the scheme is fixed here."""
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
        return response.read().decode("utf-8")


def devtools(port: int, path: str, method: str = "GET") -> dict:
    return json.loads(_devtools_raw(port, path, method))


class Session:
    """One websocket conversation with a browser tab.

    Uses ``websockets``, which ships with the Streamlit dependency set. Do not switch this to
    ``websocket-client``; that package is not a project dependency and is not installed.
    """

    def __init__(self, socket_url: str) -> None:
        import websockets.sync.client as ws_client

        self._socket = ws_client.connect(socket_url, max_size=256 * 1024 * 1024)
        self._counter = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self._counter += 1
        self._socket.send(
            json.dumps({"id": self._counter, "method": method, "params": params or {}})
        )
        while True:
            message = json.loads(self._socket.recv())
            if message.get("id") == self._counter:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    def close(self) -> None:
        self._socket.close()


def check_page(session: Session, url: str, wait_seconds: int) -> tuple[bool, str]:
    """Poll the pierced DOM until the shell renders, an error appears, or time runs out."""
    session.call("Page.enable")
    session.call("Page.navigate", {"url": url})

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        time.sleep(2)
        # pierce reaches the child iframe Streamlit Cloud renders the app into.
        blob = json.dumps(session.call("DOM.getDocument", {"depth": -1, "pierce": True}))
        for marker in ERROR_MARKERS:
            if marker in blob:
                return False, f"rendered error marker {marker!r}"
        if SHELL_MARKER in blob:
            return True, "rendered cleanly"
    return False, f"timed out after {wait_seconds}s waiting for {SHELL_MARKER!r}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live smoke for the deployed public app.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--wait", type=int, default=45, help="Seconds to allow per page.")
    parser.add_argument("--port", type=int, default=9444)
    options = parser.parse_args(argv)

    browser = find_browser()
    with tempfile.TemporaryDirectory(prefix="atlas-live-smoke-") as profile:
        process = subprocess.Popen(  # noqa: S603
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                f"--remote-debugging-port={options.port}",
                f"--user-data-dir={profile}",
                "--window-size=1440,2000",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(60):
                try:
                    devtools(options.port, "/json/version")
                    break
                except (OSError, urllib.error.URLError):
                    time.sleep(0.5)
            else:
                print("live smoke failed: browser devtools never became reachable")
                return 2

            failed = 0
            for path in PAGE_PATHS:
                url = f"{options.base_url.rstrip('/')}/{path}"
                name = path or "home"
                tab = devtools(options.port, "/json/new?about:blank", method="PUT")
                session = Session(tab["webSocketDebuggerUrl"])
                try:
                    passed, reason = check_page(session, url, options.wait)
                finally:
                    session.close()
                    # /json/close answers in plain text, not JSON.
                    _devtools_raw(options.port, f"/json/close/{tab['id']}")
                failed += 0 if passed else 1
                print(f"{'ok  ' if passed else 'FAIL'}  {name:<13} {reason}")

            if failed:
                print(f"Live smoke failed for {failed} of {len(PAGE_PATHS)} public pages.")
                return 1
            print(f"Live smoke passed for all {len(PAGE_PATHS)} public pages.")
            return 0
        finally:
            process.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
