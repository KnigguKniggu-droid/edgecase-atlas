# EdgeCase Atlas launch package

This directory contains the public-launch and Builder Competition materials. No file authorizes
deployment, outreach, or submission. Replace placeholders only from verified public analytics,
test artifacts, or consented product-feedback records.

## Required order

1. Complete `launch-checklist.md` through the public smoke-test gate.
2. Record evidence in a private copy of `metrics.example.json`.
3. Validate that copy against `metrics.schema.json`.
4. Run `python docs/launch/generate_story.py METRICS.json STORY.md`.
5. Record and audit the video using the storyboard and shot list.
6. Complete `submission-fields.md` and obtain final approval before submission.

The example metrics deliberately contain `null`. The generator refuses unresolved or inconsistent
metrics, so placeholders cannot silently become claimed results.
