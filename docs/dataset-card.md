# Dataset card: EdgeCase Atlas synthetic seed pack

## Summary

The alpha dataset is `research/data/synthetic_seed_pack.jsonl`, a deterministic pack of 100 newly
written structured-text road scenarios. It supports software validation, method development, pilot
campaigns, and later benchmark execution. It contains no copied private scenario, public-record
narrative, personal data, location trace, image, video, or vehicle telemetry.

## Schema and factors

Each line is one canonical `Scenario` with schema version `av-text-v1`. The taxonomy crosses road
type, signal, speed relation, speed limit, surface, visibility, and actor state. Actor variants cover
no actor, pedestrian states, relevant hazards, vehicles, and cyclists. Cross-field validity is
checked by the same Pydantic and Z3 contracts as product generation.

The fixed group split reserves 20 cases for development, 20 for pilot work, and 60 for confirmatory
campaigns. The final split manifest must prevent taxonomy-family near-duplicates from crossing
partitions. Pilot data never enter confirmatory outcomes.

## Provenance and license

- Source kind: synthetic.
- Authoring method: deterministic code in `research/generate_seed_pack.py`.
- Original scenario license: CC BY 4.0.
- Code license: Apache-2.0.
- Record count: 100.
- SHA-256: `f54ce18cc0fc592735ebba2cc5c2e7292496722a9468c1e05bfabcd6807ebe27`.

The pack can be regenerated locally and compared against the checksum. It uses project identifiers
only and contains no personal author attribution.

## Intended uses

- Test strict schema, validity, generation, transformation, oracle, and replay behavior.
- Develop and pilot the five matched benchmark methods.
- Freeze method-agnostic coverage and failure-signature definitions.
- Produce synthetic examples for documentation and the no-key demonstration.

## Prohibited and unsupported uses

The pack does not represent real traffic frequency, geographic diversity, crash severity, legal
requirements, demographic behavior, commercial fleets, public-road safety, or certification. It is
not suitable for training or controlling a physical vehicle.

## Known limitations

The factor grid is small, hand-specified, text-only, and benchmark-conditional. Descriptions are
templated. It lacks continuous trajectories, perception data, cultural context, road geometry,
weather dynamics, maps, and closed-loop consequences. Results on this pack do not establish
external validity.

## Future public-record import

Public government records remain future work. Any import must capture source version, download date,
checksum, schema, license, incident deduplication, exclusions, group split, independent abstraction
validation, and privacy review. Published cases must be independently rewritten and cannot include
manufacturer names, operator identifiers, raw narrative text, or causal claims.
