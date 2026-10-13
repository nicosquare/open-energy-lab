"""Simulator-owned discrete planning-study sweep and dataset generation."""

from __future__ import annotations

import copyreg
import hashlib
import importlib
import json
from dataclasses import asdict, fields, is_dataclass, replace
from pathlib import Path
from typing import Any

from open_energy_lab.demand import DemandSamplingRequest, sample_demand_family
from open_energy_lab.planning.study import (
    PlanningConfiguration,
    PlanningStudyRequest,
    build_configuration_grid,
    default_fit_feature_names,
    derive_adequacy_metrics,
    generate_grid_availability_trace,
    resolve_study_controller,
)
from open_energy_lab.planning.study_dataset import (
    PlanningStudyDatasetManifest,
    PlanningStudyDatasetWriter,
)
from open_energy_lab.weather import WeatherSamplingRequest, sample_weather_family

from .stochastic_demand import DemandFamilyEvaluationRequest, evaluate_demand_family


_DESIGN_COLUMNS = (
    "configuration_index",
    "configuration_id",
    "sample_id",
    "scenario_index",
    "battery_option_id",
    "solar_option_id",
    "battery_capacity_kwh",
    "battery_max_charge_kw",
    "battery_max_discharge_kw",
    "solar_capacity_kw",
    "installed_cost",
    "controller_name",
)

# Persisted in every manifest and input fingerprint so datasets generated with
# older dispatch/energy-balance rules cannot be silently resumed as current.
PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION = "grid-balanced-dispatch-v2"


def generate_planning_study_dataset(
    request: PlanningStudyRequest,
    *,
    weather_artifact: object,
    demand_artifact: object,
    base_scenario_reference: object,
    cooling_service_configuration: object,
    output_dir: str | Path,
    expected_timestep_hours: float | None = None,
    numeric_tolerance: float = 1e-9,
) -> PlanningStudyDatasetManifest:
    """Simulate every discrete configuration against common uncertainty samples."""

    if base_scenario_reference.time_grid.num_steps != request.horizon_steps:
        raise ValueError("base scenario horizon must match planning study horizon_steps")
    configurations = build_configuration_grid(request)
    column_order = _study_column_order(request)
    input_fingerprint = _input_fingerprint(
        request,
        weather_artifact=weather_artifact,
        demand_artifact=demand_artifact,
        base_scenario_reference=base_scenario_reference,
        cooling_service_configuration=cooling_service_configuration,
    )
    writer = PlanningStudyDatasetWriter(
        output_dir=output_dir,
        dataset_id=f"planning-study:{request.study_id}",
        request_fingerprint=input_fingerprint,
        column_order=column_order,
        shard_format=request.shard_format,
    )
    batches = request.sample_batches()

    for batch_index, sample_ids in enumerate(batches):
        missing = tuple(
            configuration
            for configuration in configurations
            if not writer.has_shard(
                configuration.configuration_index * len(batches) + batch_index
            )
        )
        if not missing:
            continue
        start = sample_ids[0]
        weather_family = sample_weather_family(
            weather_artifact,
            request=WeatherSamplingRequest(
                num_steps=request.horizon_steps,
                scenario_count=len(sample_ids),
                family_seed=request.random_seed,
                scenario_index_start=start,
                local_start_step=request.local_start_step,
            ),
            expected_timestep_hours=expected_timestep_hours,
        )
        weather_family = replace(
            weather_family,
            blackout_traces=tuple(
                {
                    "scenario_index": sample_id,
                    "grid_available": list(
                        generate_grid_availability_trace(
                            request.grid_availability,
                            study_seed=request.random_seed,
                            sample_id=sample_id,
                            horizon_steps=request.horizon_steps,
                        )
                    ),
                    "interval_annotations": [
                        f"planning-study:{request.grid_availability.mode}"
                    ]
                    * request.horizon_steps,
                }
                for sample_id in sample_ids
            ),
        )
        demand_family = sample_demand_family(
            demand_artifact,
            request=DemandSamplingRequest(
                weather_family_reference=weather_family,
                num_steps=request.horizon_steps,
                scenario_count=len(sample_ids),
                paired_family_seed=request.random_seed,
                scenario_index_start=start,
                local_start_step=request.local_start_step,
            ),
            expected_timestep_hours=expected_timestep_hours,
        )

        work = tuple(
            (
                configuration,
                request,
                weather_family,
                demand_family,
                base_scenario_reference,
                cooling_service_configuration,
                numeric_tolerance,
            )
            for configuration in missing
        )
        if request.worker_count == 1 or len(work) == 1:
            results = tuple(_simulate_configuration_batch(*item) for item in work)
        else:
            # Imported here: multiprocessing loads socket, and importing the
            # simulator package must stay free of network modules.
            from concurrent.futures import ProcessPoolExecutor
            import multiprocessing

            _register_reloaded_dataclass_reducers(work)
            with ProcessPoolExecutor(
                max_workers=request.worker_count,
                mp_context=multiprocessing.get_context("spawn"),
            ) as executor:
                futures = [
                    executor.submit(_simulate_configuration_batch, *item)
                    for item in work
                ]
                results = tuple(future.result() for future in futures)

        for configuration, rows in zip(missing, results, strict=True):
            shard_index = configuration.configuration_index * len(batches) + batch_index
            writer.write_shard(shard_index, rows)

    manifest = writer.finalize(
        metadata={
            "simulation_semantics_version": PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION,
            "study_request": request.to_dict(),
            "configuration_count": len(configurations),
            "samples_per_configuration": request.samples_per_configuration,
            "expected_row_count": request.expected_row_count,
            "row_order_policy": "configuration_index_then_sample_id",
            "sample_reuse_policy": "common_random_samples_across_configurations",
            "active_event_target": request.adequacy_event.event_target_name,
            "default_fit_feature_names": list(
                request.fit_feature_names
                or default_fit_feature_names(request.adequacy_event)
            ),
            "equipment_catalog": [
                {
                    **configuration.design_metadata(),
                    "battery": asdict(configuration.battery),
                    "solar": asdict(configuration.solar),
                }
                for configuration in configurations
            ],
            "weather_artifact_reference": _artifact_identity(weather_artifact),
            "demand_artifact_reference": _artifact_identity(demand_artifact),
        }
    )
    if manifest.row_count != request.expected_row_count:
        raise RuntimeError(
            "planning study row count does not match configurations times samples"
        )
    return manifest


