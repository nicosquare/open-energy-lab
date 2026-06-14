"""Unit coverage for cloud-event overlays and physical-bounds helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

import open_energy_lab.weather.events as weather_events


IRRADIANCE_FIELDS = (
    "global_horizontal_irradiance_w_per_m2",
    "direct_beam_irradiance_w_per_m2",
    "diffuse_horizontal_irradiance_w_per_m2",
)


def _field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


def _physical_bounds_policy() -> dict[str, object]:
    return {
        "bounds_by_field": {
            "dry_bulb_air_temperature_c": {"minimum": None, "maximum": None},
            "global_horizontal_irradiance_w_per_m2": {"minimum": 0.0, "maximum": None},
            "direct_beam_irradiance_w_per_m2": {"minimum": 0.0, "maximum": None},
            "diffuse_horizontal_irradiance_w_per_m2": {"minimum": 0.0, "maximum": None},
            "relative_humidity_pct": {"minimum": 0.0, "maximum": 100.0},
            "infrared_radiation_downwards_w_per_m2": {"minimum": 0.0, "maximum": None},
            "windspeed_10m_m_per_s": {"minimum": 0.0, "maximum": None},
            "wind_direction_10m_deg": {"minimum": 0.0, "maximum": 360.0},
            "surface_air_pressure_pa": {"minimum": 0.0, "maximum": None},
        },
        "non_negative_fields": [
            "global_horizontal_irradiance_w_per_m2",
            "direct_beam_irradiance_w_per_m2",
            "diffuse_horizontal_irradiance_w_per_m2",
            "relative_humidity_pct",
            "infrared_radiation_downwards_w_per_m2",
            "windspeed_10m_m_per_s",
            "surface_air_pressure_pa",
        ],
    }


def _unpack_overlay_result(result: object) -> tuple[Mapping[str, tuple[float, ...]], Sequence[object]]:
    if isinstance(result, tuple) and len(result) == 2:
        canonical_field_series, annotations = result
    else:
        canonical_field_series = _field(result, "canonical_field_series")
        annotations = _field(result, "cloud_event_annotations")
    assert isinstance(canonical_field_series, Mapping)
    assert isinstance(annotations, Sequence)
    return canonical_field_series, annotations


def test_apply_cloud_event_overlay_attenuates_contiguous_irradiance_steps_only() -> None:
    apply_cloud_event_overlay = getattr(weather_events, "apply_cloud_event_overlay")
    base_series = {
        "dry_bulb_air_temperature_c": (21.0, 22.0, 23.0, 24.0),
        "global_horizontal_irradiance_w_per_m2": (0.0, 400.0, 320.0, 0.0),
        "direct_beam_irradiance_w_per_m2": (0.0, 250.0, 200.0, 0.0),
        "diffuse_horizontal_irradiance_w_per_m2": (0.0, 150.0, 120.0, 0.0),
        "relative_humidity_pct": (40.0, 42.0, 44.0, 46.0),
        "infrared_radiation_downwards_w_per_m2": (300.0, 301.0, 302.0, 303.0),
        "windspeed_10m_m_per_s": (3.0, 3.1, 3.2, 3.3),
        "wind_direction_10m_deg": (90.0, 100.0, 110.0, 120.0),
        "surface_air_pressure_pa": (101000.0, 101005.0, 101010.0, 101015.0),
    }
    cloud_event_model = {
        "irradiance_fields": list(IRRADIANCE_FIELDS),
        "start_probability_by_local_step": [0.0, 1.0, 0.0, 0.0],
        "duration_distribution": {
            "kind": "empirical",
            "durations": [2],
            "probabilities": [1.0],
        },
        "attenuation_distribution": {
            "kind": "empirical",
            "attenuation_values": [0.25],
            "probabilities": [1.0],
        },
        "minimum_base_irradiance_w_per_m2": 50.0,
    }

    canonical_field_series, annotations = _unpack_overlay_result(
        apply_cloud_event_overlay(
            canonical_field_series=base_series,
            cloud_event_model=cloud_event_model,
            family_seed=5,
            scenario_index=0,
            physical_bounds_policy=_physical_bounds_policy(),
        )
    )

    assert canonical_field_series["global_horizontal_irradiance_w_per_m2"] == pytest.approx(
        (0.0, 300.0, 240.0, 0.0)
    )
    assert canonical_field_series["direct_beam_irradiance_w_per_m2"] == pytest.approx(
        (0.0, 187.5, 150.0, 0.0)
    )
    assert canonical_field_series["diffuse_horizontal_irradiance_w_per_m2"] == pytest.approx(
        (0.0, 112.5, 90.0, 0.0)
    )

    assert canonical_field_series["dry_bulb_air_temperature_c"] == base_series[
        "dry_bulb_air_temperature_c"
    ]
    assert canonical_field_series["relative_humidity_pct"] == base_series[
        "relative_humidity_pct"
    ]

    assert len(annotations) == 1
    annotation = annotations[0]
    assert _field(annotation, "start_index") == 1
    assert _field(annotation, "duration_steps") == 2
    assert _field(annotation, "attenuation_fraction") == pytest.approx(0.25)


def test_enforce_physical_bounds_clips_non_negative_and_bounded_fields() -> None:
    enforce_physical_bounds = getattr(weather_events, "enforce_physical_bounds")
    out_of_bounds_series = {
        "dry_bulb_air_temperature_c": (-5.0, 14.0, 30.0),
        "global_horizontal_irradiance_w_per_m2": (-10.0, 200.0, -1.0),
        "direct_beam_irradiance_w_per_m2": (-3.0, 150.0, 4.0),
        "diffuse_horizontal_irradiance_w_per_m2": (-1.0, 50.0, -2.0),
        "relative_humidity_pct": (-7.0, 55.0, 120.0),
        "infrared_radiation_downwards_w_per_m2": (-50.0, 310.0, 315.0),
        "windspeed_10m_m_per_s": (-2.0, 3.5, 1.0),
        "wind_direction_10m_deg": (-45.0, 180.0, 725.0),
        "surface_air_pressure_pa": (-5.0, 101100.0, 101050.0),
    }

    bounded_series = enforce_physical_bounds(
        canonical_field_series=out_of_bounds_series,
        physical_bounds_policy=_physical_bounds_policy(),
    )

    assert bounded_series["global_horizontal_irradiance_w_per_m2"] == pytest.approx(
        (0.0, 200.0, 0.0)
    )
    assert bounded_series["direct_beam_irradiance_w_per_m2"] == pytest.approx(
        (0.0, 150.0, 4.0)
    )
    assert bounded_series["diffuse_horizontal_irradiance_w_per_m2"] == pytest.approx(
        (0.0, 50.0, 0.0)
    )
    assert bounded_series["relative_humidity_pct"] == pytest.approx((0.0, 55.0, 100.0))
    assert bounded_series["infrared_radiation_downwards_w_per_m2"] == pytest.approx(
        (0.0, 310.0, 315.0)
    )
    assert bounded_series["windspeed_10m_m_per_s"] == pytest.approx((0.0, 3.5, 1.0))
    assert bounded_series["wind_direction_10m_deg"] == pytest.approx((0.0, 180.0, 360.0))
    assert bounded_series["surface_air_pressure_pa"] == pytest.approx(
        (0.0, 101100.0, 101050.0)
    )
