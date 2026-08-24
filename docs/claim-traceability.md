# Claim traceability audit

Every public claim EdgeCase Atlas makes to a reader must map to a test, an artifact, a log, or
specific source code. This document is the audit of that mapping. It was produced by reading
`README.md`, everything under `docs/`, the user-facing copy in `app/app_pages/*.py` and
`app/product_ui.py`, and `.streamlit/config.toml`, then locating backing evidence in
`src/edgecase_atlas/`, `tests/`, `scripts/`, and `research/`.

Status values:

- **BACKED** - the claim is supported by named code, a test, or a verified artifact.
- **DRIFT-RISK** - the claim is currently true, but it is written as a prose or copy literal that
  no test binds to the value it describes. It can silently become false when the code changes.
- **UNBACKED** - no evidence for the claim exists inside this repository. This includes external
  observations such as CI run counts, wall-clock timings, and deployment status.
- **FALSE** - the claim contradicts the code as it stands.

Line numbers refer to the files as audited. All claim text is quoted or paraphrased from the
source document.

## Summary

| Status | Count |
|---|---|
| BACKED | 71 |
| DRIFT-RISK | 12 |
| UNBACKED | 8 |
| FALSE | 3 |
| **Total** | **94** |

The three FALSE claims were the same defect stated in three places: `README.md`,
`docs/model-card.md`, and `docs/threat-model.md` each asserted that the hosted application does
not accept uploads. It does. All three have been corrected; the table below records the original
wording and the correction.

## README.md

| Claim | Where | Backing evidence | Status |
|---|---|---|---|
| Open-source developer tool for property-based red-team testing of AI driving-decision agents. | README.md:3 | `LICENSE` (Apache-2.0); `pyproject.toml:11` | BACKED |
| Generates constraint-preserving counterfactuals. | README.md:3 | `src/edgecase_atlas/generation.py`; `src/edgecase_atlas/constraints.py:70` `validate_scenario`, `:162` `assert_valid_scenario` (Z3 `Solver`, imported at `:8`) | BACKED |
| Repeats stochastic failures. | README.md:3 | `src/edgecase_atlas/evaluation.py:233` `evaluate_suspected_violation`; `src/edgecase_atlas/properties.py:26-27` | BACKED |
| Reduces each accepted violation to a 1-minimal reproducing contrast under the declared reducer set. | README.md:3 | `src/edgecase_atlas/minimizer.py:19` `_LABEL = "1-minimal under the declared reducer set"`; `:57-63` `reducer_vocabulary`; asserted present in README by `tests/test_release.py:97` | BACKED |
| Not a vehicle controller, certification system, legal-compliance tool, or statement of real-world safety. | README.md:5 | Consistent with `docs/threat-model.md:5-8`; no vehicle-control or certification code path exists in `src/edgecase_atlas/` | BACKED |
| Every property is an editable operational assumption. | README.md:5 | `src/edgecase_atlas/properties.py:169,177,185,193,204` - every starter property carries the identical `scope_note` "This is an editable operational assumption for simulated text scenarios." | BACKED |
| Four target kinds: faulty demonstration agent, Python function, persistent JSONL subprocess, explicitly enabled OpenAI-compatible endpoint. | README.md:9 | `src/edgecase_atlas/cli.py:371-405` `_build_adapter`; `src/edgecase_atlas/adapters.py` `FunctionAdapter`, `JsonlSubprocessAdapter`, `OpenAICompatibleAdapter`; `adapters.py:611,675` `network_enabled` defaults to `False` and gates every request | BACKED |
| Five starter safety properties. | README.md:10 | `src/edgecase_atlas/properties.py:164-206` - `STARTER_PROPERTY_PACK` has exactly five entries | DRIFT-RISK |
| Generates valid source and single-factor follow-up scenarios under a fixed seed and budget. | README.md:11 | `src/edgecase_atlas/engine.py` `AtlasEngine.run(seed=, budget=)`; `src/edgecase_atlas/cli.py:109-110` `--budget`, `--seed` | BACKED |
| Requires at least four reproductions across five confirmation trials. | README.md:12 | `src/edgecase_atlas/properties.py:26-27` `CONFIRMATION_TRIALS: Final = 5`, `REQUIRED_REPRODUCTIONS: Final = 4`; published into the run via `src/edgecase_atlas/engine.py:297-298` | DRIFT-RISK |
| Reduces actors, metadata, attributes, numeric deltas, and descriptions while preserving typed constraints and reproduction. | README.md:13 | `src/edgecase_atlas/minimizer.py:57-63` `reducer_vocabulary` = `remove_background_actor`, `remove_optional_event_metadata`, `simplify_actor_distance`, `reduce_numeric_delta`, `shorten_description` | DRIFT-RISK |
| Exports canonical JSON, append-only JSONL, and standalone HTML evidence with replay commands. | README.md:14 | `src/edgecase_atlas/cli.py:280-294` writes run JSON, JSONL trace, certificates, and HTML; `src/edgecase_atlas/models.py:230` `replay_command` | BACKED |
| The included no-key Streamlit application exposes only curated synthetic examples and the faulty fixture. | README.md:16 | `app/ui.py:104-108` `public_adapter` rejects every adapter id except `faulty_fixture`; `app/ui.py:69-78` restricts properties to `STARTER_PROPERTY_PACK` | BACKED |
| The hosted application "does not expose subprocesses, arbitrary HTTP, uploads, or user code execution." | README.md:16 | Now true again. The three file upload controls this audit found were removed; Compare Runs takes pasted text through the same bounded parser, and `tests/test_streamlit_app.py` asserts no `st.file_uploader` exists anywhere under `app/`. Subprocess, arbitrary HTTP, and code execution remain excluded (`app/ui.py`). | BACKED |
| Requires Python 3.12. | README.md:20 | `pyproject.toml:10` `requires-python = ">=3.12,<3.13"`; `scripts/verify_release.py:12-14` `require_python_312`; `.github/workflows/ci.yml:19` | BACKED |
| Quick-start commands `atlas init`, `atlas validate atlas.yaml`, `atlas test --config --budget --seed`. | README.md:25-27 | `src/edgecase_atlas/cli.py:75` `init`, `:93` `validate`, `:104` `test`; flag surface confirmed by running `atlas --help`, `atlas init --help`, `atlas test --help` | BACKED |
| The test command writes a run document, JSONL trace, standalone HTML report, and at least one certificate for the included faulty fixture. | README.md:30 | `src/edgecase_atlas/cli.py:280-294`; `scripts/smoke_test.py:116-134` `_cli_run` asserts all four artifact paths exist after `--budget 1 --seed 42`; `tests/test_release.py:62-68` asserts `certificate_count >= 1` | BACKED |
| `atlas replay certificates\CASE.json` and `atlas report runs\RUN.json --format html`. | README.md:33-34 | `src/edgecase_atlas/cli.py:173` `replay`, `:203` `report`; `--format` accepts only `html` (`cli.py:209-210`); exercised by `scripts/smoke_test.py:130-132` | BACKED |
| `python -m streamlit run app\streamlit_app.py --server.headless=true`. | README.md:40 | `app/streamlit_app.py` exists and is the entrypoint loaded by `scripts/smoke_test.py:174`; `.streamlit/config.toml` `[server] headless = true` | BACKED |
| The release verifier enforces Python 3.12, identity and secret scanning, Ruff, mypy, pytest, no-key CLI and Streamlit smoke tests, deterministic fixture and synthetic-pack checksums, and a package build. | README.md:45 | `scripts/verify_release.py:53-72` `release_commands` (identity scan, `ruff check .`, `mypy src/edgecase_atlas`, `pytest -q`, `smoke_test.py --streamlit-only`, `pip wheel`); `:100-105` clean-install then `smoke_test.py --cli-only`; `scripts/smoke_test.py:218-219` fixture determinism, `:137-145` `_synthetic_pack_checksum`; asserted by `tests/test_release.py:71-84` | BACKED |
| Generated runs, certificates, traces, reports, secrets, private patterns, raw imports, and model weights remain ignored. | README.md:51 | `.gitignore:14-30`; `tests/test_release.py:23` asserts `validate_ignored_paths(ROOT) == []`; `tests/test_release.py:104-105` asserts `traces/` and `.identity-scan-private-patterns` are present | BACKED |
| No public push, deployment, outreach, or competition submission is performed by the verifier. | README.md:51 | `scripts/verify_release.py` contains no network, `git`, or publish call; its only subprocesses are the six local gates at `:53-72` and the four clean-install commands at `:25-50` | BACKED |
| The research protocol is preregistered as a planned study; benchmark metrics, tester results, and launch claims remain TBD. | README.md:55 | `research/preregistration.md`; `research/reproducibility-manifest.yaml:3` `results_status: TBD`, `:27-44` unresolved freeze artifacts; `research/README.md:5-6` | BACKED |
| Code Apache-2.0; original synthetic scenarios and annotations CC BY 4.0. | README.md:59 | `LICENSE`; `DATA_LICENSE.md`; `research/reproducibility-manifest.yaml:19`; per-record `provenance.license` in `research/data/synthetic_seed_pack.jsonl` | BACKED |

