# EdgeCase Atlas research package

This directory contains the frozen design inputs and executable evidence validators for
`Constraint-Guided Counterfactual Fuzzing for Reason-Responsive Driving Agents`.
It does not contain confirmatory results. Every result remains `TBD` until a preregistered run
produces a complete charged-call ledger.

## Contents

- `protocol.md` defines the benchmark-conditional contribution, methods, evidence flow,
  scientific boundaries, what counts as a positive result, and what would falsify each claim.
- `prior-art-matrix.md` positions the integrated contribution against approach families across the
  seven capabilities it combines, and states the two falsifiers of the integration claim.
- `preregistration.md` records the hypotheses, experimental units, estimands, analyses, and
  go or no-go gates that must be frozen before confirmatory work.
- `preregistration-template.md` is the blank form for any further experiment.
- `evidence-ledger.md` maps every research claim to a backing artifact and a status. Rows that are
  verifiable from this repository are pre-filled. Product and launch claims live in
  `docs/evidence-ledger.md`.
- `seed-taxonomy.md` documents the scenario space, derived from the code, and separates the schema
  space, the seed-pack space, and the narrower space a run actually generates.
- `reproducibility-checklist.md` is the pass or fail gate that must be cleared before any result is
  released.
- `card-templates.md` holds blank dataset-card and model-card forms. The filled alpha cards are
  `docs/dataset-card.md` and `docs/model-card.md`.
- `baselines.py` validates canonical JSONL evidence and counts every target call.
- `analysis.py` reduces events to the campaign-block inference unit and counts independently
  confirmed unique signatures.
- `generate_seed_pack.py` deterministically creates the 100 newly written synthetic cases.
- `data/synthetic_seed_pack.jsonl` is the CC BY 4.0 alpha seed pack.
- `reproducibility-manifest.yaml` records versions, checksums, and unresolved result fields.

## Evidence commands

```powershell
.\.venv\Scripts\python.exe -m research.generate_seed_pack
.\.venv\Scripts\python.exe -m research.baselines research\runs\METHOD.jsonl
.\.venv\Scripts\python.exe -m research.analysis research\runs\CONFIRMATORY.jsonl
```

The input stream must use canonical UTF-8 JSONL with one `atlas-research-event-v1` event per
line. Every line repeats identical frozen experiment metadata. Method and campaign block are
event fields because they vary within one experiment. Missing fields, mixed target builds,
mixed partitions, mixed protocol versions, non-finite numbers, and noncanonical JSON are rejected.

Target-call events use `phase` values `search`, `retry`, `adaptive_gate`, `shrink`,
`terminal_audit`, or `held_out_confirmation`. Each event identifies its certificate,
property, relation, source or follow-up role, seed, outcome, and retry lineage. Every attempted
target invocation receives one event even when it times out, crashes, returns malformed output,
or is a retry. Each method and campaign block also declares per-phase and total counts, which the
analyzer reconciles against raw events. Generator calls remain separate because they are not
target calls. A one-minimal claim requires failure-preserving shrink evidence and a terminal audit
over the frozen reducer vocabulary. `research_confirmed` additionally requires at least 20
disjoint held-out paired reruns under `fixed-20-unanimous-v1`. Sequential confirmation remains
future work until its stopping boundaries are preregistered and implemented.

The faulty demonstration agent calibrates the oracle and end-to-end workflow only. It is excluded
from H1 through H5. The 4 of 5 rule is an adaptive engineering gate. Research confirmation is a
later held-out protocol with at least 20 paired reruns or a preregistered sequential alternative.
