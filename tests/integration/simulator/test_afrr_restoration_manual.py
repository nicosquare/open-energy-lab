"""End-to-end and shared-adapter validation against the manual aFRR oracle."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

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
from open_energy_lab.market.time import (
    CanonicalInterval,
    parse_iso8601_duration,
)
from open_energy_lab.simulator.battery import build_initial_state
from open_energy_lab.simulator.restoration_service import (
    aggregate_restoration_samples,
    apply_restoration_battery_transition,
    build_afrr_replay_request,
    build_restoration_integration_grid,
    enforce_restoration_capability,
    replay_afrr,
)
from open_energy_lab.simulator.scenario import BatteryComponent


FIXTURE = Path("tests/fixtures/restoration/manual_afrr_v1.json")
TOLERANCE = 1e-6


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _case_inputs(case: dict[str, object]):
    period_data = case["period"]
    start = _utc(period_data["start_utc"])
    end = _utc(period_data["end_utc"])
    resolution = period_data["resolution"]
    duration = parse_iso8601_duration(resolution)
    intervals = []
    cursor = start
    while cursor < end:
        intervals.append(CanonicalInterval.from_utc(cursor, cursor + duration))
        cursor += duration
    interval_tuple = tuple(intervals)
    period = CanonicalInterval.from_utc(start, end)
    battery = BatteryComponent(**case["battery"])
    capability = build_restoration_capability(case["capability"])
    commitment = case["commitment"]
    commitments = build_afrr_directional_capacity_schedule(
        schedule_id=f"{case['case_id']}-capacity",
        semantics_version="directional-restoration-capacity-v1",
        period=period,
        intervals=[
            {
                "interval": interval,
                "product": "AFRR",
                "direction": direction,
                "committed_capacity_kw": capacity,
                "eligibility": True,
                "source_or_assumption_ref": f"manual-{direction.lower()}-{index}",
            }
            for direction, capacity in (
                ("UPWARD", commitment["upward_kw"]),
                ("DOWNWARD", commitment["downward_kw"]),
            )
            for index, interval in enumerate(interval_tuple)
        ],
    )
    baseline = build_restoration_energy_baseline_schedule(
        schedule_id=f"{case['case_id']}-baseline",
        semantics_version="restoration-energy-baseline-v1",
        product="AFRR",
        period=period,
        source="manual_fixture",
        intervals=[
            {
                "interval": interval,
                "accepted_baseline_power_kw": power,
            }
            for interval, power in zip(
                interval_tuple, case["baseline_power_kw"], strict=True
            )
        ],
    )
    activation = case["activation"]
    powers = activation["requested_balancing_power_kw"]
    trajectory = build_afrr_activation_trajectory(
        {
            "trajectory_id": activation["trajectory_id"],
            "semantics_version": activation["semantics_version"],
            "product": "AFRR",
            "period": period,
            "resolution": resolution,
            "sample_semantics": "interval_average_requested_bess_power_kw",
            "sign_convention": "positive_charge_negative_discharge",
            "source_kind": activation["source_kind"],
            "created_or_retrieved_at_utc": activation[
                "created_or_retrieved_at_utc"
            ],
            "mapping_fingerprint": activation["mapping_fingerprint"],
            "samples": [
                {
                    "interval": interval,
                    "requested_balancing_power_kw": power,
                    "direction": (
                        "UPWARD" if power < 0 else "DOWNWARD" if power > 0 else None
                    ),
                    "source_observation_refs": [
                        f"manual-afrr:{case['case_id']}:{index}"
                    ],
                }
                for index, (interval, power) in enumerate(
                    zip(interval_tuple, powers, strict=True)
                )
            ],
        }
    )
    grid = build_restoration_integration_grid(
        period=period,
        resolution=resolution,
        intervals=interval_tuple,
    )
    request = build_afrr_replay_request(
        request_id=f"{case['case_id']}-request",
        semantics_version="afrr-physical-replay-v1",
        battery=battery,
        initial_state=build_initial_state(battery),
        capability=capability,
        commitments=commitments,
        baseline=baseline,
        activation_trajectory=trajectory,
        integration_grid=grid,
        tolerance=TOLERANCE,
    )
    return request


def _actual_sample_values(result, index: int) -> dict[str, object]:
    sample = result.samples[index]
    trajectory_sample = result.request.activation_trajectory.samples[index]
    return {
        "sample_index": sample.sample_index,
        "direction": (
            None
            if trajectory_sample.direction is None
            else trajectory_sample.direction.value
        ),
        "requested_balancing_power_kw": sample.requested_balancing_power_kw,
        "capability_accepted_balancing_power_kw": (
            sample.capability_accepted_balancing_power_kw
        ),
        "requested_combined_power_kw": sample.requested_combined_power_kw,
        "delivered_combined_power_kw": sample.delivered_combined_power_kw,
        "delivered_balancing_power_kw": sample.delivered_balancing_power_kw,
        "tracking_error_kw": sample.tracking_error_kw,
        "requested_activation_energy_kwh": (
            sample.requested_activation_energy_kwh
        ),
        "delivered_activation_energy_kwh": (
            sample.delivered_activation_energy_kwh
        ),
        "undelivered_activation_energy_kwh": (
            sample.undelivered_activation_energy_kwh
        ),
        "charge_energy_kwh": sample.charge_energy_kwh,
        "discharge_energy_kwh": sample.discharge_energy_kwh,
        "soc": sample.state.soc,
        "upward_power_headroom_kw": sample.upward_power_headroom_kw,
        "downward_power_headroom_kw": sample.downward_power_headroom_kw,
        "upward_energy_headroom_kwh": sample.upward_energy_headroom_kwh,
        "downward_energy_headroom_kwh": sample.downward_energy_headroom_kwh,
        "achieved_ramp_kw_per_second": sample.achieved_ramp_kw_per_second,
        "causes": list(sample.causes),
        "non_performance_duration_seconds": (
            sample.non_performance_duration_seconds
        ),
    }


def _assert_expected_subset(
    actual: dict[str, object], expected: dict[str, object]
) -> None:
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if isinstance(expected_value, float):
            assert actual_value == pytest.approx(expected_value, abs=TOLERANCE), key
        else:
            assert actual_value == expected_value, key


def _assert_totals(result, expected: dict[str, float]) -> None:
    actual = result.totals.to_dict()
    for key, expected_value in expected.items():
        if key == "final_soc":
            actual_value = result.samples[-1].state.soc
        else:
            actual_value = actual[key]
        assert actual_value == pytest.approx(expected_value, abs=TOLERANCE), key


def test_manual_afrr_cases_reproduce_published_samples_totals_and_fingerprints() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    high_level_cases = [
        case
        for case in fixture["cases"]
        if "capability_headroom_override" not in case
    ]

    for case in high_level_cases:
        request = _case_inputs(case)
        first = replay_afrr(request)
        second = replay_afrr(request)

        assert first.result_fingerprint == second.result_fingerprint
        assert first.request_fingerprint == second.request_fingerprint
        assert first.activation_trajectory_fingerprint == (
            second.activation_trajectory_fingerprint
        )
        assert [sample.sample_fingerprint for sample in first.samples] == [
            sample.sample_fingerprint for sample in second.samples
        ]
        for index, expected in enumerate(case["expected_samples"]):
            _assert_expected_subset(_actual_sample_values(first, index), expected)
        _assert_totals(first, case["expected_totals"])

        expected_directional = case.get("expected_directional", {})
        for direction_name, expected in expected_directional.items():
            performance = first.directional_performance[
                RestorationDirection(direction_name)
            ]
            assert performance.sample_count == expected["sample_count"]
            assert performance.requested_energy_kwh == pytest.approx(
                expected["requested_energy_kwh"], abs=TOLERANCE
            )
            assert performance.delivered_energy_kwh == pytest.approx(
                expected["delivered_energy_kwh"], abs=TOLERANCE
            )
            assert performance.undelivered_energy_kwh == pytest.approx(
                expected["undelivered_energy_kwh"], abs=TOLERANCE
            )
            assert performance.non_performance_duration_seconds == pytest.approx(
                expected["non_performance_duration_seconds"], abs=TOLERANCE
            )


def test_manual_power_case_isolates_shared_physical_clipping_deterministically() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    case = next(
        item
        for item in fixture["cases"]
        if item["case_id"] == "charge-power-limited"
    )
    request = _case_inputs(case)
    interval = request.integration_grid.intervals[0]
    baseline_power = request.baseline.intervals[0].accepted_baseline_power_kw
    override = case["capability_headroom_override"]
    decision = enforce_restoration_capability(
        product="AFRR",
        accepted_baseline_power_kw=baseline_power,
        requested_balancing_power_kw=(
            request.activation_trajectory.samples[0].requested_balancing_power_kw
        ),
        upward_commitment_kw=case["commitment"]["upward_kw"],
        downward_commitment_kw=case["commitment"]["downward_kw"],
        upward_headroom_kw=override["upward_kw"],
        downward_headroom_kw=override["downward_kw"],
        previous_capability_combined_power_kw=baseline_power,
        interval_seconds=(interval.end_utc - interval.start_utc).total_seconds(),
        capability=request.capability,
    )

    def _run():
        sample = apply_restoration_battery_transition(
            sample_index=0,
            interval=interval,
            product="AFRR",
            decision=decision,
            battery=request.battery,
            state=request.initial_state,
            tolerance=request.tolerance,
        )
        totals = aggregate_restoration_samples((sample,), tolerance=request.tolerance)
        return sample, totals

    first_sample, first_totals = _run()
    second_sample, second_totals = _run()
    actual = {
        **_actual_sample_values(
            type(
                "AdapterResult",
                (),
                {
                    "samples": (first_sample,),
                    "request": request,
                },
            )(),
            0,
        )
    }
    _assert_expected_subset(actual, case["expected_samples"][0])
    assert first_sample.sample_fingerprint == second_sample.sample_fingerprint
    assert first_totals.totals_fingerprint == second_totals.totals_fingerprint
    for key, expected_value in case["expected_totals"].items():
        if key == "final_soc":
            actual_value = first_sample.state.soc
        else:
            actual_value = getattr(first_totals, key)
        assert actual_value == pytest.approx(expected_value, abs=TOLERANCE), key
