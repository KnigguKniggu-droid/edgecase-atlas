# Research evidence ledger

## Scope

This ledger covers claims the **research package** makes about the method, the implementation, and
the eventual study. `docs/evidence-ledger.md` covers product and launch claims and is a separate
document. Where the two overlap, this file records what was verified by reading this repository and
does not restate the product ledger's status.

## Rules

1. Every claim gets a row before it appears in a paper, README, abstract, talk, or issue comment.
2. The `Backing artifact` column names a file path, a test node id, a command, or a log. A
   description of an artifact is not an artifact.
3. The `Status` column uses exactly one of the values in the status vocabulary below.
4. A row whose status is `Not produced` must not have its claim stated anywhere in the present
   tense. Write it as a hypothesis with an explicit `not run` marker.
5. Numbers are never carried forward from a prior version of a document. They are re-derived from
   the artifact or the row moves back to `Not produced`.

## Status vocabulary

| Status | Meaning |
|---|---|
| `Source-verified` | Established by reading the named source file in this repository. No execution required. |
| `Test-verified` | Established by a named automated test in `tests/`. The test name is recorded. |
| `Run-verified` | Established by a named, checksummed run artifact or log. |
| `Reported elsewhere` | Asserted in another repository document and not independently re-checked here. The other document is named. |
| `Not produced` | The artifact does not exist yet. The claim is a hypothesis. |
| `Retired` | The claim was withdrawn. The reason is recorded in the row. |

## A. Method and implementation claims

These were checked by reading source in this repository. No test suite, linter, or verifier was run
while writing this ledger.

