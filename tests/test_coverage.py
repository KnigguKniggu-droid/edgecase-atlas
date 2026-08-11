from edgecase_atlas.coverage import CoverageTracker
from edgecase_atlas.fixtures import known_violation_cases


def test_coverage_tracks_method_agnostic_pair_observables() -> None:
    case = known_violation_cases()[1]
    tracker = CoverageTracker()
    snapshot = tracker.observe(
        case.property,
        case.counterfactual,
        case.source_decision,
        case.follow_up_decision,
        charged_target_calls=2,
    )

    assert "factor:road_type:urban" in snapshot.cells
    assert "applicability:hazard_non_aggression:applicable" in snapshot.cells
    assert "predicate:hazard_non_aggression:violated" in snapshot.cells
    assert "action_transition:reduce_speed->proceed" in snapshot.cells
    assert "risk_transition:high->low" in snapshot.cells
    assert tracker.trajectory[-1].charged_target_calls == 2
