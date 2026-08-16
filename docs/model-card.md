# Model card: EdgeCase Atlas target adapters

## Included alpha target

The repository includes a deliberately faulty deterministic demonstration agent. Its purpose is to
prove the full testing, minimization, replay, and export workflow without an API key. It calibrates
oracle sensitivity and is excluded from H1 through H5. Its known violations are not evidence that
Atlas improves real-agent testing.

## Supported local interfaces

- A Python function returning the strict `Decision` schema.
- A persistent JSONL subprocess receiving one `Scenario` per line and returning one `Decision`.
- An OpenAI-compatible endpoint configured by a local operator.

The hosted alpha enables only curated built-in targets. It disables user code, subprocess commands,
arbitrary HTTP endpoints, and uploads.

## Output contract

Normalized actions are `stop`, `prepare_stop`, `reduce_speed`, `increase_gap`, and `proceed`.
Normalized risks are `low`, `medium`, `high`, and `critical`. An explanation is required, and
confidence is optional. Schema validation does not establish that an explanation is faithful or
that a decision is safe.

## Reproducibility fields

Research artifacts must record target model ID, build or weight hash when available, adapter type,
prompt digest, decoding parameters, quantization settings, seed behavior, reset protocol, software
version, model configuration hash, latency, and cost availability. Secrets and absolute local model
paths are excluded. Local weights are referenced only through `LLAMA_MODEL_PATH` and are never
copied into the repository.

## Cost and privacy

OpenAI-compatible use is optional and bring-your-own-key. The application budget is a fail-closed
accounting guard, not a provider spending limit. Prompts and outputs may leave the machine only when
the local operator configures a remote provider. Provider terms, retention, pricing, and location
must be reviewed separately.

## Limitations

The interface observes categorical text decisions, not perception, actuation, planning trajectories,
or hidden state. Seeds may be ignored by some providers. Stateful targets require a reset mechanism
or a separate randomized-order study. Cross-model transfer is exploratory. Atlas never requests or
publishes hidden chain-of-thought.

## Results

Benchmark accuracy, failure discovery rate, transfer, cost, and latency are `TBD`. No public model
ranking or commercial-vehicle claim is authorized.