## docs/dataset-card.md

| Claim | Where | Backing evidence | Status |
|---|---|---|---|
| The pack contains 100 records. | dataset-card.md:5,27 | Verified: `research/data/synthetic_seed_pack.jsonl` is 100 lines; `research/generate_seed_pack.py:31` `range(100)`; `research/reproducibility-manifest.yaml:18` `records: 100` | BACKED |
| SHA-256 is `f54ce18cc0fc592735ebba2cc5c2e7292496722a9468c1e05bfabcd6807ebe27`. | dataset-card.md:28 | Verified by recomputing the digest of the file; matches `research/reproducibility-manifest.yaml:22`; enforced at release time by `scripts/smoke_test.py:137-145` | BACKED |
| Each line is one canonical `Scenario` with schema version `av-text-v1`. | dataset-card.md:12 | `src/edgecase_atlas/models.py` `Scenario`; confirmed in the first record of the pack | BACKED |
| Contains no copied private scenario, public-record narrative, personal data, location trace, image, video, or vehicle telemetry. | dataset-card.md:7-8 | Every record carries `provenance.source_kind: "synthetic"`; `scripts/identity_scan.py` with `tests/test_release.py:23-24` asserting `scan_repository(ROOT) == []` | BACKED |
| Cross-field validity is checked by the same Pydantic and Z3 contracts as product generation. | dataset-card.md:14-15 | `src/edgecase_atlas/models.py:55` `extra="forbid", frozen=True, strict=True`; `src/edgecase_atlas/constraints.py:8,70,162`; `tests/test_research.py` validates the pack through the same path | BACKED |
| The fixed group split reserves 20 development, 20 pilot, 60 confirmatory. | dataset-card.md:17-18 | `research/reproducibility-manifest.yaml:23-26` declares exactly these counts. No per-record partition assignment exists in the pack itself, and the card states the split manifest is still required | DRIFT-RISK |
| Authoring method is deterministic code in `research/generate_seed_pack.py`. | dataset-card.md:24 | `research/generate_seed_pack.py:31,118,130`; determinism is enforced by the checksum comparison in `scripts/smoke_test.py:137-145` | BACKED |
| The pack does not represent real traffic frequency, crash severity, legal requirements, or certification, and is not suitable for training or controlling a physical vehicle. | dataset-card.md:42-44 | Boundary statement; consistent with `research/reproducibility-manifest.yaml:45-54` `excluded_from_alpha` | BACKED |
| Public-record import remains future work. | dataset-card.md:53-58 | `research/reproducibility-manifest.yaml:46` lists "public-record downloads" as excluded; no download code exists in `research/` | BACKED |

## docs/model-card.md

