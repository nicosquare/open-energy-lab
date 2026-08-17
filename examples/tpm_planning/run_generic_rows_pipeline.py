from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from open_energy_lab.tpm import (
    SPNSolveConfig,
    TPMArtifactBuildRequest,
    TPMQueryRequest,
    detect_spflow_backend_capabilities,
    fit_tpm_artifact_from_rows,
    query_tpm_artifact,
    register_spflow_backend_adapter,
    solve_spn_chance_model_from_artifact,
    unregister_spflow_backend_adapter,
)


EXAMPLE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_ROOT.parent.parent
OUTPUT_ROOT = REPO_ROOT / "tmp" / "open-energy-lab-pipeline-real-backends"


class _GenericRowsWorkflowAdapter(SimpleNamespace):
    @property
    def adapter_name(self) -> str:
        return "examples-generic-rows-adapter"

    @property
    def backend_name(self) -> str:
        return "fake-spflow"

    @property
    def backend_version(self) -> str:
        return "0.demo"

    @property
    def backend_module(self) -> object:
        return self

    def detect_capabilities(self) -> dict[str, object]:
        return {
            "installed_backend_module": self.backend_name,
            "installed_backend_version": self.backend_version,
            "backend_adapter_name": self.adapter_name,
            "legacy_api_module_prefix": "spn",
            "legacy_spn_api_available": True,
            "supports_real_spn_training": True,
            "supports_real_spn_query": True,
            "supports_spn_mip_serialization": True,
            "fallback_query_strategy": None,
            "reason": "demo adapter provides serialized SPN query and MIO payloads",
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
    return _GenericRowsWorkflowAdapter()


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    artifact_path = OUTPUT_ROOT / "generic_rows_tpm_artifact.json"
    summary_path = OUTPUT_ROOT / "generic_rows_pipeline_summary.json"
    environment_capabilities = detect_spflow_backend_capabilities()

    rows = (
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
    )

    use_real_backend = bool(environment_capabilities["supports_real_spn_training"])
    adapter_capabilities = None
    if use_real_backend:
        artifact = fit_tpm_artifact_from_rows(
            rows,
            output_path=artifact_path,
            build_request=TPMArtifactBuildRequest(
                artifact_id="example-generic-risk-artifact",
                dataset_reference="example-generic-risk-dataset",
                decision_features=("generator_size_kw", "tariff_plan"),
                target_name="loss_ratio",
                event_target_name="loss_event",
                target_threshold=0.05,
            ),
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
            problem_id="example-generic-risk-problem",
            decision_features=("generator_size_kw", "tariff_plan"),
            cost_terms={
                "generator_size_kw": 100.0,
                "tariff_plan": 0.0,
            },
            chance_limit_epsilon=0.5,
            solve_config=SPNSolveConfig(solver_name="gurobi"),
        )
    else:
        register_spflow_backend_adapter("examples-generic-rows-adapter", _adapter_factory)
        try:
            artifact = fit_tpm_artifact_from_rows(
                rows,
                output_path=artifact_path,
                build_request=TPMArtifactBuildRequest(
                    artifact_id="example-generic-risk-artifact",
                    dataset_reference="example-generic-risk-dataset",
                    decision_features=("generator_size_kw", "tariff_plan"),
                    target_name="loss_ratio",
                    event_target_name="loss_event",
                    target_threshold=0.05,
                ),
                spflow_backend=_GenericRowsWorkflowAdapter(),
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
                problem_id="example-generic-risk-problem",
                decision_features=("generator_size_kw", "tariff_plan"),
                cost_terms={
                    "generator_size_kw": 100.0,
                    "tariff_plan": 0.0,
                },
                chance_limit_epsilon=0.1,
                solve_config=SPNSolveConfig(solver_name="gurobi"),
            )
            adapter_capabilities = _GenericRowsWorkflowAdapter().detect_capabilities()
        finally:
            unregister_spflow_backend_adapter("examples-generic-rows-adapter")

    summary = {
        "generated_by": str(Path(__file__).relative_to(REPO_ROOT)),
        "artifact_path": str(artifact_path.relative_to(REPO_ROOT)),
        "environment_spflow_capabilities": environment_capabilities,
        "used_real_spflow_backend": use_real_backend,
        "adapter_spflow_capabilities": adapter_capabilities,
        "artifact_id": artifact.artifact_id,
        "dataset_reference": artifact.dataset_reference,
        "target_definition": dict(artifact.target_definition),
        "query_result": query_result,
        "solve_status": solve_summary.status,
        "selected_design": dict(solve_summary.selected_design),
        "objective_value": solve_summary.objective_value,
        "estimated_event_probability": solve_summary.estimated_event_probability,
        "estimated_shortfall_risk": solve_summary.estimated_shortfall_risk,
        "solve_execution_mode": solve_summary.solver_metadata.get("solve_execution_mode"),
        "requested_solver_name": solve_summary.solver_metadata.get("requested_solver_name"),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
