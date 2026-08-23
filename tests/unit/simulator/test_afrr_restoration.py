"""Product-specific deterministic aFRR replay and performance tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re

import pytest

from open_energy_lab.control.restoration_service import (
    build_afrr_directional_capacity_schedule,
    build_restoration_capability,
    build_restoration_energy_baseline_schedule,
)
from open_energy_lab.market.restoration_activation import (
    RestorationDirection,
    build_afrr_activation_trajectory,
)
from open_energy_lab.market.time import CanonicalInterval
from open_energy_lab.simulator.battery import build_initial_state
from open_energy_lab.simulator.restoration_service import (
    AFRRReplayRequest,
    RestorationReplayValidationError,
    apply_restoration_battery_transition,
    build_afrr_replay_request,
    build_restoration_integration_grid,
    enforce_restoration_capability,
    replay_afrr,
)
from open_energy_lab.simulator.scenario import BatteryComponent


START = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


def _duration(resolution: str) -> timedelta:
    return {"PT1M": timedelta(minutes=1), "PT15M": timedelta(minutes=15)}[
        resolution
    ]


def _intervals(count: int, resolution: str) -> tuple[CanonicalInterval, ...]:
    duration = _duration(resolution)
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
        name="afrr-replay-battery",
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
    *, ramp_up: float = 1.0, ramp_down: float = 1.0, max_delay: float = 5.0
):
    return build_restoration_capability(
        {
            "max_ramp_up_kw_per_second": ramp_up,
            "max_ramp_down_kw_per_second": ramp_down,
            "max_activation_delay_seconds": {
                "AFRR": max_delay,
                "MFRR": 300.0,
            },
            "min_supported_duration_seconds": {"AFRR": 1.0, "MFRR": 60.0},
            "max_supported_duration_seconds": {
                "AFRR": 900.0,
                "MFRR": 3600.0,
            },
        }
    )


def _request(
    powers: tuple[float, ...] = (-10.0, 8.0, 0.0, -6.0),
    *,
    resolution: str = "PT15M",
    baseline_powers: tuple[float, ...] | None = None,
    upward_kw: float = 20.0,
    downward_kw: float = 20.0,
    battery: BatteryComponent | None = None,
    capability=None,
):
    intervals = _intervals(len(powers), resolution)
    period = CanonicalInterval.from_utc(
        intervals[0].start_utc, intervals[-1].end_utc
    )
    baseline_values = baseline_powers or (0.0,) * len(powers)
    commitments = build_afrr_directional_capacity_schedule(
        schedule_id="afrr-replay-capacity-v1",
        semantics_version="directional-restoration-capacity-v1",
        period=period,
        intervals=[
            {
                "interval": interval,
                "product": "AFRR",
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
        schedule_id="afrr-replay-baseline-v1",
        semantics_version="restoration-energy-baseline-v1",
        product="AFRR",
        period=period,
        source="unit_fixed",
        intervals=[
            {
                "interval": interval,
                "accepted_baseline_power_kw": power,
            }
            for interval, power in zip(intervals, baseline_values, strict=True)
        ],
    )
    trajectory = build_afrr_activation_trajectory(
        {
            "trajectory_id": "afrr-replay-trajectory-v1",
            "semantics_version": "afrr-interval-average-v1",
            "product": "AFRR",
            "period": period,
            "resolution": resolution,
            "sample_semantics": "interval_average_requested_bess_power_kw",
            "sign_convention": "positive_charge_negative_discharge",
            "source_kind": "SYNTHETIC",
            "created_or_retrieved_at_utc": "2026-01-02T00:00:00Z",
            "mapping_fingerprint": None,
            "samples": [
                {
                    "interval": interval,
                    "requested_balancing_power_kw": power,
                    "direction": (
                        "UPWARD" if power < 0 else "DOWNWARD" if power > 0 else None
                    ),
                    "source_observation_refs": [f"synthetic-row-{index}"],
                }
                for index, (interval, power) in enumerate(
                    zip(intervals, powers, strict=True)
                )
            ],
        }
    )
    selected_battery = battery or _battery()
    selected_capability = capability or _capability()
    grid = build_restoration_integration_grid(
        period=period,
        resolution=resolution,
        intervals=intervals,
    )
    return build_afrr_replay_request(
        request_id="afrr-replay-request-v1",
        semantics_version="afrr-physical-replay-v1",
        battery=selected_battery,
        initial_state=build_initial_state(selected_battery),
        capability=selected_capability,
        commitments=commitments,
        baseline=baseline,
        activation_trajectory=trajectory,
        integration_grid=grid,
        tolerance=1e-6,
    )


def test_request_requires_exact_afrr_trajectory_and_native_alignment() -> None:
    request = _request()
    assert isinstance(request, AFRRReplayRequest)
    assert request.activation_trajectory.period == request.integration_grid.period
    assert request.activation_trajectory.resolution == request.integration_grid.resolution
    assert request.input_fingerprints["activation"] == (
        request.activation_trajectory.trajectory_fingerprint
    )
    assert re.fullmatch(r"[0-9a-f]{64}", request.request_fingerprint)

    with pytest.raises(
        RestorationReplayValidationError, match="AFRRActivationTrajectory|exact"
    ):
        build_afrr_replay_request(
            request_id="wrong-activation",
            semantics_version="v1",
            battery=request.battery,
            initial_state=request.initial_state,
            capability=request.capability,
            commitments=request.commitments,
            baseline=request.baseline,
            activation_trajectory=object(),
            integration_grid=request.integration_grid,
            tolerance=1e-6,
        )

    wrong_grid = build_restoration_integration_grid(
        period=request.integration_grid.period,
        resolution="PT5M",
        intervals=tuple(
            CanonicalInterval.from_utc(
                START + timedelta(minutes=5 * index),
                START + timedelta(minutes=5 * (index + 1)),
            )
            for index in range(12)
        ),
    )
    with pytest.raises(
        RestorationReplayValidationError, match="trajectory|grid|resolution|align"
    ):
        build_afrr_replay_request(
            request_id="wrong-grid",
            semantics_version="v1",
            battery=request.battery,
            initial_state=request.initial_state,
            capability=request.capability,
            commitments=request.commitments,
            baseline=request.baseline,
            activation_trajectory=request.activation_trajectory,
            integration_grid=wrong_grid,
            tolerance=1e-6,
        )


def test_nominal_replay_reports_request_delivery_state_headroom_and_direction() -> None:
    result = replay_afrr(_request())

    assert [sample.requested_balancing_power_kw for sample in result.samples] == [
        -10.0,
        8.0,
        0.0,
        -6.0,
    ]
    assert [sample.delivered_balancing_power_kw for sample in result.samples] == [
        -10.0,
        8.0,
        0.0,
        -6.0,
    ]
    assert [sample.state.soc for sample in result.samples] == pytest.approx(
        [0.475, 0.495, 0.495, 0.48]
    )
    assert [sample.upward_power_headroom_kw for sample in result.samples] == [
        10.0,
        28.0,
        20.0,
        14.0,
    ]
    assert [sample.downward_power_headroom_kw for sample in result.samples] == [
        30.0,
        12.0,
        20.0,
        26.0,
    ]
    assert all(sample.response_delay_seconds == 0.0 for sample in result.samples)
    assert all(sample.tracking_error_kw == 0.0 for sample in result.samples)
    upward = result.directional_performance[RestorationDirection.UPWARD]
    downward = result.directional_performance[RestorationDirection.DOWNWARD]
    assert upward.requested_energy_kwh == pytest.approx(4.0)
    assert upward.delivered_energy_kwh == pytest.approx(4.0)
    assert downward.requested_energy_kwh == pytest.approx(2.0)
    assert downward.delivered_energy_kwh == pytest.approx(2.0)
    assert result.totals.requested_activation_energy_kwh == pytest.approx(6.0)
    assert result.totals.delivered_activation_energy_kwh == pytest.approx(6.0)
    assert result.causes == ()


def test_ramp_limit_preserves_request_and_attributes_undelivered_energy() -> None:
    request = _request(
        (0.0, 10.0),
        resolution="PT1M",
        capability=_capability(ramp_up=0.05, ramp_down=0.05),
    )
    result = replay_afrr(request)
    limited = result.samples[1]

    assert limited.requested_balancing_power_kw == 10.0
    assert limited.capability_accepted_balancing_power_kw == 3.0
    assert limited.delivered_balancing_power_kw == 3.0
    assert limited.achieved_ramp_kw_per_second == pytest.approx(0.05)
    assert limited.tracking_error_kw == pytest.approx(7.0)
    assert limited.delivered_activation_energy_kwh == pytest.approx(0.05)
    assert limited.undelivered_activation_energy_kwh == pytest.approx(7.0 / 60.0)
    assert limited.causes == ("ramp_limit",)
    assert limited.non_performance_duration_seconds == 60.0


def test_commitment_and_directional_headroom_are_distinct_ordered_causes() -> None:
    commitment_limited = replay_afrr(
        _request((30.0,), baseline_powers=(5.0,), downward_kw=20.0)
    ).samples[0]
    assert commitment_limited.capability_accepted_balancing_power_kw == 15.0
    assert commitment_limited.causes == (
        "commitment_limit",
        "downward_headroom",
    )

    headroom_limited = replay_afrr(
        _request((10.0,), baseline_powers=(15.0,), downward_kw=10.0)
    ).samples[0]
    assert headroom_limited.requested_combined_power_kw == 25.0
    assert headroom_limited.capability_accepted_balancing_power_kw == 5.0
    assert headroom_limited.delivered_combined_power_kw == 20.0
    assert headroom_limited.delivered_balancing_power_kw == 5.0
    assert headroom_limited.causes == ("downward_headroom",)


def test_physical_power_limit_remains_separate_from_capability_headroom() -> None:
    battery = _battery()
    decision = enforce_restoration_capability(
        product="AFRR",
        accepted_baseline_power_kw=0.0,
        requested_balancing_power_kw=30.0,
        upward_commitment_kw=40.0,
        downward_commitment_kw=40.0,
        upward_headroom_kw=40.0,
        downward_headroom_kw=40.0,
        previous_capability_combined_power_kw=0.0,
        interval_seconds=900.0,
        capability=_capability(),
    )
    sample = apply_restoration_battery_transition(
        sample_index=0,
        interval=_intervals(1, "PT15M")[0],
        product="AFRR",
        decision=decision,
        battery=battery,
        state=build_initial_state(battery),
        tolerance=1e-6,
    )

    assert decision.causes == ()
    assert sample.delivered_balancing_power_kw == 20.0
    assert sample.tracking_error_kw == 10.0
    assert sample.physical_causes == ("charge_power_limit",)


def test_soc_and_energy_saturation_preserve_bounds_and_conservation() -> None:
    result = replay_afrr(
        _request(
            (10.0,),
            battery=_battery(capacity_kwh=10.0, initial_soc=0.89),
        )
    )
    sample = result.samples[0]

    assert sample.delivered_balancing_power_kw == pytest.approx(0.4)
    assert sample.state.soc == pytest.approx(0.9)
    assert sample.state.soc <= result.request.battery.max_soc
    assert sample.delivered_activation_energy_kwh == pytest.approx(0.1)
    assert sample.undelivered_activation_energy_kwh == pytest.approx(2.4)
    assert sample.causes == ("maximum_soc", "energy_headroom")
    assert result.totals.requested_activation_energy_kwh == pytest.approx(
        result.totals.delivered_activation_energy_kwh
        + result.totals.undelivered_activation_energy_kwh
    )


def test_activation_time_limit_reports_full_interval_nonperformance() -> None:
    request = _request((10.0,))
    decision = enforce_restoration_capability(
        product="AFRR",
        accepted_baseline_power_kw=0.0,
        requested_balancing_power_kw=10.0,
        upward_commitment_kw=20.0,
        downward_commitment_kw=20.0,
        upward_headroom_kw=20.0,
        downward_headroom_kw=20.0,
        previous_capability_combined_power_kw=0.0,
        interval_seconds=900.0,
        capability=request.capability,
        actual_activation_delay_seconds=6.0,
    )
    sample = apply_restoration_battery_transition(
        sample_index=0,
        interval=request.integration_grid.intervals[0],
        product="AFRR",
        decision=decision,
        battery=request.battery,
        state=request.initial_state,
        tolerance=request.tolerance,
    )

    assert sample.delivered_balancing_power_kw == 0.0
    assert sample.response_delay_seconds == 6.0
    assert sample.causes == ("activation_time_limit",)
    assert sample.non_performance_duration_seconds == 900.0


def test_zero_activation_preserves_baseline_and_has_zero_nonperformance() -> None:
    result = replay_afrr(
        _request((0.0, 0.0), baseline_powers=(-2.0, -2.0))
    )

    assert [sample.requested_combined_power_kw for sample in result.samples] == [
        -2.0,
        -2.0,
    ]
    assert [sample.delivered_combined_power_kw for sample in result.samples] == [
        -2.0,
        -2.0,
    ]
    assert all(sample.delivered_balancing_power_kw == 0.0 for sample in result.samples)
    assert result.totals.requested_activation_energy_kwh == 0.0
    assert result.totals.delivered_activation_energy_kwh == 0.0
    assert result.totals.undelivered_activation_energy_kwh == 0.0
    assert result.totals.non_performance_duration_seconds == 0.0
    assert result.causes == ()


def test_repeated_replay_is_deterministic_and_has_no_mfrr_event_surface() -> None:
    request = _request()
    first = replay_afrr(request)
    second = replay_afrr(request)

    assert first == second
    assert first.result_fingerprint == second.result_fingerprint
    assert [sample.sample_fingerprint for sample in first.samples] == [
        sample.sample_fingerprint for sample in second.samples
    ]
    assert re.fullmatch(r"[0-9a-f]{64}", first.result_fingerprint)
    serialized = first.to_dict()
    assert "events" not in serialized
    assert "mfrr" not in repr(serialized).casefold()
