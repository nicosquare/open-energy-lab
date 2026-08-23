"""Product-neutral restoration commitments, baselines, and capability tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import inspect
import re

import pytest

from open_energy_lab.control.restoration_service import (
    RestorationControlValidationError,
    build_directional_capacity_schedule,
    build_restoration_baseline_config,
    build_restoration_capability,
    build_restoration_energy_baseline_schedule,
)
from open_energy_lab.market.restoration_activation import (
    RestorationDirection,
    RestorationProduct,
)
from open_energy_lab.market.time import CanonicalInterval
from open_energy_lab.simulator.scenario import BatteryComponent


START = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
END = START + timedelta(hours=1)


def _interval(index: int) -> CanonicalInterval:
    start = START + timedelta(minutes=15 * index)
    return CanonicalInterval.from_utc(start, start + timedelta(minutes=15))


def _battery(
    *,
    initial_soc: float = 0.5,
    capacity_kwh: float = 1000.0,
    max_charge_kw: float = 500.0,
    max_discharge_kw: float = 500.0,
    efficiency: float = 0.95,
) -> BatteryComponent:
    return BatteryComponent(
        name="restoration-unit-battery",
        capacity_kwh=capacity_kwh,
        max_charge_kw=max_charge_kw,
        max_discharge_kw=max_discharge_kw,
        charge_efficiency=efficiency,
        discharge_efficiency=efficiency,
        initial_soc=initial_soc,
        min_soc=0.1,
        max_soc=0.9,
    )


def _commitment_intervals(
    *, upward_kw: float = 400.0, downward_kw: float = 200.0
) -> list[dict[str, object]]:
    result = []
    for direction, capacity in (
        ("UPWARD", upward_kw),
        ("DOWNWARD", downward_kw),
    ):
        result.extend(
            {
                "interval": _interval(index),
                "product": "AFRR",
                "direction": direction,
                "committed_capacity_kw": capacity,
                "eligibility": True,
                "source_or_assumption_ref": f"unit-{direction.lower()}-{index}",
            }
            for index in range(4)
        )
    return result


def _commitments(*, upward_kw: float = 400.0, downward_kw: float = 200.0):
    return build_directional_capacity_schedule(
        schedule_id="afrr-directional-unit-v1",
        semantics_version="directional-restoration-capacity-v1",
        product="AFRR",
        period=CanonicalInterval.from_utc(START, END),
        intervals=_commitment_intervals(
            upward_kw=upward_kw, downward_kw=downward_kw
        ),
    )


def _baseline(*, power_kw: float = 0.0):
    return build_restoration_energy_baseline_schedule(
        schedule_id="afrr-baseline-unit-v1",
        semantics_version="fixed-restoration-baseline-v1",
        product="AFRR",
        period=CanonicalInterval.from_utc(START, END),
        source="caller_fixed",
        intervals=[
            {
                "interval": _interval(index),
                "accepted_baseline_power_kw": power_kw,
            }
            for index in range(4)
        ],
    )


def _capability(**overrides: object):
    payload: dict[str, object] = {
        "max_ramp_up_kw_per_second": 100.0,
        "max_ramp_down_kw_per_second": 80.0,
        "max_activation_delay_seconds": {"AFRR": 5.0, "MFRR": 300.0},
        "min_supported_duration_seconds": {"AFRR": 1.0, "MFRR": 60.0},
        "max_supported_duration_seconds": {"AFRR": 900.0, "MFRR": 3600.0},
    }
    payload.update(overrides)
    return build_restoration_capability(payload)


def test_directional_schedule_preserves_asymmetric_explicit_commitments() -> None:
    schedule = _commitments()

    upward = schedule.intervals_for(RestorationDirection.UPWARD)
    downward = schedule.intervals_for(RestorationDirection.DOWNWARD)
    assert schedule.product is RestorationProduct.AFRR
    assert [item.committed_capacity_kw for item in upward] == [400.0] * 4
    assert [item.committed_capacity_kw for item in downward] == [200.0] * 4
    assert all(item.product is RestorationProduct.AFRR for item in schedule.intervals)
    assert re.fullmatch(r"[0-9a-f]{64}", schedule.schedule_fingerprint)


def test_commitments_require_complete_gap_free_coverage_in_both_directions() -> None:
    missing_direction = [
        item for item in _commitment_intervals() if item["direction"] == "UPWARD"
    ]
    with pytest.raises(RestorationControlValidationError, match="DOWNWARD|direction|coverage"):
        build_directional_capacity_schedule(
            schedule_id="missing-downward",
            semantics_version="v1",
            product="AFRR",
            period=CanonicalInterval.from_utc(START, END),
            intervals=missing_direction,
        )

    gap = _commitment_intervals()
    gap.pop(1)
    with pytest.raises(RestorationControlValidationError, match="gap|coverage|UPWARD"):
        build_directional_capacity_schedule(
            schedule_id="gap-upward",
            semantics_version="v1",
            product="AFRR",
            period=CanonicalInterval.from_utc(START, END),
            intervals=gap,
        )


def test_baseline_requires_complete_coverage_and_exact_product() -> None:
    baseline = _baseline(power_kw=25.0)
    assert [item.accepted_baseline_power_kw for item in baseline.intervals] == [25.0] * 4

    with pytest.raises(RestorationControlValidationError, match="gap|coverage"):
        build_restoration_energy_baseline_schedule(
            schedule_id="baseline-gap",
            semantics_version="v1",
            product="AFRR",
            period=CanonicalInterval.from_utc(START, END),
            source="caller_fixed",
            intervals=[
                {"interval": _interval(0), "accepted_baseline_power_kw": 0.0},
                {"interval": _interval(2), "accepted_baseline_power_kw": 0.0},
                {"interval": _interval(3), "accepted_baseline_power_kw": 0.0},
            ],
        )


def test_capability_is_finite_complete_and_product_specific() -> None:
    capability = _capability()
    assert capability.max_ramp_up_kw_per_second == 100.0
    assert capability.max_activation_delay_seconds[RestorationProduct.AFRR] == 5.0
    assert capability.max_supported_duration_seconds[RestorationProduct.MFRR] == 3600.0
    assert re.fullmatch(r"[0-9a-f]{64}", capability.capability_fingerprint)

    with pytest.raises(RestorationControlValidationError, match="product|MFRR|complete"):
        _capability(max_activation_delay_seconds={"AFRR": 5.0})
    with pytest.raises(RestorationControlValidationError, match="duration|min|max"):
        _capability(
            min_supported_duration_seconds={"AFRR": 901.0, "MFRR": 60.0}
        )


def test_config_rejects_baseline_that_consumes_reserved_power_headroom() -> None:
    with pytest.raises(
        RestorationControlValidationError,
        match="headroom|baseline|DOWNWARD|charge",
    ):
        build_restoration_baseline_config(
            config_id="invalid-charge-headroom",
            semantics_version="restoration-baseline-config-v1",
            product="AFRR",
            period=CanonicalInterval.from_utc(START, END),
            resolution="PT15M",
            commitments=_commitments(upward_kw=100.0, downward_kw=200.0),
            baseline=_baseline(power_kw=350.0),
            battery=_battery(),
            capability=_capability(),
            parameters={"mode": "fixed"},
        )

    with pytest.raises(
        RestorationControlValidationError,
        match="headroom|baseline|UPWARD|discharge",
    ):
        build_restoration_baseline_config(
            config_id="invalid-discharge-headroom",
            semantics_version="restoration-baseline-config-v1",
            product="AFRR",
            period=CanonicalInterval.from_utc(START, END),
            resolution="PT15M",
            commitments=_commitments(upward_kw=400.0, downward_kw=100.0),
            baseline=_baseline(power_kw=-200.0),
            battery=_battery(),
            capability=_capability(),
            parameters={"mode": "fixed"},
        )


def test_config_checks_usable_soc_energy_with_directional_efficiency() -> None:
    low_energy_battery = _battery(initial_soc=0.1, capacity_kwh=100.0)
    with pytest.raises(
        RestorationControlValidationError,
        match="usable|SOC|energy|UPWARD|efficiency",
    ):
        build_restoration_baseline_config(
            config_id="invalid-upward-energy",
            semantics_version="restoration-baseline-config-v1",
            product="AFRR",
            period=CanonicalInterval.from_utc(START, END),
            resolution="PT15M",
            commitments=_commitments(upward_kw=100.0, downward_kw=0.0),
            baseline=_baseline(),
            battery=low_energy_battery,
            capability=_capability(),
            parameters={"mode": "fixed"},
        )


def test_valid_config_is_deterministic_and_has_no_activation_lookahead() -> None:
    kwargs = {
        "config_id": "valid-afrr-fixed-v1",
        "semantics_version": "restoration-baseline-config-v1",
        "product": "AFRR",
        "period": CanonicalInterval.from_utc(START, END),
        "resolution": "PT15M",
        "commitments": _commitments(upward_kw=100.0, downward_kw=100.0),
        "baseline": _baseline(power_kw=0.0),
        "battery": _battery(),
        "capability": _capability(),
        "parameters": {"mode": "fixed", "threshold": 0.0},
    }
    first = build_restoration_baseline_config(**kwargs)
    second = build_restoration_baseline_config(**kwargs)

    assert first.configuration_fingerprint == second.configuration_fingerprint
    assert first.commitments is kwargs["commitments"]
    assert first.baseline is kwargs["baseline"]
    assert "activation" not in inspect.signature(
        build_restoration_baseline_config
    ).parameters
    assert not hasattr(first, "activation")
    assert not hasattr(first, "trajectory")
    assert not hasattr(first, "events")
