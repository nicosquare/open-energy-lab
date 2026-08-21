"""Contracts for fixed-schedule stacked energy and symmetric-FCR replay."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib
import math
from types import ModuleType
from typing import Any

import pytest

from open_energy_lab.simulator.scenario import BatteryComponent
from tests.unit.market.test_activation import _import_trace, _request as _activation_request
from tests.unit.market.test_artifact import PERIOD_END, PERIOD_START, _build_artifact


def _stacked_module() -> ModuleType:
    try:
        return importlib.import_module("open_energy_lab.simulator.stacked_service")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "open_energy_lab.simulator.stacked_service is not implemented; "
            "T028-T031 must provide schedule validation and physical replay",
            pytrace=False,
        )
        raise AssertionError from exc


def _require(name: str) -> Any:
    module = _stacked_module()
    try:
        return getattr(module, name)
    except AttributeError:
        pytest.fail(
            f"open_energy_lab.simulator.stacked_service.{name} is not implemented",
            pytrace=False,
        )


def _battery(
    *,
    capacity_kwh: float = 100.0,
    max_charge_kw: float = 20.0,
    max_discharge_kw: float = 20.0,
    initial_soc: float = 0.5,
    min_soc: float = 0.1,
    max_soc: float = 0.9,
    efficiency: float = 1.0,
) -> BatteryComponent:
    return BatteryComponent(
        name="stacked-battery",
        capacity_kwh=capacity_kwh,
        max_charge_kw=max_charge_kw,
        max_discharge_kw=max_discharge_kw,
        charge_efficiency=efficiency,
        discharge_efficiency=efficiency,
        initial_soc=initial_soc,
        min_soc=min_soc,
        max_soc=max_soc,
    )


def _energy_schedule(
    powers: list[float] | None = None,
    *,
    start: datetime = PERIOD_START,
    end: datetime = PERIOD_END,
):
    build = _require("build_energy_baseline_schedule")
    count = int((end - start) / timedelta(hours=1))
    values = [0.0] * count if powers is None else powers
    intervals = [
        {
            "start_utc": start + timedelta(hours=index),
            "end_utc": start + timedelta(hours=index + 1),
            "power_kw": value,
            "schedule_source": "fixed",
        }
        for index, value in enumerate(values)
    ]
    return build(
        schedule_id="energy-unit-v1",
        semantics_version="charge-positive-fixed-v1",
        covered_start_utc=start,
        covered_end_utc=end,
        intervals=intervals,
    )


def _fcr_schedule(
    capacities: list[float] | None = None,
    *,
    start: datetime = PERIOD_START,
    end: datetime = PERIOD_END,
    volume_refs: list[str] | None = None,
    price_refs: list[str] | None = None,
):
    build = _require("build_fcr_capacity_schedule")
    count = int((end - start) / timedelta(hours=4))
    values = [5.0] * count if capacities is None else capacities
    volume_refs = volume_refs or [f"fcr_contracted_volume:{index}" for index in range(count)]
    price_refs = price_refs or [f"fcr_capacity_price:{index}" for index in range(count)]
    intervals = [
        {
            "start_utc": start + timedelta(hours=4 * index),
            "end_utc": start + timedelta(hours=4 * (index + 1)),
            "capacity_kw": value,
            "volume_observation_ref": volume_refs[index],
            "price_observation_ref": price_refs[index],
        }
        for index, value in enumerate(values)
    ]
    return build(
        schedule_id="fcr-unit-v1",
        semantics_version="symmetric-fcr-fixed-v1",
        product_identity={
            "product": "symmetric-fcr",
            "tender": "daily",
            "block_duration": "PT4H",
        },
        covered_start_utc=start,
        covered_end_utc=end,
        intervals=intervals,
    )


def _resolution_delta(resolution: str) -> timedelta:
    return {
        "PT10S": timedelta(seconds=10),
        "PT15M": timedelta(minutes=15),
        "PT30M": timedelta(minutes=30),
        "PT1H": timedelta(hours=1),
    }[resolution]


def _activation_trace(
    values: list[float] | None = None,
    *,
    resolution: str = "PT15M",
    start: datetime = PERIOD_START,
    end: datetime = PERIOD_END,
):
    step = _resolution_delta(resolution)
    count = int((end - start) / step)
    if values is None:
        pattern = [1.0, -1.0, 0.0, 0.0]
        values = [pattern[index % len(pattern)] for index in range(count)]
    samples = [
        {
            "start_utc": start + index * step,
            "end_utc": start + (index + 1) * step,
            "value": value,
            "source_value": value,
            "source_unit": "dimensionless",
        }
        for index, value in enumerate(values)
    ]
    request = _activation_request(
        start=start,
        end=end,
        resolution=resolution,
    )
    return _import_trace(
        request,
        samples,
        trace_id=f"activation-{resolution.lower()}-unit",
    )


def _time_contract(
    *,
    activation_resolution: str = "PT15M",
    checkpoint_resolution: str = "PT15M",
    start: datetime = PERIOD_START,
    end: datetime = PERIOD_END,
):
    contract_type = _require("MultiRateTimeContract")
    return contract_type(
        start_utc=start,
        end_utc=end,
        activation_resolution=activation_resolution,
        state_checkpoint_resolution=checkpoint_resolution,
        energy_resolution="PT1H",
        fcr_resolution="PT4H",
        market_timezone="Europe/Paris",
        interval_convention="start-inclusive/end-exclusive",
    )


def _replay_request(
    *,
    market_artifact: object | None = None,
    activation_trace: object | None = None,
    battery: object | None = None,
    energy_schedule: object | None = None,
    fcr_schedule: object | None = None,
    time_contract: object | None = None,
    penalty_rule: object | None = None,
    terminal_soc_target: object | None = None,
):
    request_type = _require("StackedServiceReplayRequest")
    return request_type(
        market_artifact=_build_artifact() if market_artifact is None else market_artifact,
        activation_trace=_activation_trace() if activation_trace is None else activation_trace,
        battery=_battery() if battery is None else battery,
        energy_schedule=_energy_schedule() if energy_schedule is None else energy_schedule,
        fcr_schedule=_fcr_schedule() if fcr_schedule is None else fcr_schedule,
        time_contract=_time_contract() if time_contract is None else time_contract,
        penalty_rule=penalty_rule,
        terminal_soc_target=terminal_soc_target,
        numeric_tolerance=1e-6,
        simulation_semantics_version="stacked-service-replay-v1",
    )


def test_complete_fixed_schedules_have_deterministic_fingerprints() -> None:
    energy = _energy_schedule()
    fcr = _fcr_schedule()

    assert len(energy.intervals) == 8
    assert all(item.schedule_source == "fixed" for item in energy.intervals)
    assert energy.covered_period.start_utc == PERIOD_START
    assert energy.covered_period.end_utc == PERIOD_END
    assert len(energy.schedule_fingerprint) == 64
    assert _energy_schedule().schedule_fingerprint == energy.schedule_fingerprint
    assert len(fcr.intervals) == 2
    assert all(item.capacity_kw == 5.0 for item in fcr.intervals)
    assert len(fcr.schedule_fingerprint) == 64
    assert _fcr_schedule().schedule_fingerprint == fcr.schedule_fingerprint


def test_replay_request_accepts_exactly_one_battery_component() -> None:
    validation_error = _require("StackedServiceValidationError")

    request = _replay_request()
    assert isinstance(request.battery, BatteryComponent)
    with pytest.raises(validation_error, match="one battery|BatteryComponent"):
        _replay_request(battery=(_battery(), _battery()))


@pytest.mark.parametrize("schedule_kind", ["energy", "fcr"])
def test_schedule_builders_reject_partial_or_missing_product_blocks(
    schedule_kind: str,
) -> None:
    validation_error = _require("StackedServiceValidationError")

    if schedule_kind == "energy":
        with pytest.raises(validation_error, match="complete|hour|coverage|gap"):
            _energy_schedule([0.0] * 7)
    else:
        with pytest.raises(validation_error, match="complete|four-hour|coverage|gap"):
            _fcr_schedule([5.0])


def test_pt10s_pt15m_pt1h_pt4h_contract_builds_exact_boundary_maps() -> None:
    contract = _time_contract(activation_resolution="PT10S")
    index = contract.index

    assert len(index.activation_intervals) == 2880
    assert len(index.checkpoint_intervals) == 32
    assert len(index.energy_intervals) == 8
    assert len(index.fcr_intervals) == 2
    assert index.activation_to_checkpoint[:91] == (0,) * 90 + (1,)
    assert index.activation_to_energy[:361] == (0,) * 360 + (1,)
    assert index.activation_to_fcr[:1441] == (0,) * 1440 + (1,)
    assert index.activation_to_checkpoint[-1] == 31
    assert index.activation_to_energy[-1] == 7
    assert index.activation_to_fcr[-1] == 1


@pytest.mark.parametrize(
    ("activation", "checkpoint", "energy", "fcr"),
    [
        ("PT11S", "PT15M", "PT1H", "PT4H"),
        ("PT15M", "PT10S", "PT1H", "PT4H"),
        ("PT15M", "PT1H", "PT30M", "PT4H"),
        ("PT15M", "PT1H", "PT4H", "PT3H"),
    ],
)
def test_time_contract_rejects_noninteger_or_reversed_grid_relationships(
    activation: str,
    checkpoint: str,
    energy: str,
    fcr: str,
) -> None:
    validation_error = _require("StackedServiceValidationError")
    contract_type = _require("MultiRateTimeContract")

    with pytest.raises(validation_error, match="resolution|divide|grid|block"):
        contract_type(
            start_utc=PERIOD_START,
            end_utc=PERIOD_END,
            activation_resolution=activation,
            state_checkpoint_resolution=checkpoint,
            energy_resolution=energy,
            fcr_resolution=fcr,
            market_timezone="Europe/Paris",
            interval_convention="start-inclusive/end-exclusive",
        )


def test_request_rejects_partial_or_incompatible_replay_horizons() -> None:
    validation_error = _require("StackedServiceValidationError")
    partial_end = PERIOD_END - timedelta(minutes=15)
    activation = _activation_trace(end=partial_end)

    with pytest.raises(validation_error, match="horizon|coverage|activation|exact"):
        _replay_request(activation_trace=activation)


def test_fcr_capacity_cannot_exceed_aligned_market_volume() -> None:
    validation_error = _require("StackedServiceValidationError")
    fcr = _fcr_schedule([300_001.0, 5.0])

    with pytest.raises(validation_error, match="volume|MW|capacity"):
        _replay_request(fcr_schedule=fcr)


@pytest.mark.parametrize(
    "powers",
    [
        [18.0] * 8,
        [-18.0] * 8,
    ],
)
def test_symmetric_commitment_requires_bidirectional_power_headroom(
    powers: list[float],
) -> None:
    validation_error = _require("StackedServiceValidationError")

    with pytest.raises(validation_error, match="headroom|charge|discharge|power"):
        _replay_request(energy_schedule=_energy_schedule(powers))


@pytest.mark.parametrize(
    ("volume_refs", "price_refs"),
    [
        (["missing-volume", "fcr_contracted_volume:1"], None),
        (None, ["missing-price", "fcr_capacity_price:1"]),
    ],
)
def test_commitments_must_reference_aligned_volume_and_price_observations(
    volume_refs: list[str] | None,
    price_refs: list[str] | None,
) -> None:
    validation_error = _require("StackedServiceValidationError")
    fcr = _fcr_schedule(volume_refs=volume_refs, price_refs=price_refs)

    with pytest.raises(validation_error, match="observation|reference|aligned"):
        _replay_request(fcr_schedule=fcr)


def test_requested_and_delivered_fcr_are_attributed_from_combined_power() -> None:
    replay = _require("replay_stacked_services")
    result = replay(_replay_request())
    first = result.samples[0]
    second = result.samples[1]

    assert first.baseline_power_kw == 0.0
    assert first.fcr_capacity_kw == 5.0
    assert first.activation == 1.0
    assert first.requested_fcr_power_kw == -5.0
    assert first.requested_combined_power_kw == -5.0
    assert first.delivered_combined_power_kw == -5.0
    assert first.delivered_fcr_power_kw == -5.0
    assert first.signed_tracking_error_kw == 0.0
    assert first.non_delivery_energy_kwh == 0.0
    assert second.activation == -1.0
    assert second.requested_fcr_power_kw == 5.0
    assert second.delivered_fcr_power_kw == 5.0


def test_zero_fcr_keeps_tracking_zero_and_reports_baseline_error_separately() -> None:
    replay = _require("replay_stacked_services")
    battery = _battery(capacity_kwh=10.0, initial_soc=0.9, max_soc=0.9)
    energy = _energy_schedule([10.0] * 8)
    fcr = _fcr_schedule([0.0, 0.0])

    result = replay(
        _replay_request(battery=battery, energy_schedule=energy, fcr_schedule=fcr)
    )

    first = result.samples[0]
    assert first.requested_fcr_power_kw == 0.0
    assert first.delivered_fcr_power_kw == 0.0
    assert first.signed_tracking_error_kw == 0.0
    assert first.absolute_tracking_error_kw == 0.0
    assert first.non_delivery_energy_kwh == 0.0
    assert first.baseline_delivery_error_kw == 10.0


@pytest.mark.parametrize(
    ("initial_soc", "activation", "expected_cause"),
    [
        (0.1, 1.0, "minimum_soc_limit"),
        (0.9, -1.0, "maximum_soc_limit"),
    ],
)
def test_replay_attributes_soc_saturation_causes(
    initial_soc: float,
    activation: float,
    expected_cause: str,
) -> None:
    replay = _require("replay_stacked_services")
    battery = _battery(capacity_kwh=10.0, initial_soc=initial_soc)
    count = int((PERIOD_END - PERIOD_START) / timedelta(minutes=15))
    trace = _activation_trace([activation] * count)

    result = replay(_replay_request(battery=battery, activation_trace=trace))

    assert expected_cause in result.samples[0].saturation_causes
    assert result.samples[0].absolute_tracking_error_kw == 5.0
    assert result.samples[0].non_delivery_energy_kwh == 1.25


@pytest.mark.parametrize(
    ("baseline", "activation", "expected_causes"),
    [
        (18.0, -1.0, ("charge_power_limit",)),
        (-18.0, 1.0, ("discharge_power_limit",)),
    ],
)
def test_diagnostic_replay_attributes_power_limit_causes_in_fixed_order(
    baseline: float,
    activation: float,
    expected_causes: tuple[str, ...],
) -> None:
    diagnostic_replay = _require("replay_stacked_services_diagnostic")
    count = int((PERIOD_END - PERIOD_START) / timedelta(minutes=15))
    request = _replay_request(
        energy_schedule=_energy_schedule([baseline] * 8),
        activation_trace=_activation_trace([activation] * count),
    )

    result = diagnostic_replay(request)

    assert result.validation_status == "commitment_validation_failed"
    assert result.samples[0].saturation_causes == expected_causes


def test_simultaneous_power_and_soc_causes_follow_the_contract_order() -> None:
    diagnostic_replay = _require("replay_stacked_services_diagnostic")
    count = int((PERIOD_END - PERIOD_START) / timedelta(minutes=15))
    request = _replay_request(
        battery=_battery(capacity_kwh=10.0, initial_soc=0.9, max_soc=0.9),
        energy_schedule=_energy_schedule([18.0] * 8),
        activation_trace=_activation_trace([-1.0] * count),
    )

    result = diagnostic_replay(request)

    assert result.samples[0].saturation_causes == (
        "charge_power_limit",
        "maximum_soc_limit",
    )


def test_contiguous_saturation_samples_form_deterministic_events() -> None:
    replay = _require("replay_stacked_services")
    count = int((PERIOD_END - PERIOD_START) / timedelta(minutes=15))
    values = [-1.0] * 4 + [0.0] * 4 + [-1.0] * (count - 8)
    request = _replay_request(
        battery=_battery(capacity_kwh=10.0, initial_soc=0.9, max_soc=0.9),
        activation_trace=_activation_trace(values),
    )

    first = replay(request)
    second = replay(request)

    assert first.saturation_events == second.saturation_events
    assert first.trace_fingerprint == second.trace_fingerprint
    assert first.result_fingerprint == second.result_fingerprint
    assert all(event.sample_count > 0 and event.start_utc < event.end_utc for event in first.saturation_events)
    assert [event.event_id for event in first.saturation_events] == [
        f"saturation-{index:04d}" for index in range(len(first.saturation_events))
    ]


def test_checkpoint_hourly_and_fcr_aggregation_conserve_terminal_energy() -> None:
    replay = _require("replay_stacked_services")
    result = replay(_replay_request())

    sample_charge = sum(sample.charge_energy_kwh for sample in result.samples)
    sample_discharge = sum(sample.discharge_energy_kwh for sample in result.samples)
    assert len(result.state_checkpoints) == 33
    assert len(result.checkpoint_summaries) == 32
    assert len(result.energy_summaries) == 8
    assert len(result.fcr_summaries) == 2
    for summaries in (
        result.checkpoint_summaries,
        result.energy_summaries,
        result.fcr_summaries,
    ):
        assert sum(item.charge_energy_kwh for item in summaries) == pytest.approx(sample_charge, abs=1e-6)
        assert sum(item.discharge_energy_kwh for item in summaries) == pytest.approx(sample_discharge, abs=1e-6)
        assert sum(item.net_terminal_energy_kwh for item in summaries) == pytest.approx(sample_charge - sample_discharge, abs=1e-6)
    assert result.throughput_kwh == pytest.approx(sample_charge + sample_discharge, abs=1e-6)


def test_nonfinite_schedule_power_and_capacity_are_rejected() -> None:
    validation_error = _require("StackedServiceValidationError")

    with pytest.raises(validation_error, match="finite"):
        _energy_schedule([math.nan] + [0.0] * 7)
    with pytest.raises(validation_error, match="finite"):
        _fcr_schedule([math.inf, 5.0])
