"""Unit contracts for planning-facing piecewise assembly helpers."""

from __future__ import annotations

import pytest

from open_energy_lab.planning.piecewise import (
    DEFAULT_EXP_PIECEWISE_DOMAIN_FLOOR,
    PiecewiseCurveSpec,
    PiecewisePlanningTerms,
    SUPPORTED_FIRST_RELEASE_DECISION_TYPES,
    SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES,
    build_exponential_piecewise_curve,
    build_logarithm_piecewise_curve,
    build_piecewise_planning_terms,
    validate_first_release_decision_features,
)
from tests.integration.planning.fixture_utils import (
    TPM_ARTIFACT_FIXTURE_PATH,
    load_planning_fixture,
)


def test_build_piecewise_planning_terms_replays_committed_tpm_metadata() -> None:
    artifact_fixture = load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH)

    planning_terms = build_piecewise_planning_terms(
        artifact_fixture["approximation_metadata"],
        max_terms=2,
        decision_features=("battery_capacity_kwh", "solar_tracking_enabled"),
        decision_feature_types={
            "battery_capacity_kwh": "continuous",
            "solar_tracking_enabled": "binary",
        },
    )

    assert isinstance(planning_terms, PiecewisePlanningTerms)
    assert planning_terms.decision_features == (
        "battery_capacity_kwh",
        "solar_tracking_enabled",
    )
    assert planning_terms.decision_feature_types == {
        "battery_capacity_kwh": "continuous",
        "solar_tracking_enabled": "binary",
    }
    assert planning_terms.approximation_kind == "piecewise"
    assert planning_terms.leaf_encoding_mode == "histogram"
    assert planning_terms.sum_encoding_mode == "piecewise"
    assert planning_terms.breakpoint_policy["policy_name"] == "legacy-logspace-v1"
    assert planning_terms.mio_epsilon == pytest.approx(1e-6)
    assert planning_terms.fit_numeric_tolerance == pytest.approx(1e-9)
    assert planning_terms.query_numeric_tolerance == pytest.approx(1e-9)
    assert planning_terms.exp_breakpoints[-1] == pytest.approx(0.0)
    assert planning_terms.exp_values[-1] == pytest.approx(1.0)
    assert planning_terms.log_breakpoints[0] == pytest.approx(1.0)
    assert planning_terms.log_values[0] == pytest.approx(0.0)
    assert isinstance(planning_terms.exp_curve, PiecewiseCurveSpec)
    assert isinstance(planning_terms.log_curve, PiecewiseCurveSpec)
    assert planning_terms.max_terms == 2
    assert planning_terms.exp_curve.unbounded_domain_var is True
    assert planning_terms.exp_curve.x_points[:3] == pytest.approx(
        (
            DEFAULT_EXP_PIECEWISE_DOMAIN_FLOOR,
            planning_terms.exp_breakpoints[0],
            planning_terms.exp_breakpoints[0],
        )
    )
    assert planning_terms.exp_curve.y_points[:2] == pytest.approx((0.0, 0.0))
    assert planning_terms.exp_curve.y_points[2:] == pytest.approx(
        planning_terms.exp_values
    )
    assert planning_terms.log_curve.x_points == pytest.approx(
        planning_terms.log_breakpoints
    )
    assert planning_terms.log_curve.y_points == pytest.approx(planning_terms.log_values)


def test_build_piecewise_planning_terms_preserves_reproducibility_metadata() -> None:
    artifact_fixture = load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH)

    first = build_piecewise_planning_terms(
        artifact_fixture["approximation_metadata"],
        max_terms=3,
    )
    second = build_piecewise_planning_terms(
        artifact_fixture["approximation_metadata"],
        max_terms=3,
    )

    assert first == second
    assert first.legacy_reference_paths == (
        "legacy/old_tpm/src_py/tpm/spn/main.py",
        "legacy/old_tpm/src_py/tpm/spn/encoding.py",
        "legacy/old_tpm/src_py/tpm/spn/utils_tangent.py",
        "legacy/old_tpm/src_py/utils/densities.py",
    )


def test_build_piecewise_planning_terms_rejects_invalid_max_terms() -> None:
    artifact_fixture = load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH)

    with pytest.raises(ValueError, match="max_terms"):
        build_piecewise_planning_terms(
            artifact_fixture["approximation_metadata"],
            max_terms=0,
        )


def test_validate_first_release_decision_features_accepts_documented_scope_and_types() -> None:
    decision_features, decision_feature_types = validate_first_release_decision_features(
        ["battery_capacity_kwh", "solar_tariff_plan"],
        decision_feature_types={
            "battery_capacity_kwh": "continuous",
            "solar_tariff_plan": "categorical",
        },
    )

    assert SUPPORTED_FIRST_RELEASE_DECISION_TYPES == ("battery", "solar")
    assert SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES == (
        "continuous",
        "binary",
        "categorical",
        "mixed",
    )
    assert decision_features == ("battery_capacity_kwh", "solar_tariff_plan")
    assert decision_feature_types == {
        "battery_capacity_kwh": "continuous",
        "solar_tariff_plan": "categorical",
    }


def test_validate_first_release_decision_features_rejects_out_of_scope_feature_names() -> None:
    with pytest.raises(ValueError, match="first-release planning scope|battery/solar"):
        validate_first_release_decision_features(("inverter_capacity_kw",))


def test_build_piecewise_planning_terms_rejects_unsupported_decision_variable_types() -> None:
    artifact_fixture = load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH)

    with pytest.raises(ValueError, match="unsupported decision_variable_type|'ordinal'"):
        build_piecewise_planning_terms(
            artifact_fixture["approximation_metadata"],
            max_terms=2,
            decision_features=("battery_capacity_kwh",),
            decision_feature_types={"battery_capacity_kwh": "ordinal"},
        )


def test_piecewise_curve_builders_replay_canonical_solver_ready_specs() -> None:
    artifact_fixture = load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH)

    exp_curve = build_exponential_piecewise_curve(
        artifact_fixture["approximation_metadata"]
    )
    log_curve = build_logarithm_piecewise_curve(
        artifact_fixture["approximation_metadata"],
        max_terms=3,
    )

    assert exp_curve.domain_lower_bound == pytest.approx(-500.0)
    assert exp_curve.domain_upper_bound == pytest.approx(0.0)
    assert exp_curve.x_points[1] == pytest.approx(exp_curve.x_points[2])
    assert exp_curve.y_points[0] == pytest.approx(0.0)
    assert log_curve.domain_lower_bound == pytest.approx(1.0)
    assert log_curve.domain_upper_bound == pytest.approx(3.0)
    assert log_curve.unbounded_domain_var is False


def test_build_exponential_piecewise_curve_rejects_domain_floor_inside_grid() -> None:
    artifact_fixture = load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH)

    with pytest.raises(ValueError, match="domain_floor"):
        build_exponential_piecewise_curve(
            artifact_fixture["approximation_metadata"],
            domain_floor=-1.0,
        )
