# EdgeCase Atlas

EdgeCase Atlas is an open-source developer tool for property-based red-team testing of AI driving-decision agents. It generates constraint-preserving counterfactuals, repeats stochastic failures, and reduces each accepted violation to a 1-minimal reproducing contrast under the declared reducer set.

The 0.1 alpha targets structured-text scenarios and simulated decision agents. It is not a vehicle controller, certification system, legal-compliance tool, or statement of real-world safety. Every property is an editable operational assumption.

## Implemented workflow

1. Use the included faulty demonstration agent, a Python function, a persistent JSONL subprocess, or an explicitly enabled OpenAI-compatible endpoint.
2. Select any of the five starter safety properties.
3. Generate valid source and single-factor follow-up scenarios under a fixed seed and budget.
4. Require at least four reproductions across five confirmation trials.
5. Reduce actors, metadata, attributes, numeric deltas, and descriptions while preserving typed constraints and reproduction.
6. Export canonical JSON, append-only JSONL, and standalone HTML evidence with replay commands.

The included no-key Streamlit application runs only curated synthetic examples and the faulty fixture. It does not expose subprocesses, arbitrary HTTP endpoints, or user code execution. It accepts one bounded upload class, Atlas JSON run documents and JSONL traces of at most 2,000,000 bytes, which are strictly validated and parsed as inert data. Uploaded content is never imported, executed, forwarded, or retained.

## Quick start

EdgeCase Atlas requires Python 3.12.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\atlas.exe init
.\.venv\Scripts\atlas.exe validate atlas.yaml
.\.venv\Scripts\atlas.exe test --config atlas.yaml --budget 1 --seed 42
```

The test command writes a run document, JSONL trace, standalone HTML report, and at least one certificate for the included faulty fixture. Replay the emitted certificate path, then regenerate the offline report from the emitted run path:

```powershell
.\.venv\Scripts\atlas.exe replay certificates\CASE.json
.\.venv\Scripts\atlas.exe report runs\RUN.json --format html
```

Run the no-key local application with:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py --server.headless=true
```

## Release verification

The release verifier enforces Python 3.12, identity and secret scanning, Ruff, mypy, pytest, no-key CLI and Streamlit smoke tests, deterministic fixture and synthetic-pack checksums, and a package build:

```powershell
.\.venv\Scripts\python.exe scripts\verify_release.py
```

Generated runs, certificates, traces, reports, secrets, private patterns, raw imports, and model weights remain ignored. No public push, deployment, outreach, or competition submission is performed by the verifier.

## Research status

The research protocol is preregistered as a planned study. Benchmark metrics, tester results, and launch claims remain `TBD` until their declared evidence exists. See `research/README.md` and `docs/evidence-ledger.md`.

## License

Code is licensed under Apache-2.0. Original synthetic scenarios and annotations are licensed under CC BY 4.0 as described in `DATA_LICENSE.md`.
