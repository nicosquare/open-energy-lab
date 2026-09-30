"""Direct TPM-layer integration coverage for SPN MIO solving."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import pyomo.environ as pyo
import pytest

from open_energy_lab.tpm import SPNSolveConfig, solve_spn_chance_model_from_artifact


def _gurobi_available() -> bool:
    try:
        solver = pyo.SolverFactory("gurobi")
    except Exception:
        return False
    available = getattr(solver, "available", None)
    if not callable(available):
        return True
    try:
        return bool(available(exception_flag=False))
    except TypeError:
        return bool(available())


def _artifact_payload(locator: str) -> dict[str, object]:
    return {
        "artifact_id": "tpm-artifact-tpm-mio-solver",
        "schema_version": "v1",
        "created_at": "2026-07-14T00:00:00Z",
        "dataset_reference": "synthetic-dataset",
        "feature_schema": [
            {
                "feature_name": "battery_enabled",
                "feature_role": "decision",
                "feature_type": "binary",
                "discrete_values": [0.0, 1.0],
                "ordering": [0.0, 1.0],
                "modifiable": True,
            },
            {
                "feature_name": "solar_enabled",
                "feature_role": "decision",
                "feature_type": "binary",
                "discrete_values": [0.0, 1.0],
                "ordering": [0.0, 1.0],
                "modifiable": True,
            },
            {
                "feature_name": "shortfall",
                "feature_role": "metric_target",
                "feature_type": "continuous",
                "bounds": [0.0, 1.0],
                "modifiable": False,
            },
            {
                "feature_name": "shortfall_exceeds_threshold",
                "feature_role": "target",
                "feature_type": "binary",
                "discrete_values": [0.0, 1.0],
                "ordering": [0.0, 1.0],
                "modifiable": False,
            },
        ],
        "target_definition": {
            "target_name": "shortfall",
            "event_target_name": "shortfall_exceeds_threshold",
            "threshold_default": 0.05,
            "supported_query_mode": "exceedance-probability",
        },
        "fit_configuration": {"backend_name": "spflow"},
        "spn_payload": {
            "locator": locator,
            "serialization": "pickle",
            "backend": "spflow",
        },
        "spn_payload_format": "pickle-path",
        "query_configuration": {
            "supported_output_modes": ["conditional_probability", "log_likelihood"],
            "required_decision_features": ["battery_enabled", "solar_enabled"],
        },
        "approximation_metadata": {
            "approximation_kind": "piecewise",
            "sum_encoding_mode": "piecewise",
            "query_numeric_tolerance": 1e-9,
        },
        "provenance": {},
    }


@pytest.mark.xfail(
    strict=True,
    reason="v1 serialized spn_mip payload path is broken since 3a5307e; retired in consolidation step B3 (docs/dev/consolidation.md)",
)
@pytest.mark.skipif(not _gurobi_available(), reason="gurobi solver unavailable")
def test_solve_spn_chance_model_from_artifact_solves_with_gurobi(tmp_path: Path) -> None:
    payload_path = tmp_path / "spn_payload.pkl"
    payload_path.write_bytes(
        pickle.dumps(
            {
                "backend_module": "spn",
                "backend_version": "0.test",
                "backend_adapter_name": "legacy-spn-api",
                "canonical_target_name": "shortfall",
                "event_target_name": "shortfall_exceeds_threshold",
                "feature_schema": _artifact_payload("unused")["feature_schema"],
                "query_strategy": "spflow",
                "raw_rows": [
                    {
                        "battery_enabled": 0.0,
                        "solar_enabled": 1.0,
                        "shortfall": 0.0,
                        "shortfall_exceeds_threshold": 0.0,
                    }
                ],
                "conditional_models": {
                    "numerator_model": {
                        "root_id": 5,
                        "nodes": [
                            {
                                "id": 1,
                                "type": "leaf_binary",
                                "feature_name": "battery_enabled",
                                "densities": [0.2, 0.01],
                            },
                            {
                                "id": 2,
                                "type": "leaf_binary",
                                "feature_name": "solar_enabled",
                                "densities": [0.2, 0.01],
                            },
                            {"id": 5, "type": "product", "children": [1, 2]},
                        ],
                    },
                    "denominator_model": {
                        "root_id": 6,
                        "nodes": [
                            {
                                "id": 3,
                                "type": "leaf_binary",
                                "feature_name": "battery_enabled",
                                "densities": [0.5, 0.5],
                            },
                            {
                                "id": 4,
                                "type": "leaf_binary",
                                "feature_name": "solar_enabled",
                                "densities": [0.5, 0.5],
                            },
                            {"id": 6, "type": "product", "children": [3, 4]},
                        ],
                    },
                },
            }
        )
    )
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(_artifact_payload(payload_path.name), indent=2) + "\n",
        encoding="utf-8",
    )

    summary = solve_spn_chance_model_from_artifact(
        artifact=artifact_path,
        problem_id="tpm-layer-spn-mio",
        decision_features=("battery_enabled", "solar_enabled"),
        cost_terms={
            "battery_enabled": 1200.0,
            "solar_enabled": 950.0,
        },
        chance_limit_epsilon=0.1,
        solve_config=SPNSolveConfig(solver_name="gurobi"),
    )

    assert summary.status == "optimal"
    assert summary.selected_design == {
        "battery_enabled": 0.0,
        "solar_enabled": 1.0,
    }
    assert summary.objective_value == pytest.approx(950.0)
    assert summary.estimated_event_probability is not None
    assert summary.estimated_event_probability <= 0.1 + 1e-9
    assert summary.estimated_shortfall_risk is not None
    assert summary.estimated_shortfall_risk <= 0.1 + 1e-9
    assert summary.solver_metadata["requested_solver_name"] == "gurobi"
    assert summary.solver_metadata["solve_execution_mode"] == "native-pyomo-solver"
