from __future__ import annotations

import pytest

from edgecase_atlas.fixtures import known_violation_cases
from edgecase_atlas.normalization import normalize_action, normalize_risk
from edgecase_atlas.properties import STARTER_PROPERTY_PACK, evaluate_property


def test_normalization_is_deterministic_and_rejects_unknown_labels() -> None:
    assert normalize_action(" Prepare-Stop ") == "prepare_stop"
    assert normalize_action("BRAKE") == "stop"
    assert normalize_risk("MEDIUM") == "medium"
    with pytest.raises(ValueError, match="Unknown action"):
        normalize_action("swerve")
    with pytest.raises(ValueError, match="Unknown risk"):
        normalize_risk("urgent")


def test_starter_pack_has_five_unique_editable_operational_properties() -> None:
    assert len(STARTER_PROPERTY_PACK) == 5
    assert len({property_.property_id for property_ in STARTER_PROPERTY_PACK}) == 5
    assert all("operational" in property_.scope_note.lower() for property_ in STARTER_PROPERTY_PACK)


@pytest.mark.parametrize("case", known_violation_cases(), ids=lambda case: case.property_id)
def test_faulty_fixture_has_one_known_violation_per_property(case: object) -> None:
    result = evaluate_property(
        case.property, case.counterfactual, case.source_decision, case.follow_up_decision
    )
    assert result.applicable
    assert result.violated
    assert result.property_id == case.property_id


def test_hazard_property_preserves_non_target_fields() -> None:
    case = next(
        case for case in known_violation_cases() if case.property_id == "hazard_non_aggression"
    )
    source = case.counterfactual.source.model_dump(exclude={"actors", "scenario_id", "description"})
    follow_up = case.counterfactual.follow_up.model_dump(
        exclude={"actors", "scenario_id", "description"}
    )
    assert source == follow_up