def _simulate_configuration_batch(
    configuration: PlanningConfiguration,
    request: PlanningStudyRequest,
    weather_family: object,
    demand_family: object,
    base_scenario_reference: object,
    cooling_service_configuration: object,
    numeric_tolerance: float,
) -> tuple[dict[str, object], ...]:
    battery_updates: dict[str, object] = {
        "capacity_kwh": configuration.battery.capacity_kwh,
        "max_charge_kw": configuration.battery.max_charge_kw,
        "max_discharge_kw": configuration.battery.max_discharge_kw,
    }
    for name in (
        "charge_efficiency",
        "discharge_efficiency",
        "initial_soc",
        "min_soc",
        "max_soc",
    ):
        value = getattr(configuration.battery, name)
        if value is not None:
            battery_updates[name] = value
    battery = replace(base_scenario_reference.battery, **battery_updates)
    solar = replace(
        base_scenario_reference.pv,
        rated_power_kw=configuration.solar.capacity_kw,
        generation_cap_kw=configuration.solar.generation_cap_kw,
    )
    scenario = replace(
        base_scenario_reference,
        scenario_id=(
            f"{base_scenario_reference.scenario_id}:{configuration.configuration_id}"
        ),
        battery=battery,
        pv=solar,
    )
    if request.grid_availability.import_limit_kw is not None:
        scenario = replace(
            scenario,
            grid_import_limit_kw=request.grid_availability.import_limit_kw,
        )
    _validate_physical_configuration(scenario, configuration, numeric_tolerance)
    controller = resolve_study_controller(request.controller, battery=configuration.battery)
    family_result = evaluate_demand_family(
        DemandFamilyEvaluationRequest(
            base_scenario_reference=scenario,
            weather_family=weather_family,
            demand_family=demand_family,
            cooling_service_configuration=cooling_service_configuration,
            controller=controller,
            numeric_tolerance=numeric_tolerance,
        )
    )
    weather_by_id = {
        int(trace.scenario_index): trace for trace in weather_family.sampled_traces
    }
    rows: list[dict[str, object]] = []
    for result in family_result.scenario_results:
        sample_id = int(result.scenario_index)
        weather_trace = weather_by_id[sample_id]
        metrics = derive_adequacy_metrics(
            site_electric_load_kw=result.site_electric_load_kw,
            unmet_load_kw=result.unmet_load_kw,
            timestep_hours=family_result.timestep_hours,
            numeric_tolerance=numeric_tolerance,
        )
        row = {
            **configuration.design_metadata(),
            "sample_id": sample_id,
            "scenario_index": sample_id,
            "controller_name": family_result.controller_name,
        }
        ordered = {name: row[name] for name in _DESIGN_COLUMNS}
        for step_index in range(request.horizon_steps):
            ordered[f"ghi_{step_index}"] = float(
                weather_trace.canonical_field_series[
                    "global_horizontal_irradiance_w_per_m2"
                ][step_index]
            )
            ordered[f"pv_generation_{step_index}"] = float(
                result.pv_generation_kw[step_index]
            )
            ordered[f"load_{step_index}"] = float(result.site_electric_load_kw[step_index])
            ordered[f"controller_request_{step_index}"] = float(
                result.requested_battery_power_kw[step_index]
            )
            ordered[f"battery_power_{step_index}"] = float(
                result.realized_battery_power_kw[step_index]
            )
            ordered[f"battery_soc_{step_index}"] = float(result.battery_soc[step_index])
            ordered[f"grid_available_{step_index}"] = not bool(
                result.blackout_active[step_index]
            )
            ordered[f"unmet_load_{step_index}"] = float(result.unmet_load_kw[step_index])
        ordered.update(metrics.to_dict())
        ordered[request.adequacy_event.event_target_name] = request.adequacy_event.evaluate(
            metrics
        )
        rows.append({name: ordered[name] for name in _study_column_order(request)})
    return tuple(rows)


