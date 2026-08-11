from __future__ import annotations

import pytest
from pydantic import ValidationError

from edgecase_atlas.fixtures import known_violation_cases
from edgecase_atlas.models import (
    Actor,
    Counterfactual,
    Decision,
    FailureCertificate,
    canonical_scenario_diffs,
)


def _decision() -> Decision:
    return Decision(action="reduce_speed", risk="high", explanation="Synthetic re-review decision.")


def _with_follow_up_change(case: object, **changes: object) -> Counterfactual:
    follow_up = case.counterfactual.follow_up.model_copy(update=changes)
    return Counterfactual(
        source=case.counterfactual.source,
        follow_up=follow_up,
        changed_fields=canonical_scenario_diffs(case.counterfactual.source, follow_up),
        relation_id=case.counterfactual.relation_id,
    )


@pytest.mark.parametrize("case", known_violation_cases(), ids=lambda item: item.property_id)
def test_each_starter_property_rejects_an_unchanged_non_target_factor(case: object) -> None:
    contaminated = _with_follow_up_change(case, surface="wet")
    assert not case.property.applies(contaminated)


@pytest.mark.parametrize("case", known_violation_cases(), ids=lambda item: item.property_id)
def test_each_starter_property_enforces_its_declared_relation_id(case: object) -> None:
    wrong_relation = Counterfactual(
        source=case.counterfactual.source,
        follow_up=case.counterfactual.follow_up,
        changed_fields=case.counterfactual.changed_fields,
        relation_id="unrelated_relation",
    )
    assert not case.property.applies(wrong_relation)


def certificate_for(case: object, **changes: object) -> FailureCertificate:
    values: dict[str, object] = {
        "certificate_id": "rereview-certificate",
        "relation_id": case.counterfactual.relation_id,
        "property_id": case.property_id,
        "source": case.counterfactual.source,
        "minimized_follow_up": case.counterfactual.follow_up,
        "changed_fields": case.counterfactual.changed_fields,
        "source_decisions": (_decision(),) * 5,
        "follow_up_decisions": (_decision(),) * 5,
        "reproduction_count": 4,
        "reproduction_trials": 5,
        "model_id": "fixture",
        "model_config_hash": "a" * 64,
        "software_version": "0.1.0",
        "seed": 5,
        "latency_ms": 1,
        "estimated_cost_usd": 0.0,
        "replay_command": "atlas replay synthetic.json",
    }
    values.update(changes)
    return FailureCertificate(**values)


def test_certificate_requires_exact_retained_differences_and_starter_relation() -> None:
    case = known_violation_cases()[1]
    with pytest.raises(ValidationError, match="changed_fields"):
        certificate_for(case, changed_fields=())
    with pytest.raises(ValidationError, match="relation_id"):
        certificate_for(case, relation_id="wrong_relation")


def test_custom_property_certificates_can_use_custom_relation_ids() -> None:
    case = known_violation_cases()[0]
    certificate = certificate_for(
        case, property_id="custom_property", relation_id="custom_relation"
    )
    assert certificate.relation_id == "custom_relation"


def test_event_metadata_rejects_phone_numbers_under_allowed_keys() -> None:
    with pytest.raises(ValidationError, match="non-identifying"):
        Actor(
            actor_id="hazard-1",
            actor_type="hazard",
            distance_m=1.0,
            event_metadata=(("source", "555-0100"),),
        )
