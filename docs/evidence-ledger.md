# Evidence ledger

Every public claim must point to a reproducible artifact, recorded observation, or cited primary source. Unknown values remain `TBD` and must never be replaced with estimates presented as results.

| Claim ID | Claim | Required evidence | Status |
|---|---|---|---|
| E-001 | The demonstration agent yields a minimized certificate in under 60 seconds. | Timed clean-environment run log with hardware and software versions. | Local release smoke passed in 9.53 seconds on August 16, 2026. Clean-environment and public hardware evidence remain pending. |
| E-002 | A new user can install and generate a first certificate in under 10 minutes. | Two independent tester session timestamps and commands. | Pending |
| E-003 | A free no-key public demonstration completes successfully. | Logged-out production smoke-test record. | Backed. `scripts/live_smoke.py` loads all five public pages in a headless browser with no session or credentials and fails on a Streamlit error screen. Passed for all five on August 23, 2026 against the deployed commit. Re-runnable on demand. |
| E-004 | Failures reproduce in at least four of five trials. | Certificate fields plus JSONL trace for each accepted failure. | Local release smoke produced one replayable accepted certificate. A scanned synthetic certificate and standalone report are public under `samples/`. |
| E-005 | Generated and minimized scenarios satisfy typed constraints. | Automated constraint tests and post-shrink validation results. | Verified by 252 tests on local Python 3.12 and the public clean-wheel CI run on August 22, 2026. |
| E-006 | Tester, run, return-use, and clarity metrics. | Minimal anonymous event aggregate and written feedback ledger. | Pending |
| E-007 | Benchmark failure counts and coverage comparisons. | Frozen configs, checksummed traces, analysis scripts, and rendered results. | Pending |
| E-008 | Repository contains no private identity or research artifacts. | Working tree, Git history, report, deployment, and rendered-page scan. | Working tree, Git authors and committers, history, tags, blobs, generated artifacts, public profile fields, issue content, and release metadata passed. Production Streamlit page scanning remains pending. |

## Current verification, August 23, 2026

Measured on this date against the deployed commit `f9fc7ac`. Each line is the literal result
of the command named beside it, not an estimate.

- `python -m pytest -q`: 340 passed.
- `python -m ruff check .`: all checks passed.
- `python -m mypy src/edgecase_atlas`: no issues in 19 source files.
- `python scripts/identity_scan.py`: passed, with the local private-term list present, so the
  private-term check actually ran rather than silently inspecting nothing.
- `python scripts/live_smoke.py`: all five public pages rendered cleanly, logged out.
- `python scripts/verify_release.py`: passed, including a clean wheel build, installation into an isolated environment, and a packaged CLI smoke that produced one certificate.

The figures in the sections below are records of earlier dated runs and are retained as
history. Where they disagree with the numbers above, the numbers above are current.

## Local release-candidate evidence

The Python 3.12 release verifier passed on August 16, 2026 with 209 tests in 27.72 seconds, Ruff, strict mypy, identity scanning, two deterministic fixture runs, replay, report regeneration, no-key Streamlit rendering, and package construction. The integrated smoke took 9.53 seconds.

- Fixture fingerprint: `33fe5c513691efe20ab52d869f958c81a75de48e34663b4ad841309d8a896697`
- Synthetic seed-pack SHA-256: `f54ce18cc0fc592735ebba2cc5c2e7292496722a9468c1e05bfabcd6807ebe27`
- Package: `edgecase-atlas 0.1.0` wheel built successfully and was removed with the bounded temporary directory.

These are local engineering checks, not pilot results, public availability evidence, benchmark outcomes, certification claims, or real-world safety evidence.

## Observed public launch evidence

- Public repository: `https://github.com/KnigguKniggu-droid/edgecase-atlas`
- Default branch: `main`
- Integrated public commit: `8945c2a`
- Latest corrected release: `v0.1.1`
- Public CI: `https://github.com/KnigguKniggu-droid/edgecase-atlas/actions/runs/32607602392`
- CI result: 252 tests plus identity scanning, Ruff, strict mypy, hosted smoke, wheel build, forced clean-wheel installation, and packaged CLI smoke passed.
- Pilot recruitment issue: `https://github.com/KnigguKniggu-droid/edgecase-atlas/issues/1`
- Streamlit production URL, logged-out smoke, tester counts, repeated-use counts, feedback counts, video, and competition submission remain pending.

These facts are repository observations, not user adoption, research outcomes, or real-world safety evidence.

## Source policy

- Prefer official documentation, primary research papers, and government records.
- Record URL, title, publisher, publication date, retrieval date, applicable license, and exact supported claim.
- Treat NHTSA records as scenario inspiration only. Do not infer incident rates, manufacturer rankings, or causes.
- Keep interviews outside the research dataset unless a written institutional IRB determination permits a publishable study.
