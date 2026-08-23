# Prior-art capability matrix

## Purpose and honesty rule

This matrix positions EdgeCase Atlas against the *approach families* it draws from. It exists to
make the integration claim falsifiable: if any single existing family already supplies all seven
capabilities in one workflow, the integration claim is dead and this file must say so.

Rows are approach families, not named papers. Named-citation rows are deliberately excluded here
because this file is written to a standard where every cell must be traceable to a specific
sentence in a verified source. `protocol.md` contains a separate table with named works and
identifiers. Those identifiers are **not** verified by this file and must be re-checked against the
primary sources before any of them is repeated in a public claim. See
`How to promote a family row to a citation row` below.

Do not add a row for a work you have not opened. An invented citation invalidates the whole
document.

## Capability columns

| Column | Capability | What counts as having it |
|---|---|---|
| C1 | Black-box testing of driving reasoning agents | The system under test is exercised only through its decision interface, with no gradient, weight, activation, or internal-state access. |
| C2 | Paired counterfactuals with explicit sensitivity and invariance relations | Tests are pairs of scenarios differing by a declared relation, and the declaration states whether the output must change (sensitivity) or must not change (invariance). |
| C3 | Typed feasibility constraints | Generated and reduced scenarios are checked against a machine-checkable cross-field validity theory, not only per-field ranges. |
| C4 | Operational-factor, predicate, and decision-boundary coverage | A coverage universe spans scene factors, property-predicate outcomes, and output-transition boundaries, tracked against a cost axis. |
| C5 | Repeated stochastic evaluation | A suspected failure is re-run multiple times under a declared reproduction rule before it is accepted as evidence. |
| C6 | Hierarchical minimization | Reduction proceeds through ordered, domain-aware reducer stages and terminates with an audit establishing minimality under a declared reducer vocabulary. |
| C7 | Replayable causal certificates | Each accepted failure exports a self-contained, content-addressed artifact carrying both scenarios, all trial decisions, target and configuration identity, and an executable replay command. |

C7's word "causal" names the artifact's structure, not a causal-inference claim. The certificate
records the declared retained difference between two scenarios. It does not establish that this
difference caused the decision change in any counterfactual-identification sense.

## Legend

- **Yes** means a routine, defining property of the family.
- **Partial** means some members have it, or the family has a weaker variant.
- **No** means not a property of the family.
- **N/A** means the capability is not meaningful for the family's target.

## Matrix

| Approach family | C1 black-box driving agents | C2 paired sensitivity/invariance | C3 typed feasibility | C4 factor, predicate, boundary coverage | C5 repeated stochastic eval | C6 hierarchical minimization | C7 replayable certificates |
|---|---|---|---|---|---|---|---|
| Closed-loop simulator fuzzing of whole AV stacks | Partial: targets a stack, not a reasoning agent | No: single-scenario search | Partial: physical plausibility, not a typed theory | Partial: behavior or code coverage | Partial: seed repeats are common, the gate is rarely declared | Partial: seed and scenario reduction | Partial: scenario replay files |
| Constrained probabilistic scenario description languages and generators | N/A: generation, not testing | No | Yes: constraint solving is the point | No: generation-side diversity, not oracle coverage | No | No | Partial: scenario programs re-execute |
| Specification-guided or traffic-rule-guided AV fuzzing | Partial | No: a rule is violated in one scenario | Partial | Partial: rule-predicate coverage | Partial | Partial | Partial |
| Behavior-coverage-guided AV testing | Partial | No | Partial | Partial: behavior coverage, not paired-predicate coverage | Partial | Partial | Partial |
| Metamorphic testing of driving perception and decision systems | Yes | Yes: metamorphic relations are the mechanism | Partial: realism heuristics more often than a solver | No | Partial | No | No |
| Metamorphic and invariance testing of LLMs and NLP models | N/A: not driving-specific | Yes | No: text-level and untyped | No | Partial: some average over samples | No | No |
| Property-based testing libraries with automatic shrinking | N/A: general software | Partial: relational properties are expressible, paired-scenario framing is rare | Partial: type-driven, the domain theory is user-supplied | No | Partial: some support flaky-aware retry | Yes: shrinking is the defining feature | Partial: failing example plus seed |
| Delta debugging and test-case reduction, including reduction under nondeterminism | N/A | No | Partial | No | Yes: the nondeterminism-aware variants are built on repeated trials | Yes | Partial |
| Counterfactual explanation and contrastive robustness evaluation for ML | Partial | Yes: contrast pairs are the mechanism | Partial: feasibility and actionability constraints appear in some work | No | No | Partial: sparsity objectives approximate minimality | No |
| Static benchmark suites for driving VLM and LLM reliability | Yes | Partial: some include perturbed variants | No | No: item coverage, not predicate coverage | Partial | No | No |
| Adversarial and red-team prompt suites for LLM agents | Yes | Partial | No | No | Partial | No | Partial: prompt logs |
| Flaky-test detection and repeated-run confirmation in CI | N/A | No | No | No | Yes | No | Partial: run logs |
| **EdgeCase Atlas (this project)** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |

