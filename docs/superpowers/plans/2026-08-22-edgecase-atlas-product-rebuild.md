# EdgeCase Atlas Product Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the single demonstration dashboard with a useful, navigable public product containing five validated workflows.

**Architecture:** Keep the tested Python engine and Streamlit deployment. Split page scripts from pure upload, benchmark, comparison, and rendering modules so trust-boundary logic remains independently testable.

**Tech Stack:** Python 3.12, Streamlit 1.59, Pydantic v2, Altair-compatible native charts, Pytest, Ruff, and mypy.

**Spec:** `docs/superpowers/plans/2026-08-11-edgecase-atlas.md`

## Global Constraints

- Preserve public anonymity and the simulated-research disclaimer.
- Execute no uploaded code and call no uploaded endpoints.
- Limit uploaded artifacts to 2,000,000 bytes and validate them server-side.
- Use measured synthetic calibration results only.
- Keep the no-key demonstration deterministic and complete within 10 seconds.
- Preserve JSON, JSONL, and offline HTML exports.

## Tasks

- [ ] Add strict JSON and JSONL ingestion with adversarial tests.
- [ ] Add deterministic five-property showcase and benchmark services.
- [ ] Add reusable native Streamlit evidence components.
- [ ] Add top navigation for Home, Test Lab, Compare Runs, Certificates, and Research.
- [ ] Replace static scenario tables with visual factor cards and a failure timeline.
- [ ] Add uploaded-run comparison and trace inspection.
- [ ] Add five-property certificate gallery and reproducible benchmark.
- [ ] Run focused tests, the full release verifier, identity scan, and responsive browser review.
- [ ] Push to public main, verify CI, and smoke-test the logged-out deployment.
