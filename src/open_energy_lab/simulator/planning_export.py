"""Simulator-owned planning dataset export workflow.

Migration evidence:
- Preserve the legacy emphasis on scenario-level time-series signals from
  `legacy/old_tpm/src_py/simulator/feature_engineering.py`.
- Improve the contract by exporting deterministic raw horizon columns such as
  `ghi_<step>` and `load_<step>` instead of expanding notebook-era aggregate
  feature sets from `add_aggregate_features()`.
- Reject notebook-owned binary target engineering such as
  `add_simple_binary_indicator()`. The library owns a numeric `shortfall`
  target derived directly from simulator `unmet_load_kw` and
  `site_electric_load_kw` traces.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from open_energy_lab.planning.dataset import PlanningDatasetArtifact


FEATURE_NAME = "009-tpm-planning"
SUPPORTED_PLANNING_TARGETS = ("shortfall",)
PLANNING_DATASET_SCHEMA_VERSION = "v1"
_TARGET_DEFAULT_THRESHOLD = 0.05
_EVENT_TARGET_NAME = "shortfall_exceeds_threshold"
_ROW_ORDER_POLICY = "scenario_index_ascending"
# Preserve raw horizon flattening used by the historical simulator
# feature-engineering workflow, but collapse the public export contract to the
# exact series fields the first planning dataset needs instead of migrating all
# aggregate columns.
_FLATTENED_FIELD_PREFIXES = {
    "global_horizontal_irradiance_w_per_m2": "ghi",
    "site_electric_load_kw": "load",
    "unmet_load_kw": "unmet_load",
}
_WEATHER_SERIES_FIELDS = frozenset({"global_horizontal_irradiance_w_per_m2"})


@dataclass(frozen=True, slots=True)
class PlanningExportRequest:
    """Simulator-owned request for exporting a planning-ready dataset artifact."""

    export_id: str
    flattened_series_fields: tuple[str, ...]
    design_metadata_rows: tuple[Mapping[str, object], ...] = field(default_factory=tuple)
    target_name: str = "shortfall"
    include_provenance: bool = True
    numeric_tolerance: float = 1e-9


def export_planning_dataset(
    *,
    family_result_reference: object,
    weather_family_reference: object,
    request: PlanningExportRequest,
) -> PlanningDatasetArtifact:
    """Export one deterministic planning dataset artifact from aligned simulator families."""

    flattened_series_fields = _validated_flattened_series_fields(
        request.flattened_series_fields
    )
    _validate_request(request, flattened_series_fields)

    scenario_results = tuple(getattr(family_result_reference, "scenario_results"))
    weather_traces = tuple(getattr(weather_family_reference, "sampled_traces"))
    design_rows = tuple(request.design_metadata_rows)

    _validate_alignment(
        family_result_reference=family_result_reference,
        weather_family_reference=weather_family_reference,
        scenario_results=scenario_results,
        weather_traces=weather_traces,
        design_rows=design_rows,
        flattened_series_fields=flattened_series_fields,
        numeric_tolerance=request.numeric_tolerance,
    )

    design_columns = tuple(str(column_name) for column_name in design_rows[0].keys())
    horizon_steps = int(getattr(weather_family_reference, "num_steps"))
    timestep_hours = float(getattr(family_result_reference, "timestep_hours"))
    column_order = (
        *design_columns,
        *tuple(
            f"{_FLATTENED_FIELD_PREFIXES[field_name]}_{step_index}"
            for field_name in flattened_series_fields
            for step_index in range(horizon_steps)
        ),
        request.target_name,
        _EVENT_TARGET_NAME,
    )

    rows = tuple(
        _build_row(
            scenario_result=scenario_result,
            weather_trace=weather_trace,
            design_row=design_row,
            flattened_series_fields=flattened_series_fields,
            timestep_hours=timestep_hours,
            numeric_tolerance=request.numeric_tolerance,
        )
        for scenario_result, weather_trace, design_row in zip(
            scenario_results,
            weather_traces,
            design_rows,
            strict=True,
        )
    )

    return PlanningDatasetArtifact(
        dataset_id=request.export_id,
        schema_version=PLANNING_DATASET_SCHEMA_VERSION,
        row_count=len(rows),
        horizon_steps=horizon_steps,
        timestep_hours=timestep_hours,
        column_order=column_order,
        rows=rows,
        design_feature_schema=_design_feature_schema(design_columns, design_rows[0]),
        series_field_schema={
            _FLATTENED_FIELD_PREFIXES[field_name]: {
                "source_field": field_name,
                "column_prefix": _FLATTENED_FIELD_PREFIXES[field_name],
            }
            for field_name in flattened_series_fields
        },
        target_metadata={
            "target_name": request.target_name,
            "event_target_name": _EVENT_TARGET_NAME,
            "numerator_source_field": "unmet_load_kw",
            "denominator_source_field": "site_electric_load_kw",
            "aggregation_rule": (
                "sum(unmet_load_kw * timestep_hours) / "
                "sum(site_electric_load_kw * timestep_hours)"
            ),
            "threshold_default": _TARGET_DEFAULT_THRESHOLD,
            "event_threshold_source": "threshold_default",
            "event_threshold_comparison": ">",
            "supported_query_mode": "exceedance-probability",
        },
        provenance=(
            {
                "family_id": str(getattr(family_result_reference, "family_id")),
                "weather_family_id": str(getattr(weather_family_reference, "family_id")),
                "family_seed": int(getattr(weather_family_reference, "family_seed")),
                "paired_family_seed": int(getattr(family_result_reference, "paired_family_seed")),
            }
            if request.include_provenance
            else {}
        ),
        export_configuration={
            "row_order_policy": _ROW_ORDER_POLICY,
            "flattened_series_fields": list(flattened_series_fields),
            "include_provenance": request.include_provenance,
            "numeric_tolerance": request.numeric_tolerance,
            "target_name": request.target_name,
        },
    )


def _validate_request(
    request: PlanningExportRequest,
    flattened_series_fields: tuple[str, ...],
) -> None:
    if not request.export_id:
        raise ValueError("export_id must be non-empty")
    if request.numeric_tolerance <= 0:
        raise ValueError("numeric_tolerance must be positive")
    if request.target_name not in SUPPORTED_PLANNING_TARGETS:
        raise ValueError(
            "target_name must be limited to the supported planning targets: "
            + ", ".join(SUPPORTED_PLANNING_TARGETS)
        )
    if not flattened_series_fields:
        raise ValueError("flattened_series_fields must not be empty")
    if not request.design_metadata_rows:
        raise ValueError("design metadata rows must not be empty")


def _validated_flattened_series_fields(flattened_series_fields: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(field_name) for field_name in flattened_series_fields))
    unsupported = [
        field_name for field_name in normalized if field_name not in _FLATTENED_FIELD_PREFIXES
    ]
    if unsupported:
        raise ValueError(
            "unsupported flattened field request; supported flattened fields are: "
            + ", ".join(sorted(_FLATTENED_FIELD_PREFIXES))
        )
    return normalized


def _validate_alignment(
    *,
    family_result_reference: object,
    weather_family_reference: object,
    scenario_results: tuple[object, ...],
    weather_traces: tuple[object, ...],
    design_rows: tuple[Mapping[str, object], ...],
    flattened_series_fields: tuple[str, ...],
    numeric_tolerance: float,
) -> None:
    scenario_count = len(scenario_results)
    if scenario_count == 0:
        raise ValueError("scenario_results must not be empty")
    if len(weather_traces) != scenario_count:
        raise ValueError("weather traces must align with simulator scenario count")
    if len(design_rows) != scenario_count:
        raise ValueError("design metadata rows must align with simulator scenario count")

    declared_weather_count = int(getattr(weather_family_reference, "scenario_count"))
    if declared_weather_count != scenario_count:
        raise ValueError("weather family scenario_count must align with sampled traces")

    scenario_indices = [int(getattr(result, "scenario_index")) for result in scenario_results]
    weather_indices = [int(getattr(trace, "scenario_index")) for trace in weather_traces]
    design_indices = [_scenario_index_from_design_row(row) for row in design_rows]

    expected_order = list(range(scenario_count))
    if scenario_indices != expected_order:
        raise ValueError("simulator scenario order must be scenario_index ascending")
    if weather_indices != scenario_indices:
        raise ValueError("weather traces must align with simulator scenario order")
    if design_indices != scenario_indices:
        raise ValueError("design metadata rows must align with simulator scenario order")

    design_columns = tuple(str(column_name) for column_name in design_rows[0].keys())
    for design_row in design_rows[1:]:
        if tuple(str(column_name) for column_name in design_row.keys()) != design_columns:
            raise ValueError("design metadata rows must share consistent feature names")

    horizon_steps = int(getattr(weather_family_reference, "num_steps"))
    if horizon_steps <= 0:
        raise ValueError("weather family num_steps must be positive")

    weather_timestep = float(getattr(weather_family_reference, "timestep_hours"))
    family_timestep = float(getattr(family_result_reference, "timestep_hours"))
    if abs(weather_timestep - family_timestep) > numeric_tolerance:
        raise ValueError("weather family and simulator family timestep_hours must align")

    weather_seed = int(getattr(weather_family_reference, "family_seed"))
    family_seed = int(getattr(family_result_reference, "paired_family_seed"))
    if weather_seed != family_seed:
        raise ValueError("weather and simulator family seeds must align")

    for scenario_result, weather_trace in zip(scenario_results, weather_traces, strict=True):
        if str(getattr(scenario_result, "weather_reference")) != str(
            getattr(weather_trace, "derived_identity")
        ):
            raise ValueError("weather references must align by scenario and order")

        for field_name in flattened_series_fields:
            series_values = _series_values_for_export(
                scenario_result=scenario_result,
                weather_trace=weather_trace,
                field_name=field_name,
            )
            if len(series_values) != horizon_steps:
                raise ValueError("flattened field series length must align with family horizon")

        if len(tuple(getattr(weather_trace, "timestamp_utc"))) != horizon_steps:
            raise ValueError("weather trace timestamps must align with family horizon")
        if len(tuple(getattr(scenario_result, "site_electric_load_kw"))) != horizon_steps:
            raise ValueError("site_electric_load_kw must align with family horizon")
        if len(tuple(getattr(scenario_result, "unmet_load_kw"))) != horizon_steps:
            raise ValueError("unmet_load_kw must align with family horizon")


def _scenario_index_from_design_row(design_row: Mapping[str, object]) -> int:
    if "scenario_index" not in design_row:
        raise ValueError("design metadata rows must include scenario_index")
    return int(design_row["scenario_index"])


def _build_row(
    *,
    scenario_result: object,
    weather_trace: object,
    design_row: Mapping[str, object],
    flattened_series_fields: tuple[str, ...],
    timestep_hours: float,
    numeric_tolerance: float,
) -> Mapping[str, object]:
    row: dict[str, object] = {
        str(column_name): value for column_name, value in design_row.items()
    }
    for field_name in flattened_series_fields:
        prefix = _FLATTENED_FIELD_PREFIXES[field_name]
        series_values = _series_values_for_export(
            scenario_result=scenario_result,
            weather_trace=weather_trace,
            field_name=field_name,
        )
        for step_index, value in enumerate(series_values):
            row[f"{prefix}_{step_index}"] = value

    row["shortfall"] = _derive_shortfall(
        load_series=tuple(float(value) for value in getattr(scenario_result, "site_electric_load_kw")),
        unmet_load_series=tuple(float(value) for value in getattr(scenario_result, "unmet_load_kw")),
        timestep_hours=timestep_hours,
        numeric_tolerance=numeric_tolerance,
    )
    row[_EVENT_TARGET_NAME] = int(row["shortfall"] > _TARGET_DEFAULT_THRESHOLD)
    return row


def _series_values_for_export(
    *,
    scenario_result: object,
    weather_trace: object,
    field_name: str,
) -> tuple[float, ...]:
    if field_name in _WEATHER_SERIES_FIELDS:
        raw_values = getattr(weather_trace, "canonical_field_series")[field_name]
    else:
        raw_values = getattr(scenario_result, field_name)
    return tuple(float(value) for value in raw_values)


def _derive_shortfall(
    *,
    load_series: tuple[float, ...],
    unmet_load_series: tuple[float, ...],
    timestep_hours: float,
    numeric_tolerance: float,
) -> float:
    # The legacy reference file experimented with engineered blackout labels.
    # The unified library owns a reproducible numeric planning target instead:
    # unmet-load energy divided by total load energy over the exported horizon.
    unmet_energy = sum(unmet_load_series) * timestep_hours
    load_energy = sum(load_series) * timestep_hours
    if abs(load_energy) <= numeric_tolerance:
        if abs(unmet_energy) <= numeric_tolerance:
            return 0.0
        raise ValueError("shortfall target cannot be derived from zero total load energy")
    return unmet_energy / load_energy


def _design_feature_schema(
    design_columns: tuple[str, ...],
    design_row: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    feature_schema: list[Mapping[str, object]] = []
    for column_name in design_columns:
        if column_name == "scenario_index":
            continue
        feature_schema.append(
            {
                "feature_name": column_name,
                "feature_role": "decision",
                "feature_type": _design_feature_type(design_row[column_name]),
            }
        )
    return tuple(feature_schema)


def _design_feature_type(value: object) -> str:
    if isinstance(value, bool):
        return "binary"
    if isinstance(value, (int, float)):
        return "continuous"
    return "categorical"


__all__ = [
    "FEATURE_NAME",
    "PlanningExportRequest",
    "SUPPORTED_PLANNING_TARGETS",
    "export_planning_dataset",
]
