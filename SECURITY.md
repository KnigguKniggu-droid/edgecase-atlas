# Security policy

## Supported release

EdgeCase Atlas 0.1.x receives security fixes during the alpha. This software is for simulated research and debugging. It must never control a vehicle or be treated as certification evidence.

## Reporting a vulnerability

Use the repository's private security-advisory channel after the public repository launches. Do not include secrets, personal data, private research, or exploit details in a public issue. A public issue may state only that a private report is waiting.

## Trust boundaries

The public Streamlit application accepts only curated synthetic examples and the included faulty fixture. It does not expose subprocess execution, arbitrary HTTP targets, uploads, arbitrary model identifiers, or user code execution.

Local CLI adapters can execute user-configured Python functions or subprocesses. Run them only when their code and command are trusted. OpenAI-compatible access stays disabled until the user supplies an explicit configuration and environment-based secret.

Atlas validates model output against strict schemas, caps configured API cost at 25 USD, escapes report content, and treats safety properties as editable assumptions. These controls do not prove real-world safety.

## Secret and privacy handling

Keep keys in ignored environment or deployment-secret settings. Never commit `.env`, Streamlit secrets, model weights, generated runs, private-pattern files, personal identifiers, affiliations, location traces, or unrelated research material. Run `python scripts/identity_scan.py` before every public release.
