"""Unit contracts for simulator-owned planning dataset export."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from open_energy_lab.simulator.planning_export import (
    PlanningExportRequest,
    SUPPORTED_PLANNING_TARGETS,
    export_planning_dataset,
)


@dataclass(frozen=True, slots=True)
class _WeatherTrace:
    scenario_index: int
    derived_identity: str
    timestamp_utc: tuple[str, ...]
    timestep_hours: float
    canonical_field_series: dict[str, tuple[float, ...]]


@dataclass(frozen=True, slots=True)
class _WeatherFamily:
    family_id: str
    family_seed: int
    scenario_count: int
    num_steps: int
    timestep_hours: float
    sampled_traces: tuple[_WeatherTrace, ...]


@dataclass(frozen=True, slots=True)
class _ScenarioResult:
    scenario_index: int
    weather_reference: str
    site_electric_load_kw: tuple[float, ...]
    unmet_load_kw: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class _FamilyResult:
    family_id: str
    scenario_results: tuple[_ScenarioResult, ...]
    paired_family_seed: int
    timestep_hours: float


def _aligned_weather_family() -> _WeatherFamily:
    return _WeatherFamily(
        family_id="weather-family:unit-test",
        family_seed=13,
        scenario_count=2,
        num_steps=3,
        timestep_hours=24.0,
        sampled_traces=(
            _WeatherTrace(
                scenario_index=0,
                derived_identity="weather-family:unit-test:scenario-0",
                timestamp_utc=(
                    "2026-01-01T00:00:00Z",
                    "2026-01-02T00:00:00Z",
                    "2026-01-03T00:00:00Z",
                ),
                timestep_hours=24.0,
                canonical_field_series={
                    "dry_bulb_air_temperature_c": (30.0, 31.0, 32.0),
                    "global_horizontal_irradiance_w_per_m2": (500.0, 600.0, 700.0),
                    "direct_beam_irradiance_w_per_m2": (200.0, 250.0, 300.0),
                    "diffuse_horizontal_irradiance_w_per_m2": (120.0, 130.0, 140.0),
                },
            ),
            _WeatherTrace(
                scenario_index=1,
                derived_identity="weather-family:unit-test:scenario-1",
                timestamp_utc=(
                    "2026-01-01T00:00:00Z",
                    "2026-01-02T00:00:00Z",
                    "2026-01-03T00:00:00Z",
                ),
                timestep_hours=24.0,
                canonical_field_series={
                    "dry_bulb_air_temperature_c": (29.0, 30.0, 31.0),
                    "global_horizontal_irradiance_w_per_m2": (450.0, 550.0, 650.0),
                    "direct_beam_irradiance_w_per_m2": (190.0, 240.0, 290.0),
                    "diffuse_horizontal_irradiance_w_per_m2": (110.0, 120.0, 130.0),
                },
            ),
        ),
    )


def _aligned_family_result() -> _FamilyResult:
    return _FamilyResult(
        family_id="paired-family:unit-test",
        paired_family_seed=13,
        timestep_hours=24.0,
        scenario_results=(
            _ScenarioResult(
                scenario_index=0,
                weather_reference="weather-family:unit-test:scenario-0",
                site_electric_load_kw=(10.0, 20.0, 30.0),
                unmet_load_kw=(0.0, 0.0, 3.0),
            ),
            _ScenarioResult(
                scenario_index=1,
                weather_reference="weather-family:unit-test:scenario-1",
                site_electric_load_kw=(5.0, 15.0, 25.0),
                unmet_load_kw=(0.0, 1.0, 0.0),
            ),
        ),
    )


def _design_metadata_rows() -> tuple[dict[str, object], ...]:
    return (
        {
            "scenario_index": 0,
            "battery_capacity_kwh": 8.0,
            "solar_capacity_kw": 4.0,
            "design_name": "baseline-a",
        },
        {
            "scenario_index": 1,
            "battery_capacity_kwh": 10.0,
            "solar_capacity_kw": 5.0,
            "design_name": "baseline-b",
        },
    )


def _request(*, flattened_series_fields: tuple[str, ...]) -> PlanningExportRequest:
    return PlanningExportRequest(
        export_id="planning-export-unit",
        flattened_series_fields=flattened_series_fields,
        design_metadata_rows=_design_metadata_rows(),
        target_name="shortfall",
        include_provenance=True,
        numeric_tolerance=1e-9,
    )


def test_planning_export_request_defaults_to_shortfall_target() -> None:
    request = _request(
        flattened_series_fields=(
            "global_horizontal_irradiance_w_per_m2",
            "site_electric_load_kw",
            "unmet_load_kw",
        )
    )

    assert SUPPORTED_PLANNING_TARGETS == ("shortfall",)
    assert request.target_name == "shortfall"
    assert request.design_metadata_rows == _design_metadata_rows()
    assert request.include_provenance is True
    assert request.numeric_tolerance == pytest.approx(1e-9)


def test_export_planning_dataset_rejects_missing_design_rows_for_scenarios() -> None:
    request = PlanningExportRequest(
        export_id="planning-export-unit",
        flattened_series_fields=(
            "global_horizontal_irradiance_w_per_m2",
            "site_electric_load_kw",
        ),
        design_metadata_rows=_design_metadata_rows()[:1],
        target_name="shortfall",
        include_provenance=True,
        numeric_tolerance=1e-9,
    )

    with pytest.raises(ValueError, match="design metadata|row|scenario"):
        export_planning_dataset(
            family_result_reference=_aligned_family_result(),
            weather_family_reference=_aligned_weather_family(),
            request=request,
        )


def test_export_planning_dataset_rejects_weather_scenario_order_mismatch() -> None:
    weather_family = _aligned_weather_family()
    misordered_weather_family = _WeatherFamily(
        family_id=weather_family.family_id,
        family_seed=weather_family.family_seed,
        scenario_count=weather_family.scenario_count,
        num_steps=weather_family.num_steps,
        timestep_hours=weather_family.timestep_hours,
        sampled_traces=tuple(reversed(weather_family.sampled_traces)),
    )

    with pytest.raises(ValueError, match="align|scenario|order"):
        export_planning_dataset(
            family_result_reference=_aligned_family_result(),
            weather_family_reference=misordered_weather_family,
            request=_request(
                flattened_series_fields=(
                    "global_horizontal_irradiance_w_per_m2",
                    "site_electric_load_kw",
                    "unmet_load_kw",
                )
            ),
        )


def test_export_planning_dataset_rejects_unsupported_flattened_series_fields() -> None:
    with pytest.raises(ValueError, match="unsupported|flattened|field"):
        export_planning_dataset(
            family_result_reference=_aligned_family_result(),
            weather_family_reference=_aligned_weather_family(),
            request=_request(
                flattened_series_fields=(
                    "pv_capacity_factor",
                    "site_electric_load_kw",
                )
            ),
        )
