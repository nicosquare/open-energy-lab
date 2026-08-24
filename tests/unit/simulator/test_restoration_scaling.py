"""Deterministic counted-input scaling contracts for restoration services."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
from typing import TypeVar

import pytest

from open_energy_lab.control.restoration_service import (
    build_directional_capacity_schedule,
    build_restoration_baseline_config,
    build_restoration_capability,
    build_restoration_energy_baseline_schedule,
)
from open_energy_lab.market.restoration_activation import (
    MFRRActivationEvent,
    build_afrr_activation_trajectory,
    build_mfrr_activation_sequence,
)
from open_energy_lab.market.restoration_artifact import (
    RESTORATION_MARKET_SCHEMA_VERSION,
    build_restoration_market_artifact,
)
from open_energy_lab.market.time import CanonicalInterval
import open_energy_lab.simulator.restoration_service as restoration_service_module
from open_energy_lab.simulator.battery import build_initial_state
from open_energy_lab.simulator.restoration_service import (
    aggregate_restoration_samples,
    build_afrr_replay_request,
    build_mfrr_replay_request,
    build_restoration_integration_grid,
    build_restoration_replay_result_core,
    replay_afrr,
    replay_mfrr,
)
from open_energy_lab.simulator.scenario import BatteryComponent


T = TypeVar("T")
START = datetime(2026, 2, 1, 0, 0, tzinfo=UTC)
SEGMENT_FIELDS = frozenset(
    {
        "activation_delay_seconds",
        "ramp_up_seconds",
        "hold_seconds",
        "ramp_down_seconds",
    }
)


class _CountingSequence(Sequence[T]):
    """Sequence that records element reads without relying on elapsed time."""

    def __init__(self, values: Sequence[T]) -> None:
        self._values = tuple(values)
        self.item_visits = 0

    def __len__(self) -> int:
        return len(self._values)

    def __getitem__(self, index: int | slice) -> T | tuple[T, ...]:
        value = self._values[index]
        self.item_visits += len(value) if isinstance(index, slice) else 1
        return value

    def __iter__(self) -> Iterator[T]:
        for value in self._values:
            self.item_visits += 1
            yield value

    def reset(self) -> None:
        self.item_visits = 0


class _CountingSegmentMapping(Mapping[str, object]):
    """Event payload that counts reads of the four analytic shape segments."""

    def __init__(self, values: Mapping[str, object]) -> None:
        self._values = dict(values)
        self.segment_visits = 0

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __getitem__(self, key: str) -> object:
        if key in SEGMENT_FIELDS:
            self.segment_visits += 1
        return self._values[key]

    def to_dict(self) -> dict[str, object]:
        return dict(self._values)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _intervals(
    count: int,
    *,
    step_seconds: int,
    start: datetime = START,
) -> tuple[CanonicalInterval, ...]:
    step = timedelta(seconds=step_seconds)
    return tuple(
        CanonicalInterval.from_utc(start + index * step, start + (index + 1) * step)
        for index in range(count)
    )


def _period(intervals: Sequence[CanonicalInterval]) -> CanonicalInterval:
    return CanonicalInterval.from_utc(
        intervals[0].start_utc,
        intervals[-1].end_utc,
    )


def _battery() -> BatteryComponent:
    return BatteryComponent(
        name="restoration-scaling-battery",
        capacity_kwh=1000.0,
        max_charge_kw=100.0,
        max_discharge_kw=100.0,
        charge_efficiency=1.0,
        discharge_efficiency=1.0,
        initial_soc=0.5,
        min_soc=0.1,
        max_soc=0.9,
    )


def _capability():
    return build_restoration_capability(
        {
            "max_ramp_up_kw_per_second": 100.0,
            "max_ramp_down_kw_per_second": 100.0,
            "max_activation_delay_seconds": {"AFRR": 5.0, "MFRR": 300.0},
            "min_supported_duration_seconds": {"AFRR": 1.0, "MFRR": 60.0},
            "max_supported_duration_seconds": {"AFRR": 600.0, "MFRR": 600.0},
        }
    )


def _commitments(
    product: str,
    intervals: Sequence[CanonicalInterval],
):
    period = _period(intervals)
    return build_directional_capacity_schedule(
        schedule_id=f"{product.lower()}-scaling-commitments-v1",
        semantics_version="directional-restoration-capacity-v1",
        product=product,
        period=period,
        intervals=[
            {
                "interval": interval,
                "product": product,
                "direction": direction,
                "committed_capacity_kw": 20.0,
                "eligibility": True,
                "source_or_assumption_ref": (
                    f"scaling-{direction.lower()}-{index}"
                ),
            }
            for direction in ("UPWARD", "DOWNWARD")
            for index, interval in enumerate(intervals)
        ],
    )


def _baseline(product: str, intervals: Sequence[CanonicalInterval]):
    return build_restoration_energy_baseline_schedule(
        schedule_id=f"{product.lower()}-scaling-baseline-v1",
        semantics_version="restoration-energy-baseline-v1",
        product=product,
        period=_period(intervals),
        source="scaling_fixed_zero",
        intervals=[
            {"interval": interval, "accepted_baseline_power_kw": 0.0}
            for interval in intervals
        ],
    )


def _grid(intervals: Sequence[CanonicalInterval]):
    return build_restoration_integration_grid(
        period=_period(intervals),
        resolution="PT1M",
        intervals=intervals,
    )


def _market_artifact_payload(
    observations: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    count = len(observations)
    intervals = _intervals(count, step_seconds=900)
    period = _period(intervals)
    response = b'{"synthetic":"bounded-observations"}'
    document_ref = "rte-scaling-observations-v1"
    return {
        "schema_version": RESTORATION_MARKET_SCHEMA_VERSION,
        "artifact_id": "rte-afrr-scaling-v1",
        "source": "RTE",
        "source_version": "5.2",
        "profile_id": "fr-rte-balancing-energy-v5.2-afrr-v1",
        "resource": "standard_afrr_data",
        "request_identity": hashlib.sha256(b"bounded-request").hexdigest(),
        "requested_period": period.to_dict(),
        "covered_period": period.to_dict(),
        "retrieved_at_utc": "2026-08-23T12:00:00Z",
        "series_manifest": {
            "afrr_requested_need_upward": {
                "requested": True,
                "required": True,
                "availability": "PRESENT",
            }
        },
        "series": [
            {
                "series_id": "afrr_requested_need_upward",
                "semantic_version": "afrr-requested-need-v1",
                "source": "RTE",
                "source_version": "5.2",
                "resource": "standard_afrr_data",
                "source_field": "afrr_requested_need_upward",
                "product": "AFRR",
                "process": "automatic_restoration",
                "direction": "UPWARD",
                "area": "France control area",
                "requested_period": period.to_dict(),
                "covered_period": period.to_dict(),
                "source_resolution": "PT15M",
                "canonical_resolution": "PT15M",
                "source_unit": "MW",
                "canonical_unit": "MW",
                "currency": None,
                "availability": "PRESENT",
                "transformations": [],
                "observations": observations,
            }
        ],
        "request_evidence": [
            {
                "request_id": document_ref,
                "resource": "standard_afrr_data",
                "start_utc": _utc(period.start_utc),
                "end_utc": _utc(period.end_utc),
                "attempt_count": 1,
                "http_status_class": "2xx",
                "response_media_type": "application/json",
                "response_bytes": len(response),
                "raw_sha256": hashlib.sha256(response).hexdigest(),
                "source_revision": None,
            }
        ],
        "raw_retention": {
            "policy": "DIGEST_ONLY",
            "responses": {
                document_ref: {
                    "status": "digest_only",
                    "sidecar_locator": None,
                    "sidecar_sha256": None,
                }
            },
        },
        "redistribution_policy": {
            "owner": "RTE",
            "attribution": "RTE Balancing Energy API v5.2",
            "repository_storage": "permitted_private_restricted",
            "repository_publication": "prohibited",
            "package_distribution": "prohibited",
            "release_distribution": "prohibited",
            "public_ci_artifact": "prohibited",
            "public_mirror_or_fork": "prohibited",
            "external_artifact_store": "prohibited",
            "visibility_change_action": "remove_or_reassess_before_change",
        },
        "predecessor_artifact_fingerprint": None,
    }


def _market_observations(count: int) -> list[dict[str, object]]:
    intervals = _intervals(count, step_seconds=900)
    return [
        {
            "interval": interval.to_dict(),
            "value_state": "VALUE",
            "value": float(index),
            "source_row": index,
            "source_field": "afrr_requested_need_upward",
            "document_ref": "rte-scaling-observations-v1",
            "conversion_ref": None,
        }
        for index, interval in enumerate(intervals)
    ]


def test_market_validation_and_fingerprinting_visit_observations_linearly() -> None:
    observation_count = 64
    first_input = _CountingSequence(_market_observations(observation_count))
    second_input = _CountingSequence(_market_observations(observation_count))

    first = build_restoration_market_artifact(
        _market_artifact_payload(first_input)
    )
    second = build_restoration_market_artifact(
        _market_artifact_payload(second_input)
    )

    assert first_input.item_visits <= observation_count
    assert second_input.item_visits <= observation_count
    assert len(first.series) == 1
    assert len(first.series[0].observations) == observation_count
    assert first.content_fingerprint == second.content_fingerprint
    assert first.artifact_fingerprint == second.artifact_fingerprint


def test_afrr_validation_replay_aggregation_and_fingerprints_scale_linearly() -> None:
    sample_count = 96
    intervals = _intervals(sample_count, step_seconds=60)
    period = _period(intervals)
    battery = _battery()
    capability = _capability()
    commitments = _commitments("AFRR", intervals)
    baseline = _baseline("AFRR", intervals)
    grid = _grid(intervals)
    sample_payloads = [
        {
            "interval": interval,
            "requested_balancing_power_kw": -5.0 if index % 2 == 0 else 5.0,
            "direction": "UPWARD" if index % 2 == 0 else "DOWNWARD",
            "source_observation_refs": [f"afrr-scaling-{index}"],
        }
        for index, interval in enumerate(intervals)
    ]
    source_samples = _CountingSequence(sample_payloads)
    trajectory = build_afrr_activation_trajectory(
        {
            "trajectory_id": "afrr-scaling-trajectory-v1",
            "semantics_version": "afrr-interval-average-v1",
            "product": "AFRR",
            "period": period,
            "resolution": "PT1M",
            "sample_semantics": "interval_average_requested_bess_power_kw",
            "sign_convention": "positive_charge_negative_discharge",
            "source_kind": "SYNTHETIC",
            "created_or_retrieved_at_utc": "2026-02-02T00:00:00Z",
            "mapping_fingerprint": None,
            "samples": source_samples,
        }
    )
    assert source_samples.item_visits <= sample_count
    assert len(trajectory.samples) == sample_count

    validation_commitments = _CountingSequence(commitments.intervals)
    validated_schedule = replace(commitments, intervals=validation_commitments)
    build_restoration_baseline_config(
        config_id="afrr-scaling-validation-v1",
        semantics_version="restoration-baseline-config-v1",
        product="AFRR",
        period=period,
        resolution="PT1M",
        commitments=validated_schedule,
        baseline=baseline,
        battery=battery,
        capability=capability,
        parameters={"mode": "fixed"},
        required_duration_seconds=60.0,
    )
    assert validation_commitments.item_visits <= 2 * len(commitments.intervals)

    validation_samples = _CountingSequence(trajectory.samples)
    counted_trajectory = replace(trajectory, samples=validation_samples)
    counted_request = build_afrr_replay_request(
        request_id="afrr-scaling-request-v1",
        semantics_version="afrr-physical-replay-v1",
        battery=battery,
        initial_state=build_initial_state(battery),
        capability=capability,
        commitments=commitments,
        baseline=baseline,
        activation_trajectory=counted_trajectory,
        integration_grid=grid,
        tolerance=1e-6,
    )
    assert validation_samples.item_visits <= sample_count
    validation_samples.reset()

    canonical_request = build_afrr_replay_request(
        request_id="afrr-scaling-request-v1",
        semantics_version="afrr-physical-replay-v1",
        battery=battery,
        initial_state=build_initial_state(battery),
        capability=capability,
        commitments=commitments,
        baseline=baseline,
        activation_trajectory=trajectory,
        integration_grid=grid,
        tolerance=1e-6,
    )
    reference = replay_afrr(canonical_request)

    replay_commitments = _CountingSequence(commitments.intervals)
    replay_baseline = _CountingSequence(baseline.intervals)
    replay_grid = _CountingSequence(grid.intervals)
    instrumented_request = replace(
        counted_request,
        commitments=replace(commitments, intervals=replay_commitments),
        baseline=replace(baseline, intervals=replay_baseline),
        integration_grid=replace(grid, intervals=replay_grid),
    )
    result = replay_afrr(instrumented_request)

    assert validation_samples.item_visits <= 3 * sample_count
    assert replay_commitments.item_visits <= 2 * len(commitments.intervals)
    assert replay_baseline.item_visits <= sample_count + 1
    assert replay_grid.item_visits <= 2 * sample_count
    assert len(result.samples) == sample_count
    assert result.result_fingerprint == reference.result_fingerprint

    aggregation_samples = _CountingSequence(result.samples)
    totals = aggregate_restoration_samples(aggregation_samples, tolerance=1e-6)
    assert aggregation_samples.item_visits <= sample_count
    assert totals.totals_fingerprint == result.totals.totals_fingerprint

    fingerprint_samples = _CountingSequence(result.samples)
    core_result = build_restoration_replay_result_core(
        request=canonical_request.core,
        samples=fingerprint_samples,
    )
    assert fingerprint_samples.item_visits <= sample_count
    assert len(core_result.samples) == sample_count
    assert core_result.result_fingerprint == result.core_result_fingerprint


def _mfrr_event_payload(index: int) -> dict[str, object]:
    return {
        "event_id": f"mfrr-scaling-{index:03d}",
        "product": "MFRR",
        "kind": "SCHEDULED" if index % 2 == 0 else "DIRECT",
        "direction": "UPWARD" if index % 2 == 0 else "DOWNWARD",
        "requested_start_utc": _utc(START + timedelta(minutes=5 * index)),
        "activation_delay_seconds": 60.0,
        "ramp_up_seconds": 60.0,
        "hold_seconds": 60.0,
        "ramp_down_seconds": 60.0,
        "requested_power_kw": 10.0,
        "source_kind": "SYNTHETIC",
        "mapping_fingerprint": None,
        "source_observation_refs": [f"mfrr-scaling-source-{index}"],
    }


def test_mfrr_event_validation_expansion_and_replay_scale_by_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_count = 24
    segments_per_event = len(SEGMENT_FIELDS)
    event_segment_count = event_count * segments_per_event
    grid_count = event_count * 5
    intervals = _intervals(grid_count, step_seconds=60)
    period = _period(intervals)
    battery = _battery()
    capability = _capability()
    commitments = _commitments("MFRR", intervals)
    baseline = _baseline("MFRR", intervals)
    grid = _grid(intervals)

    segment_payloads = [
        _CountingSegmentMapping(_mfrr_event_payload(index))
        for index in range(event_count)
    ]
    source_events = _CountingSequence(segment_payloads)
    sequence_payload = {
        "sequence_id": "mfrr-scaling-events-v1",
        "semantics_version": "mfrr-delay-ramp-hold-v1",
        "product": "MFRR",
        "period": period,
        "shape_semantics": "delay_linear_ramp_hold_linear_ramp",
        "sign_convention": "positive_charge_negative_discharge",
        "source_kind": "SYNTHETIC",
        "created_or_retrieved_at_utc": "2026-02-02T00:00:00Z",
        "events": source_events,
    }
    sequence = build_mfrr_activation_sequence(sequence_payload)
    canonical_sequence = build_mfrr_activation_sequence(
        {
            **sequence_payload,
            "events": [payload.to_dict() for payload in segment_payloads],
        }
    )

    assert source_events.item_visits <= event_count
    assert sum(item.segment_visits for item in segment_payloads) <= event_segment_count
    assert len(sequence.events) == event_count
    assert sequence.sequence_fingerprint == canonical_sequence.sequence_fingerprint

    validation_events = _CountingSequence(sequence.events)
    counted_sequence = replace(sequence, events=validation_events)
    counted_request = build_mfrr_replay_request(
        request_id="mfrr-scaling-request-v1",
        semantics_version="mfrr-physical-replay-v1",
        battery=battery,
        initial_state=build_initial_state(battery),
        capability=capability,
        commitments=commitments,
        baseline=baseline,
        activation_sequence=counted_sequence,
        integration_grid=grid,
        tolerance=1e-6,
    )
    assert validation_events.item_visits <= event_count
    validation_events.reset()

    canonical_request = build_mfrr_replay_request(
        request_id="mfrr-scaling-request-v1",
        semantics_version="mfrr-physical-replay-v1",
        battery=battery,
        initial_state=build_initial_state(battery),
        capability=capability,
        commitments=commitments,
        baseline=baseline,
        activation_sequence=canonical_sequence,
        integration_grid=grid,
        tolerance=1e-6,
    )
    reference = replay_mfrr(canonical_request)

    average_power_calls = 0
    original_average = MFRRActivationEvent.signed_average_power_kw

    def counted_average(
        event: MFRRActivationEvent,
        interval: CanonicalInterval,
    ) -> float:
        nonlocal average_power_calls
        average_power_calls += 1
        return original_average(event, interval)

    owned_sample_visits = 0
    original_performance = restoration_service_module._mfrr_event_performance

    def counted_performance(**kwargs: object):
        nonlocal owned_sample_visits
        indexed_samples = _CountingSequence(kwargs["indexed_samples"])
        kwargs["indexed_samples"] = indexed_samples
        performance = original_performance(**kwargs)
        owned_sample_visits += indexed_samples.item_visits
        return performance

    monkeypatch.setattr(
        MFRRActivationEvent,
        "signed_average_power_kw",
        counted_average,
    )
    monkeypatch.setattr(
        restoration_service_module,
        "_mfrr_event_performance",
        counted_performance,
    )

    replay_commitments = _CountingSequence(commitments.intervals)
    replay_baseline = _CountingSequence(baseline.intervals)
    replay_grid = _CountingSequence(grid.intervals)
    instrumented_request = replace(
        counted_request,
        commitments=replace(commitments, intervals=replay_commitments),
        baseline=replace(baseline, intervals=replay_baseline),
        integration_grid=replace(grid, intervals=replay_grid),
    )
    result = replay_mfrr(instrumented_request)

    assert validation_events.item_visits <= event_count
    assert average_power_calls <= event_segment_count
    assert owned_sample_visits <= 2 * event_segment_count
    assert replay_commitments.item_visits <= 2 * len(commitments.intervals)
    assert replay_baseline.item_visits <= grid_count + 1
    assert replay_grid.item_visits <= 3 * grid_count
    assert len(result.samples) == grid_count
    assert len(result.event_performance) == event_count
    assert sum(item.sample_count for item in result.event_performance) == (
        event_segment_count
    )
    assert result.result_fingerprint == reference.result_fingerprint
