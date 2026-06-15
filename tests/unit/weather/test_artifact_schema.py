"""Unit coverage for weather artifact schema and loading rules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_energy_lab.weather._canonical import CANONICAL_WEATHER_FIELD_ORDER
from open_energy_lab.weather import WeatherSamplingRequest
from open_energy_lab.weather.artifact import (
    UnsupportedWeatherArtifactVersionError,
    load_weather_artifact,
)
from open_energy_lab.weather.fit import WeatherFitConfig, fit_weather_model


def _recorded_tmy_response() -> dict[str, object]:
    return {
        "source_name": "PVGIS TMY",
        "timezone_name": "America/Phoenix",
        "source_metadata": {"provider": "pvgis", "dataset_year": 2020},
        "records": [
            {
                "Date & time (UTC)": "2024-01-01T00:00:00Z",
                "T2m [°C]": 8.0,
                "G(h) [W/m2]": 0.0,
                "Gb(n) [W/m2]": 0.0,
                "Gd(h) [W/m2]": 0.0,
                "RH [%]": 45.0,
                "IR(h) [W/m2]": 280.0,
                "WS10m [m/s]": 2.1,
                "WD10m [°]": 90.0,
                "SP [Pa]": 101325.0,
            },
            {
                "Date & time (UTC)": "2024-01-01T01:00:00Z",
                "T2m [°C]": 9.0,
                "G(h) [W/m2]": 10.0,
                "Gb(n) [W/m2]": 4.0,
                "Gd(h) [W/m2]": 6.0,
                "RH [%]": 42.0,
                "IR(h) [W/m2]": 281.0,
                "WS10m [m/s]": 2.4,
                "WD10m [°]": 95.0,
                "SP [Pa]": 101300.0,
            },
            {
                "Date & time (UTC)": "2024-01-01T02:00:00Z",
                "T2m [°C]": 11.0,
                "G(h) [W/m2]": 30.0,
                "Gb(n) [W/m2]": 12.0,
                "Gd(h) [W/m2]": 18.0,
                "RH [%]": 39.0,
                "IR(h) [W/m2]": 282.0,
                "WS10m [m/s]": 2.8,
                "WD10m [°]": 100.0,
                "SP [Pa]": 101280.0,
            },
        ],
    }


def _write_artifact(path: Path) -> dict[str, object]:
    artifact = fit_weather_model(
        33.4484,
        -112.0740,
        recorded_response=_recorded_tmy_response(),
        fit_config=WeatherFitConfig(timestep_hours=1.0, notes=("unit-test",)),
        output_path=path,
    )
    return artifact.to_dict()


def test_fit_weather_model_persists_schema_and_provenance(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    written_payload = _write_artifact(artifact_path)

    persisted_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    reloaded = load_weather_artifact(artifact_path)

    assert persisted_payload["schema_version"] == "v1"
    assert persisted_payload["canonical_field_order"] == list(CANONICAL_WEATHER_FIELD_ORDER)
    assert persisted_payload["provenance"]["source_name"] == "PVGIS TMY"
    assert persisted_payload["provenance"]["source_metadata"]["provider"] == "pvgis"
    assert persisted_payload["training_record_summary"]["record_count"] == 3
    assert reloaded.artifact_id == written_payload["artifact_id"]
    assert reloaded.timestep_hours == pytest.approx(1.0)
    assert reloaded.supported_load_modes == ("offline",)


def test_load_weather_artifact_enforces_timestep_lock(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    _write_artifact(artifact_path)

    with pytest.raises(ValueError, match="expected artifact timestep_hours 0.5"):
        load_weather_artifact(artifact_path, expected_timestep_hours=0.5)


def test_load_weather_artifact_rejects_unsupported_versions(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    payload = _write_artifact(artifact_path)
    payload["schema_version"] = "v999"
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        UnsupportedWeatherArtifactVersionError,
        match="unsupported weather artifact schema_version 'v999'",
    ):
        load_weather_artifact(artifact_path)


def test_loaded_weather_artifact_can_sample_family_directly(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    _write_artifact(artifact_path)

    artifact = load_weather_artifact(artifact_path, expected_timestep_hours=1.0)
    family = artifact.sample_family(
        request=WeatherSamplingRequest(num_steps=3, scenario_count=2, family_seed=19),
        expected_timestep_hours=1.0,
    )

    assert family.artifact_reference == artifact.artifact_id
    assert family.scenario_count == 2


def test_load_weather_artifact_rejects_missing_sampling_parameters(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    payload = _write_artifact(artifact_path)
    del payload["base_model_parameters"]["physical_bounds_policy"]
    artifact_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="base_model_parameters is missing required keys: physical_bounds_policy",
    ):
        load_weather_artifact(artifact_path)
