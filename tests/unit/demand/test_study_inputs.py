from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta

import pytest

from open_energy_lab.demand.study_inputs import (
    SyntheticCommercialDemandConfig,
    build_measured_demand_training_payload,
    build_synthetic_demand_training_payload,
)
from open_energy_lab.weather.tmy import fetch_tmy_dataset
from tests.integration.weather.fixture_utils import (
    RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH,
    load_weather_fixture,
)


def _canonical_dataset():
    return fetch_tmy_dataset(
        24.4539,
        54.3773,
        recorded_response=load_weather_fixture(
            RECORDED_PVGIS_TMY_RESPONSE_FIXTURE_PATH
        ),
        timezone_name="Asia/Dubai",
    )


def test_synthetic_small_commercial_payload_is_labeled_and_reproducible() -> None:
    dataset = _canonical_dataset()
    config = SyntheticCommercialDemandConfig(random_seed=41)

    first = build_synthetic_demand_training_payload(dataset, config=config)
    repeated = build_synthetic_demand_training_payload(dataset, config=config)

    assert first == repeated
    assert first["provenance"]["demand_source_mode"] == "synthetic"
    assert first["provenance"]["site_calibration_status"] == "not_site_calibrated"
    assert len(first["non_thermal_electric_demand_kw"]) == len(dataset.timestamp_utc)
    assert min(first["non_thermal_electric_demand_kw"]) >= 0.0
    assert min(first["cooling_demand_rt"]) >= 0.0


def _write_measured_csv(path, *, day_count: int, include_cooling: bool = True) -> None:
    fields = [
        "timestamp_utc",
        "dry_bulb_air_temperature_c",
        "relative_humidity_pct",
        "global_horizontal_irradiance_w_per_m2",
        "non_thermal_electric_demand_kw",
    ]
    if include_cooling:
        fields.append("cooling_demand_rt")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        start = datetime(2024, 1, 1, tzinfo=UTC)
        for index in range(day_count * 24):
            timestamp = start + timedelta(hours=index)
            row = {
                "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
                "dry_bulb_air_temperature_c": 30.0,
                "relative_humidity_pct": 60.0,
                "global_horizontal_irradiance_w_per_m2": 500.0,
                "non_thermal_electric_demand_kw": 20.0,
            }
            if include_cooling:
                row["cooling_demand_rt"] = 15.0
            writer.writerow(row)


def test_measured_csv_requires_ninety_complete_hourly_days(tmp_path) -> None:
    short_path = tmp_path / "short.csv"
    _write_measured_csv(short_path, day_count=89)

    with pytest.raises(ValueError, match="at least 90 complete hourly days"):
        build_measured_demand_training_payload(
            short_path,
            timezone_name="UTC",
        )

    valid_path = tmp_path / "valid.csv"
    _write_measured_csv(valid_path, day_count=90)
    payload = build_measured_demand_training_payload(
        valid_path,
        timezone_name="UTC",
    )
    assert len(payload["timestamp_utc"]) == 90 * 24
    assert payload["provenance"]["demand_source_mode"] == "measured_csv"


def test_measured_total_electricity_without_separate_cooling_is_rejected(tmp_path) -> None:
    path = tmp_path / "total-only.csv"
    path.write_text(
        "timestamp_utc,dry_bulb_air_temperature_c,relative_humidity_pct,"
        "global_horizontal_irradiance_w_per_m2,total_electric_demand_kw\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="double count cooling"):
        build_measured_demand_training_payload(path, timezone_name="UTC")