| ID | Claim | Backing artifact | Status |
|---|---|---|---|
| R-001 | The reproduction gate requires at least 4 reproductions across 5 trials. | `src/edgecase_atlas/properties.py` defines `CONFIRMATION_TRIALS = 5` and `REQUIRED_REPRODUCTIONS = 4`. `evaluation.evaluate_suspected_violation` compares `reproduction_count >= required_reproductions`. | Source-verified |
| R-002 | The gate constants are published in the engine configuration hash, so a changed gate changes every certificate identity. | `engine._engine_config_hash` hashes `confirmation_trials`, `required_reproductions`, `software_version`, `coverage_estimand`, and the reducer vocabulary. `recompute_certificate_id` includes `engine_config_hash`. | Source-verified |
| R-003 | The gate constants are surfaced to the user interface rather than hard-coded in prose. | `tests/test_product_surface.py` asserts the banner text and a `reproduction gate` metric built from `REQUIRED_REPRODUCTIONS` and `CONFIRMATION_TRIALS`. | Test-verified |
| R-004 | The search, engineering-gate, shrink, and held-out confirmation seed streams are disjoint. | `evaluation.SeedStreams._seeds` domain-separates by stream label inside the SHA-256 preimage. `tests/test_task2_regressions.py` asserts pairwise disjointness across all four streams; `tests/test_evaluation.py::test_seed_streams_are_disjoint_and_deterministic` asserts three of them. | Test-verified |
| R-005 | The held-out confirmation stream is reserved and never consumed by the alpha engine. | `SeedStreams.held_out_confirmation_seeds` exists but has no call site in `engine.py` or `minimizer.py`. `RunMetadata.confirmation_note` states the stream is unexecuted. | Source-verified |
| R-006 | Scenario validity is enforced by a solver-backed cross-field theory, not only by field ranges. | `constraints.validate_scenario` builds one Z3 `Solver` per scenario and checks `speed.nonnegative`, `speed_limit.positive`, `signal.road_incompatible`, `actor.distance_nonnegative`, and `actor.pedestrian_state_incompatible`. | Source-verified |
| R-007 | Constraint validity is re-checked on every reduced candidate, not only at generation. | `minimizer.operation_to_counterfactual` routes through `generation.build_counterfactual`, which calls `assert_valid_scenario` on both sides before constructing the `Counterfactual`. | Source-verified |
| R-008 | Overspeed is deliberately a valid scenario rather than a constraint violation. | `constraints.validate_scenario` docstring and predicate list: the speed-limit relation constrains only nonnegative speed and positive limit. | Source-verified |
| R-009 | A relation is rejected if it changes any field outside its declared target plus documented non-causal paths. | `properties._is_isolated` permits only `NON_CAUSAL_PATHS` (`scenario_id`, `description`) and the relation's own target paths. `generation.build_counterfactual` raises when `property_.applies` is false. | Source-verified |
| R-010 | The declared changed-field list always equals the canonical diff of the two scenarios. | `models.Counterfactual.validate_declared_differences` and `models.FailureCertificate.validate_reproduction_evidence` both compare against `canonical_scenario_diffs`. | Source-verified |
| R-011 | The reducer vocabulary is exactly five named operations and is published in the certificate. | `minimizer.HierarchicalMinimizer.reducer_vocabulary` lists `remove_background_actor`, `remove_optional_event_metadata`, `simplify_actor_distance`, `reduce_numeric_delta`, `shorten_description`. `FailureCertificate.reducer_vocabulary` carries it. | Source-verified |
| R-012 | A certificate is emitted only when a terminal audit found no further single reduction. | `minimizer.minimize` sets `terminal_audit_complete = all(not attempt.accepted ...)` and passes it as `MinimizationResult.accepted`. `engine.run` appends a certificate only under `if minimization.accepted`. | Source-verified |
| R-013 | The `1-minimal` label is scoped to the declared reducer set and is not a global minimality claim. | `minimizer._LABEL` is the literal string `1-minimal under the declared reducer set`, carried into `FailureCertificate.reducer_label`. | Source-verified |
| R-014 | Every attempted target invocation is charged exactly once, including failures. | `evaluation._decide` calls `ledger.record` inside a `finally` block, so timeouts and exceptions are charged before the exception propagates. `CallLedger.record` increments `target_calls_total` unconditionally. | Source-verified |
| R-015 | Charged calls are attributed to exactly one of three phases. | `CallLedger.record` increments `search_calls`, `confirmation_calls`, or `minimization_calls`, and `EvaluationPhase` is `search`, `confirmation`, or `minimization`. | Source-verified |
| R-016 | An unknown cost estimate cannot be serialized as a real zero cost. | `FailureCertificate.validate_reproduction_evidence` rejects a certificate whose `cost_estimate_available` is false and whose `estimated_cost_usd` is nonzero. `CallLedger.cost_estimate_available` is true only when every charged call had a known cost. | Source-verified |
| R-017 | The certificate identifier is a deterministic content digest over stable evidence fields. | `engine.recompute_certificate_id` hashes a canonical JSON object of relation, property, both scenarios, changed fields, all trial decisions, reproduction counts, target identity, config hashes, reducer label and vocabulary, and the audit flag. | Source-verified |
| R-018 | The abstract simulator export refuses a certificate whose content digest or replay command does not match. | `metadrive_export.export_metadrive_abstract` raises on a non-canonical replay command and on a digest mismatch. | Source-verified |
| R-019 | Provenance rejects contact, identity, and precise-location markers. | `models.Provenance._validate_non_identifying_text` against `_PERSONAL_DATA_MARKERS` and `_PHONE_PATTERN`; `Actor.validate_event_metadata` applies the same markers. | Source-verified |
| R-020 | The provenance guard is structural and incomplete, so a public dataset still needs a separate privacy review. | `models.Provenance` class docstring states exactly this limitation. | Source-verified |
| R-021 | The alpha seed pack contains 100 records and is regenerable from code. | `research/data/synthetic_seed_pack.jsonl` has 100 lines (`wc -l`). `research/generate_seed_pack.py` constructs `range(100)` deterministically with no input file. | Source-verified |
| R-022 | The seed pack checksum is `f54ce18cc0fc592735ebba2cc5c2e7292496722a9468c1e05bfabcd6807ebe27`. | `research/reproducibility-manifest.yaml` and `docs/dataset-card.md`. Not recomputed while writing this ledger. | Reported elsewhere |
| R-023 | The five benchmark method identifiers are declared, but only their evidence format is implemented. | `research/baselines.py` `METHODS` is an accepted-identifier tuple used by a JSONL validator. No search implementation exists for `random_valid_sampling`, `fixed_metamorphic_templates`, `unguided_llm_generation`, or `diversity_criticality_search`. | Source-verified |
| R-024 | `research_confirmed` requires at least 20 held-out paired reruns with a violation in every pair. | `research/analysis.py` rejects the flag when `len(held_out) < 20` or when `held_out_successes != len(held_out)`. | Source-verified |
| R-025 | The statistics used for the planned analyses are dependency-free and deterministic under a seed. | `research/statistics.py` implements exact sign enumeration up to 20 blocks, seeded Monte Carlo above that, a seeded paired bootstrap, and Holm adjustment. | Source-verified |
| R-026 | The engine's own generated corpus never emits a background actor, so the `remove_background_actor` reducer is unreachable on engine-generated cases. | `generation.transform_for_property` constructs actors with the `Actor.relevance` default of `relevant` and never sets `background`. `minimizer._is_background` requires `relevance == "background"`. Same holds for `research/generate_seed_pack.py`. No test asserting this was located. | Source-verified |
| R-027 | The engine and minimizer pass the trial count and required reproductions as literals rather than reading the exported constants. | `engine.run` calls `streams.engineering_gate_seeds(5)` and `required_reproductions=4`. `minimizer.minimize` defaults `trial_count: int = 5` and passes `required_reproductions=4`. The constants are still hashed into the engine config, so a constant change would alter certificate identity without altering behaviour. | Source-verified |

