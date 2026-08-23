# EdgeCase Atlas public alpha status

Status: public repository and release live on August 22, 2026. Streamlit production deployment remains pending.

The initial Python 3.12 release verifier completed identity and secret scanning, Ruff, strict mypy, 209 tests, a no-key CLI and Streamlit smoke, deterministic checksum comparison, replay, offline report regeneration, and package construction.

The final smoke produced one accepted fixture certificate in 9.53 seconds. Its stable fingerprint was `33fe5c513691efe20ab52d869f958c81a75de48e34663b4ad841309d8a896697`. The 100-record synthetic seed pack matched SHA-256 `f54ce18cc0fc592735ebba2cc5c2e7292496722a9468c1e05bfabcd6807ebe27`.

These values describe one local engineering run. They are not tester metrics, benchmark results, production-availability evidence, certification claims, or real-world safety evidence.

Streamlit deployment still requires interactive account authentication. Pilot outcomes and competition submission require their separate evidence and approval gates. Payment remains outside authorization.

## Public milestone

Public `main` at commit `8945c2a` passed the complete GitHub Actions verifier with 252 tests. Release `v0.1.1` is the latest corrected source release. Public issues and privacy-safe pilot feedback forms are enabled. No tester, adoption, benchmark, simulator, or competition result is claimed.
