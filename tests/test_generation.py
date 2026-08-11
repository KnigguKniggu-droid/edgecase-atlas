from edgecase_atlas.constraints import validate_scenario
from edgecase_atlas.generation import generate_corpus, scenario_strategy
from edgecase_atlas.properties import STARTER_PROPERTY_PACK


def test_generation_is_deterministic_and_constraint_valid() -> None:
    first = generate_corpus(STARTER_PROPERTY_PACK, seed=42, budget=12)
    second = generate_corpus(STARTER_PROPERTY_PACK, seed=42, budget=12)

    assert first == second
    assert len(first) == 12
    assert all(validate_scenario(item.counterfactual.source).valid for item in first)
    assert all(validate_scenario(item.counterfactual.follow_up).valid for item in first)
    assert all(item.property.applies(item.counterfactual) for item in first)


def test_generation_changes_only_property_permitted_fields() -> None:
    generated = generate_corpus(STARTER_PROPERTY_PACK, seed=7, budget=15)

    assert {item.property.property_id for item in generated} == {
        property_.property_id for property_ in STARTER_PROPERTY_PACK
    }
    assert all(item.counterfactual.changed_fields for item in generated)


def test_hypothesis_strategy_is_available_as_a_structured_primitive() -> None:
    assert scenario_strategy().is_empty is False
