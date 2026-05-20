"""Contract tests for foundational weather-field metadata."""

from __future__ import annotations

import pytest

from open_energy_lab.simulator._weather_schema import (
    DEFERRED_STANDARD_WEATHER_FIELD_NAMES,
    IRRADIANCE_FIELD_NAMES,
    REQUIRED_WEATHER_FIELD_NAMES,
    canonical_tmy_label,
    get_weather_field_spec,
    is_deferred_standard_weather_field,
    validate_weather_field_names,
)


def test_required_and_irradiance_fields_keep_canonical_tmy_mappings() -> None:
    assert REQUIRED_WEATHER_FIELD_NAMES == (
        "timestamp_utc",
        "dry_bulb_air_temperature_c",
    )
    assert IRRADIANCE_FIELD_NAMES == (
        "global_horizontal_irradiance_w_per_m2",
        "direct_beam_irradiance_w_per_m2",
        "diffuse_horizontal_irradiance_w_per_m2",
    )
    assert canonical_tmy_label("timestamp_utc") == "Date & time (UTC)"
    assert canonical_tmy_label("dry_bulb_air_temperature_c") == "T2m [°C]"
    assert canonical_tmy_label("global_horizontal_irradiance_w_per_m2") == "G(h) [W/m2]"


def test_deferred_standard_fields_remain_explicit() -> None:
    assert DEFERRED_STANDARD_WEATHER_FIELD_NAMES == (
        "relative_humidity_pct",
        "infrared_radiation_downwards_w_per_m2",
        "windspeed_10m_m_per_s",
        "wind_direction_10m_deg",
        "surface_air_pressure_pa",
    )
    assert is_deferred_standard_weather_field("relative_humidity_pct") is True
    assert is_deferred_standard_weather_field("timestamp_utc") is False
    spec = get_weather_field_spec("surface_air_pressure_pa")
    assert spec.tmy_label == "SP [Pa]"


def test_validate_weather_field_names_accepts_canonical_human_readable_names() -> None:
    assert validate_weather_field_names(
        [
            "timestamp_utc",
            "dry_bulb_air_temperature_c",
            "global_horizontal_irradiance_w_per_m2",
        ]
    ) == (
        "timestamp_utc",
        "dry_bulb_air_temperature_c",
        "global_horizontal_irradiance_w_per_m2",
    )


def test_validate_weather_field_names_rejects_unknown_or_duplicate_names() -> None:
    with pytest.raises(ValueError, match="unknown weather field 'T2m \\[°C\\]'"):
        validate_weather_field_names(["T2m [°C]"])

    with pytest.raises(ValueError, match="unknown weather field 'ambient_temperature_c'"):
        validate_weather_field_names(["ambient_temperature_c"])

    with pytest.raises(ValueError, match="duplicate weather field 'timestamp_utc'"):
        validate_weather_field_names(["timestamp_utc", "timestamp_utc"])
