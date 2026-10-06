"""Open CPU evidence for compiled physical/model-coordinate decision links."""

from __future__ import annotations

import pytest
from tpm.mio.encode import _decode_decision_value

from tpm import (
    TPMApproximationDomain,
    build_compiled_spflow_decision_link_model,
    compile_spflow_model_to_mio,
    load_tpm_artifact,
)
from tpm.spflow_backend import load_spflow_payload
from tpm.query import marginalize_spflow_model


@pytest.fixture(scope="module")
def compiled_x_payload():
    artifact = load_tpm_artifact(
        "tests/fixtures/tpm/tpm_artifact_domains_v3.json"
    )
    runtime = load_spflow_payload(artifact)
    assert runtime is not None
    model = marginalize_spflow_model(runtime["model"], [3])
    return compile_spflow_model_to_mio(
        model,
        fitted_artifact=artifact,
        approximation_domains=(
            TPMApproximationDomain(
                feature_name="x",
                lower=60.0,
                upper=140.0,
                source="highs-link-smoke",
            ),
        ),
    )


@pytest.mark.parametrize(
    ("physical_value", "expected_coordinate"),
    [(60.0, 1.0 / 6.0), (100.0, 0.5), (140.0, 5.0 / 6.0)],
)
def test_highs_solves_physical_to_model_coordinate_links(
    compiled_x_payload,
    physical_value: float,
    expected_coordinate: float,
) -> None:
    import pyomo.environ as pyo

    model = build_compiled_spflow_decision_link_model(
        pyo,
        compiled_payload=compiled_x_payload,
        decision_features=("x",),
    )
    decision = model._tpm_decision_variables["x"]
    decision["physical_var"].fix(physical_value)

    solver = pyo.SolverFactory("highs")
    solver.options["threads"] = 1
    results = solver.solve(model)

    assert str(results.solver.termination_condition).lower() == "optimal"
    assert pyo.value(decision["physical_var"]) == pytest.approx(physical_value)
    assert pyo.value(decision["model_coordinate_var"]) == pytest.approx(
        expected_coordinate,
        abs=1e-9,
    )


def test_highs_reports_outside_physical_value_infeasible(compiled_x_payload) -> None:
    import pyomo.environ as pyo

    model = build_compiled_spflow_decision_link_model(
        pyo,
        compiled_payload=compiled_x_payload,
        decision_features=("x",),
    )
    model._tpm_decision_variables["x"]["physical_var"].fix(59.0)

    solver = pyo.SolverFactory("highs")
    solver.options["threads"] = 1
    results = solver.solve(model, load_solutions=False)

    assert "infeasible" in str(results.solver.termination_condition).lower()


def test_declared_binary_order_maps_solver_states_back_to_caller_labels(
    compiled_x_payload,
) -> None:
    import pyomo.environ as pyo

    model = build_compiled_spflow_decision_link_model(
        pyo,
        compiled_payload=compiled_x_payload,
        decision_features=("activation",),
    )
    decision = model._tpm_decision_variables["activation"]
    feature_spec = {
        spec.feature_name: spec
        for spec in load_tpm_artifact(
            "tests/fixtures/tpm/tpm_artifact_domains_v3.json"
        ).feature_specs
    }["activation"]

    decision["normalized_var"].set_value(0.0)
    assert _decode_decision_value(
        feature_spec,
        decision_payload=decision,
        value_function=pyo.value,
        numeric_tolerance=1e-9,
    ) == "off"
    decision["normalized_var"].set_value(1.0)
    assert _decode_decision_value(
        feature_spec,
        decision_payload=decision,
        value_function=pyo.value,
        numeric_tolerance=1e-9,
    ) == "on"
