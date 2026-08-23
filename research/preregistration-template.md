# Preregistration template

## How to use this file

Copy this file to `research/preregistrations/<experiment-id>.md`, fill every field, then freeze it.
`preregistration.md` in this directory is the filled draft for the main confirmatory study and is
the worked example to read alongside this template.

Rules for filling it in:

- Every `<...>` placeholder must be replaced or explicitly marked `not applicable` with a reason.
- Never write a number you have not derived. Write `TBD` and leave the go or no-go gate unmet.
- Once frozen, the only permitted edit is an append to the deviation log at the end.
- A field you cannot fill is a design gap, not a formatting problem. Do not freeze around it.

---

## 0. Identity

| Field | Value |
|---|---|
| Experiment id | `<stable machine identifier, matching experiment-manifest.yaml>` |
| Title | `<title>` |
| Protocol version | `<semver, matching protocol.md>` |
| Status | `draft` / `frozen` / `running` / `complete` / `aborted` |
| Freeze timestamp | `<UTC ISO 8601, or TBD>` |
| Repository commit at freeze | `<full commit hash, or TBD>` |
| Software version | `<edgecase_atlas.__version__ at freeze>` |
| Property pack version and digest | `<version>` / `<engine property_pack_digest>` |
| Engine config hash | `<engine._engine_config_hash output>` |
| Results status | `not_run` until an auditable run exists |

Do not record any personal name, institution, mentor, email address, or local filesystem path in
this file. Reference code by repository-relative path only.

## 1. Question and claim boundary

**Question.** `<one sentence, answerable by the measurements in section 4>`

**Claim if positive.** `<the exact sentence that would be published, no adjectives>`

**Claim boundary.** State explicitly what the result will not establish. At minimum:

- Not a safety proof, certification artifact, or statement about any physical vehicle.
- Not a claim about internal reasoning or explanation faithfulness.
- Conditional on `<target build, prompt, decoding configuration, adapter, reset protocol, property
  pack version, seed corpus>`.
- `<any further conditionality>`

## 2. Hypotheses

One primary hypothesis. Every additional hypothesis contributes at most one designated p-value to a
multiplicity family.

| Id | Statement | Estimand | Null | Alternative | Alpha | Family |
|---|---|---|---|---|---|---|
| H1 | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | primary |
| H2 | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<correction method>` |

Multiplicity correction: `<method, and exactly which p-values it covers>`

Anything not in this table is exploratory and must be labelled exploratory wherever it appears.

## 3. Design

| Field | Value |
|---|---|
| Experimental unit | `<the unit that is independent; queries inside a campaign are not>` |
| Number of units | `<n>` |
| Arms or methods | `<stable machine identifiers>` |
| Preselected primary comparator | `<one arm, chosen before any outcome is viewed>` |
| Blocking | `<what is fixed within a block>` |
| Randomization | `<what is randomized, and the seed source>` |
| Reset between arms | `<target state, history, cache, tools, random state>` |
| Blinding | `<what is blind to what, and until when>` |
| Budget axis | `<the cost axis all arms share, e.g. total charged target calls>` |
| Per-arm budget | `<value, and what it excludes>` |
| Stopping rule | `<fixed budget, or a preregistered sequential design with its boundaries>` |

**Information parity.** Fill one row per arm. Any asymmetry is a deliberate design choice and must
be justified here, not discovered later.

| Information | `<arm 1>` | `<arm 2>` | `<...>` |
|---|---|---|---|
| Seed scenarios | | | |
| Property and relation definitions | | | |
| Feasibility constraints | | | |
| Prior target outputs | | | |
| Coverage feedback | | | |

## 4. Measurements

| Outcome | Id | Definition | Instrument | Unit |
|---|---|---|---|---|
| Primary | `<...>` | `<computable definition, no ambiguity>` | `<file and function that computes it>` | `<per what>` |
| Secondary | `<...>` | `<...>` | `<...>` | `<...>` |

**Deduplication or signature definition.** `<the exact tuple, with the normalization and equivalence
map identified by digest>`

**Coverage universe.** `<the finite cell families and their digest, if coverage is an outcome>`

**Adjudication.** `<who or what resolves ambiguous cases, blind to arm, and before outcomes are
computed>`

## 5. Analysis plan

| Hypothesis | Primary analysis | Sensitivity analyses | Implementation |
|---|---|---|---|
| H1 | `<test>` | `<listed before execution>` | `<path and function>` |

- Missing data rule: `<how timeouts, crashes, malformed outputs, and retries are handled>`
- Exclusion rule: `<frozen before outcomes, and summarized by arm>`
- Power: `<simulation-based, with the assumed rate, effect, variance, dispersion, and target power,
  or TBD>`
- Fallback if a model fails to converge: `<named in advance>`

## 6. Reproduction and confirmation

| Field | Value |
|---|---|
| Discovery gate | `<the adaptive heuristic, and an explicit statement that it is not confirmation>` |
| Confirmation design | `<identifier, trial count, acceptance rule>` |
| Seed streams | `<which streams exist, and the evidence that they are disjoint>` |
| Reducer vocabulary and order | `<frozen list>` |
| Minimality claim scope | `<what the label means and what it does not>` |

## 7. Data and privacy

| Field | Value |
|---|---|
| Data sources | `<paths and checksums>` |
| Licenses | `<per source>` |
| Partition rule | `<group-level, applied before any target execution>` |
| Personal data | `<must be none, with the guard named>` |
| Human subjects | `<none, or the written institutional determination reference>` |

## 8. Go or no-go conditions

Confirmatory execution may not begin until every box is checked. An unchecked box is a hard block.

- [ ] The primary comparator and the superiority margin interpretation are frozen.
- [ ] The cost ledger reconciles every attempted call, including retries and failures.
- [ ] Power analysis supports the planned unit count, or the count has been increased.
- [ ] Seed streams are proven disjoint by an automated test.
- [ ] Outcome and minimality functions pass adversarial tests.
- [ ] Every data source has passed license, provenance, privacy, deduplication, and split review.
- [ ] Any external bridge required by a hypothesis is executable before selection occurs.
- [ ] `<experiment-specific gate>`

## 9. Deviation log

Append-only. One row per deviation, written at the time it happens, not reconstructed afterwards.

| Date (UTC) | Section | What changed | Why | Analysis status after change |
|---|---|---|---|---|
| | | | | `confirmatory` / `exploratory` |

Any change to sections 2 through 5 after freeze moves the affected analysis to `exploratory`
permanently. There is no path back.
