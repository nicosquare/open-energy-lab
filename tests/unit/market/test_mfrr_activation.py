"""Typed mFRR scheduled/direct activation event and sequence tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import re

import pytest

from open_energy_lab.market.restoration_activation import (
    MFRRActivationEvent,
    MFRRActivationKind,
    MFRRActivationSequence,
    RestorationActivationIntegrityError,
    RestorationActivationValidationError,
    RestorationDirection,
    RestorationProduct,
    RestorationSourceKind,
    build_derived_simulation_mapping,
    build_mfrr_activation_sequence,
    build_mfrr_sequence_from_rte_sa_requested_volume,
)
from open_energy_lab.market.time import CanonicalInterval


START = datetime(2026, 1, 3, 0, 0, tzinfo=UTC)
END = START + timedelta(minutes=30)
PERIOD = CanonicalInterval.from_utc(START, END)


def _event(
    *,
    event_id: str,
    kind: str,
    direction: str,
    start: datetime,
    delay: float = 0.0,
    ramp_up: float = 0.0,
    hold: float = 300.0,
    ramp_down: float = 0.0,
    power: float = 12.0,
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "product": "MFRR",
        "kind": kind,
        "direction": direction,
        "requested_start_utc": start.isoformat().replace("+00:00", "Z"),
        "activation_delay_seconds": delay,
        "ramp_up_seconds": ramp_up,
        "hold_seconds": hold,
        "ramp_down_seconds": ramp_down,
        "requested_power_kw": power,
        "source_kind": "SYNTHETIC",
        "mapping_fingerprint": None,
        "source_observation_refs": [f"synthetic:{event_id}"],
    }


def _payload() -> dict[str, object]:
    return {
        "sequence_id": "synthetic-mfrr-events-v1",
        "semantics_version": "mfrr-delay-ramp-hold-v1",
        "product": "MFRR",
        "period": PERIOD,
        "shape_semantics": "delay_linear_ramp_hold_linear_ramp",
        "sign_convention": "positive_charge_negative_discharge",
        "source_kind": "SYNTHETIC",
        "created_or_retrieved_at_utc": "2026-01-04T00:00:00Z",
        "events": [
            _event(
                event_id="scheduled-up",
                kind="SCHEDULED",
                direction="UPWARD",
                start=START,
            ),
            _event(
                event_id="direct-down",
                kind="DIRECT",
                direction="DOWNWARD",
                start=START + timedelta(minutes=10),
                delay=60.0,
                ramp_up=60.0,
                hold=120.0,
                ramp_down=60.0,
                power=10.0,
            ),
        ],
    }


def _mapping(*, direction: str = "UPWARD"):
    return build_derived_simulation_mapping(
        {
            "mapping_id": f"rte-mfrr-sa-{direction.lower()}-v1",
            "source_artifact_fingerprint": "a" * 64,
            "source_series_fingerprints": ["b" * 64],
            "product": "MFRR",
            "direction": direction,
            "asset_allocation_fraction": 0.001,
            "unit_scale_kw_per_mw": 1000.0,
            "capacity_commitment_ref": "c" * 64,
            "driver_semantics": "mfrr_sa_requested_volume",
            "comparison_series": ["d" * 64],
            "assumptions": [
                "one fixed fraction applies throughout",
                "each retained SA interval maps to a rectangular simulation event",
                "area requested volume is not an observed asset command",
            ],
            "created_at_utc": "2026-01-04T01:00:00Z",
            "output_label": "derived_simulation",
        },
        driver_values_mw=(100.0, 50.0),
        committed_capacity_kw=200.0,
    )


def test_scheduled_and_direct_events_keep_exact_identity_and_direction() -> None:
    sequence = build_mfrr_activation_sequence(_payload())
    scheduled, direct = sequence.events

    assert sequence.product is RestorationProduct.MFRR
    assert sequence.source_kind is RestorationSourceKind.SYNTHETIC
    assert scheduled.kind is MFRRActivationKind.SCHEDULED
    assert scheduled.direction is RestorationDirection.UPWARD
    assert direct.kind is MFRRActivationKind.DIRECT
    assert direct.direction is RestorationDirection.DOWNWARD
    assert scheduled.event_fingerprint != direct.event_fingerprint
    assert re.fullmatch(r"[0-9a-f]{64}", sequence.sequence_fingerprint)


def test_event_energy_is_the_exact_analytic_piecewise_integral() -> None:
    sequence = build_mfrr_activation_sequence(_payload())
    scheduled, direct = sequence.events

    assert scheduled.requested_energy_kwh == pytest.approx(1.0)
    assert scheduled.signed_requested_energy_kwh == pytest.approx(-1.0)
    assert direct.requested_energy_kwh == pytest.approx(0.5)
    assert direct.signed_requested_energy_kwh == pytest.approx(0.5)
    assert sequence.requested_upward_energy_kwh == pytest.approx(1.0)
    assert sequence.requested_downward_energy_kwh == pytest.approx(0.5)
    assert sequence.net_requested_energy_kwh == pytest.approx(-0.5)


def test_delay_ramp_hold_ramp_interval_averages_conserve_event_energy() -> None:
    direct = build_mfrr_activation_sequence(_payload()).events[1]
    start = START + timedelta(minutes=10)
    intervals = tuple(
        CanonicalInterval.from_utc(
            start + timedelta(minutes=index),
            start + timedelta(minutes=index + 1),
        )
        for index in range(5)
    )

    averages = [direct.signed_average_power_kw(interval) for interval in intervals]
    assert averages == pytest.approx([0.0, 5.0, 10.0, 10.0, 5.0])
    assert sum(averages) / 60.0 == pytest.approx(direct.requested_energy_kwh)
    assert direct.activation_start_utc == "2026-01-03T00:11:00Z"
    assert direct.requested_completion_utc == "2026-01-03T00:15:00Z"


def test_sequence_orders_events_by_start_then_id_and_covers_zero_outside_events() -> None:
    payload = _payload()
    payload["events"] = list(reversed(payload["events"]))
    sequence = build_mfrr_activation_sequence(payload)

    assert [event.event_id for event in sequence.events] == [
        "scheduled-up",
        "direct-down",
    ]
    assert sequence.period == PERIOD
    assert sequence.events[0].complete_interval.start_utc == START
    assert sequence.events[-1].complete_interval.end_utc < END

    empty = _payload()
    empty["sequence_id"] = "empty-mfrr-v1"
    empty["events"] = []
    empty_sequence = build_mfrr_activation_sequence(empty)
    assert empty_sequence.events == ()
    assert empty_sequence.requested_upward_energy_kwh == 0.0
    assert empty_sequence.requested_downward_energy_kwh == 0.0


@pytest.mark.parametrize(
    "second_start,second_duration",
    (
        (START, 60.0),
        (START + timedelta(minutes=1), 60.0),
        (START + timedelta(minutes=4), 120.0),
    ),
)
def test_every_partial_nested_or_same_start_overlap_is_rejected(
    second_start: datetime, second_duration: float
) -> None:
    payload = _payload()
    payload["events"] = [
        _event(
            event_id="first",
            kind="SCHEDULED",
            direction="UPWARD",
            start=START,
            hold=300.0,
        ),
        _event(
            event_id="second",
            kind="DIRECT",
            direction="DOWNWARD",
            start=second_start,
            hold=second_duration,
        ),
    ]

    with pytest.raises(
        RestorationActivationValidationError, match="overlap|first|second"
    ):
        build_mfrr_activation_sequence(payload)


def test_touching_half_open_events_are_not_an_overlap() -> None:
    payload = _payload()
    payload["events"] = [
        _event(
            event_id="first",
            kind="SCHEDULED",
            direction="UPWARD",
            start=START,
            hold=300.0,
        ),
        _event(
            event_id="second",
            kind="DIRECT",
            direction="DOWNWARD",
            start=START + timedelta(minutes=5),
            hold=300.0,
        ),
    ]

    assert len(build_mfrr_activation_sequence(payload).events) == 2


@pytest.mark.parametrize(
    "field,value,message",
    (
        ("activation_delay_seconds", -1.0, "delay|non-negative"),
        ("ramp_up_seconds", -1.0, "ramp|non-negative"),
        ("hold_seconds", -1.0, "hold|non-negative"),
        ("ramp_down_seconds", -1.0, "ramp|non-negative"),
        ("requested_power_kw", -1.0, "power|non-negative"),
    ),
)
def test_event_rejects_negative_duration_or_power(
    field: str, value: float, message: str
) -> None:
    payload = _payload()
    payload["events"][0][field] = value
    with pytest.raises(RestorationActivationValidationError, match=message):
        build_mfrr_activation_sequence(payload)


def test_event_rejects_zero_total_duration_and_supplied_energy() -> None:
    zero_duration = _payload()
    zero_duration["events"][0].update(
        {
            "activation_delay_seconds": 0.0,
            "ramp_up_seconds": 0.0,
            "hold_seconds": 0.0,
            "ramp_down_seconds": 0.0,
        }
    )
    with pytest.raises(
        RestorationActivationValidationError, match="duration|positive"
    ):
        build_mfrr_activation_sequence(zero_duration)

    supplied_energy = _payload()
    supplied_energy["events"][0]["requested_energy_kwh"] = 999.0
    with pytest.raises(
        RestorationActivationValidationError, match="energy|derived|input"
    ):
        build_mfrr_activation_sequence(supplied_energy)


def test_events_must_lie_completely_inside_the_declared_horizon() -> None:
    outside = _payload()
    outside["events"][1]["requested_start_utc"] = (
        END - timedelta(minutes=1)
    ).isoformat().replace("+00:00", "Z")
    with pytest.raises(
        RestorationActivationValidationError, match="event|horizon|period|outside"
    ):
        build_mfrr_activation_sequence(outside)


def test_sequence_and_event_fingerprints_verify_every_semantic_input() -> None:
    baseline = build_mfrr_activation_sequence(_payload())
    assert MFRRActivationSequence.from_dict(baseline.to_dict()) == baseline
    assert MFRRActivationEvent.from_dict(baseline.events[0].to_dict()) == (
        baseline.events[0]
    )
    assert build_mfrr_activation_sequence(_payload()) == baseline

    changed_kind = _payload()
    changed_kind["events"][1]["kind"] = "SCHEDULED"
    assert (
        build_mfrr_activation_sequence(changed_kind).sequence_fingerprint
        != baseline.sequence_fingerprint
    )

    changed_time = _payload()
    changed_time["created_or_retrieved_at_utc"] = "2026-01-04T00:00:01Z"
    assert (
        build_mfrr_activation_sequence(changed_time).sequence_fingerprint
        != baseline.sequence_fingerprint
    )

    corrupted = deepcopy(baseline.to_dict())
    corrupted["events"][0]["requested_power_kw"] = 11.0
    with pytest.raises(RestorationActivationIntegrityError, match="fingerprint"):
        MFRRActivationSequence.from_dict(corrupted)


def test_rte_sa_mapping_creates_only_scheduled_events_and_preserves_sparse_rows() -> None:
    intervals = tuple(
        CanonicalInterval.from_utc(
            START + timedelta(minutes=15 * index),
            START + timedelta(minutes=15 * (index + 1)),
        )
        for index in range(4)
    )
    sequence = build_mfrr_sequence_from_rte_sa_requested_volume(
        sequence_id="rte-derived-mfrr-sa-v1",
        semantics_version="mfrr-delay-ramp-hold-v1",
        period=CanonicalInterval.from_utc(START, START + timedelta(hours=1)),
        created_or_retrieved_at_utc="2026-01-04T02:00:00Z",
        mapping=_mapping(),
        intervals=intervals,
        upward_requested_volume_mw=(100.0, 0.0, None, 50.0),
        downward_requested_volume_mw=(0.0, 0.0, None, 0.0),
        committed_capacity_kw=(200.0, 200.0, 200.0, 200.0),
        source_observation_refs=tuple(
            (f"rte-mfrr-sa-row-{index}",) for index in range(4)
        ),
    )

    assert [event.kind for event in sequence.events] == [
        MFRRActivationKind.SCHEDULED,
        MFRRActivationKind.SCHEDULED,
    ]
    assert [event.requested_power_kw for event in sequence.events] == [100.0, 50.0]
    assert [event.requested_energy_kwh for event in sequence.events] == [25.0, 12.5]
    assert all(
        event.source_kind is RestorationSourceKind.DERIVED_SIMULATION
        for event in sequence.events
    )
    assert not any(event.kind is MFRRActivationKind.DIRECT for event in sequence.events)


def test_rte_sa_mapping_rejects_opposing_volume_and_capacity_excess() -> None:
    interval = CanonicalInterval.from_utc(START, START + timedelta(minutes=15))
    common = {
        "sequence_id": "invalid-rte-mfrr-sa-v1",
        "semantics_version": "mfrr-delay-ramp-hold-v1",
        "period": interval,
        "created_or_retrieved_at_utc": "2026-01-04T02:00:00Z",
        "mapping": _mapping(),
        "intervals": (interval,),
        "committed_capacity_kw": (200.0,),
        "source_observation_refs": (("rte-mfrr-sa-row-0",),),
    }
    with pytest.raises(
        RestorationActivationValidationError,
        match="opposing|upward|downward|interval 0",
    ):
        build_mfrr_sequence_from_rte_sa_requested_volume(
            **common,
            upward_requested_volume_mw=(100.0,),
            downward_requested_volume_mw=(1.0,),
        )

    with pytest.raises(
        RestorationActivationValidationError,
        match="100|50|capacity|fraction|interval 0|UPWARD",
    ):
        build_mfrr_sequence_from_rte_sa_requested_volume(
            **{**common, "committed_capacity_kw": (50.0,)},
            upward_requested_volume_mw=(100.0,),
            downward_requested_volume_mw=(0.0,),
        )
