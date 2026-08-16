# Contributing

EdgeCase Atlas accepts narrow, test-first changes that preserve its simulated-research boundary and anonymous public identity.

## Development check

Use Python 3.12, then run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\verify_release.py
```

Write a failing test, verify the intended failure, implement the smallest change, run focused tests, then run the complete release verifier. Keep public properties framed as editable operational assumptions, not universal rules or certification criteria.

## Public data and identity

Add only independently written synthetic fixtures or records with documented public provenance and license. Do not copy private scenarios, prompts, outputs, model files, personal identifiers, affiliations, local paths, secrets, or unrelated research.

Use the project pseudonym and a GitHub noreply address for public commits. Do not commit generated runs, certificates, traces, reports, raw imports, `.env` files, Streamlit secrets, or `.identity-scan-private-patterns`.

## Scope

The 0.1 alpha covers structured text, five starter properties, three local adapters, CLI artifacts, offline reports, and a no-key synthetic Streamlit demonstration. Production vehicle interfaces, physical testing, billing, arbitrary hosted endpoints, uploads, and commercial safety claims remain out of scope.