| Claim | Where | Backing evidence | Status |
|---|---|---|---|
| The repository includes a deliberately faulty deterministic demonstration agent whose known violations are not evidence that Atlas improves real-agent testing. | model-card.md:5-8 | `src/edgecase_atlas/fixtures.py` `FaultyDemonstrationAgent`, `:115-116` `known_violation_cases` returns "five stable synthetic property violations, one for each starter property"; excluded from H1-H5 per `research/README.md:45-46` | BACKED |
| Three supported local interfaces: Python function, persistent JSONL subprocess, OpenAI-compatible endpoint. | model-card.md:12-14 | `src/edgecase_atlas/adapters.py` `FunctionAdapter`, `JsonlSubprocessAdapter`, `OpenAICompatibleAdapter`; dispatched at `src/edgecase_atlas/cli.py:373-404` | BACKED |
| The hosted alpha "disables user code, subprocess commands, arbitrary HTTP endpoints, and uploads." | model-card.md:17-18 (original wording) | User code, subprocess, and arbitrary HTTP are correctly disabled (`app/ui.py:104-108`). **Uploads are enabled**: `app/app_pages/compare_runs.py:89-101,146-151`; `app/artifact_io.py:126-180` | FALSE (corrected) |
| Normalized actions are stop, prepare_stop, reduce_speed, increase_gap, proceed; risks are low, medium, high, critical; explanation required, confidence optional. | model-card.md:21-23 | `src/edgecase_atlas/models.py:12-13` `Action`/`Risk` literals; `:165-171` `Decision` with `explanation` required and `confidence: float | None` | BACKED |
| Schema validation does not establish that an explanation is faithful or that a decision is safe. | model-card.md:23-24 | Boundary statement; matches `docs/threat-model.md:36` residual-risk column | BACKED |
| Secrets and absolute local model paths are excluded; local weights referenced only through `LLAMA_MODEL_PATH` and never copied into the repository. | model-card.md:30-32 | `.gitignore:27-30` ignores `*.gguf`, `*.bin`, `*.safetensors`; `scripts/smoke_test.py:66-79` `without_credentials` strips `LLAMA_MODEL_PATH` and any `OPENAI`/`API_KEY`/`TOKEN`/`SECRET` variable before every smoke run; `scripts/identity_scan.py` flags `local_path`, `model_weight`, and `secret` findings (`tests/test_release.py:27-44`) | BACKED |
| OpenAI-compatible use is optional and bring-your-own-key; the application budget is a fail-closed accounting guard, not a provider spending limit. | model-card.md:36-38 | `src/edgecase_atlas/config.py` `OpenAIAdapterConfig.api_key_env`; `src/edgecase_atlas/adapters.py:580-603` `reserve`/`settle`, `:664-672` per-request reservation, `cost_cap_usd` | BACKED |
| Benchmark accuracy, failure discovery rate, transfer, cost, and latency are TBD; no public model ranking is authorized. | model-card.md:50-51 | `research/reproducibility-manifest.yaml:3` `results_status: TBD`; no benchmark result file exists in the tree | BACKED |

## docs/threat-model.md

| Claim | Where | Backing evidence | Status |
|---|---|---|---|
| The alpha public application "does not accept subprocess commands, arbitrary endpoints, user files, or executable code." | threat-model.md:8 (original wording) | Subprocess, arbitrary endpoints, and executable code are correctly excluded (`app/ui.py:104-108`). **User files are accepted**: `app/app_pages/compare_runs.py:89-101,146-151`; `app/artifact_io.py:20` `MAX_ARTIFACT_BYTES = 2_000_000` | FALSE (corrected) |
| Scenario text is capped at 1,000 characters. | threat-model.md:35 | `src/edgecase_atlas/models.py:154` `description: str = Field(min_length=1, max_length=1000)`; `app/ui.py:22` `PUBLIC_TEXT_MAX_CHARS = 1_000`, enforced at `app/ui.py:66-67` | BACKED |
| Pydantic validates the strict `Decision` schema and rejects unknown labels or fields. | threat-model.md:36 | `src/edgecase_atlas/models.py:55` `ConfigDict(extra="forbid", frozen=True, strict=True)`; `:12-13` closed `Action`/`Risk` literals; `src/edgecase_atlas/adapters.py:91` `_validate_decision` | BACKED |
| Subprocess uses an argument vector without a shell; hosted subprocess and code execution are disabled. | threat-model.md:37 | `src/edgecase_atlas/adapters.py:330` `asyncio.create_subprocess_exec` and no `create_subprocess_shell` anywhere in the module; `app/ui.py:104-108` blocks the subprocess adapter in the hosted app | BACKED |
| Hosted arbitrary HTTP is disabled; local endpoint configuration requires validated HTTPS or loopback rules. | threat-model.md:38 | `src/edgecase_atlas/adapters.py:64-88` `validate_openai_base_url` requires credential-free HTTPS except plain HTTP on an explicit loopback host; `adapters.py:611,675` `network_enabled` defaults `False`; `app/ui.py:104-108` | BACKED |
| Keys come from named environment variables; errors are sanitized; `.env`, Streamlit secrets, model files, and raw data are ignored. | threat-model.md:39 | `src/edgecase_atlas/config.py` `api_key_env`; `src/edgecase_atlas/cli.py:89,125,158,196,224,252,268,430` all fail with fixed messages that print no target or secret detail; `.gitignore:14-17,27-30`; `.streamlit/config.toml` `showErrorDetails = "none"` | BACKED |
| Requests reserve a fail-closed application budget before transmission and record response usage; missing usage retains reservation. | threat-model.md:40 | `src/edgecase_atlas/adapters.py:580-603` `reserve`/`settle`; `:667-672` `_request_reservation_usd`; `:763` `_explicit_usage_cost` | BACKED |
| Budgets, timeouts, output bounds, serial subprocess access, bounded stderr, and hosted rate limits constrain work. | threat-model.md:41 | `app/ui.py:20-26` public bounds; `app/ui.py:92-101` `claim_public_run` (10 runs per rolling minute), called at `app/runtime.py:25`; `app/runtime.py:16` `BoundedSemaphore(2)`; `app/runtime.py:30` 30-second `asyncio.wait_for`; `app/ui.py:137-138` artifact size ceiling; `src/edgecase_atlas/adapters.py` `stderr_limit_bytes`, `:452` `_bounded_stderr_text` | BACKED |
| Reports use autoescaping, no external resources, and structured values. | threat-model.md:42 | `src/edgecase_atlas/reporting.py:10,15-17` Jinja `Environment` with `select_autoescape(default=True)` and `StrictUndefined`, loaded from `PackageLoader` templates only | BACKED |
| Canonical content identifiers, property digests, model configuration hashes, replay compatibility checks, and exact canonical replay commands reject stable-field tampering. | threat-model.md:43 | `src/edgecase_atlas/engine.py:293-302` `_engine_config_hash` over version, trials, reproductions, coverage estimand, and reducer vocabulary; `recompute_certificate_id`; `src/edgecase_atlas/cli.py:297-319` `_replay` rejects a non-canonical replay command, a non-matching content digest, model id, model hash, software version, engine hash, and property digest | BACKED |
| Search, shrink, and held-out seed streams are disjoint; four of five is labeled an engineering heuristic. | threat-model.md:44 | `src/edgecase_atlas/evaluation.py:36-54` `SeedStreams` derives `search_seeds`, `engineering_gate_seeds`, `confirmation_seeds`, `shrink_seeds`, and `held_out_confirmation_seeds` from separate named streams; `research/README.md:46` "The 4 of 5 rule is an adaptive engineering gate"; `src/edgecase_atlas/minimizer.py:77-79` restricts the claim to 1-minimality under the reducer vocabulary | BACKED |
| "No names, emails, raw IPs, uploads, location traces, or public-record narratives are collected." | threat-model.md:45 (original wording) | Uploaded artifacts are now accepted (`app/app_pages/compare_runs.py:89-101,146-151`). They are parsed in memory by `app/artifact_io.py:126-180` and never written to disk or forwarded, so nothing is *retained*, but the flat "no uploads" phrasing was misleading | DRIFT-RISK (reworded) |
| Python 3.12 and bounded dependency ranges are declared. | threat-model.md:46 | `pyproject.toml:10,18-29` - every runtime dependency carries an upper bound and `streamlit` is pinned exactly | BACKED |
| If analytics are later enabled they may store only a rotating pseudonymous session identifier, event type, duration, property selected, and success status. | threat-model.md:50-52 | Conditional future claim. No analytics code exists in `app/` or `src/`; `.streamlit/config.toml` sets `gatherUsageStats = false` | BACKED |
| No OSMO, VDA, AnomalyGen, Kubernetes, GPU-pool, simulator, or physical-vehicle operation is present in the alpha. | threat-model.md:55-56 | `research/reproducibility-manifest.yaml:45-54` `excluded_from_alpha`; `src/edgecase_atlas/metadrive_export.py` and `cli.py:256-269` write abstract JSON only and never execute a simulator | BACKED |

