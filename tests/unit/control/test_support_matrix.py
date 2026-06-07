"""Support-matrix and unsupported-scenario coverage for native controllers."""

from __future__ import annotations

import importlib
from collections.abc import Mapping

import pytest


EXPECTED_SUPPORT_MATRIX = {
    "PriceThresholdController": {"ArbitrageScenario"},
    "SocGuardrailController": {"ArbitrageScenario", "BatteryLoadPVScenario"},
    "PVSelfConsumptionController": {"BatteryLoadPVScenario"},
}


def _load_control_config_module():
    return importlib.import_module("open_energy_lab.control._config")


def _field(value: object, field_name: str) -> object:
    if isinstance(value, Mapping):
        return value[field_name]
    return getattr(value, field_name)


def test_shipped_controller_support_declarations_match_contract() -> None:
    module = _load_control_config_module()

    declarations = getattr(module, "SHIPPED_CONTROLLER_SUPPORT")

    assert set(declarations) == set(EXPECTED_SUPPORT_MATRIX)

    for controller_name, expected_scenarios in EXPECTED_SUPPORT_MATRIX.items():
        declaration = declarations[controller_name]

        assert _field(declaration, "controller_name") == controller_name
        assert set(_field(declaration, "supported_scenario_kinds")) == expected_scenarios

        unsupported_reason_template = _field(
            declaration,
            "unsupported_reason_template",
        )
        assert isinstance(unsupported_reason_template, str)
        assert unsupported_reason_template


@pytest.mark.parametrize(
    ("controller_name", "scenario_kind"),
    (
        ("PriceThresholdController", "ArbitrageScenario"),
        ("SocGuardrailController", "ArbitrageScenario"),
        ("SocGuardrailController", "BatteryLoadPVScenario"),
        ("PVSelfConsumptionController", "BatteryLoadPVScenario"),
    ),
)
def test_supported_scenarios_are_accepted_by_support_guard(
    controller_name: str,
    scenario_kind: str,
) -> None:
    module = _load_control_config_module()

    require_supported_scenario = getattr(module, "require_supported_scenario")

    require_supported_scenario(controller_name, scenario_kind)


@pytest.mark.parametrize(
    ("controller_name", "scenario_kind"),
    (
        ("PriceThresholdController", "BatteryLoadPVScenario"),
        ("PVSelfConsumptionController", "ArbitrageScenario"),
    ),
)
def test_unsupported_scenarios_fail_immediately_with_deterministic_reason(
    controller_name: str,
    scenario_kind: str,
) -> None:
    module = _load_control_config_module()

    require_supported_scenario = getattr(module, "require_supported_scenario")

    with pytest.raises(ValueError) as first_error:
        require_supported_scenario(controller_name, scenario_kind)

    with pytest.raises(ValueError) as second_error:
        require_supported_scenario(controller_name, scenario_kind)

    assert str(first_error.value) == str(second_error.value)
    assert controller_name in str(first_error.value)
    assert scenario_kind in str(first_error.value)
    assert "unsupported" in str(first_error.value).lower()


def test_package_root_controller_exports_align_with_support_declarations() -> None:
    config_module = _load_control_config_module()
    root_module = importlib.import_module("open_energy_lab.control")

    declarations = getattr(config_module, "SHIPPED_CONTROLLER_SUPPORT")
    controller_exports = {
        name for name in root_module.__all__ if name.endswith("Controller")
    }

    assert controller_exports == set(declarations)