## Where each Atlas cell is implemented

Every Atlas cell above points at code in this repository. Nothing in the Atlas row depends on an
unrun experiment.

| Column | Implementation |
|---|---|
| C1 | `src/edgecase_atlas/evaluation.py`. The `AgentAdapter` protocol is a single `async decide(scenario, seed) -> Decision` method. No other target access exists. |
| C2 | `src/edgecase_atlas/properties.py`. `STARTER_PROPERTY_PACK` pairs an `applies` predicate over a `Counterfactual` with an `oracle` over both decisions. `paraphrase_invariance` is an invariance relation. The other four are sensitivity or non-relaxation relations. |
| C3 | `src/edgecase_atlas/constraints.py`. `validate_scenario` builds one Z3 model per scenario and checks cross-field predicates (`signal.road_incompatible`, `actor.pedestrian_state_incompatible`) alongside range predicates. |
| C4 | `src/edgecase_atlas/coverage.py`. `CoverageTracker.observe` emits `factor:*`, `relation:*`, `applicability:*`, `predicate:*`, `action_transition:*`, and `risk_transition:*` cells against a charged-target-call axis. |
| C5 | `src/edgecase_atlas/properties.py` constants `CONFIRMATION_TRIALS = 5` and `REQUIRED_REPRODUCTIONS = 4`. `evaluation.evaluate_suspected_violation` applies the gate. |
| C6 | `src/edgecase_atlas/minimizer.py`. `HierarchicalMinimizer` runs greedy stages over a five-operation `reducer_vocabulary`, then an exhaustive terminal audit of every remaining single operation. |
| C7 | `src/edgecase_atlas/models.py` `FailureCertificate` plus `engine.recompute_certificate_id`. The certificate identifier is a digest over the stable evidence fields, and the replay command is derived from it. |

## What this matrix does not claim

- It does not claim Atlas invented any single column. Each column is standard practice somewhere.
- It does not claim the families are mutually exclusive. Several real systems straddle rows.
- It does not claim completeness of the family list. A missing family is a defect in this file.
- It does not claim any Atlas advantage in discovery rate, coverage, or reduction size. Those are
  hypotheses in `preregistration.md` with status `not run`.

The only claim is that no listed family routinely supplies all seven columns in one workflow, and
that the combination is the contribution under test.

## How to promote a family row to a citation row

A named-work row may be added only when all of the following are recorded in the row's footnote:

1. Title, venue or archive, year, and a persistent identifier.
2. Retrieval date and the exact version or revision read.
3. For each cell that is not `No`, the specific section or sentence that supports the value.
4. A note on whether the work's target is a full AV stack, a perception module, a reasoning agent,
   or general software, because that determines whether C1 applies at all.

If any of these is missing, keep the claim at family granularity. It is better to be vague and true
than specific and unverifiable.

## Falsifiers for the integration claim

The integration claim is retracted if either of these is found.

- **F1.** A single existing system supplies all seven columns for driving reasoning agents. The
  matrix row for it would then be all `Yes`, and Atlas would have no integration claim left.
- **F2.** The columns turn out not to interact. If the paired-relation, coverage, repetition, and
  minimization components can be shown to contribute independently and additively, then the
  integration is only a bundle, and each part should be credited to its own family instead.

F2 is tested by the ablation arms named in `protocol.md`, not by this document.
