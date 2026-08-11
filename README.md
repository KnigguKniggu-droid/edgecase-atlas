# EdgeCase Atlas

EdgeCase Atlas is an open-source developer tool for property-based red-team testing of AI driving-decision agents. It generates constraint-preserving counterfactuals, reruns stochastic failures, and shrinks each reproducible violation into a small causal certificate.

The alpha targets structured text scenarios and simulated decision agents. It is not a vehicle controller, certification system, or statement of real-world safety.

## Planned alpha workflow

1. Connect the included demonstration agent, a Python function, a JSONL subprocess, or an OpenAI-compatible model.
2. Select editable operational-design-domain safety properties.
3. Generate valid source and follow-up scenarios under a fixed budget.
4. Require a failure to reproduce in at least four of five trials.
5. Minimize the scenario while preserving validity and reproduction.
6. Export JSON, JSONL, and standalone HTML evidence.

## Development

EdgeCase Atlas requires Python 3.12.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

The CLI surface is `atlas init`, `atlas validate`, `atlas test`, `atlas replay`, and `atlas report`.

## License

Code is licensed under Apache-2.0. Original synthetic scenarios and annotations are licensed under CC BY 4.0 as described in `DATA_LICENSE.md`.