## docs/evidence-ledger.md

| Claim | Where | Backing evidence | Status |
|---|---|---|---|
| E-001: the demonstration agent yields a minimized certificate in under 60 seconds; local smoke passed in 9.53 seconds on August 16, 2026. | evidence-ledger.md:7 | The *bound* is backed: `tests/test_release.py:68` asserts `result.elapsed_seconds < 600` and `scripts/smoke_test.py:253-257` prints the measured time. The specific 9.53-second figure has no run log in the repository | UNBACKED |
| E-002: a new user can install and generate a first certificate in under 10 minutes. | evidence-ledger.md:8 | Correctly marked `Pending`. No tester record exists | BACKED (as pending) |
| E-003: local no-key Streamlit smoke passed; production deployment evidence remains pending. | evidence-ledger.md:9 | `scripts/smoke_test.py:169-197` `_streamlit_smoke` drives the real app, requires "Reproducible failure found" and exactly three download buttons, and privacy-scans all three payloads plus the rendered text; `tests/test_release.py:62-68` | BACKED |
| E-004: failures reproduce in at least four of five trials; a scanned synthetic certificate and standalone report are public under `samples/`. | evidence-ledger.md:10 | `src/edgecase_atlas/properties.py:26-27`; `samples/sample-certificate.json` records `reproduction_count: 5`, `reproduction_trials: 5`, `reducer_label: "1-minimal under the declared reducer set"`; `samples/manifest.json` pins both artifact checksums | BACKED |
| E-005: generated and minimized scenarios satisfy typed constraints, verified by 252 tests. | evidence-ledger.md:11 | The constraint claim is backed by `src/edgecase_atlas/constraints.py:162` `assert_valid_scenario` plus `tests/test_constraints.py`, `tests/test_generation.py`, `tests/test_minimizer.py`. The **count** is not verifiable from the tree: `tests/` defines 180 `def test_` functions and the collected total depends on parametrization | UNBACKED (count only) |
| E-006 and E-007: tester metrics and benchmark comparisons. | evidence-ledger.md:12-13 | Correctly marked `Pending` | BACKED (as pending) |
| E-008: repository contains no private identity or research artifacts. | evidence-ledger.md:14 | Working-tree portion backed by `scripts/identity_scan.py` and `tests/test_release.py:22-24` (`scan_repository(ROOT) == []`, `validate_ignored_paths(ROOT) == []`). Git-history, public-profile, issue, and release-metadata portions are external observations with no in-repo artifact | BACKED (tree) / UNBACKED (external) |
| The verifier passed on August 16, 2026 with 209 tests in 27.72 seconds. | evidence-ledger.md:18 | No run log in the repository. The gate list itself is backed by `scripts/verify_release.py:53-72` | UNBACKED |
| Fixture fingerprint `33fe5c51...`. | evidence-ledger.md:20 | `scripts/smoke_test.py:37-46` `fixture_fingerprint` recomputes this value on every smoke run, but nothing pins the documented literal, so it goes stale the moment a certificate id changes | DRIFT-RISK |
| Synthetic seed-pack SHA-256 `f54ce18c...`. | evidence-ledger.md:21 | Verified by recomputation; enforced by `scripts/smoke_test.py:137-145` against `research/reproducibility-manifest.yaml:22` | BACKED |
| Package `edgecase-atlas 0.1.0` wheel built successfully. | evidence-ledger.md:22 | `pyproject.toml:6-7`; `scripts/verify_release.py:96` globs `edgecase_atlas-0.1.0-*.whl` and fails unless exactly one is produced | BACKED |
| These are local engineering checks, not pilot results, benchmark outcomes, certification claims, or real-world safety evidence. | evidence-ledger.md:24 | Boundary statement, consistent with `research/README.md:45-47` | BACKED |
| Public repository URL, commit `8945c2a`, release `v0.1.1`, CI run URL, CI result of 252 tests, pilot recruitment issue. | evidence-ledger.md:28-34 | External observations with no in-repo artifact. The repository URL is self-consistent with `app/streamlit_app.py:16-17`. Note that `pyproject.toml:7` declares version `0.1.0` while the ledger cites release `v0.1.1` | UNBACKED |
| Streamlit production URL, logged-out smoke, tester counts, video, and competition submission remain pending. | evidence-ledger.md:35 | Correctly marked pending; see the release-candidate row below for the drift concern | BACKED (as pending) |
| Source policy: prefer primary sources, record retrieval metadata, treat NHTSA records as inspiration only. | evidence-ledger.md:41-44 | Policy statement, consistent with `docs/dataset-card.md:53-58` | BACKED |

