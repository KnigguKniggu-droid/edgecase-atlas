# Synthetic seed taxonomy

## What this describes

This is the scenario space the tool actually covers, read off the code rather than off the design
intent. Three distinct spaces exist and are easy to confuse:

1. **The schema space.** Everything `models.Scenario` will accept.
2. **The seed-pack space.** The 100 fixed records in `research/data/synthetic_seed_pack.jsonl`,
   produced by `research/generate_seed_pack.py`.
3. **The engine-generated space.** What `generation.generate_corpus` produces during a run.

The third is much smaller than the first. Any external-validity statement must name which space it
refers to.

## 1. Schema space

Source: `src/edgecase_atlas/models.py`, constrained by `src/edgecase_atlas/constraints.py`.

### Scenario-level dimensions

| Dimension | Type | Values or range | Notes |
|---|---|---|---|
| `schema_version` | literal | `av-text-v1` | Single frozen version. |
| `road_type` | categorical, 4 | `residential`, `urban`, `highway`, `intersection` | |
| `signal` | categorical, 4 | `red`, `yellow`, `green`, `none` | Z3 predicate `signal.road_incompatible` requires `intersection` or `urban` whenever the signal is not `none`. |
| `surface` | categorical, 3 | `dry`, `wet`, `icy` | No interaction with speed is enforced. |
| `visibility` | categorical, 3 | `clear`, `reduced`, `occluded` | No interaction with actor distance is enforced. |
| `speed_mph` | continuous | `0` to `250`, finite | |
| `speed_limit_mph` | continuous | greater than `0` to `150`, finite | |
| `speed_mph` vs `speed_limit_mph` | derived | unconstrained | Overspeed is deliberately legal, because it is the input to `overspeed_risk_monotonicity`. |
| `actors` | sequence | 0 to 64, unique `actor_id` | |
| `description` | text | 1 to 1000 characters | The only free-text field a relation may target. |
| `provenance.source_kind` | categorical, 3 | `synthetic`, `public_record`, `curated_sample` | Only `synthetic` is produced in the alpha. |
| `seed` | integer | `0` to `2**63 - 1` | Recorded per scenario, distinct from the run seed. |

The categorical cross-product of the four discrete scene factors is 4 road types times 4 signals
times 3 surfaces times 3 visibilities, minus the combinations the signal-road predicate forbids.
`residential` and `highway` admit only `signal = none`, so the reachable count is
`(2 road types * 4 signals + 2 road types * 1 signal) * 3 * 3 = 90` scene-factor cells before any
actor or speed dimension is considered.

### Actor-level dimensions

| Dimension | Type | Values or range | Notes |
|---|---|---|---|
| `actor_type` | categorical, 4 | `pedestrian`, `vehicle`, `cyclist`, `hazard` | |
| `relevance` | categorical, 2 | `relevant`, `background` | Defaults to `relevant`. Only `background` actors are removable by the minimizer. |
| `pedestrian_state` | categorical, 4 plus null | `standing`, `crossing`, `on_sidewalk`, `running_toward_road`, or unset | A model validator and the Z3 predicate `actor.pedestrian_state_incompatible` both require `actor_type == pedestrian` when set. |
| `lane_relation` | categorical, 6 | `ego_lane`, `adjacent_lane`, `oncoming_lane`, `sidewalk`, `off_road`, `unknown` | Defaults to `unknown`. Not cross-checked against `pedestrian_state`. |
| `distance_m` | continuous | `0` to `10000`, finite | |
| `event_metadata` | key-value pairs | up to 16, unique keys drawn from `movement`, `intent`, `state`, `severity`, `signal_phase`, `source` | Values up to 240 characters, screened for personal-data markers. |

### Decision space, which the coverage universe also indexes

Source: `models.Decision`.

- `action`, 5 values: `stop`, `prepare_stop`, `reduce_speed`, `increase_gap`, `proceed`.
- `risk`, 4 ordered levels: `low`, `medium`, `high`, `critical`.
- `explanation`, required, 1 to 2000 characters.
- `confidence`, optional, `0` to `1`.

This yields 25 possible action transitions and 16 possible risk transitions per pair, which are the
`action_transition:*` and `risk_transition:*` coverage cells in `coverage.py`.

### Aggression partial order

Source: `properties.ACTION_AGGRESSION_TRANSITIONS`. A transition counts as a relaxation only when
it moves toward `proceed`:

