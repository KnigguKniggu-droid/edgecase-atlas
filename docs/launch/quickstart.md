# EdgeCase Atlas quick start

This no-key path targets a first certificate in under 10 minutes on Windows when Python 3.12 and an
internet connection for dependency installation are available. Atlas is simulated research and
debugging software. It is not vehicle-control or certification software.

From the repository root, run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\atlas.exe init
.\.venv\Scripts\atlas.exe validate atlas.yaml
.\.venv\Scripts\atlas.exe test --config atlas.yaml --budget 5 --seed 42
```

The last command writes:

- `runs/RUN_ID.json`, the canonical run artifact.
- `traces/RUN_ID.jsonl`, the complete charged-call trace.
- `certificates/CERTIFICATE_ID.json`, each minimized certificate.
- `reports/RUN_ID.html`, a standalone offline report.

Replay one certificate and rebuild the report:

```powershell
.\.venv\Scripts\atlas.exe replay certificates\CERTIFICATE_ID.json --config atlas.yaml
.\.venv\Scripts\atlas.exe report runs\RUN_ID.json --format html
```

Replace `RUN_ID` and `CERTIFICATE_ID` with the filenames printed by the test command. If no
certificate appears at budget 5, rerun with `--budget 25`. Do not add an API key for this demo.

Run the research evidence checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_research.py -q
.\.venv\Scripts\python.exe -m research.generate_seed_pack
```

Public deployment, pilot outreach, and competition submission require separate identity, logged-out
smoke-test, measured-results, and user-approval gates.
