"""Unit contracts for planning-facing piecewise assembly helpers."""

from __future__ import annotations

import copy

import pytest

from open_energy_lab.planning.piecewise import (
    DEFAULT_EXP_PIECEWISE_DOMAIN_FLOOR,
    PlanningMIOCompatibilityError,
    PiecewiseCurveSpec,
    PiecewisePlanningTerms,
    SUPPORTED_FIRST_RELEASE_DECISION_TYPES,
    SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES,
    build_current_spflow_planning_payload,
    build_exponential_piecewise_curve,
    build_logarithm_piecewise_curve,
    build_piecewise_planning_terms,
    validate_first_release_decision_features,
    validate_current_spflow_mio_payload,
)
from open_energy_lab.tpm.domains import TPMApproximationDomain, TPMNormalizationSpec
from tests.integration.planning.fixture_utils import (
    TPM_ARTIFACT_FIXTURE_PATH,
    load_planning_fixture,
)


def _compiled_mio_payload() -> dict[str, object]:
    return {
        "schema_version": "v1",
        "payload_format": "open-energy-lab-spflow-mio",
        "compiler_version": "spflow-v1-mio-v1",
        "backend_compiler_version": "spflow-v1-mio-v1",
        "backend_generation": "current-spflow",
        "backend_api_version": "1.1.0",
        "approximation_kind": "piecewise",
        "leaf_encoding_mode": "piecewise-log-density",
        "sum_encoding_mode": "weighted-logsumexp",
        "output_channels": 1,
        "num_repetitions": 1,
        "breakpoint_policy": {"breakpoint_count": 5},
        "mio_epsilon": 1e-6,
        "feature_schema": [
            {
                "feature_name": "battery_capacity_kwh",
                "feature_type": "continuous",
                "feature_role": "decision",
                "modifiable": True,
                "bounds": [2.0, 12.0],
            },
            {
                "feature_name": "shortfall_event",
                "feature_type": "binary",
                "feature_role": "target",
                "modifiable": False,
                "discrete_values": [0.0, 1.0],
                "ordering": [0.0, 1.0],
            },
        ],
        "root_id": 0,
        "nodes": [
            {
                "id": 0,
                "type": "bernoulli",
                "feature_names": ["shortfall_event"],
                "probabilities": [[0.75, 0.25]],
            }
        ],
    }


def _compiled_mio_v2_payload() -> dict[str, object]:
    normalization = TPMNormalizationSpec(
        feature_name="battery_capacity_kwh",
        feature_kind="continuous",
        kind="min-max",
        origin="caller-declared",
        lower=0.0,
        upper=20.0,
    )
    validity = TPMApproximationDomain(
        feature_name="battery_capacity_kwh",
        lower=2.0,
        upper=12.0,
        source="planning-unit",
    ).derive_validity(
        feature_index=0,
        normalization=normalization,
        relative_breakpoints=(0.0, 0.5, 1.0),
        compiler_version="spflow-v1-mio-v2",
        payload_schema_version="v2",
    )
    payload = _compiled_mio_payload()
    payload.update(
        {
            "schema_version": "v2",
            "compiler_version": "spflow-v1-mio-v2",
            "backend_compiler_version": "spflow-v1-mio-v2",
            "feature_schema": [
                {
                    "feature_name": "battery_capacity_kwh",
                    "feature_type": "continuous",
                    "feature_role": "decision",
                    "modifiable": True,
                }
            ],
            "compiled_validity": [validity.to_dict()],
            "nodes": [
                {
                    "id": 0,
                    "type": "normal",
                    "scope": [0],
                    "curves": [
                        {
                            "scope": 0,
                            "feature_name": "battery_capacity_kwh",
                            "breakpoints": list(validity.model_breakpoints),
                            "model_breakpoints": list(validity.model_breakpoints),
                            "physical_breakpoints": list(
                                validity.physical_breakpoints
                            ),
                            "log_values": [-1.0, -0.5, -1.0],
                        }
                    ],
                }
            ],
        }
    )
    return payload


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
    assert planning_terms.breakpoint_policy["policy_name"] == (
        "canonical-five-breakpoint-v1"
    )
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


def test_current_spflow_mio_payload_builds_conditional_planning_models() -> None:
    compiled = _compiled_mio_payload()

    planning_payload = build_current_spflow_planning_payload(
        compiled,
        approximation_metadata={
            "compiler_version": "spflow-v1-mio-v1",
            "mio_epsilon": 1e-6,
        },
        decision_features=("battery_capacity_kwh",),
        event_target_name="shortfall_event",
        chance_limit_epsilon=0.3,
        shortfall_threshold=0.08,
        payload_locator="sidecars/model.pkl",
    )

    assert planning_payload["source"] == "current-spflow-mio-compiler"
    assert planning_payload["compiled_mio"] == compiled
    conditional = planning_payload["conditional_models"]
    assert conditional["numerator_model"]["nodes"][-1]["fixed_value"] == 1
    assert conditional["denominator_model"]["nodes"][-1]["fixed_value"] == 0


@pytest.mark.parametrize(
    ("field_name", "incompatible_value"),
    [
        ("schema_version", "v999"),
        ("compiler_version", "legacy-compiler"),
        ("backend_api_version", "0.1"),
        ("output_channels", 2),
    ],
)
def test_current_spflow_mio_payload_rejects_incompatible_metadata(
    field_name: str,
    incompatible_value: object,
) -> None:
    compiled = _compiled_mio_payload()
    compiled[field_name] = incompatible_value

    with pytest.raises(
        PlanningMIOCompatibilityError,
        match=field_name,
    ):
        validate_current_spflow_mio_payload(compiled)


def test_planning_consumer_accepts_matching_compiled_v2_validity() -> None:
    compiled = _compiled_mio_v2_payload()

    validated = validate_current_spflow_mio_payload(compiled)

    assert validated["compiled_validity"] == compiled["compiled_validity"]


def test_planning_consumer_rejects_compiled_v2_breakpoint_mismatch() -> None:
    compiled = copy.deepcopy(_compiled_mio_v2_payload())
    compiled["nodes"][0]["curves"][0]["breakpoints"][1] = 0.4

    with pytest.raises(PlanningMIOCompatibilityError, match="model breakpoints"):
        validate_current_spflow_mio_payload(compiled)


def test_planning_consumer_keeps_compiled_v1_normalized_only() -> None:
    compiled = _compiled_mio_payload()
    compiled["compiled_validity"] = []

    with pytest.raises(PlanningMIOCompatibilityError, match="normalized-only"):
        validate_current_spflow_mio_payload(compiled)