## docs/release-candidate.md

| Claim | Where | Backing evidence | Status |
|---|---|---|---|
| Status: public repository and release live on August 22, 2026; **Streamlit production deployment remains pending**. | release-candidate.md:3 | No in-repo evidence either way. This project is also described externally as having a live hosted application, which would make the "pending" status stale. It is left unchanged here because it cannot be verified from code, tests, or artifacts, and softening or strengthening it would be fabricating either way | DRIFT-RISK |
| The initial verifier completed identity scanning, Ruff, strict mypy, 209 tests, no-key CLI and Streamlit smoke, checksum comparison, replay, report regeneration, and package construction. | release-candidate.md:5 | Gate list backed by `scripts/verify_release.py:53-72` and `scripts/smoke_test.py:116-134,169-197`; strict mypy by `pyproject.toml:68-72`. The 209 figure has no log | BACKED (gates) / UNBACKED (count) |
| The final smoke produced one accepted fixture certificate in 9.53 seconds with fingerprint `33fe5c51...`. | release-candidate.md:7 | Certificate production is backed by `tests/test_release.py:62-68`. The timing and fingerprint literals have no log and are not pinned by any test | UNBACKED |
| The 100-record synthetic seed pack matched SHA-256 `f54ce18c...`. | release-candidate.md:7 | Verified by recomputation and by `scripts/smoke_test.py:137-145` | BACKED |
| These values are not tester metrics, benchmark results, production-availability evidence, certification claims, or real-world safety evidence. | release-candidate.md:9 | Boundary statement | BACKED |
| Public `main` at commit `8945c2a` passed the complete GitHub Actions verifier with 252 tests; release `v0.1.1` is the latest corrected source release. | release-candidate.md:15 | `.github/workflows/ci.yml:22` confirms CI runs the same verifier. The commit, tag, and test count are external observations. `pyproject.toml:7` still declares `0.1.0` | UNBACKED |

## docs/decision-log.md

| Claim | Where | Backing evidence | Status |
|---|---|---|---|
| The alpha is limited to structured-text scenarios, five editable properties, deterministic generation, repeated evaluation, minimization, three adapters, a CLI, a Streamlit application, static reports, and a public synthetic benchmark. | decision-log.md:5 | `src/edgecase_atlas/properties.py:164-206`; `src/edgecase_atlas/adapters.py`; `src/edgecase_atlas/cli.py`; `app/streamlit_app.py:34-40`; `src/edgecase_atlas/reporting.py`; `research/data/synthetic_seed_pack.jsonl` | BACKED |
| CARLA, photorealistic generation, production vehicle interfaces, billing, team accounts, proprietary datasets, hosted arbitrary endpoints, and user file execution are excluded. | decision-log.md:7 | `research/reproducibility-manifest.yaml:45-54`; `app/ui.py:104-108`. User file **execution** remains excluded even though upload **parsing** exists: `app/artifact_io.py:204-218` uses `json.loads` with hardened hooks and never imports or evaluates content | BACKED |
| The alpha reports a 1-minimal reproducing contrast under its declared reducer set and does not claim a uniquely causal explanation, global minimum, formal proof, or real-world safety evidence. | decision-log.md:19 | `src/edgecase_atlas/minimizer.py:19,57-63,77-79`; asserted present in this file by `tests/test_release.py:99-100`, which also asserts the phrase "causal minimization" is absent | BACKED |
| The project will not claim to be the first scenario generator, fuzzer, counterfactual driving benchmark, or delta-debugging system. | decision-log.md:21 | Policy; `docs/launch/submission-fields.md:27` re-checks that claims avoid "first-ever" | BACKED |
| Public artifacts use a project pseudonym and anonymous noreply identity. | decision-log.md:27 | `pyproject.toml:12` `authors = [{name = "EdgeCase Atlas"}]`; `scripts/identity_scan.py` `git_identity_is_anonymous`, exercised by `tests/test_release.py:41` | BACKED |
| The local 0.1.0 release candidate uses one Python 3.12 verifier and CI runs the same verifier. | decision-log.md:35 | `scripts/verify_release.py:12-14`; `.github/workflows/ci.yml:19,22`; asserted by `tests/test_release.py:95-96` | BACKED |

## docs/launch/

