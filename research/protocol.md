# Constraint-Guided Counterfactual Fuzzing for Reason-Responsive Driving Agents

## Research status

This document is a protocol, not a result report. Metrics, p-values, user outcomes, transfer rates,
and launch results are `TBD`. Confirmatory execution cannot begin until every go or no-go condition
in `preregistration.md` passes.

## Defensible contribution

EdgeCase Atlas is a black-box testing workflow for structured-text driving-decision agents. It
combines user-declared required-sensitivity and required-invariance relations, typed feasibility
constraints, paired scenario interventions, decision-transition coverage, stochastic
reconfirmation, and domain-aware 1-minimization into replayable failure certificates. The study
tests whether this integrated workflow discovers more distinct independently confirmed property
violations per charged target-agent call and produces smaller independently reproducible contrasts
than matched search baselines on a fixed benchmark.

This is an integration claim. Atlas does not claim the first counterfactual driving benchmark, LLM
driving fuzzer, coverage-guided driving fuzzer, customizable driving property system, scenario
generator, or stochastic minimizer. A certificate is `1-minimal under the declared reducer set`
only when no single remaining reducer operation preserves validity and the adaptive gate. It is not
a globally smallest counterexample, causal proof, safety proof, certification artifact, or
real-world validation.

The five safety properties are editable operational assumptions. A finding is a property or oracle
violation under those assumptions, not a violation of universal driving law.

## Prior-art boundary

