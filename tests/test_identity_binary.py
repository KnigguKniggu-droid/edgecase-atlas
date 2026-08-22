from pathlib import Path

from scripts.identity_scan import Finding, scan_bytes


def test_identity_scan_fails_closed_on_nul_byte_content() -> None:
    assert scan_bytes(Path("opaque.bin"), b"safe\0hidden") == [
        Finding(Path("opaque.bin"), "opaque_binary")
    ]