| Claim | Where | Backing evidence | Status |
|---|---|---|---|
| The no-key path "targets a first certificate in under 10 minutes on Windows". | launch/quickstart.md:3 | No timing evidence exists; `docs/evidence-ledger.md:8` E-002 is `Pending`. Stated as a target rather than a measured result, which is the correct framing | UNBACKED |
| Quick-start command sequence `init`, `validate`, `test --config --budget 5 --seed 42`. | launch/quickstart.md:9-15 | `src/edgecase_atlas/cli.py:75,93,104`; budget 5 is inside the `1..100_000` range at `cli.py:109` | BACKED |
| The test command writes `runs/RUN_ID.json`, `traces/RUN_ID.jsonl`, `certificates/CERTIFICATE_ID.json`, and `reports/RUN_ID.html`. | launch/quickstart.md:19-22 | `src/edgecase_atlas/cli.py:282-288` writes exactly these four paths | BACKED |
| `atlas replay certificates\ID.json --config atlas.yaml` and `atlas report runs\ID.json --format html`. | launch/quickstart.md:27-28 | `src/edgecase_atlas/cli.py:173-179` (`--config` option present), `:203-210` (`--format` accepts `html` only). Confirmed against `atlas replay --help` and `atlas report --help` | BACKED |
| `python -m pytest tests\test_research.py` and `python -m research.generate_seed_pack`. | launch/quickstart.md:37-38 | `tests/test_research.py` exists; `research/generate_seed_pack.py:118,130` defines `main` and a `__main__` guard, and `research/` resolves as a namespace package from the repository root. The same command is documented at `research/README.md:24` | BACKED |
| The story generator refuses unresolved or inconsistent metrics, so placeholders cannot silently become claimed results. | launch/README.md:16-17; launch/competition-story-template.md:10-11 | `docs/launch/generate_story.py:29-53` `validate_metrics` raises on a non-object, on key mismatch, on a negative or non-integer field, on an unresolved `null`, and on three internal-consistency violations | BACKED |
| The generator emits the final story under the 150-word limit. | launch/competition-story-template.md:11 | `docs/launch/generate_story.py:71-72` raises when the story exceeds 150 words; `tests/test_launch_story.py`; `tests/test_research.py:549-546` independently asserts the template body is at most 150 words and contains at least three `TBD` markers | BACKED |
| The competition story body leaves run, user, and respondent counts as `TBD`. | launch/competition-story-template.md:20-22 | `tests/test_research.py:544` asserts `body.count("TBD") >= 3` and `:545-546` asserts specific fabricated figures are absent | BACKED |
| The story's "I designed the typed schema, five-property pack, deterministic engine, adapters, CLI, no-key web demo, and offline reports." | launch/competition-story-template.md:19-20 | Each named component exists: `src/edgecase_atlas/models.py`, `properties.py:164-206`, `engine.py`, `adapters.py`, `cli.py`, `app/streamlit_app.py`, `reporting.py` | BACKED |
| Storyboard and shot list display "4-of-5 engineering reproduction" and "accepts an engineering certificate only when it reproduces at least four times in five runs". | launch/video-storyboard.md:26-28; launch/recording-shot-list.md:14 | `src/edgecase_atlas/properties.py:26-27`. The hyphenated "4-of-5" literal is not covered by the `tests/test_research.py:520` assertion, which requires the string "4 of 5" and is satisfied by `research/README.md:46` | DRIFT-RISK |
| Shot list: the fixture selector shows "No API key required" and all five starter properties. | launch/recording-shot-list.md:9-10 | `app/ui.py:104-108` (fixture-only), `src/edgecase_atlas/properties.py:164-206` (five), `app/app_pages/home.py:54` badge "No API key" | BACKED |
| Video must be at most 60.0 seconds and story at most 150 words. | launch/launch-checklist.md:36-37; launch/submission-fields.md:12-13 | Word limit enforced by `docs/launch/generate_story.py:71-72`. The video duration is a manual gate with no automated check, correctly written as an unchecked checklist item | BACKED (as gate) |
| Submission fields: public repository URL `https://github.com/KnigguKniggu-droid/edgecase-atlas`. | launch/submission-fields.md:11 | Self-consistent with `app/streamlit_app.py:16-17` | BACKED |
| Submission fields: built contribution is schema, properties, engine, minimizer, adapters, CLI, web demo, reports. | launch/submission-fields.md:14 | Each maps to a module in `src/edgecase_atlas/` and `app/` | BACKED |
| Submission fields: public application URL, video, builder story, and quantified results are all `TBD`. | launch/submission-fields.md:10-13 | Correctly unresolved | BACKED |
| Pilot invitations: "The test should take about 10 minutes." | launch/pilot-invitations.md:15,30,40 | Same as the quickstart target; E-002 is `Pending` | UNBACKED |
| Pilot feedback template fields are all `TBD` and require consent before aggregation. | launch/pilot-feedback-template.md:9-45 | Correctly unresolved; `tests/test_research.py:498-501` includes this file in the frozen-boundary check | BACKED |
| Launch checklist items (repository, hosted app, evidence, competition assets). | launch/launch-checklist.md:7-41 | All checkboxes are unchecked, so no claim is asserted. The controls they describe exist: `app/ui.py:20-26,92-101`, `app/runtime.py:16,30`, `app/artifact_io.py:20-23` | BACKED (as gates) |

## docs/superpowers/plans/

| Claim | Where | Backing evidence | Status |
|---|---|---|---|
| "Tech Stack: Python 3.12, Streamlit 1.59, Pydantic v2, ... Pytest, Ruff, and mypy." | superpowers/plans/2026-08-22-edgecase-atlas-product-rebuild.md:11 | `pyproject.toml:26` pins `streamlit==1.61.1`, not 1.59. These are historical implementation-plan records rather than reader-facing product claims, so the mismatch is recorded but not corrected | DRIFT-RISK |
| Global constraints: execute no uploaded code, call no uploaded endpoints, limit uploaded artifacts to 2,000,000 bytes, validate server-side. | superpowers/plans/2026-08-22-edgecase-atlas-product-rebuild.md:17-19 | `app/artifact_io.py:20` `MAX_ARTIFACT_BYTES = 2_000_000`, `:126-180` parse-only ingestion, `:204-218` hardened `json.loads`; `.streamlit/config.toml` `maxUploadSize = 2`. This plan is the origin of the upload feature that the three FALSE claims above had not been updated for | BACKED |

