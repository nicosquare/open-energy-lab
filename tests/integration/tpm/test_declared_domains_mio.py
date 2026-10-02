"""Real-SPFlow compiler validity checks for declared physical domains."""

from __future__ import annotations

import pytest

from tpm import (
    TPMApproximationDomain,
    compile_spflow_model_to_mio,
    evaluate_compiled_spflow_probability,
    load_tpm_artifact,
)
from tpm.optional_spflow import load_spflow_payload
from tpm.query import marginalize_spflow_model


ARTIFACT_PATH = "tests/fixtures/tpm/tpm_artifact_domains_v3.json"


@pytest.fixture(scope="module")
def compiled_declared_x():
    artifact = load_tpm_artifact(ARTIFACT_PATH)
    runtime = load_spflow_payload(artifact)
    assert runtime is not None
    model = marginalize_spflow_model(runtime["model"], [3])
    compiled = compile_spflow_model_to_mio(
        model,
        fitted_artifact=artifact,
        approximation_domains=(
            TPMApproximationDomain(
                feature_name="x",
                lower=60.0,
                upper=140.0,
                source="declared-domain-integration",
            ),
        ),
    )
    return artifact, model, compiled


@pytest.mark.parametrize("x_value", [60.0, 100.0, 140.0])
def test_physical_and_model_coordinate_evaluation_agree_at_valid_points(
    compiled_declared_x,
    x_value: float,
) -> None:
    _, model, compiled = compiled_declared_x
    model_x = (x_value - 40.0) / 120.0
    physical = {
        "x": x_value,
        "activation": "off",
        "service_tier": "economy",
        "demand_above_100": 0.0,
    }
    coordinates = {
        "x": model_x,
        "activation": 0.0,
        "service_tier": 0.0,
        "demand_above_100": 0.0,
    }

    physical_probability = evaluate_compiled_spflow_probability(
        compiled,
        physical_evidence=physical,
    )
    coordinate_probability = evaluate_compiled_spflow_probability(
        compiled,
        model_coordinate_evidence=coordinates,
    )

    import torch

    native_evidence = torch.tensor(
        [[model_x, 0.0, 0.0, 0.0, 0.0]],
        dtype=torch.float64,
    )
    with torch.no_grad():
        native_probability = float(
            torch.exp(model.log_likelihood(native_evidence)).reshape(-1)[0]
        )

    assert physical_probability == pytest.approx(coordinate_probability, abs=1e-12)
    assert physical_probability == pytest.approx(native_probability, abs=1e-6)


@pytest.mark.parametrize("x_value", [59.999, 140.001])
def test_physical_evaluation_rejects_values_outside_compiled_validity(
    compiled_declared_x,
    x_value: float,
) -> None:
    _, _, compiled = compiled_declared_x

    with pytest.raises(ValueError, match="x.*outside compiled validity"):
        evaluate_compiled_spflow_probability(
            compiled,
            physical_evidence={
                "x": x_value,
                "activation": "off",
                "service_tier": "economy",
                "demand_above_100": 0.0,
            },
        )


@pytest.mark.parametrize("coordinate", [0.16, 0.84])
def test_model_coordinate_evaluation_rejects_extrapolation(
    compiled_declared_x,
    coordinate: float,
) -> None:
    _, _, compiled = compiled_declared_x

    with pytest.raises(ValueError, match="x.*outside compiled validity"):
        evaluate_compiled_spflow_probability(
            compiled,
            model_coordinate_evidence={
                "x": coordinate,
                "activation": 0.0,
                "service_tier": 0.0,
                "demand_above_100": 0.0,
            },
        )


def test_marginalized_continuous_feature_needs_no_approximation_interval(
    compiled_declared_x,
) -> None:
    _, _, compiled = compiled_declared_x

    assert [record["feature_name"] for record in compiled["compiled_validity"]] == [
        "x"
    ]
    assert "demand" not in {
        curve["feature_name"]
        for node in compiled["nodes"]
        if node["type"] == "normal"
        for curve in node["curves"]
    }


def test_discrete_only_graph_compiles_and_evaluates_without_artificial_intervals() -> None:
    artifact = load_tpm_artifact(ARTIFACT_PATH)
    runtime = load_spflow_payload(artifact)
    assert runtime is not None
    discrete_model = marginalize_spflow_model(runtime["model"], [0, 3])

    compiled = compile_spflow_model_to_mio(
        discrete_model,
        fitted_artifact=artifact,
        approximation_domains=(),
    )
    probability = evaluate_compiled_spflow_probability(
        compiled,
        physical_evidence={
            "activation": "off",
            "service_tier": "economy",
            "demand_above_100": 0.0,
        },
    )

    assert compiled["compiled_validity"] == []
    assert probability > 0.0
