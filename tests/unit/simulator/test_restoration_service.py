"""Shared restoration replay request, capability, physics, and energy tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re

import pytest

from open_energy_lab.market.restoration_activation import (
    RestorationDirection,
    RestorationProduct,
)
from open_energy_lab.market.time import CanonicalInterval
from open_energy_lab.simulator.battery import build_initial_state
from open_energy_lab.simulator.restoration_service import (
    RESTORATION_CAUSE_ORDER,
    RestorationReplayInputKind,
    RestorationReplayValidationError,
    aggregate_restoration_samples,
    apply_restoration_battery_transition,
    build_restoration_integration_grid,
    build_restoration_replay_request_core,
    build_restoration_replay_result_core,
    enforce_restoration_capability,
)
from tests.unit.control.test_restoration_service import (
    END,
    START,
    _baseline,
    _battery,
    _capability,
    _commitments,
    _interval,
)


def _grid():
    return build_restoration_integration_grid(
        period=CanonicalInterval.from_utc(START, END),
        resolution="PT15M",
        intervals=tuple(_interval(index) for index in range(4)),
    )


def _request(
    *,
    product: str = "AFRR",
    input_kind: str = "AFRR_TRAJECTORY",
    tolerance: float = 1e-6,
):
    battery = _battery()
    return build_restoration_replay_request_core(
        request_id="afrr-shared-replay-unit-v1",
        semantics_version="restoration-replay-core-v1",
        product=product,
        activation_input_kind=input_kind,
        battery=battery,
        initial_state=build_initial_state(battery),
        capability=_capability(),
        commitments=_commitments(upward_kw=100.0, downward_kw=100.0),
        baseline=_baseline(),
        integration_grid=_grid(),
        tolerance=tolerance,
        input_fingerprints={
            "activation": "a" * 64,
            "commitments": _commitments(
                upward_kw=100.0, downward_kw=100.0
            ).schedule_fingerprint,
            "baseline": _baseline().schedule_fingerprint,
            "capability": _capability().capability_fingerprint,
        },
    )


def test_request_discriminators_are_exact_and_never_accept_fcr() -> None:
    request = _request()
    assert request.product is RestorationProduct.AFRR
    assert request.activation_input_kind is RestorationReplayInputKind.AFRR_TRAJECTORY

    with pytest.raises(RestorationReplayValidationError, match="AFRR|trajectory|MFRR"):
        _request(input_kind="MFRR_EVENT_SEQUENCE")
    with pytest.raises(RestorationReplayValidationError, match="product|AFRR|MFRR"):
        _request(product="FCR")
    with pytest.raises(RestorationReplayValidationError, match="kind|input|trajectory|event"):
        _request(input_kind="FCR_TRACE")


def test_integration_grid_requires_exact_gap_free_native_resolution() -> None:
    grid = _grid()
    assert grid.period == CanonicalInterval.from_utc(START, END)
    assert grid.resolution == "PT15M"
    assert len(grid.intervals) == 4

    with pytest.raises(RestorationReplayValidationError, match="gap|coverage"):
        build_restoration_integration_grid(
            period=CanonicalInterval.from_utc(START, END),
            resolution="PT15M",
            intervals=(_interval(0), _interval(2), _interval(3)),
        )
    with pytest.raises(RestorationReplayValidationError, match="resolution|duration"):
        build_restoration_integration_grid(
            period=CanonicalInterval.from_utc(START, END),
            resolution="PT5M",
            intervals=tuple(_interval(index) for index in range(4)),
        )


def test_capability_enforcement_attributes_limits_and_orders_causes() -> None:
    capability = _capability(
        max_ramp_up_kw_per_second=0.05,
        max_ramp_down_kw_per_second=0.05,
    )
    decision = enforce_restoration_capability(
        product="AFRR",
        accepted_baseline_power_kw=0.0,
        requested_balancing_power_kw=-300.0,
        upward_commitment_kw=200.0,
        downward_commitment_kw=200.0,
        upward_headroom_kw=150.0,
        downward_headroom_kw=200.0,
        previous_capability_combined_power_kw=0.0,
        interval_seconds=900.0,
        actual_activation_delay_seconds=10.0,
        requested_duration_seconds=1000.0,
        capability=capability,
    )

    assert decision.requested_combined_power_kw == -300.0
    assert decision.capability_accepted_combined_power_kw == 0.0
    assert decision.causes == (
        "commitment_limit",
        "upward_headroom",
        "ramp_limit",
        "activation_time_limit",
        "duration_limit",
    )
    assert tuple(RESTORATION_CAUSE_ORDER.index(cause) for cause in decision.causes) == tuple(
        sorted(RESTORATION_CAUSE_ORDER.index(cause) for cause in decision.causes)
    )


def test_battery_adapter_keeps_capability_and_physical_attribution_separate() -> None:
    battery = _battery(max_charge_kw=500.0)
    state = build_initial_state(battery)
    decision = enforce_restoration_capability(
        product="AFRR",
        accepted_baseline_power_kw=0.0,
        requested_balancing_power_kw=800.0,
        upward_commitment_kw=1000.0,
        downward_commitment_kw=1000.0,
        upward_headroom_kw=1000.0,
        downward_headroom_kw=1000.0,
        previous_capability_combined_power_kw=0.0,
        interval_seconds=900.0,
        capability=_capability(
            max_ramp_up_kw_per_second=1000.0,
            max_ramp_down_kw_per_second=1000.0,
        ),
    )
    sample = apply_restoration_battery_transition(
        sample_index=0,
        interval=_interval(0),
        product="AFRR",
        decision=decision,
        battery=battery,
        state=state,
        tolerance=1e-6,
    )

    assert decision.causes == ()
    assert sample.capability_causes == ()
    assert sample.physical_causes == ("charge_power_limit",)
    assert sample.causes == ("charge_power_limit",)
    assert sample.capability_accepted_combined_power_kw == 800.0
    assert sample.delivered_combined_power_kw == 500.0
    assert sample.delivered_balancing_power_kw == 500.0
    assert sample.tracking_error_kw == 300.0
    assert sample.state.soc <= battery.max_soc


def test_ordered_physical_causes_distinguish_power_soc_and_energy() -> None:
    battery = _battery(initial_soc=0.9, capacity_kwh=100.0, max_charge_kw=500.0)
    state = build_initial_state(battery)
    decision = enforce_restoration_capability(
        product="MFRR",
        accepted_baseline_power_kw=0.0,
        requested_balancing_power_kw=800.0,
        upward_commitment_kw=1000.0,
        downward_commitment_kw=1000.0,
        upward_headroom_kw=1000.0,
        downward_headroom_kw=1000.0,
        previous_capability_combined_power_kw=0.0,
        interval_seconds=900.0,
        capability=_capability(
            max_ramp_up_kw_per_second=1000.0,
            max_ramp_down_kw_per_second=1000.0,
        ),
    )
    sample = apply_restoration_battery_transition(
        sample_index=0,
        interval=_interval(0),
        product="MFRR",
        decision=decision,
        battery=battery,
        state=state,
        tolerance=1e-6,
    )

    assert sample.physical_causes == (
        "charge_power_limit",
        "maximum_soc",
        "energy_headroom",
    )


def test_energy_aggregation_conserves_charge_discharge_net_and_activation() -> None:
    battery = _battery(max_charge_kw=500.0, max_discharge_kw=500.0)
    state = build_initial_state(battery)
    samples = []
    previous = 0.0
    for index, power in enumerate((100.0, -200.0)):
        decision = enforce_restoration_capability(
            product="AFRR",
            accepted_baseline_power_kw=0.0,
            requested_balancing_power_kw=power,
            upward_commitment_kw=500.0,
            downward_commitment_kw=500.0,
            upward_headroom_kw=500.0,
            downward_headroom_kw=500.0,
            previous_capability_combined_power_kw=previous,
            interval_seconds=900.0,
            capability=_capability(
                max_ramp_up_kw_per_second=1000.0,
                max_ramp_down_kw_per_second=1000.0,
            ),
        )
        sample = apply_restoration_battery_transition(
            sample_index=index,
            interval=_interval(index),
            product="AFRR",
            decision=decision,
            battery=battery,
            state=state,
            tolerance=1e-6,
        )
        samples.append(sample)
        state = sample.state
        previous = decision.capability_accepted_combined_power_kw

    totals = aggregate_restoration_samples(tuple(samples), tolerance=1e-6)
    assert totals.charge_energy_kwh == pytest.approx(25.0)
    assert totals.discharge_energy_kwh == pytest.approx(50.0)
    assert totals.net_terminal_energy_kwh == pytest.approx(-25.0)
    assert totals.throughput_kwh == pytest.approx(75.0)
    assert totals.requested_activation_energy_kwh == pytest.approx(75.0)
    assert totals.delivered_activation_energy_kwh == pytest.approx(75.0)
    assert totals.undelivered_activation_energy_kwh == pytest.approx(0.0)


def test_tolerance_and_result_fingerprints_are_validated_and_deterministic() -> None:
    with pytest.raises(RestorationReplayValidationError, match="tolerance|positive|finite"):
        _request(tolerance=0.0)

    request = _request()
    battery = request.battery
    state = request.initial_state
    decision = enforce_restoration_capability(
        product="AFRR",
        accepted_baseline_power_kw=0.0,
        requested_balancing_power_kw=0.0,
        upward_commitment_kw=100.0,
        downward_commitment_kw=100.0,
        upward_headroom_kw=100.0,
        downward_headroom_kw=100.0,
        previous_capability_combined_power_kw=0.0,
        interval_seconds=900.0,
        capability=request.capability,
    )
    sample = apply_restoration_battery_transition(
        sample_index=0,
        interval=_interval(0),
        product="AFRR",
        decision=decision,
        battery=battery,
        state=state,
        tolerance=request.tolerance,
    )
    first = build_restoration_replay_result_core(request=request, samples=(sample,))
    second = build_restoration_replay_result_core(request=request, samples=(sample,))

    assert first.result_fingerprint == second.result_fingerprint
    assert first.totals == second.totals
    assert re.fullmatch(r"[0-9a-f]{64}", request.request_fingerprint)
    assert re.fullmatch(r"[0-9a-f]{64}", sample.sample_fingerprint)
    assert re.fullmatch(r"[0-9a-f]{64}", first.result_fingerprint)