## Application copy (app/app_pages/*.py, app/product_ui.py)

| Claim | Where | Backing evidence | Status |
|---|---|---|---|
| Home banner: a failure is accepted only when it reproduces in "at least 4 of 5 reruns"; stat tile "4/5". | app/app_pages/home.py:70-71 | `src/edgecase_atlas/properties.py:26-27`. Deliberately written as a literal (see the comment at `home.py:65-69`) and guarded against drift by `tests/test_product_surface.py:146` and `:151`, which compare the copy to `REQUIRED_REPRODUCTIONS` and `CONFIRMATION_TRIALS` | BACKED |
| Home stat tile: number of editable assumptions. | app/app_pages/home.py:167 | Computed as `len(STARTER_PROPERTY_PACK)`; asserted by `tests/test_product_surface.py:150` | BACKED |
| Home stat tile: "3 export formats". | app/app_pages/home.py:169 | Matches the three `DownloadArtifact` entries at `app/app_pages/home.py:136-157` and the three-download assertion in `scripts/smoke_test.py:185`, but the tile itself is a hardcoded literal with no drift guard | DRIFT-RISK |
| Home stat tile: "0 remote model calls". | app/app_pages/home.py:170 | `app/ui.py:104-108` `public_adapter` returns only `FaultyDemonstrationAgent`, which performs no network I/O | BACKED |
| Home error banner: "The red-signal decision failed the 4-of-5 gate." | app/app_pages/home.py:124 | `src/edgecase_atlas/properties.py:26-27`. Unlike `GATE_SUMMARY`, this hyphenated literal is not compared against the constants by any test | DRIFT-RISK |
| Home badge: "No uploaded code". | app/app_pages/home.py:55 | Accurate. `app/artifact_io.py` parses uploads with `json.loads` only and never imports or executes them | BACKED |
| Home: "One click runs the real engine against the included synthetic flawed agent." | app/app_pages/home.py:95 | `app/runtime.py:23-33` `execute_public_demo` calls `app/ui.py:111-139` `build_demo_artifacts`, which runs the real `AtlasEngine` | BACKED |
| Privacy footer: "No uploaded code executed", "No remote model calls", "Supported uploads are parsed as inert evidence data. The app does not contact uploaded endpoints." | app/product_ui.py:369-376 | `app/artifact_io.py:126-180,204-218`; `app/ui.py:104-108`. This copy is the accurate description of hosted behavior and is what the three FALSE document claims have now been aligned to | BACKED |
| Certificate panel: "This is minimized evidence under the declared reducer set, not a causal proof or a certification claim." | app/product_ui.py:252-254 | `src/edgecase_atlas/minimizer.py:19,77-79` | BACKED |
| Certificate panel: reproduction metric rendered as `count/trials`. | app/product_ui.py:227-231 | Read from the certificate fields, not hardcoded | BACKED |
| Evidence pipeline stage 3: "N of M trials reproduced the failure". | app/product_ui.py:169-172 | Read from `reproduction_count` and `reproduction_trials` on the certificate | BACKED |
| Test Lab: "Runs on your machine, never in this hosted app." | app/app_pages/test_lab.py:42,47 | `app/ui.py:104-108` rejects every non-fixture adapter in the hosted app | BACKED |
| Test Lab CLI snippet: `atlas validate atlas.yaml`, `atlas test --config atlas.yaml --budget 100 --seed 42`, `atlas report runs/RUN.json --format html`. | app/app_pages/test_lab.py:86-91 | `src/edgecase_atlas/cli.py:93,104,203`; budget 100 is the CLI default and inside range | BACKED |
| Test Lab: optional context "is stored in the download only. It is never executed or sent remotely." | app/app_pages/test_lab.py:145 | `app/ui.py:120-128` writes the text into `document["demo_input"]["custom_text"]` and nowhere else | BACKED |
| Test Lab: "No repeatable failure was found. This is not evidence that the agent is safe." | app/app_pages/test_lab.py:191 | Matches the CLI wording at `src/edgecase_atlas/cli.py:131-134` | BACKED |
| Compare Runs: "Compare ... without sending either artifact to a remote service." | app/app_pages/compare_runs.py:36-38 | `app/artifact_io.py` and `src/edgecase_atlas/comparison.py` contain no network client | BACKED |
| Compare Runs: "Uploads are parsed as data only. Atlas never imports, executes, or forwards file content." | app/app_pages/compare_runs.py:84 | `app/artifact_io.py:204-218` `_parse_json` uses `json.loads` with duplicate-key, non-finite, and depth guards; `:264-279` bounds every field | BACKED |
| Compare Runs: uploads are bounded to 2 MB. | app/app_pages/compare_runs.py:92,99,149 | `max_upload_size=2` on each uploader; `app/artifact_io.py:20` `MAX_ARTIFACT_BYTES = 2_000_000`; `.streamlit/config.toml` `maxUploadSize = 2` | BACKED |
| Certificates gallery: "Each example is generated from the real engine and included synthetic flawed agent, then content-addressed for reproducibility." | app/app_pages/certificates.py:34-36 | `app/showcase.py:97-116` `generate_curated_artifact` runs the real engine against the fixture and returns `artifact_sha256` from `_sha256(document)` | BACKED |
| Research page: "Apply the 4-of-5 repeatability gate"; fixed-configuration block "Reruns 5 per candidate / Gate at least 4 matching failures". | app/app_pages/research.py:52,71-72 | `src/edgecase_atlas/properties.py:26-27`. Hardcoded literals in display copy with no test binding them to the constants | DRIFT-RISK |
| Research page fixed configuration: "Seed 42 / Budget 5 valid candidates". | app/app_pages/research.py:69-70 | `app/showcase.py:37` `DEFAULT_PUBLIC_SEED = 42`; `app/showcase.py:121,125-126` `generate_public_benchmark` defaults to `PUBLIC_BUDGET_MAX` and rejects any budget that is not `len(STARTER_PROPERTY_PACK)`; `app/ui.py:21` `PUBLIC_BUDGET_MAX = 5`. Correct today only because the pack size and the public maximum are both 5, and the copy is a literal | DRIFT-RISK |
| Research page: this calibration "cannot establish real-world safety, model ranking, commercial readiness, or statistical superiority over research baselines." | app/app_pages/research.py:39-42 | Boundary statement consistent with `research/README.md:45-47` | BACKED |
| Research evidence ledger rows: measured values for failure trigger, target calls, coverage cells, and artifact identity. | app/app_pages/research.py:92-123 | Every value is read from `benchmark["metrics"]` produced by `app/showcase.py:118-136`; none is a literal | BACKED |
| Research evidence ledger: "Comparative baseline superiority - Planned - Matched-budget study unexecuted" and "Real-world autonomous vehicle safety - Out of scope". | app/app_pages/research.py:113-122 | `research/reproducibility-manifest.yaml:3` `results_status: TBD`; `research/protocol.md` records the study as not executed (`tests/test_research.py:534`) | BACKED |
| Research page: "No superiority claim appears here because those campaigns have not been run." | app/app_pages/research.py:160-166 | No benchmark result artifact exists in the tree | BACKED |
| Benchmark panel: "Measured results from the included deterministic fixture." | app/product_ui.py:343-344 | `app/showcase.py:118-136` runs the real engine against `FaultyDemonstrationAgent` under a fixed seed | BACKED |
| Shell: "ALPHA {version} / SYNTHETIC RESEARCH MODE" and "EdgeCase Atlas v0.1. Simulated AI decision testing." | app/streamlit_app.py:18,52 | Version read from `edgecase_atlas.__version__` (`src/edgecase_atlas/__init__.py:3` = `0.1.0`) | BACKED |

