"""Unit contracts for cooling-service configuration and conversion helpers."""

from __future__ import annotations

import importlib

import pytest

from open_energy_lab.simulator._units import DEFAULT_ABSOLUTE_TOLERANCE


def _demand_module():
    try:
        return importlib.import_module("open_energy_lab.simulator.demand")
    except ModuleNotFoundError:
        pytest.fail("open_energy_lab.simulator.demand is not implemented")


def test_local_electric_cooling_configuration_requires_positive_kw_per_rt() -> None:
    module = _demand_module()

    with pytest.raises(ValueError, match="electric_kw_per_rt"):
        module.LocalElectricCoolingConfiguration(
            source_name="invalid-local-cooling",
            electric_kw_per_rt=0.0,
            valid_for_feature_version="008-weather-demand-modeling",
        )


def test_derive_local_cooling_electric_kw_scales_rt_trace() -> None:
    module = _demand_module()
    config = module.LocalElectricCoolingConfiguration(
        source_name="unit-test-local-cooling",
        electric_kw_per_rt=1.25,
        valid_for_feature_version="008-weather-demand-modeling",
        notes="Deterministic first-release conversion factor.",
    )

    derived_kw = module.derive_local_cooling_electric_kw(
        cooling_demand_rt=[0.0, 2.5, 4.0],
        config=config,
    )

    assert derived_kw == pytest.approx(
        [0.0, 3.125, 5.0],
        abs=DEFAULT_ABSOLUTE_TOLERANCE,
    )


def test_cooling_service_configuration_accepts_exactly_one_service_path() -> None:
    module = _demand_module()
    local_config = module.LocalElectricCoolingConfiguration(
        source_name="unit-test-local-cooling",
        electric_kw_per_rt=1.1,
        valid_for_feature_version="008-weather-demand-modeling",
    )
    district_tariff = module.DistrictCoolingTariff(
        currency="USD",
        rate_per_rt_hour=0.22,
        time_alignment="step-start",
        tariff_name="unit-test-district",
    )

    with pytest.raises(ValueError, match="exactly one|mixed|service path"):
        module.CoolingServiceConfiguration(
            service_path="local-electric",
            local_electric_cooling=local_config,
            district_cooling_tariff=district_tariff,
            source="unit-test",
        )

    with pytest.raises(ValueError, match="district|tariff"):
        module.CoolingServiceConfiguration(
            service_path="district-cooling",
            source="unit-test",
        )