- from `stop` to any of `prepare_stop`, `reduce_speed`, `increase_gap`, `proceed`
- from `prepare_stop` to any of `reduce_speed`, `increase_gap`, `proceed`
- from `reduce_speed` to `proceed`
- from `increase_gap` to `proceed`
- from `proceed` to nothing

`reduce_speed` and `increase_gap` are deliberately incomparable. A test result that depends on
ordering those two is out of scope for this property pack.

## 2. Relation space

Source: `generation.transform_for_property`. Exactly five relations exist, one per starter property.

| Relation id | Property | Fields the relation may change | Kind |
|---|---|---|---|
| `red_signal` | `red_signal_no_proceed` | `signal` only. The source is forced to `road_type = intersection`, `signal = green`, no actors. | Sensitivity: `proceed` is forbidden on the red side. |
| `add_relevant_hazard` | `hazard_non_aggression` | Adds exactly one new `hazard` actor with `relevance = relevant`, `lane_relation = ego_lane`, distance 2 to 25 m, `event_metadata = (severity, relevant)`. Source has no actors. | Sensitivity: the action must not relax. |
| `increase_speed` | `overspeed_risk_monotonicity` | `speed_mph` only, raised above a limit drawn from 25, 30, 35, 45, 55 by 1 to 20 mph. | Sensitivity: risk must not fall. |
| `pedestrian_crossing` | `crossing_pedestrian_caution` | One pedestrian's `pedestrian_state` from `on_sidewalk` to `crossing`, and its `lane_relation` from `sidewalk` to `ego_lane`. | Sensitivity: neither the action may relax nor the risk fall. |
| `semantic_paraphrase` | `paraphrase_invariance` | `description` only, one noun substituted. | Invariance: normalized action and risk must both be preserved. |

Every relation additionally permits changes to the paths in `properties.NON_CAUSAL_PATHS`, which
are `scenario_id` and `description`. The paired follow-up always takes a `-paired` suffix on its
identifier, so `scenario_id` is a retained difference in every pair and is never a causal factor.

## 3. Coverage universe

Source: `coverage.CoverageTracker.observe`. Six cell families, all observable from outside the
target:

| Family | Cardinality | Derivation |
|---|---|---|
| `factor:road_type:*` | 4 | Emitted for both sides of every pair. |
| `factor:signal:*` | 4 | |
| `factor:surface:*` | 3 | |
| `factor:visibility:*` | 3 | |
| `factor:speed_band:*` | 4 | `over_limit` when speed exceeds the limit, otherwise `slow` below 25 mph, `moderate` from 25 to 45 mph inclusive, `fast` above 45 mph. The over-limit test is applied first, so a 60 mph reading under a 65 mph limit is `fast`, not `over_limit`. |
| `relation:*` | 5 | One per relation id. |
| `applicability:<property>:*` | 10 | 5 properties times `applicable` or `not_applicable`. |
| `predicate:<property>:*` | 15 | 5 properties times `violated`, `satisfied`, or `not_evaluated`. |
| `action_transition:A->B` | 25 | Observed source and follow-up actions. |
| `risk_transition:R->R` | 16 | Observed source and follow-up risks. |

The trajectory is recorded against `charged_target_calls`, and `extend_constant_to` appends
flat points for minimization calls that produce no new cells, so the cost axis is not silently
discounted.

## 4. Seed-pack space

Source: `research/generate_seed_pack.py`, 100 records indexed `0` to `99`.

| Dimension | Rule | Realized values |
|---|---|---|
| `road_type` | `index % 4` | All 4, 25 records each. |
| `surface` | `(index // 4) % 3` | All 3. |
| `visibility` | `(index // 12) % 3` | All 3. |
| `speed_limit_mph` | `index % 7` over `(20, 25, 30, 35, 45, 55, 65)` | All 7. |
| `signal` | `(index // 4) % 4` over `(red, yellow, green, none)`, and only for `urban` and `intersection` | All 4 on signalled roads; `none` on `residential` and `highway`. |
| `speed_mph` | `max(5.0, limit + ((index % 5) - 2) * 5.0)` | Limit offsets of `-10`, `-5`, `0`, `+5`, `+10` mph, floored at 5 mph. Both under-limit and over-limit cases occur. |
| Actor variant | `index % 5` | `0` no actor, `1` pedestrian, `2` hazard, `3` vehicle, `4` cyclist. 20 records each. |
| `pedestrian_state` | `(index // 5) % 4` on pedestrian records | All 4 states. `lane_relation` is `sidewalk` for `on_sidewalk`, otherwise `ego_lane`. |
| `distance_m` | `3 + index % 18` for pedestrians, `5 + index % 40` for others | Discrete metres. |
| `lane_relation` for non-pedestrians | `adjacent_lane` for cyclists, `ego_lane` for hazards and vehicles | |
| Stratum label | `taxonomy-stratum-{index % 20}` in `provenance.transformation_history` | 20 strata, 5 records each. This is the handle for the group-level partition split. |