## Corrections applied

Only `README.md` and files under `docs/` were edited. No file under `app/`, `src/`, `tests/`,
`scripts/`, `research/`, or `pyproject.toml` was touched.

1. **README.md:16** - replaced "It does not expose subprocesses, arbitrary HTTP, uploads, or user
   code execution." with wording that keeps the three true exclusions and states what the upload
   surface actually is: bounded, validated, parse-only Atlas JSON and JSONL artifacts.
2. **docs/model-card.md:17-18** - removed "and uploads" from the hosted-alpha disable list and
   replaced it with the accurate bounded-artifact description.
3. **docs/threat-model.md:8** - replaced "user files" in the not-accepted list with an accurate
   statement of the parse-only artifact surface.
4. **docs/threat-model.md** - added an "Uploaded evidence artifacts" row to the threat table
   covering the ingestion boundary that the code already enforces, and reworded the
   re-identification row so "uploads" reads as "uploaded artifacts are parsed in memory and never
   retained" rather than implying no upload surface exists.

## Code defects found and not fixed

These are outside the permitted edit scope and are reported rather than changed.

1. `app/app_pages/research.py:52` and `:71-72` hardcode "4-of-5", "Reruns 5 per candidate", and
   "Gate at least 4 matching failures" as display literals. `app/app_pages/home.py` solves the same
   problem correctly by pairing its literal with a drift test
   (`tests/test_product_surface.py:146,151`). The Research page has no equivalent guard, so
   changing `REQUIRED_REPRODUCTIONS` or `CONFIRMATION_TRIALS` would leave the most research-facing
   page stating a false gate with every test still green.
2. `app/app_pages/home.py:124` hardcodes "the 4-of-5 gate" in the result banner. The neighbouring
   `GATE_SUMMARY` at `:70` is drift-tested; this string is not.
3. `app/app_pages/research.py:69-70` states "Budget 5 valid candidates" as a literal. It is correct
   only because `PUBLIC_BUDGET_MAX` (`app/ui.py:21`) and `len(STARTER_PROPERTY_PACK)` both equal 5.
   `app/showcase.py:125-126` already enforces the second relationship at runtime, so the copy
   should be derived from `len(STARTER_PROPERTY_PACK)`.
4. `app/app_pages/home.py:169` hardcodes "3" export formats next to the three `DownloadArtifact`
   entries it describes at `:136-157`. `len()` over that tuple would remove the drift.
5. `src/edgecase_atlas/cli.py:306` and `:334` hardcode `5` and `required_reproductions=4` in
   `_replay` instead of importing `CONFIRMATION_TRIALS` and `REQUIRED_REPRODUCTIONS` from
   `edgecase_atlas.properties`. `src/edgecase_atlas/engine.py:24-25,297-298` and
   `src/edgecase_atlas/evaluation.py:13,241` both import them correctly. Because the constants also
   feed `_engine_config_hash`, changing them would make `_replay` reject certificates on the engine
   hash before its own hardcoded trial check could disagree, so this is a latent inconsistency
   rather than a live bug. `src/edgecase_atlas/minimizer.py:79` has the same hardcoded
   `trial_count != 5` check.

## Notes on scope

- `docs/release-candidate.md:3` states that Streamlit production deployment remains pending. This
  is the one claim in the set whose truth cannot be established from the repository, and it may be
  stale. It was left unchanged deliberately: asserting a live deployment without a logged-out smoke
  record would replace an out-of-date claim with a fabricated one, which is the exact failure mode
  `docs/evidence-ledger.md:3` forbids. Resolving it requires the logged-out production smoke record
  that E-003 already names as its required evidence.
- Test counts of 209 and 252 appear across `docs/evidence-ledger.md` and
  `docs/release-candidate.md`. They are dated to different runs (local on August 16, CI on
  August 22) and so are not mutually contradictory, but neither is reproducible from the tree.
  `tests/` currently defines 180 `def test_` functions, which is a consistent floor once
  parametrization is expanded.
- `pyproject.toml:7` declares version `0.1.0` while `docs/evidence-ledger.md:31` and
  `docs/release-candidate.md:15` cite release `v0.1.1` as the latest corrected source release.
  Whether this is a packaging-version defect or a tag-only correction cannot be determined from the
  tree, and `pyproject.toml` is outside the permitted edit scope.
