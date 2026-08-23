"""End-to-end manual mFRR oracle and reserve-product separation checks."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from open_energy_lab.control.restoration_service import (
    build_mfrr_directional_capacity_schedule,
    build_restoration_capability,
    build_restoration_energy_baseline_schedule,
)
from open_energy_lab.market.activation import load_regulation_activation_trace
from open_energy_lab.market.restoration_activation import (
    RestorationActivationValidationError,
    build_afrr_activation_trajectory,
    build_mfrr_activation_sequence,
)
from open_energy_lab.market.time import (
    CanonicalInterval,
    parse_iso8601_duration,
)
from open_energy_lab.simulator.battery import build_initial_state
from open_energy_lab.simulator.restoration_service import (
    RestorationReplayValidationError,
    build_afrr_replay_request,
    build_mfrr_replay_request,
    build_restoration_integration_grid,
    replay_mfrr,
)
from open_energy_lab.simulator.scenario import BatteryComponent


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPOSITORY_ROOT / "tests/fixtures/restoration/manual_mfrr_v1.json"
FCR_TRACE_PATH = (
    REPOSITORY_ROOT / "tests/fixtures/market/france_2022-08-19_activation_v1.json"
)
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
VALID_CASES = {item["case_id"]: item for item in FIXTURE["valid_cases"]}


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _case_intervals(case: dict[str, object]) -> tuple[CanonicalInterval, ...]:
    period = case["period"]
    assert isinstance(period, dict)
    start = _datetime(str(period["start_utc"]))
    end = _datetime(str(period["end_utc"]))
    duration = parse_iso8601_duration(str(period["resolution"]))
    intervals = []
    cursor = start
    while cursor < end:
        next_cursor = cursor + duration
        intervals.append(CanonicalInterval.from_utc(cursor, next_cursor))
        cursor = next_cursor
    assert cursor == end
    return tuple(intervals)


def _request(case: dict[str, object]):
    intervals = _case_intervals(case)
    period = CanonicalInterval.from_utc(
        intervals[0].start_utc,
        intervals[-1].end_utc,
    )
    battery_data = case["battery"]
    capability_data = case["capability"]
    commitment_data = case["commitment"]
    sequence_data = case["sequence"]
    assert isinstance(battery_data, dict)
    assert isinstance(capability_data, dict)
    assert isinstance(commitment_data, dict)
    assert isinstance(sequence_data, dict)
    battery = BatteryComponent(**battery_data)
    capability = build_restoration_capability(capability_data)
    commitments = build_mfrr_directional_capacity_schedule(
        schedule_id=f"{case['case_id']}-commitments",
        semantics_version="directional-restoration-capacity-v1",
        period=period,
        intervals=[
            {
                "interval": interval,
                "product": "MFRR",
                "direction": direction,
                "committed_capacity_kw": capacity,
                "eligibility": True,
                "source_or_assumption_ref": f"manual:{direction.lower()}:{index}",
            }
            for direction, capacity in (
                ("UPWARD", commitment_data["upward_kw"]),
                ("DOWNWARD", commitment_data["downward_kw"]),
            )
            for index, interval in enumerate(intervals)
        ],
    )
    baseline_values = case["baseline_power_kw"]
    assert isinstance(baseline_values, list)
    baseline = build_restoration_energy_baseline_schedule(
        schedule_id=f"{case['case_id']}-baseline",
        semantics_version="restoration-energy-baseline-v1",
        product="MFRR",
        period=period,
        source="manual_fixed",
        intervals=[
            {
                "interval": interval,
                "accepted_baseline_power_kw": value,
            }
            for interval, value in zip(intervals, baseline_values, strict=True)
        ],
    )
    sequence = build_mfrr_activation_sequence(
        {
            **sequence_data,
            "product": "MFRR",
            "period": period,
            "shape_semantics": "delay_linear_ramp_hold_linear_ramp",
            "sign_convention": "positive_charge_negative_discharge",
            "events": [
                {**event, "product": "MFRR"}
                for event in sequence_data["events"]
            ],
        }
    )
    resolution = str(case["period"]["resolution"])
    grid = build_restoration_integration_grid(
        period=period,
        resolution=resolution,
        intervals=intervals,
    )
    return build_mfrr_replay_request(
        request_id=f"{case['case_id']}-request",
        semantics_version="mfrr-physical-replay-v1",
        battery=battery,
        initial_state=build_initial_state(battery),
        capability=capability,
        commitments=commitments,
        baseline=baseline,
        activation_sequence=sequence,
        integration_grid=grid,
        tolerance=1e-6,
    )


@pytest.mark.parametrize("case_id", tuple(VALID_CASES))
def test_manual_mfrr_cases_reproduce_every_published_sample_event_and_total(
    case_id: str,
) -> None:
    case = VALID_CASES[case_id]
    request = _request(case)
    first = replay_mfrr(request)
    second = replay_mfrr(request)

    assert first.result_fingerprint == second.result_fingerprint
    assert len(first.samples) == len(case["expected_samples"])
    for actual, expected in zip(
        first.samples,
        case["expected_samples"],
        strict=True,
    ):
        assert actual.sample_index == expected["sample_index"]
        assert actual.event_id == expected["event_id"]
        expected_kind = expected["kind"]
        assert (None if actual.mfrr_kind is None else actual.mfrr_kind.value) == expected_kind
        for field_name in (
            "requested_balancing_power_kw",
            "delivered_balancing_power_kw",
            "requested_activation_energy_kwh",
            "delivered_activation_energy_kwh",
            "undelivered_activation_energy_kwh",
            "non_performance_duration_seconds",
        ):
            assert getattr(actual, field_name) == pytest.approx(expected[field_name])
        if "requested_combined_power_kw" in expected:
            assert actual.requested_combined_power_kw == pytest.approx(
                expected["requested_combined_power_kw"]
            )
        if "delivered_combined_power_kw" in expected:
            assert actual.delivered_combined_power_kw == pytest.approx(
                expected["delivered_combined_power_kw"]
            )
        assert actual.state.soc == pytest.approx(expected["soc"])
        assert list(actual.causes) == expected["causes"]

    assert len(first.event_performance) == len(case["expected_events"])
    for actual, expected in zip(
        first.event_performance,
        case["expected_events"],
        strict=True,
    ):
        assert actual.event_id == expected["event_id"]
        assert actual.kind.value == expected["kind"]
        assert actual.direction.value == expected["direction"]
        for field_name in (
            "requested_start_utc",
            "actual_start_utc",
            "requested_completion_utc",
            "actual_completion_utc",
        ):
            assert getattr(actual, field_name) == expected[field_name]
        for field_name in (
            "requested_energy_kwh",
            "delivered_energy_kwh",
            "undelivered_energy_kwh",
            "maximum_achieved_ramp_kw_per_second",
            "non_performance_duration_seconds",
        ):
            assert getattr(actual, field_name) == pytest.approx(expected[field_name])
        assert list(actual.causes) == expected["causes"]

    expected_totals = case["expected_totals"]
    for field_name in (
        "charge_energy_kwh",
        "discharge_energy_kwh",
        "net_terminal_energy_kwh",
        "throughput_kwh",
        "requested_activation_energy_kwh",
        "delivered_activation_energy_kwh",
        "undelivered_activation_energy_kwh",
        "non_performance_duration_seconds",
    ):
        assert getattr(first.totals, field_name) == pytest.approx(
            expected_totals[field_name]
        )
    assert first.samples[-1].state.soc == pytest.approx(expected_totals["final_soc"])


def test_manual_overlap_is_rejected_before_replay() -> None:
    case = FIXTURE["invalid_cases"][0]
    period = case["period"]
    sequence = case["sequence"]
    assert isinstance(period, dict)
    assert isinstance(sequence, dict)

    with pytest.raises(RestorationActivationValidationError, match="overlap"):
        build_mfrr_activation_sequence(
            {
                **sequence,
                "product": "MFRR",
                "period": CanonicalInterval.from_utc(
                    _datetime(period["start_utc"]),
                    _datetime(period["end_utc"]),
                ),
                "shape_semantics": "delay_linear_ramp_hold_linear_ramp",
                "sign_convention": "positive_charge_negative_discharge",
                "events": [
                    {**event, "product": "MFRR"}
                    for event in sequence["events"]
                ],
            }
        )


def test_fcr_afrr_and_mfrr_activation_types_cannot_be_substituted() -> None:
    request = _request(VALID_CASES["upward-scheduled-rectangular"])
    interval = request.integration_grid.intervals[0]
    afrr = build_afrr_activation_trajectory(
        {
            "trajectory_id": "wrong-afrr",
            "semantics_version": "v1",
            "product": "AFRR",
            "period": request.integration_grid.period,
            "resolution": request.integration_grid.resolution,
            "sample_semantics": "interval_average_requested_bess_power_kw",
            "sign_convention": "positive_charge_negative_discharge",
            "source_kind": "SYNTHETIC",
            "created_or_retrieved_at_utc": "2026-01-04T00:00:00Z",
            "mapping_fingerprint": None,
            "samples": [
                {
                    "interval": interval,
                    "requested_balancing_power_kw": 0.0,
                    "direction": None,
                    "source_observation_refs": ["synthetic:wrong-afrr"],
                }
            ],
        }
    )
    fcr = load_regulation_activation_trace(FCR_TRACE_PATH)

    for wrong_activation in (afrr, fcr):
        with pytest.raises(
            RestorationReplayValidationError,
            match="MFRRActivationSequence|exact",
        ):
            build_mfrr_replay_request(
                request_id="wrong-product",
                semantics_version="v1",
                battery=request.battery,
                initial_state=request.initial_state,
                capability=request.capability,
                commitments=request.commitments,
                baseline=request.baseline,
                activation_sequence=wrong_activation,
                integration_grid=request.integration_grid,
            )

    with pytest.raises(
        RestorationReplayValidationError,
        match="AFRRActivationTrajectory|exact",
    ):
        build_afrr_replay_request(
            request_id="wrong-product",
            semantics_version="v1",
            battery=request.battery,
            initial_state=request.initial_state,
            capability=request.capability,
            commitments=request.commitments,
            baseline=request.baseline,
            activation_trajectory=request.activation_sequence,
            integration_grid=request.integration_grid,
        )
