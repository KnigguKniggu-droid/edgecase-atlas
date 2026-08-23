# Competition story generation

Do not manually replace placeholders. Copy `metrics.example.json` outside the repository, fill it
with traceable evidence, validate it against `metrics.schema.json`, and run:

```text
python docs/launch/generate_story.py METRICS.json STORY.md
```

The deterministic generator rejects unresolved, negative, extra, and internally inconsistent
fields. It emits the final story under the 150-word limit.

## Story

AI driving-decision agents can sound plausible while violating editable safety assumptions. I built
EdgeCase Atlas, a developer tool that creates valid paired counterfactuals, repeats stochastic
checks, minimizes failures, and exports replayable certificates. The hardest engineering problem
was preserving scenario validity and complete call accounting while reducing flaky failures without
overstating the evidence. I designed the typed schema, five-property pack, deterministic engine,
adapters, CLI, no-key web demo, and offline reports. By the evidence cutoff, Atlas completed TBD
test runs for TBD distinct users; TBD independently ran the CLI, and TBD of TBD pilot respondents
said the minimized pair improved debugging clarity. Next, I will compare five matched search
methods and confirm retained failures on fresh simulator seeds.