| Work | Established capability | Atlas boundary |
|---|---|---|
| [DriveFuzz](https://arxiv.org/abs/2211.01829) | Guided whole-stack simulator fuzzing | Atlas targets a structured-text decision interface. |
| [DriveBench](https://arxiv.org/abs/2501.04003) | Driving VLM reliability benchmarking | It motivates reliability but is not a search baseline. |
| [ICR-Drive](https://arxiv.org/abs/2604.05378) | Matched instruction perturbations and paraphrase invariance | Atlas adds typed scene-factor relations, multiple output oracles, and reduced replay artifacts. |
| [Scenario Generation for Testing of Autonomous Driving Systems Using Real-World Failure Records](https://arxiv.org/abs/2606.31131) | LLM conversion of public failure records into MetaDrive scenarios | Atlas tests the reasoning agent and does not import public records in alpha. |
| [EvoDrive](https://arxiv.org/abs/2606.03678) | LLM-guided multi-objective simulator scenario generation | Atlas uses declared metamorphic oracles and a black-box target-agent role. |
| [RMT](https://arxiv.org/abs/2012.10672) and [METAL](https://arxiv.org/abs/2312.06056) | Editable driving relations and metamorphic testing of probabilistic LLMs | Atlas specializes these ideas to typed driving decisions and replayable contrasts. |
| [Stochastic CPS delta debugging](https://arxiv.org/abs/2607.25695) | Reduction under flaky execution | Atlas must compare a generic stochastic reducer and cannot claim first stochastic minimization. |
| [BehAVExplor](https://arxiv.org/abs/2307.07493), [LawBreaker](https://arxiv.org/abs/2208.14656), and [Scenic](https://arxiv.org/abs/2010.06580) | Behavior coverage, property-guided fuzzing, and constrained scenario generation | Coverage and constraints are evaluated as an integrated method, not claimed individually as novel. |

## Population and experimental unit

The target population is all valid source scenarios and permitted transformations in the frozen
benchmark DSL, evaluated against one frozen target build, prompt, decoding configuration, adapter,
reset protocol, and property-pack version. H1 through H4 are benchmark-conditional. Cross-model,
simulator, property-pack, and public-road generalization remain exploratory.

One campaign block is the independent unit. A block fixes a seed-pool split, target configuration,
and method-independent randomization seed. Each of the five methods runs once in every block.
Method execution order is randomized within block, and target state is reset between methods.
Queries inside a campaign are dependent and are never analyzed as independent replicates.

## Five compared methods

The method identifiers are stable machine fields:

1. `random_valid_sampling` draws uniformly from the accepted finite factor taxonomy.
2. `fixed_metamorphic_templates` applies the same frozen relation templates without adaptive
   coverage feedback.
3. `unguided_llm_generation` uses a frozen generator build, prompt, temperature, token cap, and
   retry rule, with no target-derived search guidance.
4. `diversity_criticality_search` balances method-agnostic diversity and declared criticality. It
   is preselected as the strongest primary comparator before confirmatory outcomes are viewed.
5. `atlas` uses constraint-preserving relation search and method-agnostic observable coverage.

All methods receive the same seed split, property definitions, validity constraints, target-call
budget, reset rule, failure oracle, 4 of 5 adaptive filter, reducer options, held-out confirmation
rule, and stopping policy. Any deliberately weaker method is calibration evidence, not the decisive
comparator.

| Information | Random | Templates | Unguided LLM | Diversity-criticality | Atlas |
|---|---:|---:|---:|---:|---:|
| Seed scenarios | Yes | Yes | Yes | Yes | Yes |
| Property and relation definitions | Yes | Yes | Yes | Yes | Yes |
| Feasibility constraints | Yes | Yes | Yes | Yes | Yes |
| Prior target outputs | No | No | No | Yes | Yes |
| Observable coverage feedback | No | No | No | Yes | Yes |
| Generator feedback | Not applicable | Not applicable | Fixed validation response only | Not applicable | Not applicable |

## Seed corpus and partitions

The alpha seed pack contains 100 deterministic, newly written synthetic scenarios under CC BY 4.0.
It spans road type, signal, surface, visibility, speed relation, and actor-state factors. Source
families are split before target execution into 20 development, 20 pilot, and 60 confirmatory seeds
by a frozen group-level rule. Near-duplicate taxonomy families cannot cross partitions.

No private scenario, prompt, result, model path, personal identifier, or institutional material is
included. Public government records are not downloaded or represented in the alpha. A future
government-record import must record version, date, checksum, license, incident-level deduplication,
group split, independent abstraction validation, and privacy review. It may support crash-inspired
challenge cases only, not prevalence, manufacturer ranking, exposure, severity, or causal claims.

## Call accounting and fairness

The design names 12 paired campaign blocks and five methods. The historical `6,000` figure is
`primary search calls only`, calculated as 5 methods times 12 blocks times 100 search allocations.
It is not the total experimental cost. A paired evaluation costs at least two target calls. Retries,
source calls, follow-up calls, adaptive 4 of 5 checks, held-out confirmation, and shrink validation
add calls. The final total must be derived from the complete ledger, never inferred from 6,000.

Every target attempt is charged once as `search`, `retry`, `adaptive_gate`, `shrink`,
`terminal_audit`, or `held_out_confirmation`. Each method-campaign summary declares every
phase count and the total. The analyzer reconciles those declarations against raw attempts,
including failures and retries. The ledger also stores generator calls, tokens, cost, wall time,
invalid proposals, repair attempts, timeouts, malformed outputs, and cost-cap failures. Total
target-agent calls are the primary budget axis. Search-only efficiency and end-to-end monetary or
compute cost are secondary axes.

Three pilot campaign blocks may find implementation defects and bound conservative power inputs.
Pilot events, signatures, parameter estimates chosen after unblinding, and outcomes never enter
confirmatory results. Hyperparameters freeze after pilot.

## Failure signature and outcome

The canonical unique signature is:

```text
(property_pack_version, relation_id, source_action, follow_up_action,
 source_risk, follow_up_risk, sorted_retained_changed_paths, applicability_stratum)
```

Values use frozen normalization and an equivalence map. The paths are retained changed paths, not
causal factors. Manual adjudication is blind to method and resolved before outcomes. Coarser and
finer deduplication definitions are sensitivity analyses.

For method `m` in campaign block `b`, the primary outcome is the number of distinct independently
confirmed signatures discovered within the charged target-call budget. Deduplication occurs within
each campaign. The global union is secondary because assigning global duplicates to the first
campaign would create order dependence.

## Reproduction and reduction

Search and shrinking use 4 of 5 violations as an adaptive engineering heuristic only. Discovery,
shrink, and held-out confirmation seeds are disjoint. The implemented
`fixed-20-unanimous-v1` design requires at least 20 fresh paired reruns and a violation in every
pair before `research_confirmed` is accepted. Exact binomial intervals may be reported but do not
replace that machine gate. A sequential binomial design is reserved for future work and cannot be
accepted until its stopping boundaries, operating characteristics, identifier, and validator are
preregistered and implemented.

The original and minimized pairs run on the same held-out confirmation seeds. Rejection traces and
failed minimizations remain in the analysis. The eligible H4 set includes every independently
confirmed pre-minimization certificate. Failed reductions count as zero reduction.

## Statistical analysis map

- H1 uses a blocked paired randomization test at campaign-block level against the preselected
  `diversity_criticality_search` comparator. A negative-binomial mixed model with method effect,
  block effect or random intercept, and log charged-call offset is a sensitivity analysis.
- H2 reduces each method-campaign coverage curve to one normalized AUC and uses a blocked paired
  permutation test.
- Time to first independently confirmed violation is right-censored at budget. Kaplan-Meier curves
  and a stratified log-rank test are descriptive. Restricted mean calls to first failure is analyzed
  by blocked randomization because adaptive search can violate proportional hazards.
- Exact McNemar tests apply only to a frozen shared transfer set where both conditions classify the
  same items. They do not compare adaptive H1 trajectories.
- Paired Wilcoxon tests compare original and minimized certificate size, and may compare paired
  certificate-level simulator summaries. Nested simulator seeds are not independent pairs.
- Bootstrap confidence intervals are sensitivity analyses. Campaign resampling acknowledges that
  12 blocks can be unstable. Simulator resampling clusters by certificate.
- H1 retains its one-sided alpha of 0.05. Holm correction applies to one designated p-value from
  each of H2 through H5. Secondary endpoints are labeled and do not expand the confirmatory family.

Simulation-based power analysis must reach at least 80 percent under conservative baseline rate,
1.30 rate ratio, block variance, overdispersion, and zero-inflation assumptions. If 12 blocks do not
pass, the number of blocks increases before preregistration.

## Later simulator validation

H5 is future construct validation, not alpha execution. About 30 certificates would be selected by
a frozen, outcome-blind, stratified rule over relation, action transition, and retained paths. A
fixed action-to-controller mapping, timing rule, termination rule, road surface, traffic state, and
vehicle dynamics must exist before selection. Each source and follow-up pair uses the same five
simulator seeds. The certificate, not the episode, is the inference unit. Conversion failures stay
in the denominator under the preregistered rule.

MetaDrive is not installed or run in the alpha. CARLA and public-road testing remain excluded.

## Physical-AI future-work boundary

The user-requested physical-AI capabilities are recorded only as future infrastructure options.
OSMO Video Data Augmentation (VDA), OSMO workflow submission, AnomalyGen defect image generation,
Kubernetes provisioning, and resilient GPU-pool scaling are not executed and are not current Atlas
contributions. The alpha has no video data, defect-image data, GPU pool, OSMO storage root, cluster,
or budget for these workflows. They require a separate research question, licensed inputs, compute
plan, storage root, credentials, risk review, and explicit authorization before use.

## Ethics and reproducibility

The main study uses synthetic structured text, software agents, and later simulation. It excludes
physical vehicle commands, public-road tests, personal images, license plates, location traces,
hidden chain-of-thought, personal contact data, and human-subject claims.

Product interviews guide development only and are not research data. An independently reviewed
written IRB or institutional determination is required before any publishable usability study,
recruitment, or analysis of participant responses. Adult pilot feedback is stored as product notes
with no unnecessary identifiers.

The reproducibility release includes schemas, properties, seed split, provenance, prompts, model
identifiers and hashes, quantization settings where applicable, random seeds, coverage definitions,
oracle tests, canonical JSONL traces, environment lock information, statistical scripts, dataset and
model cards, deviation log, and one machine-readable certificate per reported violation.
