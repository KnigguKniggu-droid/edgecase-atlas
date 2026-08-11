from __future__ import annotations

import pytest

from edgecase_atlas.fixtures import known_violation_cases
from edgecase_atlas.models import (
    Counterfactual,
    Decision,
    Provenance,
    Scenario,
    canonical_scenario_diffs,
)
from edgecase_atlas.properties import STARTER_PROPERTY_PACK, evaluate_property


def _decision(action: str, risk: str) -> Decision:
    return Decision(action=action, risk=risk, explanation="Synthetic property semantics test.")  # type: ignore[arg-type]


def _non_applicable_relation() -> Counterfactual:
    source = Scenario(
        scenario_id="non-applicable-source",
        seed=2,
        road_type="urban",
        speed_mph=20.0,
        speed_limit_mph=35.0,
        signal="none",
        surface="dry",
        visibility="clear",
        description="Synthetic non-applicable relation.",
        provenance=Provenance(
            source_kind="synthetic",
            source_reference="edgecase-atlas-property-semantics",
            license="CC BY 4.0",
        ),
    )
    follow_up = source.model_copy(update={"scenario_id": "non-applicable-follow-up"})
    return Counterfactual(
        source=source,
        follow_up=follow_up,
        changed_fields=canonical_scenario_diffs(source, follow_up),
        relation_id="unrelated_identity_change",
    )


@pytest.mark.parametrize("case", known_violation_cases(), ids=lambda item: item.property_id)
def test_each_property_has_a_passing_applicable_pair(case: object) -> None:
    safe_source = _decision("reduce_speed", "high")
    safe_follow_up = _decision("reduce_speed", "high")
    result = evaluate_property(case.property, case.counterfactual, safe_source, safe_follow_up)
    assert result.applicable
    assert not result.violated
    assert result.reason == "Operational assumption satisfied"


@pytest.mark.parametrize("property_", STARTER_PROPERTY_PACK, ids=lambda item: item.property_id)
def test_each_property_has_a_non_applicable_pair(property_: object) -> None:
    result = evaluate_property(
        property_,
        _non_applicable_relation(),
        _decision("proceed", "low"),
        _decision("proceed", "low"),
    )
    assert not result.applicable
    assert not result.violated
    assert result.reason == "Not applicable"
