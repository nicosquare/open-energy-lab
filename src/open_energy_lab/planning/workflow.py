"""Staged and convenience APIs for discrete solar-storage planning studies."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

from open_energy_lab.tpm.artifact import TPMArtifact
from open_energy_lab.tpm.fit import TPMFitConfig, fit_tpm_artifact_from_study_manifest
from open_energy_lab.tpm.mio import compile_spflow_model_to_mio
from open_energy_lab.tpm.optional_spflow import load_spflow_payload
from open_energy_lab.tpm.query import TPMQueryRequest, query_tpm_artifact

from .optional_solver import PlanningSolveConfig, PlanningSolveSummary, solve_planning_problem
from .problem import PlanningProblemDefinition, assemble_planning_problem
from .study import PlanningStudyRequest
from .study_dataset import PlanningStudyDatasetManifest, load_study_dataset_manifest


@dataclass(frozen=True, slots=True)
class CompiledPlanningStudyTPM:
    artifact: TPMArtifact
    compiled_payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class VerifiedPlanningStudySolution:
    status: str
    solve_summary: PlanningSolveSummary
    native_event_probability: float | None
    probability_discrepancy: float | None
    validation_tolerance: float
    diagnostics: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlanningStudyRunResult:
    dataset_manifest: PlanningStudyDatasetManifest
    tpm_artifact: TPMArtifact
    compiled_payload: Mapping[str, object]
    solution: VerifiedPlanningStudySolution


def fit_planning_study_tpm(
    manifest: PlanningStudyDatasetManifest | str | Path,
    *,
    output_path: str | Path,
    fit_feature_names: tuple[str, ...] | None = None,
    max_tensor_bytes: int = 1_073_741_824,
    fit_config: TPMFitConfig | None = None,
) -> TPMArtifact:
    """Fit the compact study feature set after an explicit memory preflight."""

    return fit_tpm_artifact_from_study_manifest(
        manifest,
        output_path=output_path,
        fit_feature_names=fit_feature_names,
        max_tensor_bytes=max_tensor_bytes,
        fit_config=fit_config,
    )


def compile_planning_study_tpm(
    artifact: TPMArtifact,
    *,
    output_path: str | Path | None = None,
) -> CompiledPlanningStudyTPM:
    """Compile and persist the supported current-SPFlow MIO contract."""

    runtime_payload = load_spflow_payload(artifact)
    if runtime_payload is None or runtime_payload.get("model") is None:
        raise ValueError("planning-study compilation requires a persisted SPFlow model")
    compiled = compile_spflow_model_to_mio(
        runtime_payload["model"], feature_schema=artifact.feature_specs
    )
    compiler_policy = dict(compiled["breakpoint_policy"])
    updated = replace(
        artifact,
        approximation_metadata={
            **dict(artifact.approximation_metadata),
            "backend_compiler_version": compiled["backend_compiler_version"],
            "compiler_schema_version": compiled["schema_version"],
            "compiler_version": compiled["compiler_version"],
            "compiler_status": "production-validated",
            "compiler_sum_encoding_mode": compiled["sum_encoding_mode"],
            "leaf_encoding_mode": compiled["leaf_encoding_mode"],
            "breakpoint_policy": {
                **compiler_policy,
                "piecewise_breakpoint_count": compiler_policy["breakpoint_count"],
            },
            "mio_epsilon": compiled["mio_epsilon"],
        },
    )
    if output_path is None and not artifact.source_path:
        raise ValueError("output_path is required for an in-memory TPM artifact")
    destination = Path(output_path) if output_path is not None else Path(artifact.source_path)
    updated.write_json(destination)
    updated = replace(updated, source_path=destination.as_posix())
    return CompiledPlanningStudyTPM(artifact=updated, compiled_payload=compiled)


def solve_planning_study(
    artifact: TPMArtifact,
    manifest: PlanningStudyDatasetManifest | str | Path,
    *,
    chance_limit_epsilon: float,
    solve_config: PlanningSolveConfig | None = None,
    validation_tolerance: float = 1e-6,
) -> VerifiedPlanningStudySolution:
    """Optimize the encoded SPN directly and verify the selected design natively."""

    resolved_manifest = (
        manifest
        if isinstance(manifest, PlanningStudyDatasetManifest)
        else load_study_dataset_manifest(manifest)
    )
    if validation_tolerance <= 0.0:
        raise ValueError("validation_tolerance must be positive")
    option_costs = _option_costs(resolved_manifest)
    threshold = float(artifact.target_definition["threshold_default"])
    definition = PlanningProblemDefinition(
        problem_id=f"planning-study:{resolved_manifest.dataset_id}",
        decision_features=("battery_option_id", "solar_option_id"),
        decision_feature_types={
            "battery_option_id": "categorical",
            "solar_option_id": "categorical",
        },
        shortfall_threshold=threshold,
        chance_limit_epsilon=chance_limit_epsilon,
        option_costs=option_costs,
        risk_evaluation_mode="spn_mip",
    )
    assembled = assemble_planning_problem(definition, artifact)
    solve_summary = solve_planning_problem(
        assembled,
        solve_config=solve_config or PlanningSolveConfig(),
    )
    if solve_summary.status != "optimal":
        return VerifiedPlanningStudySolution(
            status=solve_summary.status,
            solve_summary=solve_summary,
            native_event_probability=None,
            probability_discrepancy=None,
            validation_tolerance=float(validation_tolerance),
            diagnostics={"reason": "native verification requires an optimal design"},
        )

    query = query_tpm_artifact(
        artifact,
        TPMQueryRequest(
            decision_assignments=solve_summary.selected_design,
            output_mode="conditional_probability",
            target_threshold=threshold,
            execution_mode="production",
        ),
    )
    native_probability = float(query["value"])
    encoded_probability = float(solve_summary.estimated_shortfall_risk)
    discrepancy = abs(native_probability - encoded_probability)
    limit_violation = native_probability > float(chance_limit_epsilon) + 1e-9
    mismatch = discrepancy > float(validation_tolerance)
    status = "validation_failed" if mismatch or limit_violation else "optimal"
    return VerifiedPlanningStudySolution(
        status=status,
        solve_summary=solve_summary,
        native_event_probability=native_probability,
        probability_discrepancy=discrepancy,
        validation_tolerance=float(validation_tolerance),
        diagnostics={
            "encoded_event_probability": encoded_probability,
            "chance_limit_epsilon": float(chance_limit_epsilon),
            "native_limit_violation": limit_violation,
            "encoded_native_mismatch": mismatch,
            "query_source": query["source"],
        },
    )


def run_planning_study(
    request: PlanningStudyRequest,
    *,
    weather_artifact: object,
    demand_artifact: object,
    base_scenario_reference: object,
    cooling_service_configuration: object,
    output_dir: str | Path,
    chance_limit_epsilon: float,
    expected_timestep_hours: float,
    max_tensor_bytes: int = 1_073_741_824,
    solve_config: PlanningSolveConfig | None = None,
) -> PlanningStudyRunResult:
    """Run dataset generation, compact fit, compilation, solve, and verification."""

    from open_energy_lab.simulator.planning_study import generate_planning_study_dataset

    root = Path(output_dir)
    manifest = generate_planning_study_dataset(
        request,
        weather_artifact=weather_artifact,
        demand_artifact=demand_artifact,
        base_scenario_reference=base_scenario_reference,
        cooling_service_configuration=cooling_service_configuration,
        output_dir=root / "dataset",
        expected_timestep_hours=expected_timestep_hours,
    )
    artifact_path = root / "tpm" / "artifact.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = fit_planning_study_tpm(
        manifest,
        output_path=artifact_path,
        max_tensor_bytes=max_tensor_bytes,
    )
    compiled = compile_planning_study_tpm(artifact, output_path=artifact_path)
    solution = solve_planning_study(
        compiled.artifact,
        manifest,
        chance_limit_epsilon=chance_limit_epsilon,
        solve_config=solve_config,
    )
    return PlanningStudyRunResult(
        dataset_manifest=manifest,
        tpm_artifact=compiled.artifact,
        compiled_payload=compiled.compiled_payload,
        solution=solution,
    )


def _option_costs(
    manifest: PlanningStudyDatasetManifest,
) -> dict[str, dict[object, float]]:
    catalog = manifest.metadata.get("equipment_catalog")
    if not isinstance(catalog, list):
        raise ValueError("study manifest equipment_catalog must be a list")
    battery: dict[object, float] = {}
    solar: dict[object, float] = {}
    for entry in catalog:
        if not isinstance(entry, Mapping):
            raise ValueError("equipment_catalog entries must be mappings")
        battery_entry = entry.get("battery")
        solar_entry = entry.get("solar")
        if not isinstance(battery_entry, Mapping) or not isinstance(solar_entry, Mapping):
            raise ValueError("equipment_catalog entries must include battery and solar")
        battery[battery_entry["option_id"]] = float(battery_entry["installed_cost"])
        solar[solar_entry["option_id"]] = float(solar_entry["installed_cost"])
    return {"battery_option_id": battery, "solar_option_id": solar}


__all__ = [
    "CompiledPlanningStudyTPM",
    "PlanningStudyRunResult",
    "VerifiedPlanningStudySolution",
    "compile_planning_study_tpm",
    "fit_planning_study_tpm",
    "run_planning_study",
    "solve_planning_study",
]
