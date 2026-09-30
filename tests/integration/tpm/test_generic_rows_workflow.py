"""Generic row-based TPM workflow coverage outside the planning dataset contract."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pyomo.environ as pyo
import pytest

from open_energy_lab.tpm import (
    SPNSolveConfig,
    TPMArtifactBuildRequest,
    fit_tpm_artifact_from_rows,
    query_tpm_artifact,
    register_spflow_backend_adapter,
    solve_spn_chance_model_from_artifact,
    unregister_spflow_backend_adapter,
)
from open_energy_lab.tpm.query import TPMQueryRequest


class _FakeGenericWorkflowAdapter(SimpleNamespace):
    @property
    def adapter_name(self) -> str:
        return "fake-generic-workflow-adapter"

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
            "reason": "fake generic workflow adapter available",
        }

    def fit_runtime_payload(self, runtime_payload):
        payload = dict(runtime_payload)
        payload["query_strategy"] = "spflow"
        payload["query_probability"] = 0.08
        payload["query_log_likelihood"] = -1.2
        payload["conditional_models"] = {
            "numerator_model": {
                "root_id": 5,
                "nodes": [
                    {
                        "id": 1,
                        "type": "leaf_histogram",
                        "feature_name": "generator_size_kw",
                        "breaks": [0.0, 0.4, 1.0],
                        "densities": [0.2, 0.01],
                    },
                    {
                        "id": 2,
                        "type": "leaf_categorical",
                        "feature_name": "tariff_plan",
                        "densities": [0.01, 0.2],
                    },
                    {"id": 5, "type": "product", "children": [1, 2]},
                ],
            },
            "denominator_model": {
                "root_id": 6,
                "nodes": [
                    {
                        "id": 3,
                        "type": "leaf_histogram",
                        "feature_name": "generator_size_kw",
                        "breaks": [0.0, 0.4, 1.0],
                        "densities": [0.5, 0.5],
                    },
                    {
                        "id": 4,
                        "type": "leaf_categorical",
                        "feature_name": "tariff_plan",
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
    return _FakeGenericWorkflowAdapter()


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
def test_generic_rows_can_fit_query_and_solve_without_planning_dataset_contract(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "generic-risk-artifact.json"
    register_spflow_backend_adapter("fake-generic-workflow-adapter", _adapter_factory)
    try:
        fit_tpm_artifact_from_rows(
            (
                {
                    "generator_size_kw": 2.0,
                    "tariff_plan": "flat",
                    "ambient_band": "low",
                    "loss_ratio": 0.01,
                },
                {
                    "generator_size_kw": 6.0,
                    "tariff_plan": "peak",
                    "ambient_band": "high",
                    "loss_ratio": 0.12,
                },
            ),
            output_path=artifact_path,
            build_request=TPMArtifactBuildRequest(
                artifact_id="generic-risk-artifact",
                dataset_reference="generic-risk-dataset",
                decision_features=("generator_size_kw", "tariff_plan"),
                target_name="loss_ratio",
                event_target_name="loss_event",
                target_threshold=0.05,
            ),
            spflow_backend=_FakeGenericWorkflowAdapter(),
        )
        query_result = query_tpm_artifact(
            artifact_path,
            TPMQueryRequest(
                decision_assignments={
                    "generator_size_kw": 2.0,
                    "tariff_plan": "flat",
                },
                marginalized_features=("ambient_band",),
                output_mode="conditional_probability",
                target_name="loss_ratio",
            ),
        )
        solve_summary = solve_spn_chance_model_from_artifact(
            artifact=artifact_path,
            problem_id="generic-risk-problem",
            decision_features=("generator_size_kw", "tariff_plan"),
            cost_terms={
                "generator_size_kw": 100.0,
                "tariff_plan": 0.0,
            },
            chance_limit_epsilon=0.1,
            solve_config=SPNSolveConfig(solver_name="gurobi"),
        )
    finally:
        unregister_spflow_backend_adapter("fake-generic-workflow-adapter")

    assert query_result["source"] == "spflow_backend"
    assert query_result["target_name"] == "loss_ratio"
    assert query_result["resolved_target_name"] == "loss_event"
    assert query_result["value"] == pytest.approx(0.08)
    assert solve_summary.status == "optimal"
    assert solve_summary.selected_design == {
        "generator_size_kw": pytest.approx(2.0),
        "tariff_plan": "flat",
    }
    assert solve_summary.estimated_event_probability is not None
    assert solve_summary.estimated_event_probability <= 0.1 + 1e-9
    assert solve_summary.estimated_shortfall_risk is not None
    assert solve_summary.estimated_shortfall_risk <= 0.1 + 1e-9