R-026 and R-027 are recorded as findings, not as defects to be fixed by this document. They belong
in the limitations section of any write-up because they bound what the reducer and gate evidence
actually demonstrate.

## B. Study claims that do not yet have evidence

Every row below is `Not produced`. None of these claims may be stated as a result. The hypothesis
text lives in `preregistration.md`.

| ID | Claim | Required evidence | Status |
|---|---|---|---|
| R-101 | Atlas discovers more distinct independently confirmed failure signatures per charged target call than the preselected comparator. | Frozen experiment manifest, complete charged-call JSONL ledger for all 5 methods across all confirmatory blocks, blind adjudication record, blocked paired randomization output. | Not produced |
| R-102 | Atlas improves normalized coverage area under the charged-call curve. | Per-method-per-block coverage trajectories from `coverage.CoverageTracker`, frozen coverage-universe digest, blocked paired permutation output. | Not produced |
| R-103 | Generated candidates satisfy feasibility constraints at the preregistered pre-repair rate. | Raw pre-repair proposal log with an explicit denominator, including rejected proposals, plus `constraints.validate_scenario` outcomes per proposal. | Not produced |
| R-104 | Minimization removes the preregistered fraction of active factors. | Per-certificate pre- and post-minimization factor counts across every eligible certificate, failed minimizations scored as zero. | Not produced |
| R-105 | Certified abstract violations reproduce in a simulator. | An executed simulator bridge, a frozen outcome-blind selection rule, paired seeds, and per-certificate episode outcomes. MetaDrive is not installed or executed in the alpha. | Not produced |
| R-106 | Findings transfer across target models. | A frozen shared transfer set with matched binary outcomes per model. Exploratory only; models are not pooled as independent units. | Not produced |
| R-107 | The five capabilities interact rather than contribute additively. | Ablation arms with a shared budget and shared oracle, reported per component. | Not produced |
| R-108 | Any statement about tool usability, adoption, tester counts, or time-to-first-certificate for a new user. | Out of scope for this research package. See `docs/evidence-ledger.md`. No usability claim is authorized without a written institutional determination. | Not produced |

## C. Row template

Copy this block for a new claim. Do not delete a row when a claim is dropped; set it to `Retired`
and record why.

```text
| R-xxx | <one sentence, present tense, no adjectives> | <path, test node id, command, or log> | <one status value> |
```

If you cannot fill the `Backing artifact` cell with something a reader could open, the claim is not
ready to be written down.
