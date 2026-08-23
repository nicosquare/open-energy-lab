"""Product-specific deterministic mFRR event replay tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re

import pytest

from open_energy_lab.control.restoration_service import (
    build_mfrr_directional_capacity_schedule,
    build_restoration_capability,
    build_restoration_energy_baseline_schedule,
)
from open_energy_lab.market.restoration_activation import (
    MFRRActivationKind,
    RestorationDirection,
    build_mfrr_activation_sequence,
)
from open_energy_lab.market.time import CanonicalInterval
from open_energy_lab.simulator.battery import build_initial_state
from open_energy_lab.simulator.restoration_service import (
    MFRRReplayRequest,
    RestorationReplayValidationError,
    apply_restoration_battery_transition,
    build_mfrr_replay_request,
    build_restoration_integration_grid,
    enforce_restoration_capability,
    replay_mfrr,
)
from open_energy_lab.simulator.scenario import BatteryComponent


START = datetime(2026, 1, 3, 1, 0, tzinfo=UTC)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _intervals(
    count: int,
    *,
    step_seconds: int = 60,
) -> tuple[CanonicalInterval, ...]:
    duration = timedelta(seconds=step_seconds)
    return tuple(
        CanonicalInterval.from_utc(
            START + index * duration,
            START + (index + 1) * duration,
        )
        for index in range(count)
    )


def _battery(
    *,
    capacity_kwh: float = 100.0,
    max_charge_kw: float = 20.0,
    max_discharge_kw: float = 20.0,
    initial_soc: float = 0.5,
) -> BatteryComponent:
    return BatteryComponent(
        name="mfrr-replay-battery",
        capacity_kwh=capacity_kwh,
        max_charge_kw=max_charge_kw,
        max_discharge_kw=max_discharge_kw,
        charge_efficiency=1.0,
        discharge_efficiency=1.0,
        initial_soc=initial_soc,
        min_soc=0.1,
        max_soc=0.9,
    )


def _capability(
    *,
    ramp_up: float = 1.0,
    ramp_down: float = 1.0,
    max_delay: float = 300.0,
    min_duration: float = 60.0,
    max_duration: float = 3600.0,
):
    return build_restoration_capability(
        {
            "max_ramp_up_kw_per_second": ramp_up,
            "max_ramp_down_kw_per_second": ramp_down,
            "max_activation_delay_seconds": {
                "AFRR": 5.0,
                "MFRR": max_delay,
            },
            "min_supported_duration_seconds": {
                "AFRR": 1.0,
                "MFRR": min_duration,
            },
            "max_supported_duration_seconds": {
                "AFRR": 900.0,
                "MFRR": max_duration,
            },
        }
    )


def _event(
    *,
    event_id: str = "downward-da-001",
    kind: str = "DIRECT",
    direction: str = "DOWNWARD",
    start_offset_seconds: int = 0,
    delay_seconds: float = 60.0,
    ramp_up_seconds: float = 120.0,
    hold_seconds: float = 180.0,
    ramp_down_seconds: float = 120.0,
    power_kw: float = 10.0,
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "product": "MFRR",
        "kind": kind,
        "direction": direction,
        "requested_start_utc": _utc(
            START + timedelta(seconds=start_offset_seconds)
        ),
        "activation_delay_seconds": delay_seconds,
        "ramp_up_seconds": ramp_up_seconds,
        "hold_seconds": hold_seconds,
        "ramp_down_seconds": ramp_down_seconds,
        "requested_power_kw": power_kw,
        "source_kind": "SYNTHETIC",
        "mapping_fingerprint": None,
        "source_observation_refs": [f"synthetic:{event_id}"],
    }


def _sequence(
    events: list[dict[str, object]],
    *,
    intervals: tuple[CanonicalInterval, ...],
):
    period = CanonicalInterval.from_utc(
        intervals[0].start_utc,
        intervals[-1].end_utc,
    )
    return build_mfrr_activation_sequence(
        {
            "sequence_id": "mfrr-replay-sequence-v1",
            "semantics_version": "mfrr-delay-ramp-hold-v1",
            "product": "MFRR",
            "period": period,
            "shape_semantics": "delay_linear_ramp_hold_linear_ramp",
            "sign_convention": "positive_charge_negative_discharge",
            "source_kind": "SYNTHETIC",
            "created_or_retrieved_at_utc": "2026-01-04T00:00:00Z",
            "events": events,
        }
    )


def _request(
    events: list[dict[str, object]] | None = None,
    *,
    count: int = 8,
    step_seconds: int = 60,
    baseline_power_kw: float = 0.0,
    upward_kw: float = 20.0,
    downward_kw: float = 20.0,
    battery: BatteryComponent | None = None,
    capability=None,
):
    intervals = _intervals(count, step_seconds=step_seconds)
    period = CanonicalInterval.from_utc(
        intervals[0].start_utc,
        intervals[-1].end_utc,
    )
    commitments = build_mfrr_directional_capacity_schedule(
        schedule_id="mfrr-replay-capacity-v1",
        semantics_version="directional-restoration-capacity-v1",
        period=period,
        intervals=[
            {
                "interval": interval,
                "product": "MFRR",
                "direction": direction,
                "committed_capacity_kw": capacity,
                "eligibility": True,
                "source_or_assumption_ref": f"unit-{direction.lower()}-{index}",
            }
            for direction, capacity in (
                ("UPWARD", upward_kw),
                ("DOWNWARD", downward_kw),
            )
            for index, interval in enumerate(intervals)
        ],
    )
    baseline = build_restoration_energy_baseline_schedule(
        schedule_id="mfrr-replay-baseline-v1",
        semantics_version="restoration-energy-baseline-v1",
        product="MFRR",
        period=period,
        source="unit_fixed",
        intervals=[
            {
                "interval": interval,
                "accepted_baseline_power_kw": baseline_power_kw,
            }
            for interval in intervals
        ],
    )
    selected_battery = battery or _battery()
    selected_capability = capability or _capability()
    activation_sequence = _sequence(
        [_event()] if events is None else events,
        intervals=intervals,
    )
    resolution = f"PT{step_seconds // 60}M" if step_seconds % 60 == 0 else f"PT{step_seconds}S"
    grid = build_restoration_integration_grid(
        period=period,
        resolution=resolution,
        intervals=intervals,
    )
    return build_mfrr_replay_request(
        request_id="mfrr-replay-request-v1",
        semantics_version="mfrr-physical-replay-v1",
        battery=selected_battery,
        initial_state=build_initial_state(selected_battery),
        capability=selected_capability,
        commitments=commitments,
        baseline=baseline,
        activation_sequence=activation_sequence,
        integration_grid=grid,
        tolerance=1e-6,
    )


def test_request_requires_exact_mfrr_sequence_and_conserving_boundaries() -> None:
    request = _request()

    assert isinstance(request, MFRRReplayRequest)
    assert request.input_fingerprints["activation"] == (
        request.activation_sequence.sequence_fingerprint
    )
    assert re.fullmatch(r"[0-9a-f]{64}", request.request_fingerprint)

    with pytest.raises(
        RestorationReplayValidationError,
        match="MFRRActivationSequence|exact",
    ):
        build_mfrr_replay_request(
            request_id="wrong-activation",
            semantics_version="v1",
            battery=request.battery,
            initial_state=request.initial_state,
            capability=request.capability,
            commitments=request.commitments,
            baseline=request.baseline,
            activation_sequence=object(),
            integration_grid=request.integration_grid,
            tolerance=1e-6,
        )

    with pytest.raises(
        RestorationReplayValidationError,
        match="boundary|segment|grid|conserv",
    ):
        _request(
            [
                _event(
                    delay_seconds=0.0,
                    ramp_up_seconds=90.0,
                    hold_seconds=90.0,
                    ramp_down_seconds=0.0,
                )
            ],
            count=4,
        )


def test_delayed_ramped_direct_event_expands_exactly_and_reports_timing() -> None:
    result = replay_mfrr(_request())

    assert [sample.requested_balancing_power_kw for sample in result.samples] == pytest.approx(
        [0.0, 2.5, 7.5, 10.0, 10.0, 10.0, 7.5, 2.5]
    )
    assert [sample.delivered_balancing_power_kw for sample in result.samples] == pytest.approx(
        [0.0, 2.5, 7.5, 10.0, 10.0, 10.0, 7.5, 2.5]
    )
    assert all(sample.event_id == "downward-da-001" for sample in result.samples)
    assert all(sample.mfrr_kind is MFRRActivationKind.DIRECT for sample in result.samples)
    performance = result.event_performance[0]
    assert performance.requested_start_utc == "2026-01-03T01:00:00Z"
    assert performance.actual_start_utc == "2026-01-03T01:01:00Z"
    assert performance.requested_completion_utc == "2026-01-03T01:08:00Z"
    assert performance.actual_completion_utc == "2026-01-03T01:08:00Z"
    assert performance.requested_energy_kwh == pytest.approx(5.0 / 6.0)
    assert performance.delivered_energy_kwh == pytest.approx(5.0 / 6.0)
    assert performance.undelivered_energy_kwh == pytest.approx(0.0)
    assert performance.maximum_achieved_ramp_kw_per_second == pytest.approx(5.0 / 60.0)
    assert result.totals.requested_activation_energy_kwh == pytest.approx(5.0 / 6.0)
    assert result.totals.requested_activation_energy_kwh == pytest.approx(
        result.totals.delivered_activation_energy_kwh
        + result.totals.undelivered_activation_energy_kwh
    )


def test_scheduled_direct_and_direction_aggregates_remain_distinct() -> None:
    events = [
        _event(
            event_id="upward-sa",
            kind="SCHEDULED",
            direction="UPWARD",
            delay_seconds=0.0,
            ramp_up_seconds=0.0,
            hold_seconds=120.0,
            ramp_down_seconds=0.0,
            power_kw=6.0,
        ),
        _event(
            event_id="downward-da",
            kind="DIRECT",
            direction="DOWNWARD",
            start_offset_seconds=240,
            delay_seconds=0.0,
            ramp_up_seconds=0.0,
            hold_seconds=120.0,
            ramp_down_seconds=0.0,
            power_kw=3.0,
        ),
    ]
    result = replay_mfrr(_request(events, count=6))

    assert [item.event_id for item in result.event_performance] == [
        "upward-sa",
        "downward-da",
    ]
    assert result.kind_performance[MFRRActivationKind.SCHEDULED].requested_energy_kwh == pytest.approx(0.2)
    assert result.kind_performance[MFRRActivationKind.DIRECT].requested_energy_kwh == pytest.approx(0.1)
    assert result.directional_performance[RestorationDirection.UPWARD].requested_energy_kwh == pytest.approx(0.2)
    assert result.directional_performance[RestorationDirection.DOWNWARD].requested_energy_kwh == pytest.approx(0.1)
    assert result.samples[2].event_id is None
    assert result.samples[3].event_id is None


@pytest.mark.parametrize(
    "request_kwargs,expected_cause",
    (
        (
            {
                "events": [
                    _event(
                        delay_seconds=360.0,
                        ramp_up_seconds=0.0,
                        hold_seconds=60.0,
                        ramp_down_seconds=0.0,
                    )
                ],
                "count": 7,
            },
            "activation_time_limit",
        ),
        (
            {
                "events": [
                    _event(
                        delay_seconds=0.0,
                        ramp_up_seconds=0.0,
                        hold_seconds=30.0,
                        ramp_down_seconds=0.0,
                    )
                ],
                "count": 2,
                "step_seconds": 30,
            },
            "duration_limit",
        ),
        (
            {
                "events": [
                    _event(
                        delay_seconds=0.0,
                        ramp_up_seconds=0.0,
                        hold_seconds=120.0,
                        ramp_down_seconds=0.0,
                    )
                ],
                "count": 2,
                "capability": _capability(ramp_up=0.01, ramp_down=0.01),
            },
            "ramp_limit",
        ),
        (
            {
                "events": [
                    _event(
                        direction="UPWARD",
                        delay_seconds=0.0,
                        ramp_up_seconds=0.0,
                        hold_seconds=60.0,
                        ramp_down_seconds=0.0,
                        power_kw=50.0,
                    )
                ],
                "count": 1,
                "upward_kw": 50.0,
            },
            "upward_headroom",
        ),
        (
            {
                "events": [
                    _event(
                        direction="UPWARD",
                        delay_seconds=0.0,
                        ramp_up_seconds=0.0,
                        hold_seconds=60.0,
                        ramp_down_seconds=0.0,
                        power_kw=10.0,
                    )
                ],
                "count": 1,
                "battery": _battery(initial_soc=0.1),
            },
            "minimum_soc",
        ),
        (
            {
                "events": [
                    _event(
                        delay_seconds=0.0,
                        ramp_up_seconds=0.0,
                        hold_seconds=60.0,
                        ramp_down_seconds=0.0,
                        power_kw=10.0,
                    )
                ],
                "count": 1,
                "baseline_power_kw": 15.0,
                "downward_kw": 10.0,
            },
            "downward_headroom",
        ),
    ),
)
def test_mfrr_replay_attributes_timing_duration_ramp_and_physical_shortfalls(
    request_kwargs: dict[str, object],
    expected_cause: str,
) -> None:
    result = replay_mfrr(_request(**request_kwargs))

    assert expected_cause in result.causes
    assert any(expected_cause in sample.causes for sample in result.samples)
    assert result.totals.undelivered_activation_energy_kwh > 0.0
    assert result.totals.requested_activation_energy_kwh == pytest.approx(
        result.totals.delivered_activation_energy_kwh
        + result.totals.undelivered_activation_energy_kwh
    )


def test_empty_sequence_preserves_baseline_and_zero_activation() -> None:
    request = _request(
        [],
        count=1,
        step_seconds=900,
        baseline_power_kw=-2.0,
        upward_kw=5.0,
        downward_kw=5.0,
    )
    result = replay_mfrr(request)

    assert result.event_performance == ()
    assert result.samples[0].event_id is None
    assert result.samples[0].requested_combined_power_kw == -2.0
    assert result.samples[0].delivered_combined_power_kw == -2.0
    assert result.samples[0].delivered_balancing_power_kw == 0.0
    assert result.totals.requested_activation_energy_kwh == 0.0
    assert result.totals.delivered_activation_energy_kwh == 0.0
    assert result.totals.undelivered_activation_energy_kwh == 0.0
    assert result.causes == ()


def test_mfrr_physical_power_limit_remains_separate_from_service_headroom() -> None:
    battery = _battery()
    interval = _intervals(1)[0]
    decision = enforce_restoration_capability(
        product="MFRR",
        accepted_baseline_power_kw=0.0,
        requested_balancing_power_kw=-50.0,
        upward_commitment_kw=50.0,
        downward_commitment_kw=50.0,
        upward_headroom_kw=50.0,
        downward_headroom_kw=50.0,
        previous_capability_combined_power_kw=0.0,
        interval_seconds=60.0,
        capability=_capability(),
        requested_duration_seconds=60.0,
    )
    sample = apply_restoration_battery_transition(
        sample_index=0,
        interval=interval,
        product="MFRR",
        decision=decision,
        battery=battery,
        state=build_initial_state(battery),
        tolerance=1e-6,
        event_id="physical-power-limit",
        mfrr_kind="DIRECT",
    )

    assert decision.causes == ()
    assert sample.delivered_balancing_power_kw == -20.0
    assert sample.physical_causes == ("discharge_power_limit",)
    assert sample.undelivered_activation_energy_kwh == pytest.approx(0.5)


def test_ramp_limited_return_to_baseline_extends_actual_event_completion() -> None:
    result = replay_mfrr(
        _request(
            [
                _event(
                    delay_seconds=0.0,
                    ramp_up_seconds=0.0,
                    hold_seconds=60.0,
                    ramp_down_seconds=0.0,
                    power_kw=10.0,
                )
            ],
            count=4,
            capability=_capability(ramp_up=1.0, ramp_down=0.01),
        )
    )

    performance = result.event_performance[0]
    assert performance.requested_completion_utc == "2026-01-03T01:01:00Z"
    assert performance.actual_completion_utc is None
    assert [sample.event_id for sample in result.samples] == [
        "downward-da-001",
        "downward-da-001",
        "downward-da-001",
        "downward-da-001",
    ]
    assert "ramp_limit" in performance.causes
    assert performance.non_performance_duration_seconds == 180.0


def test_repeated_mfrr_replay_is_deterministic_and_event_energy_conserves() -> None:
    request = _request()
    first = replay_mfrr(request)
    second = replay_mfrr(request)

    assert first.result_fingerprint == second.result_fingerprint
    assert [sample.sample_fingerprint for sample in first.samples] == [
        sample.sample_fingerprint for sample in second.samples
    ]
    assert [item.performance_fingerprint for item in first.event_performance] == [
        item.performance_fingerprint for item in second.event_performance
    ]
    assert sum(item.requested_energy_kwh for item in first.event_performance) == pytest.approx(
        first.totals.requested_activation_energy_kwh
    )
    assert sum(item.delivered_energy_kwh for item in first.event_performance) == pytest.approx(
        first.totals.delivered_activation_energy_kwh
    )
