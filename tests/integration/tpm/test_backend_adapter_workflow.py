"""End-to-end TPM workflow coverage through a registered backend adapter."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pyomo.environ as pyo
import pytest

from open_energy_lab.planning import load_planning_dataset
from open_energy_lab.planning import fit_tpm_artifact
from open_energy_lab.tpm import (
    SPNSolveConfig,
    query_tpm_artifact,
    register_spflow_backend_adapter,
    solve_spn_chance_model_from_artifact,
    unregister_spflow_backend_adapter,
)
from open_energy_lab.tpm.query import TPMQueryRequest
from tests.integration.planning.fixture_utils import PLANNING_DATASET_ARTIFACT_FIXTURE_PATH


class _FakeWorkflowAdapter(SimpleNamespace):
    @property
    def adapter_name(self) -> str:
        return "fake-workflow-adapter"

    @property
    def backend_name(self) -> str:
        return "fake-spflow"

    @property
    def backend_version(self) -> str:
        return "0.test"

    @property
    def backend_module(self) -> object:
        return self

    def detect_capabilities(self) -> dict[str, object]:
        return {
            "installed_backend_module": self.backend_name,
            "installed_backend_version": self.backend_version,
            "backend_adapter_name": self.adapter_name,
            "legacy_spn_api_available": True,
            "supports_real_spn_training": True,
            "supports_real_spn_query": True,
            "supports_spn_mip_serialization": True,
            "fallback_query_strategy": None,
            "reason": "fake workflow adapter available",
        }

    def fit_runtime_payload(self, runtime_payload):
        payload = dict(runtime_payload)
        payload["query_strategy"] = "spflow"
        payload["query_probability"] = 0.08
        payload["query_log_likelihood"] = -1.5
        payload["conditional_models"] = {
            "numerator_model": {
                "root_id": 5,
                "nodes": [
                    {
                        "id": 1,
                        "type": "leaf_categorical",
                        "feature_name": "design_name",
                        "densities": [0.2, 0.01],
                    },
                    {
                        "id": 2,
                        "type": "leaf_histogram",
                        "feature_name": "battery_capacity_kwh",
                        "breaks": [0.0, 0.5, 1.0],
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
                        "type": "leaf_categorical",
                        "feature_name": "design_name",
                        "densities": [0.5, 0.5],
                    },
                    {
                        "id": 4,
                        "type": "leaf_histogram",
                        "feature_name": "battery_capacity_kwh",
                        "breaks": [0.0, 0.5, 1.0],
                        "densities": [0.5, 0.5],
                    },
                    {"id": 6, "type": "product", "children": [3, 4]},
                ],
            },
        }
        return payload

    def evaluate_runtime_query(
        self,
        runtime_payload,
        *,
        feature_specs,
        decision_assignments,
        marginalized_features,
        event_target_name,
        output_mode,
        numeric_tolerance,
    ):
        value = (
            float(runtime_payload["query_probability"])
            if output_mode == "conditional_probability"
            else float(runtime_payload["query_log_likelihood"])
        )
        return {
            "matched_row_count": 1,
            "total_row_count": len(runtime_payload["raw_rows"]),
            "source": "spflow_backend",
            "value": value,
            "resolved_target_name": event_target_name,
        }


def _adapter_factory(_runtime_payload):
    return _FakeWorkflowAdapter()


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


@pytest.mark.xfail(
    strict=True,
    reason="v1 serialized spn_mip payload path is broken since 3a5307e; retired in consolidation step B3 (docs/dev/consolidation.md)",
)
@pytest.mark.skipif(not _gurobi_available(), reason="gurobi solver unavailable")
def test_registered_backend_adapter_supports_fit_reload_query_and_solve(
    tmp_path: Path,
) -> None:
    dataset = load_planning_dataset(PLANNING_DATASET_ARTIFACT_FIXTURE_PATH)
    artifact_path = tmp_path / "tpm-artifact.json"
    register_spflow_backend_adapter("fake-workflow-adapter", _adapter_factory)
    try:
        fit_tpm_artifact(
            dataset,
            output_path=artifact_path,
            spflow_backend=_FakeWorkflowAdapter(),
        )
        query_result = query_tpm_artifact(
            artifact_path,
            TPMQueryRequest(
                decision_assignments={
                    "battery_capacity_kwh": 8.0,
                    "design_name": "baseline-a",
                },
                marginalized_features=("solar_capacity_kw",),
                output_mode="conditional_probability",
            ),
        )
        solve_summary = solve_spn_chance_model_from_artifact(
            artifact=artifact_path,
            problem_id="adapter-workflow-problem",
            decision_features=("battery_capacity_kwh", "design_name"),
            cost_terms={
                "battery_capacity_kwh": 100.0,
                "design_name": 0.0,
            },
            chance_limit_epsilon=0.1,
            solve_config=SPNSolveConfig(solver_name="gurobi"),
        )
    finally:
        unregister_spflow_backend_adapter("fake-workflow-adapter")

    assert query_result["source"] == "spflow_backend"
    assert query_result["value"] == pytest.approx(0.08)
    assert solve_summary.status == "optimal"
    assert solve_summary.selected_design["design_name"] in {"baseline-a", "baseline-b"}
    assert solve_summary.estimated_event_probability is not None
    assert solve_summary.estimated_event_probability <= 0.1 + 1e-9
    assert solve_summary.estimated_shortfall_risk is not None
    assert solve_summary.estimated_shortfall_risk <= 0.1 + 1e-9