def _study_column_order(request: PlanningStudyRequest) -> tuple[str, ...]:
    return (
        *_DESIGN_COLUMNS,
        *(f"ghi_{index}" for index in range(request.horizon_steps)),
        *(f"pv_generation_{index}" for index in range(request.horizon_steps)),
        *(f"load_{index}" for index in range(request.horizon_steps)),
        *(f"controller_request_{index}" for index in range(request.horizon_steps)),
        *(f"battery_power_{index}" for index in range(request.horizon_steps)),
        *(f"battery_soc_{index}" for index in range(request.horizon_steps)),
        *(f"grid_available_{index}" for index in range(request.horizon_steps)),
        *(f"unmet_load_{index}" for index in range(request.horizon_steps)),
        "shortfall_ratio",
        "unmet_energy_kwh",
        "unmet_timestep_fraction",
        request.adequacy_event.event_target_name,
    )


def _validate_physical_configuration(
    scenario: object,
    configuration: PlanningConfiguration,
    tolerance: float,
) -> None:
    comparisons = {
        "battery_capacity_kwh": (
            float(scenario.battery.capacity_kwh),
            configuration.battery.capacity_kwh,
        ),
        "battery_max_charge_kw": (
            float(scenario.battery.max_charge_kw),
            configuration.battery.max_charge_kw,
        ),
        "battery_max_discharge_kw": (
            float(scenario.battery.max_discharge_kw),
            configuration.battery.max_discharge_kw,
        ),
        "solar_capacity_kw": (
            float(scenario.pv.rated_power_kw),
            configuration.solar.capacity_kw,
        ),
    }
    mismatched = [
        name for name, (actual, expected) in comparisons.items()
        if abs(actual - expected) > tolerance
    ]
    if mismatched:
        raise ValueError(
            "simulator design metadata does not match physical configuration: "
            + ", ".join(mismatched)
        )


def _artifact_identity(value: object) -> str:
    for name in ("artifact_id", "dataset_id", "source_path"):
        resolved = getattr(value, name, None)
        if resolved:
            return str(resolved)
    return str(value)


def _input_fingerprint(
    request: PlanningStudyRequest,
    *,
    weather_artifact: object,
    demand_artifact: object,
    base_scenario_reference: object,
    cooling_service_configuration: object,
) -> str:
    payload: dict[str, Any] = {
        "simulation_semantics_version": PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION,
        "request": request.to_dict(),
        "weather_artifact": _artifact_identity(weather_artifact),
        "demand_artifact": _artifact_identity(demand_artifact),
        "base_scenario": repr(base_scenario_reference),
        "cooling_service_configuration": repr(cooling_service_configuration),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _register_reloaded_dataclass_reducers(value: object) -> None:
    """Keep spawn pickling valid after deliberate package-module reload tests."""

    seen: set[int] = set()

    def visit(item: object) -> None:
        identity = id(item)
        if identity in seen:
            return
        seen.add(identity)
        if is_dataclass(item) and not isinstance(item, type):
            item_type = type(item)
            module = importlib.import_module(item_type.__module__)
            current_type = _resolve_qualified_name(module, item_type.__qualname__)
            if current_type is not item_type:
                copyreg.pickle(item_type, _reduce_reloaded_dataclass)
            for item_field in fields(item):
                visit(getattr(item, item_field.name))
        elif isinstance(item, dict):
            for key, nested in item.items():
                visit(key)
                visit(nested)
        elif isinstance(item, tuple | list):
            for nested in item:
                visit(nested)

    visit(value)


def _reduce_reloaded_dataclass(value: object) -> tuple[object, tuple[object, ...]]:
    payload = {
        item_field.name: getattr(value, item_field.name)
        for item_field in fields(value)
    }
    return (
        _reconstruct_reloaded_dataclass,
        (type(value).__module__, type(value).__qualname__, payload),
    )


def _reconstruct_reloaded_dataclass(
    module_name: str,
    qualified_name: str,
    payload: dict[str, object],
) -> object:
    module = importlib.import_module(module_name)
    item_type = _resolve_qualified_name(module, qualified_name)
    return item_type(**payload)


def _resolve_qualified_name(module: object, qualified_name: str) -> object:
    value = module
    for component in qualified_name.split("."):
        value = getattr(value, component)
    return value


__all__ = [
    "PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION",
    "generate_planning_study_dataset",
]
