from __future__ import annotations

import pytest

from open_energy_lab.planning.study_validation import (
    SPNCandidateScore,
    assess_calibration,
    assess_recommendation,
    brier_score_by_configuration,
    select_spn_candidate,
)


def _held_out_rows() -> tuple[dict[str, object], ...]:
    return (
        {"configuration_id": "b1__s1", "event": 0},
        {"configuration_id": "b1__s1", "event": 0},
        {"configuration_id": "b1__s2", "event": 1},
        {"configuration_id": "b1__s2", "event": 0},
    )


def test_candidate_selection_uses_validation_brier_then_node_count() -> None:
    rows = _held_out_rows()
    probabilities = {"b1__s1": 0.1, "b1__s2": 0.4}
    brier = brier_score_by_configuration(
        rows,
        probabilities=probabilities,
        event_target_name="event",
    )
    candidates = (
        SPNCandidateScore("uncompiled", brier - 0.01, 2, False, "unsupported"),
        SPNCandidateScore("larger", brier, 12, True),
        SPNCandidateScore("smaller", brier, 8, True),
    )

    assert select_spn_candidate(candidates).candidate_name == "smaller"


def test_calibration_checks_errors_labels_and_selected_interval() -> None:
    assessment = assess_calibration(
        _held_out_rows(),
        probabilities={"b1__s1": 0.0, "b1__s2": 0.5},
        event_target_name="event",
        selected_configuration_id="b1__s1",
        mean_error_limit=0.05,
        max_error_limit=0.10,
    )

    assert assessment.both_labels_observed
    assert assessment.selected_probability_in_confidence_interval
    assert assessment.passed


def test_recommendation_is_blocked_by_held_out_upper_risk_bound() -> None:
    calibration = assess_calibration(
        _held_out_rows(),
        probabilities={"b1__s1": 0.0, "b1__s2": 0.5},
        event_target_name="event",
        selected_configuration_id="b1__s1",
    )
    result = assess_recommendation(
        calibration=calibration,
        solve_status="optimal",
        native_mio_discrepancy=0.0,
        chance_limit=0.05,
    )

    assert result.status == "exploratory"
    assert result.one_sided_upper_risk_bound > 0.05
    assert any("held-out" in reason for reason in result.blocking_reasons)


def test_candidate_selection_fails_when_none_compile() -> None:
    with pytest.raises(ValueError, match="no SPN candidate compiled"):
        select_spn_candidate((SPNCandidateScore("bad", 0.1, 1, False, "bad graph"),))

