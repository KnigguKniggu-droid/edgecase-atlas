# Constraint-Guided Counterfactual Fuzzing for Reason-Responsive Driving Agents

## Status and freeze rule

Status: draft, not preregistered. Results are `TBD`. Any design change after the eventual freeze is
logged and analyzed as exploratory. Pilot data are excluded from all confirmatory outcomes.

The confirmatory target is one frozen structured-text agent build. The benchmark contains five
editable operational properties and a deterministic synthetic seed corpus. Claims do not extend to
commercial vehicles, public roads, certification, or universal safety.

## Hypotheses

### H1: preregistered primary margin

Atlas will discover at least 30 percent more unique minimized failure signatures at a budget of 100
valid evaluations than the strongest baseline. The strongest baseline is selected before outcomes
as `diversity_criticality_search`. The 30 percent is a tested superiority margin, not merely a point
estimate target: `H0: rate ratio <= 1.30` versus `H1: rate ratio > 1.30`, one-sided alpha 0.05.
Because `100 valid evaluations` can hide retries and paired calls, the operational budget axis is
total charged target calls. The legacy 100-allocation view is reported only as a secondary axis.

### H2: coverage target

Atlas will improve combined rule and decision-boundary coverage area under the query curve by at
least 20 percent. The finite method-agnostic universe contains operational factors, relation
applicability, property predicate outcomes, action transitions, and risk transitions with frozen
weights. The 20 percent is an effect-size target unless power analysis supports a formal margin.

### H3: proposal feasibility target

At least 95 percent of generated candidates will satisfy all constraints and at least 98 percent of
non-target fields will remain unchanged. The single confirmatory H3 endpoint is raw pre-repair
proposal feasibility with an explicit denominator. Post-validation feasibility and exact frozen
field preservation are software release invariants. The 98 percent value is reported as a secondary
target and cannot create a second H3 p-value.

### H4: minimization target

Minimization will remove at least 40 percent of active factors and 30 percent of text length while
retaining failure in at least 4 of 5 reruns. The designated confirmatory endpoint is active-factor
reduction across every eligible certificate, with failed minimizations scored as zero. Text length
is secondary. The 4 of 5 result is an adaptive search and shrink heuristic only. Final reproduction
uses held-out confirmation with at least 20 paired reruns or a frozen sequential binomial design.
Factors are counted retained editable fields, not causal factors.

### H5: simulator construct-validity target

At least 60 percent of selected abstract violations will reproduce in MetaDrive as a collision,
near miss, illegal-lane event, deadlock, or statistically lower time-to-collision. This is a future
descriptive target unless power analysis supports a one-sided lower-bound claim. The certificate is
the inference unit. Conversion failures remain in the denominator under the frozen estimand.
MetaDrive execution is outside the alpha.

H1 is the single primary hypothesis. H2 through H5 contribute one designated p-value each to a Holm
family. Cross-model transfer is exploratory and target models are not pooled as independent units.

## Design

Five methods run in 12 paired campaign blocks: `random_valid_sampling`,
`fixed_metamorphic_templates`, `unguided_llm_generation`,
`diversity_criticality_search`, and `atlas`. Every block fixes a source-family split, target build,
and method-independent seed. Method order is randomized within block. Target state, history, cache,
tools, and random state reset between methods.

The alpha pack has 100 newly written synthetic seeds. The frozen group split assigns 20 development,
20 pilot, and 60 confirmatory seeds before target execution. Three pilot campaigns debug the
implementation and bound conservative power assumptions. Their events and outcomes do not enter the
12 confirmatory blocks.

The `6,000` planning value is `primary search calls only`. It excludes the second side of paired
evaluations, retries, adaptive 4 of 5 checks, confirmation, and shrink validation. It must not be
reported as total experimental cost. The canonical ledger derives every target and generator call,
tokens, cost, wall time, invalid proposal, repair, timeout, and malformed output.