### What the seed pack does not contain

- No record has more than one actor. Multi-actor interaction is unrepresented.
- No record has `relevance = background`. Every actor is `relevant`.
- No record has non-empty `event_metadata`.
- No record uses `oncoming_lane`, `off_road`, or `unknown` for `lane_relation`.
- Descriptions are one templated sentence keyed to road type, surface, and visibility. There is no
  lexical or syntactic variety for paraphrase work.
- `provenance.source_kind` is always `synthetic`.

## 5. Engine-generated space

Source: `generation._base_scenario` and `generation.scenario_from_primitive`. This is what a run
actually evaluates, and it is narrower than the seed pack.

| Dimension | Realized values in `generate_corpus` |
|---|---|
| `road_type` | All 4, uniformly sampled from the run's seeded `Random`. |
| `signal` before transformation | `none` on `residential` and `highway`; one of `none`, `yellow`, `green` on `urban` and `intersection`. **`red` is never a base value.** It is only ever introduced by the `red_signal` relation, which also forces `road_type = intersection`. |
| `surface`, `visibility` | All values, uniformly sampled. |
| `speed_mph` before transformation | Integer 5 to 45 mph. |
| `speed_limit_mph` | One of 25, 30, 35, 45, 55. |
| `actors` before transformation | Always empty. `scenario_from_primitive` sets `actors=()`. |
| `actors` after transformation | At most one, and only for `add_relevant_hazard` and `pedestrian_crossing`. |
| `description` | One of three fixed strings, depending on the relation. |
| `provenance` | Fixed: `synthetic`, `edgecase-atlas-generated-v1`, CC BY 4.0. |

### Consequences that bound what a run can demonstrate

These follow directly from the table above and belong in any limitations section.

- **The `remove_background_actor` reducer is unreachable.** Nothing in generation produces an actor
  with `relevance = background`, and `minimizer._is_background` requires it. One of the five
  advertised reducer operations therefore never fires on engine-generated cases. Recorded as R-026
  in `evidence-ledger.md`.
- **`remove_optional_event_metadata` fires only on the hazard relation**, which is the sole source
  of `event_metadata`.
- **`reduce_numeric_delta` fires only on the `increase_speed` relation**, since it targets
  `speed_mph` above the source limit.
- **`simplify_actor_distance` fires only on the two relations that create an actor.**
- **`shorten_description` fires on every relation**, because both scenarios always carry a longer
  description than the reducer's target text.
- **Coverage cells for `oncoming_lane`, `off_road`, multi-actor scenes, `background` relevance, and
  `public_record` provenance are unreachable from a run**, so a coverage figure computed over the
  full schema space would be misleading. The coverage universe in `coverage.py` deliberately does
  not index those dimensions.

## 6. Dimensions the tool does not model at all

Named here so no reader infers them from the word "driving":

Trajectories, velocities of other actors, headings, accelerations, road geometry, lane widths,
curvature, gradients, intersections beyond a categorical label, traffic density, right-of-way,
signage other than the signal colour, time of day, weather dynamics over time, perception inputs,
sensor noise, occlusion geometry, actuation, latency of the vehicle platform, maps, localization,
and any closed-loop consequence of the decision. The tool observes one categorical decision about
one static, textually described moment.

## 7. Extending the taxonomy

A new dimension is not added by editing this file. The order is:

1. Add the field to `models.py` with an explicit type and bound.
2. Add or extend a predicate in `constraints.py` if the field can contradict another field.
3. Decide whether it belongs in the coverage universe in `coverage.py`. If it is not observable
   from outside the target, it does not.
4. Add a relation in `generation.transform_for_property` only if a property depends on it.
5. Add a reducer in `minimizer.py` only if the field can be simplified without breaking validity.
6. Update this file, and update the checksum row in `reproducibility-manifest.yaml` if the seed pack
   changes.

Skipping step 2 is the failure mode that produces unfalsifiable scenarios.
