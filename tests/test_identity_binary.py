from pathlib import Path

from scripts.identity_scan import Finding, scan_bytes

ROOT = Path(__file__).parents[1]


def test_identity_scan_fails_closed_on_nul_byte_content() -> None:
    assert scan_bytes(Path("opaque.bin"), b"safe\0hidden") == [
        Finding(Path("opaque.bin"), "opaque_binary")
    ]


def test_identity_scan_allows_only_hash_pinned_public_font_binary() -> None:
    relative_path = Path("app/static/fonts/IBMPlexSans-Regular-Latin1.woff2")
    payload = (ROOT / relative_path).read_bytes()

    assert scan_bytes(relative_path, payload) == []

    tampered = payload[:-1] + bytes([payload[-1] ^ 1])
    assert scan_bytes(relative_path, tampered) == [
        Finding(relative_path, "opaque_binary")
    ]