Two reduced ablations add about 1,200 planning calls before overhead: no reduction and generic
stochastic delta debugging. The faulty fixture calibrates the oracle only and is excluded from H1
through H5. A minimized transfer set is selected later by outcome-blind stratification. About 30
selected pairs over five paired MetaDrive seeds imply about 300 source and follow-up episodes, but
certificates remain the independent unit.

## Primary outcome and signature

For method `m` and block `b`, `Y[m,b]` is the number of distinct independently confirmed failure
signatures found within the charged target-call budget. Signatures are deduplicated within each
campaign. Corpus union is secondary.

```text
(property_pack_version, relation_id, source_action, follow_up_action,
 source_risk, follow_up_risk, sorted_retained_changed_paths, applicability_stratum)
```

All fields use normalized values and frozen equivalence rules. Coarse and fine signatures are
prespecified sensitivity analyses. Method-blind adjudication finishes before outcome calculation.

## Confirmation and minimization

Search, shrink, and held-out streams are disjoint. Four violations in five trials admit a candidate
to adaptive search or reduction. It does not make a research-confirmed certificate. After adaptive
choices freeze, the original and minimized pairs run on at least 20 shared fresh seeds or the frozen
sequential design. Exact binomial intervals estimate reproduction. The operational lower confidence
floor is frozen after power work and before confirmatory execution.

The reducer vocabulary and order freeze before runs. Terminal 1-minimality auditing attempts every
single remaining reducer operation. All rejected candidates, confirmation failures, and failed
minimizations remain in the intention-to-minimize analysis.

## Confirmatory analyses

1. H1 uses a blocked paired randomization test on campaign counts against the preselected comparator.
   A negative-binomial mixed model is a sensitivity analysis with method effect, block effect or
   random intercept, and log charged-call offset.
2. H2 uses one normalized coverage AUC per method and campaign with a blocked paired permutation test.
3. Kaplan-Meier and stratified log-rank summaries describe calls to first confirmed violation.
   Restricted mean calls through budget receives blocked inference.
4. Exact McNemar applies only to a frozen shared transfer set with matched binary outcomes.
5. H4 uses a paired Wilcoxon or randomization analysis at certificate level. Simulator paired
   summaries also aggregate within certificate before inference.
6. Bootstrap intervals are sensitivity analyses clustered by campaign or certificate. Their
   instability with 12 blocks is reported.
7. Holm correction covers the four designated H2 through H5 p-values. H1 keeps alpha 0.05.

The negative-binomial model freezes NB1 or NB2, convergence checks, zero-inflation diagnostics, and
a randomization fallback. Simulation-based power must reach at least 80 percent under conservative
rate, 1.30 margin, block variance, dispersion, and zero-inflation assumptions. Campaign count rises
before preregistration if 12 blocks fail.

## Missingness and exclusions

Every attempted target call is charged. Timeouts, crashes, malformed outputs, retries, invalid
proposals, confirmation failures, shrink failures, and later simulator conversion failures cannot
be silently dropped. Exclusions are frozen before outcomes and summarized by method and block.

## Ethics and IRB boundary

The confirmatory software study uses synthetic scenarios and models. It contains no public-road
testing, vehicle commands, personal images, personal identifiers, location traces, or hidden
chain-of-thought. Product pilots are not research participants. Any publishable usability study
requires a written institutional IRB determination before recruitment or collection.

## Go or no-go conditions

Do not preregister or execute confirmatory runs until:

1. The comparator and H1 1.30 margin interpretation are frozen.
2. The charged-call ledger reconciles paired calls, retries, confirmation, and shrinking.
3. Simulation supports the campaign count at at least 80 percent power.
4. Search, shrink, and held-out seed streams are proven disjoint.
5. Signature and 1-minimality functions pass adversarial tests.
6. Any future public-record stratum passes license, provenance, privacy, deduplication, and group split.
7. The MetaDrive bridge and outcome-blind selection rule are executable before transfer selection.
