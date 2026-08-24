"""mFRR directional commitments and no-lookahead baseline tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import inspect
import re

import pytest

from open_energy_lab.control.restoration_service import (
    MFRRBaselineConfig,
    MFRRBaselineMode,
    RestorationControlValidationError,
    build_afrr_baseline_config,
    build_directional_capacity_schedule,
    build_mfrr_baseline,
    build_mfrr_baseline_config,
    build_mfrr_directional_capacity_schedule,
    build_restoration_capability,
)
from open_energy_lab.market.restoration_activation import (
    RestorationDirection,
    RestorationProduct,
)
from open_energy_lab.market.time import CanonicalInterval
from open_energy_lab.simulator.scenario import BatteryComponent


START = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
END = START + timedelta(hours=1)
PERIOD = CanonicalInterval.from_utc(START, END)


def _interval(index: int) -> CanonicalInterval:
    start = START + timedelta(minutes=15 * index)
    return CanonicalInterval.from_utc(start, start + timedelta(minutes=15))


def _battery(
    *,
    capacity_kwh: float = 2000.0,
    initial_soc: float = 0.5,
    max_charge_kw: float = 500.0,
    max_discharge_kw: float = 500.0,
) -> BatteryComponent:
    return BatteryComponent(
        name="mfrr-control-battery",
        capacity_kwh=capacity_kwh,
        max_charge_kw=max_charge_kw,
        max_discharge_kw=max_discharge_kw,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        initial_soc=initial_soc,
        min_soc=0.1,
        max_soc=0.9,
    )


def _capability(**overrides: object):
    payload: dict[str, object] = {
        "max_ramp_up_kw_per_second": 10.0,
        "max_ramp_down_kw_per_second": 10.0,
        "max_activation_delay_seconds": {"AFRR": 5.0, "MFRR": 300.0},
        "min_supported_duration_seconds": {"AFRR": 1.0, "MFRR": 60.0},
        "max_supported_duration_seconds": {"AFRR": 900.0, "MFRR": 3600.0},
    }
    payload.update(overrides)
    return build_restoration_capability(payload)


def _commitment_rows(
    *, upward_kw: float = 100.0, downward_kw: float = 200.0
) -> list[dict[str, object]]:
    return [
        {
            "interval": _interval(index),
            "product": "MFRR",
            "direction": direction,
            "committed_capacity_kw": capacity,
            "eligibility": True,
            "source_or_assumption_ref": f"fixed-{direction.lower()}-{index}",
        }
        for direction, capacity in (
            ("UPWARD", upward_kw),
            ("DOWNWARD", downward_kw),
        )
        for index in range(4)
    ]


def _commitments(*, upward_kw: float = 100.0, downward_kw: float = 200.0):
    return build_mfrr_directional_capacity_schedule(
        schedule_id="mfrr-fixed-capacity-v1",
        semantics_version="directional-restoration-capacity-v1",
        period=PERIOD,
        intervals=_commitment_rows(
            upward_kw=upward_kw,
            downward_kw=downward_kw,
        ),
    )


def _config(**overrides: object):
    kwargs: dict[str, object] = {
        "config_id": "mfrr-baseline-config-v1",
        "semantics_version": "mfrr-baseline-v1",
        "period": PERIOD,
        "resolution": "PT15M",
        "commitments": _commitments(),
        "battery": _battery(),
        "capability": _capability(),
        "mode": "ZERO",
        "fixed_power_kw": None,
        "declared_service_duration_seconds": 900.0,
        "headroom_bias": 0.0,
        "tolerance": 1e-6,
    }
    kwargs.update(overrides)
    return build_mfrr_baseline_config(**kwargs)


def test_mfrr_schedule_preserves_fixed_asymmetric_directional_commitments() -> None:
    schedule = _commitments()

    assert schedule.product is RestorationProduct.MFRR
    assert [
        item.committed_capacity_kw
        for item in schedule.intervals_for(RestorationDirection.UPWARD)
    ] == [100.0] * 4
    assert [
        item.committed_capacity_kw
        for item in schedule.intervals_for(RestorationDirection.DOWNWARD)
    ] == [200.0] * 4
    assert re.fullmatch(r"[0-9a-f]{64}", schedule.schedule_fingerprint)


def test_mfrr_schedule_rejects_wrong_product_and_incomplete_alignment() -> None:
    wrong_product = _commitment_rows()
    wrong_product[0]["product"] = "AFRR"
    with pytest.raises(RestorationControlValidationError, match="MFRR|product"):
        build_mfrr_directional_capacity_schedule(
            schedule_id="wrong-product",
            semantics_version="v1",
            period=PERIOD,
            intervals=wrong_product,
        )

    gap = _commitment_rows()
    gap.pop(0)
    with pytest.raises(
        RestorationControlValidationError,
        match="gap|coverage|UPWARD",
    ):
        build_mfrr_directional_capacity_schedule(
            schedule_id="gap",
            semantics_version="v1",
            period=PERIOD,
            intervals=gap,
        )


@pytest.mark.parametrize(
    "mode,fixed_power_kw,expected",
    (
        ("ZERO", None, [0.0] * 4),
        ("FIXED", 50.0, [50.0] * 4),
        ("FIXED", (-25.0, 0.0, 25.0, 50.0), [-25.0, 0.0, 25.0, 50.0]),
        ("DETERMINISTIC_HEADROOM", None, [-50.0] * 4),
    ),
)
def test_mfrr_baseline_modes_are_complete_product_specific_and_reproducible(
    mode: str,
    fixed_power_kw: float | tuple[float, ...] | None,
    expected: list[float],
) -> None:
    config = _config(mode=mode, fixed_power_kw=fixed_power_kw)
    first = build_mfrr_baseline(config)
    second = build_mfrr_baseline(config)

    assert config.mode is MFRRBaselineMode(mode)
    assert first.product is RestorationProduct.MFRR
    assert first.baseline.period == PERIOD
    assert [
        item.accepted_baseline_power_kw for item in first.baseline.intervals
    ] == expected
    assert first.bundle_fingerprint == second.bundle_fingerprint
    assert first.baseline.schedule_fingerprint == second.baseline.schedule_fingerprint


def test_mfrr_deterministic_bias_selects_declared_headroom_bounds() -> None:
    upper = build_mfrr_baseline(
        _config(mode="DETERMINISTIC_HEADROOM", headroom_bias=1.0)
    )
    lower = build_mfrr_baseline(
        _config(mode="DETERMINISTIC_HEADROOM", headroom_bias=-1.0)
    )

    assert [item.accepted_baseline_power_kw for item in lower.baseline.intervals] == [
        -400.0
    ] * 4
    assert [item.accepted_baseline_power_kw for item in upper.baseline.intervals] == [
        300.0
    ] * 4


def test_mfrr_baseline_rejects_reserved_headroom_consumption() -> None:
    with pytest.raises(
        RestorationControlValidationError,
        match="DOWNWARD|headroom|baseline|charge",
    ):
        build_mfrr_baseline(_config(mode="FIXED", fixed_power_kw=350.0))

    with pytest.raises(
        RestorationControlValidationError,
        match="UPWARD|headroom|baseline|discharge",
    ):
        build_mfrr_baseline(_config(mode="FIXED", fixed_power_kw=-450.0))


def test_mfrr_config_checks_declared_duration_and_usable_energy() -> None:
    with pytest.raises(
        RestorationControlValidationError,
        match="duration|MFRR|supported",
    ):
        _config(declared_service_duration_seconds=30.0)

    with pytest.raises(
        RestorationControlValidationError,
        match="duration|MFRR|supported",
    ):
        _config(declared_service_duration_seconds=3601.0)

    with pytest.raises(
        RestorationControlValidationError,
        match="usable|SOC|energy|UPWARD|efficiency",
    ):
        build_mfrr_baseline(
            _config(
                commitments=_commitments(upward_kw=100.0, downward_kw=0.0),
                battery=_battery(capacity_kwh=100.0, initial_soc=0.1),
            )
        )


def test_mfrr_config_checks_activation_time_and_ramp_by_direction() -> None:
    with pytest.raises(
        RestorationControlValidationError,
        match="UPWARD|ramp|activation|200|150",
    ):
        _config(
            commitments=_commitments(upward_kw=200.0, downward_kw=0.0),
            capability=_capability(max_ramp_down_kw_per_second=0.5),
        )

    with pytest.raises(
        RestorationControlValidationError,
        match="DOWNWARD|ramp|activation|200|150",
    ):
        _config(
            commitments=_commitments(upward_kw=0.0, downward_kw=200.0),
            capability=_capability(max_ramp_up_kw_per_second=0.5),
        )


def test_mfrr_config_rejects_afrr_schedule_and_misaligned_fixed_grid() -> None:
    afrr_rows = [{**row, "product": "AFRR"} for row in _commitment_rows()]
    afrr = build_directional_capacity_schedule(
        schedule_id="afrr-capacity",
        semantics_version="v1",
        product="AFRR",
        period=PERIOD,
        intervals=afrr_rows,
    )
    with pytest.raises(RestorationControlValidationError, match="MFRR|product"):
        _config(commitments=afrr)

    with pytest.raises(
        RestorationControlValidationError,
        match="fixed|grid|interval|length",
    ):
        _config(mode="FIXED", fixed_power_kw=(0.0, 0.0))


def test_mfrr_config_and_builder_have_no_activation_lookahead_surface() -> None:
    config = _config(mode="DETERMINISTIC_HEADROOM")

    assert isinstance(config, MFRRBaselineConfig)
    assert re.fullmatch(r"[0-9a-f]{64}", config.configuration_fingerprint)
    for forbidden in ("activation", "trajectory", "requested_power", "events"):
        assert not hasattr(config, forbidden)
    assert tuple(inspect.signature(build_mfrr_baseline).parameters) == ("config",)
    assert not any(
        "activation" in name or "event" in name or "sequence" in name
        for name in inspect.signature(build_mfrr_baseline_config).parameters
    )


def test_mfrr_builder_rejects_afrr_config_exact_type_substitution() -> None:
    afrr_rows = [{**row, "product": "AFRR"} for row in _commitment_rows()]
    afrr_commitments = build_directional_capacity_schedule(
        schedule_id="afrr-capacity",
        semantics_version="v1",
        product="AFRR",
        period=PERIOD,
        intervals=afrr_rows,
    )
    afrr_config = build_afrr_baseline_config(
        config_id="afrr-config",
        semantics_version="v1",
        period=PERIOD,
        resolution="PT15M",
        commitments=afrr_commitments,
        battery=_battery(),
        capability=_capability(
            max_ramp_up_kw_per_second=100.0,
            max_ramp_down_kw_per_second=100.0,
        ),
        mode="ZERO",
        fixed_power_kw=None,
    )

    with pytest.raises(RestorationControlValidationError, match="MFRRBaselineConfig"):
        build_mfrr_baseline(afrr_config)  # type: ignore[arg-type]
