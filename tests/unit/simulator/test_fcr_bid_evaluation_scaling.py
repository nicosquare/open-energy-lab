"""Instrumented linear-scaling gates for the ordinary-day FCR evaluator."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType

from oel_validation.scripts.run_fcr_bid_reference_parity import (
    assemble_reference_request,
)
from open_energy_lab.market.activation import (
    ActivationImportRequest,
    import_regulation_activation_trace,
)
from oel_validation.fcr_bid_evaluation import compare_reference_values
from oel_validation.reference_fcr import load_golden_reference_fixture
from open_energy_lab.simulator import fcr_bid_evaluation as evaluation
from open_energy_lab.simulator.fcr_settlement import settle_fixed_fcr_bid
from open_energy_lab.simulator.stacked_service import (
    _PhysicalReplayInputs,
    _aggregate_physical_samples,
    _physical_samples,
)


FIXTURE_PATH = Path(
    "tests/fixtures/fcr_bid_evaluation/"
    "robust_storage_bidding_2023-06-18_aggregate_v1.json"
)


class CountingTuple(tuple):
    """Tuple that records each request for a complete iterator."""

    def __new__(cls, values):
        instance = super().__new__(cls, values)
        instance.iterations = 0
        return instance

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()

    def reset(self) -> None:
        self.iterations = 0


def _ordinary_day_case():
    fixture = load_golden_reference_fixture(FIXTURE_PATH)
    period = fixture.mapping.target_period
    step = timedelta(seconds=10)
    activation = import_regulation_activation_trace(
        ActivationImportRequest(
            source_name="Feature 012 scaling oracle",
            source_locator="authored-zero-activation",
            source_revision="v1",
            source_timezone="Europe/Paris",
            requested_start_utc=period.start_utc,
            requested_end_utc=period.end_utc,
            source_resolution="PT10S",
            source_value_kind="interval_average",
            source_sign_meaning="positive is upward/discharge",
            normalization_rule={
                "conversion": "identity",
                "formula": "activation",
                "point_to_interval": "already_interval_average",
                "clip_min": -1.0,
                "clip_max": 1.0,
                "target_sign": "positive is upward/discharge",
            },
            redistribution_basis={"source": "project-authored test data"},
        ),
        [
            {
                "start_utc": period.start_utc + index * step,
                "end_utc": period.start_utc + (index + 1) * step,
                "value": 0.0,
                "source_value": 0.0,
                "source_unit": "dimensionless",
            }
            for index in range(8_640)
        ],
        trace_id="feature-012-scaling-zero-activation-v1",
        created_at_utc=datetime(2026, 8, 26, tzinfo=UTC),
    )
    zero_activation_bounds = {
        "charge_energy_kwh": 0.012,
        "discharge_energy_kwh": 0.012,
        "stored_energy_kwh": 0.012 / 0.92,
        "power_extrema_kw": 0.0005,
        "day_ahead_revenue_eur": 0.001073575,
        "fcr_capacity_revenue_eur": 0.00037976,
        "activation_revenue_eur": 0.0,
        "combined_fcr_revenue_eur": 0.00037976,
        "total_revenue_eur": 0.001453335,
    }
    policy = replace(
        fixture.precision_policy,
        field_bounds=MappingProxyType(
            {
                key: replace(value, decision_bound=zero_activation_bounds[key])
                for key, value in fixture.precision_policy.field_bounds.items()
            }
        ),
    )
    fixture = replace(fixture, precision_policy=policy)
    request = assemble_reference_request(
        fixture=fixture,
        activation_trace=activation,
    )
    return fixture, request


def test_ordinary_day_stages_use_bounded_complete_iterations() -> None:
    fixture, request = _ordinary_day_case()
    energy_intervals = CountingTuple(request.energy_schedule.intervals)
    fcr_intervals = CountingTuple(request.fcr_schedule.intervals)
    object.__setattr__(request.energy_schedule, "intervals", energy_intervals)
    object.__setattr__(request.fcr_schedule, "intervals", fcr_intervals)

    diagnostics = evaluation._preflight_diagnostics(request)

    assert [item.code for item in diagnostics] == ["preflight_valid"]
    assert energy_intervals.iterations <= 2
    assert fcr_intervals.iterations <= 2

    activation_samples = CountingTuple(request.activation_trace.samples)
    object.__setattr__(request.activation_trace, "samples", activation_samples)
    physical_inputs = _PhysicalReplayInputs(
        activation_trace=request.activation_trace,
        battery=request.battery,
        energy_schedule=request.energy_schedule,
        fcr_schedule=request.fcr_schedule,
        time_contract=request.time_contract,
        numeric_tolerance=request.numeric_tolerance,
        terminal_soc_target=request.terminal_soc_target,
    )
    replay_samples = _physical_samples(physical_inputs)

    assert len(replay_samples) == 8_640
    assert activation_samples.iterations <= 2

    counted_replay_samples = CountingTuple(replay_samples)
    physical = _aggregate_physical_samples(
        physical_inputs,
        counted_replay_samples,
    )

    assert physical.samples is counted_replay_samples
    assert counted_replay_samples.iterations <= 2
    assert len(physical.checkpoint_summaries) == 96
    assert len(physical.energy_summaries) == 24
    assert len(physical.fcr_summaries) == 6
    assert (
        len(physical.state_checkpoints)
        + len(physical.checkpoint_summaries)
        + len(physical.energy_summaries)
        + len(physical.fcr_summaries)
        + len(physical.saturation_events)
        < 2 * len(counted_replay_samples)
    )

    counted_replay_samples.reset()
    physical_metrics = evaluation._daily_physical_metrics(request, physical)
    assert counted_replay_samples.iterations <= 2

    counted_replay_samples.reset()
    settlement = settle_fixed_fcr_bid(request, counted_replay_samples)
    assert counted_replay_samples.iterations <= 2

    activation_samples.reset()
    actual_values = evaluation._reference_actual_values(
        request,
        physical_metrics,
        settlement,
    )
    comparison = compare_reference_values(
        fixture=fixture,
        actual_values=actual_values,
        activation_trace=request.activation_trace,
    )
    assert comparison.fields
    assert activation_samples.iterations <= 2

    counted_replay_samples.reset()
    trace_payload = evaluation._physical_trace_payload(physical)
    evaluation._fingerprint(trace_payload)
    assert len(trace_payload["samples"]) == 8_640
    assert counted_replay_samples.iterations <= 2
