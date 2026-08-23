# EdgeCase Atlas threat model

## Scope

EdgeCase Atlas is simulated research and debugging software for structured-text decisions. It is
not a vehicle controller, safety monitor, certification system, or legal-compliance tool. The alpha
public application runs only curated synthetic scenarios and the included faulty fixture. It does
not accept subprocess commands, arbitrary endpoints, or executable code. It accepts one bounded
upload class, Atlas JSON run documents and JSONL traces, which are strictly validated and parsed as
inert data.

## Assets

- Integrity of scenarios, property definitions, model configuration, call ledgers, certificates,
  reports, and replay commands.
- Confidentiality of optional API keys and local model paths.
- Public anonymity of repository history, deployment metadata, generated artifacts, and pages.
- Availability of the free demonstration within bounded CPU, memory, request, and cost limits.
- Clear scientific separation between adaptive engineering evidence and held-out confirmation.

## Trust boundaries

1. Scenario text and model output are untrusted data.
2. Local Python functions and JSONL subprocesses are trusted by the local operator but are never
   enabled in the hosted application.
3. OpenAI-compatible endpoints are local-only or explicitly configured by a local operator. The
   hosted application does not expose arbitrary endpoint entry.
4. Environment variables, ignored files, and deployment secrets hold credentials. They never enter
   reports, traces, logs, exceptions, or Git.
5. Exported JSON, JSONL, and HTML cross from runtime state into portable evidence and require strict
   validation, canonical serialization, escaping, and compatibility checks.

## Threats and controls

| Threat | Control | Residual risk |
|---|---|---|
| Prompt injection in scenario text | Text is capped at 1,000 characters, treated only as scenario data, and never executed as instruction by Atlas. | A target model may still follow malicious text. Its output remains untrusted evidence. |
| Malformed or adversarial model output | Pydantic validates the strict `Decision` schema and rejects unknown labels or fields. | Semantically misleading but schema-valid explanations require oracle and human review. |
| Command injection | Subprocess uses an argument vector without a shell. Hosted subprocess and code execution are disabled. | Local operators remain responsible for commands they configure. |
| Server-side request forgery | Hosted arbitrary HTTP is disabled. Local endpoint configuration requires validated HTTPS or loopback rules. | A local operator can intentionally connect to a trusted private service. |
| Secret leakage | Keys come from named environment variables. Errors are sanitized. `.env`, Streamlit secrets, model files, and raw data are ignored. | External providers receive prompts when the operator enables them. |
| Cost exhaustion | Requests reserve a fail-closed application budget before transmission and record response usage. Missing usage retains reservation. | The local counter is not a provider-account spending limit. |
| Denial of service | Budgets, timeouts, output bounds, serial subprocess access, bounded stderr, and hosted rate limits constrain work. | Free hosting may still cold start or suspend. |
| HTML or spreadsheet injection | Reports use autoescaping, no external resources, and structured values. JSONL remains data. | Downstream tools must retain safe import settings. |
| Evidence tampering | Canonical content identifiers, property digests, model configuration hashes, replay compatibility checks, and exact canonical replay commands reject stable-field tampering. | Volatile latency and unavailable costs are observations, not authenticated semantic identity. |
| Scientific leakage from adaptive reuse | Search, shrink, and held-out seed streams are disjoint. Four of five is labeled an engineering heuristic. | Small held-out samples can still be uncertain and require exact intervals. |
| Uploaded evidence artifacts | Uploads are limited to `.json` and `.jsonl` Atlas artifacts of at most 2,000,000 bytes, checked against an allowlisted media type, rejected on duplicate keys, non-finite numbers, excess nesting, or oversized fields, and validated against the canonical run and trace schemas before any value is displayed. Content is parsed with a JSON reader only. It is never imported, executed, forwarded, or written to disk. | A malformed artifact still consumes bounded parse work inside the hosted request and rate limits. |
| Re-identification | No names, emails, raw IPs, location traces, or public-record narratives are collected. Uploaded artifacts are parsed in memory and never retained. Public artifacts receive identity scans. | A future public dataset import requires a separate privacy review. |
| Supply-chain compromise | Python 3.12 and bounded dependency ranges are declared. Release verification builds offline where possible. | Dependency integrity still depends on the installation source and lock process. |

## Privacy and analytics

If analytics are later enabled, they may store only a rotating pseudonymous session identifier,
event type, duration, property selected, and success status. Raw IP addresses, scenario text,
decisions, names, emails, and uploads are excluded. Pilot notes must avoid unnecessary identifiers.

## Physical-AI boundary

No OSMO, VDA, AnomalyGen, Kubernetes, GPU-pool, simulator, or physical-vehicle operation is present
in the alpha. Adding one changes the threat model and requires separate credentials, storage,
compute, data-license, image-safety, cluster, and incident-response reviews.
