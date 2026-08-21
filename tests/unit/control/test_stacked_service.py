"""Contracts for deterministic fixed-schedule stacked-service baselines."""

from __future__ import annotations

import importlib
import inspect
import math
from types import ModuleType
from typing import Any

import pytest

from open_energy_lab.control import PriceThresholdConfig
from tests.unit.market.test_artifact import _build_artifact
from tests.unit.simulator.test_stacked_service import _battery, _fcr_schedule


def _module() -> ModuleType:
    try:
        return importlib.import_module("open_energy_lab.control.stacked_service")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "open_energy_lab.control.stacked_service is not implemented; "
            "T042-T043 must provide deterministic baseline builders",
            pytrace=False,
        )
        raise AssertionError from exc


def _require(name: str) -> Any:
    try:
        return getattr(_module(), name)
    except AttributeError:
        pytest.fail(
            f"open_energy_lab.control.stacked_service.{name} is not implemented",
            pytrace=False,
        )


def _threshold_config(*, request_kw: float = 9.0) -> PriceThresholdConfig:
    return PriceThresholdConfig(
        charge_below_import_price=51.0,
        discharge_above_import_price=55.0,
        charge_request_kw=request_kw,
        discharge_request_kw=request_kw,
        controller_name="feature-010-price-threshold",
    )


def _regulation_config(*, capacities: list[float] | None = None):
    config_type = _require("RegulationOnlyBaselineConfig")
    return config_type(
        schedule_id="regulation-only-unit-v1",
        semantics_version="regulation-only-no-recovery-v1",
        fcr_schedule=_fcr_schedule(capacities),
    )


def _arbitrage_config(*, request_kw: float = 9.0):
    config_type = _require("ArbitrageOnlyBaselineConfig")
    return config_type(
        schedule_id="arbitrage-only-unit-v1",
        semantics_version="price-threshold-fixed-v1",
        price_threshold_config=_threshold_config(request_kw=request_kw),
    )


def _stacked_config(*, request_kw: float = 9.0, capacities: list[float] | None = None):
    config_type = _require("StackedHeuristicConfig")
    return config_type(
        schedule_id="stacked-heuristic-unit-v1",
        semantics_version="headroom-clipped-price-threshold-v1",
        price_threshold_config=_threshold_config(request_kw=request_kw),
        fcr_schedule=_fcr_schedule(capacities),
    )


def test_regulation_only_uses_zero_energy_no_recovery_and_fixed_fcr() -> None:
    build = _require("build_regulation_only_baseline")
    fcr = _fcr_schedule([3.0, 4.0])
    config_type = _require("RegulationOnlyBaselineConfig")
    config = config_type(
        schedule_id="regulation-only-unit-v1",
        semantics_version="regulation-only-no-recovery-v1",
        fcr_schedule=fcr,
    )

    baseline = build(config, battery=_battery())

    assert [item.power_kw for item in baseline.energy_schedule.intervals] == [0.0] * 8
    assert baseline.fcr_schedule is fcr
    assert baseline.recovery_dispatch_kw == ()


def test_regulation_only_centers_initial_energy_with_directional_efficiencies() -> None:
    build = _require("build_regulation_only_baseline")
    battery = _battery(efficiency=0.92, min_soc=0.1, max_soc=0.9)

    baseline = build(_regulation_config(), battery=battery)

    efficiency_product = 0.92 * 0.92
    expected_kwh = (90.0 + efficiency_product * 10.0) / (1.0 + efficiency_product)
    assert baseline.initial_stored_energy_kwh == pytest.approx(expected_kwh)
    assert baseline.battery.initial_soc == pytest.approx(expected_kwh / 100.0)


def test_arbitrage_only_invokes_current_price_threshold_and_commits_zero_fcr() -> None:
    build = _require("build_arbitrage_only_baseline")

    baseline = build(
        _arbitrage_config(),
        market_artifact=_build_artifact(),
        battery=_battery(),
    )

    assert [item.power_kw for item in baseline.energy_schedule.intervals] == [
        9.0,
        9.0,
        0.0,
        0.0,
        0.0,
        0.0,
        -9.0,
        -9.0,
    ]
    assert all(item.capacity_kw == 0.0 for item in baseline.fcr_schedule.intervals)


def test_stacked_builder_clips_both_directions_after_reserving_fcr_headroom() -> None:
    build = _require("build_stacked_heuristic_baseline")

    baseline = build(
        _stacked_config(capacities=[5.0, 5.0]),
        market_artifact=_build_artifact(),
        battery=_battery(max_charge_kw=10.0, max_discharge_kw=10.0),
    )

    assert [item.power_kw for item in baseline.energy_schedule.intervals] == [
        5.0,
        5.0,
        0.0,
        0.0,
        0.0,
        0.0,
        -5.0,
        -5.0,
    ]


def test_stacked_builder_rejects_an_empty_admissible_power_interval() -> None:
    validation_error = _require("StackedBaselineValidationError")
    build = _require("build_stacked_heuristic_baseline")

    with pytest.raises(validation_error, match="empty|headroom|reserve"):
        build(
            _stacked_config(capacities=[11.0, 11.0]),
            market_artifact=_build_artifact(),
            battery=_battery(max_charge_kw=10.0, max_discharge_kw=10.0),
        )


def test_builders_are_deterministic_and_expose_no_activation_lookahead() -> None:
    build = _require("build_stacked_heuristic_baseline")
    kwargs = {
        "market_artifact": _build_artifact(),
        "battery": _battery(max_charge_kw=10.0, max_discharge_kw=10.0),
    }

    first = build(_stacked_config(), **kwargs)
    second = build(_stacked_config(), **kwargs)

    assert first.configuration_fingerprint == second.configuration_fingerprint
    assert first.energy_schedule.schedule_fingerprint == second.energy_schedule.schedule_fingerprint
    assert "activation" not in inspect.signature(build).parameters


def test_baseline_configs_reject_nonfinite_thresholds() -> None:
    validation_error = _require("StackedBaselineValidationError")
    config_type = _require("ArbitrageOnlyBaselineConfig")
    invalid_threshold = PriceThresholdConfig(
        charge_below_import_price=math.nan,
        discharge_above_import_price=55.0,
        charge_request_kw=5.0,
        discharge_request_kw=5.0,
    )

    with pytest.raises(validation_error, match="finite|threshold"):
        config_type(
            schedule_id="invalid",
            semantics_version="invalid-v1",
            price_threshold_config=invalid_threshold,
        )
