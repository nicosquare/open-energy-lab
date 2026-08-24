"""Exact signed interval-average aFRR activation trajectory tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import re

import pytest

from open_energy_lab.market.restoration_activation import (
    AFRRActivationTrajectory,
    RestorationActivationIntegrityError,
    RestorationActivationValidationError,
    RestorationDirection,
    RestorationProduct,
    RestorationSourceKind,
    build_afrr_activation_trajectory,
    build_afrr_trajectory_from_rte_requested_need,
    build_derived_simulation_mapping,
)
from open_energy_lab.market.time import CanonicalInterval


START = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
END = START + timedelta(hours=1)


def _interval(index: int) -> CanonicalInterval:
    start = START + timedelta(minutes=15 * index)
    return CanonicalInterval.from_utc(start, start + timedelta(minutes=15))


def _payload() -> dict[str, object]:
    powers = (-10.0, 8.0, 0.0, -6.0)
    directions = ("UPWARD", "DOWNWARD", None, "UPWARD")
    return {
        "trajectory_id": "synthetic-afrr-unit-v1",
        "semantics_version": "afrr-interval-average-v1",
        "product": "AFRR",
        "period": CanonicalInterval.from_utc(START, END),
        "resolution": "PT15M",
        "sample_semantics": "interval_average_requested_bess_power_kw",
        "sign_convention": "positive_charge_negative_discharge",
        "source_kind": "SYNTHETIC",
        "created_or_retrieved_at_utc": "2026-01-02T00:00:00Z",
        "mapping_fingerprint": None,
        "samples": [
            {
                "interval": _interval(index),
                "requested_balancing_power_kw": power,
                "direction": direction,
                "source_observation_refs": [f"synthetic-afrr-row-{index}"],
            }
            for index, (power, direction) in enumerate(
                zip(powers, directions, strict=True)
            )
        ],
    }


def _mapping(*, direction: str = "UPWARD"):
    return build_derived_simulation_mapping(
        {
            "mapping_id": f"rte-afrr-{direction.lower()}-0.001-v1",
            "source_artifact_fingerprint": "a" * 64,
            "source_series_fingerprints": ["b" * 64],
            "product": "AFRR",
            "direction": direction,
            "asset_allocation_fraction": 0.001,
            "unit_scale_kw_per_mw": 1000.0,
            "capacity_commitment_ref": "c" * 64,
            "driver_semantics": "afrr_requested_need",
            "comparison_series": ["d" * 64],
            "assumptions": [
                "one fixed fraction applies to every interval",
                "the area need is not an observed battery command",
            ],
            "created_at_utc": "2026-01-02T01:00:00Z",
            "output_label": "derived_simulation",
        },
        driver_values_mw=(425.0, 315.0, 290.0, 345.0),
        committed_capacity_kw=500.0,
    )


def test_trajectory_preserves_signed_interval_average_semantics_and_lineage() -> None:
    trajectory = build_afrr_activation_trajectory(_payload())

    assert trajectory.product is RestorationProduct.AFRR
    assert trajectory.source_kind is RestorationSourceKind.SYNTHETIC
    assert trajectory.period == CanonicalInterval.from_utc(START, END)
    assert trajectory.resolution == "PT15M"
    assert trajectory.sample_semantics == "interval_average_requested_bess_power_kw"
    assert trajectory.sign_convention == "positive_charge_negative_discharge"
    assert trajectory.created_or_retrieved_at_utc == "2026-01-02T00:00:00Z"
    assert [item.requested_balancing_power_kw for item in trajectory.samples] == [
        -10.0,
        8.0,
        0.0,
        -6.0,
    ]
    assert [item.direction for item in trajectory.samples] == [
        RestorationDirection.UPWARD,
        RestorationDirection.DOWNWARD,
        None,
        RestorationDirection.UPWARD,
    ]
    assert trajectory.samples[0].source_observation_refs == (
        "synthetic-afrr-row-0",
    )


def test_energy_is_integrated_directly_from_interval_average_power() -> None:
    trajectory = build_afrr_activation_trajectory(_payload())

    assert [item.signed_requested_energy_kwh for item in trajectory.samples] == [
        -2.5,
        2.0,
        0.0,
        -1.5,
    ]
    assert trajectory.requested_upward_energy_kwh == pytest.approx(4.0)
    assert trajectory.requested_downward_energy_kwh == pytest.approx(2.0)
    assert trajectory.net_requested_energy_kwh == pytest.approx(-2.0)
    assert trajectory.absolute_requested_energy_kwh == pytest.approx(6.0)


def test_exact_native_coverage_rejects_gaps_overlaps_and_wrong_resolution() -> None:
    gap = _payload()
    gap["samples"] = [gap["samples"][0], *gap["samples"][2:]]
    with pytest.raises(RestorationActivationValidationError, match="gap|coverage"):
        build_afrr_activation_trajectory(gap)

    overlap = _payload()
    overlap["samples"][1]["interval"] = CanonicalInterval.from_utc(
        START + timedelta(minutes=10), START + timedelta(minutes=25)
    )
    with pytest.raises(RestorationActivationValidationError, match="overlap|coverage"):
        build_afrr_activation_trajectory(overlap)

    wrong_resolution = _payload()
    wrong_resolution["resolution"] = "PT5M"
    with pytest.raises(
        RestorationActivationValidationError, match="resolution|duration"
    ):
        build_afrr_activation_trajectory(wrong_resolution)


def test_direction_product_and_interval_average_meaning_are_exact() -> None:
    wrong_direction = _payload()
    wrong_direction["samples"][0]["direction"] = "DOWNWARD"
    with pytest.raises(RestorationActivationValidationError, match="direction|negative"):
        build_afrr_activation_trajectory(wrong_direction)

    zero_direction = _payload()
    zero_direction["samples"][2]["direction"] = "UPWARD"
    with pytest.raises(RestorationActivationValidationError, match="direction|zero"):
        build_afrr_activation_trajectory(zero_direction)

    wrong_product = _payload()
    wrong_product["product"] = "MFRR"
    with pytest.raises(RestorationActivationValidationError, match="AFRR|product"):
        build_afrr_activation_trajectory(wrong_product)

    point_values = _payload()
    point_values["sample_semantics"] = "instantaneous_setpoint_kw"
    with pytest.raises(
        RestorationActivationValidationError, match="interval_average|semantics"
    ):
        build_afrr_activation_trajectory(point_values)


def test_source_kind_controls_mapping_identity_without_hidden_derivation() -> None:
    synthetic_with_mapping = _payload()
    synthetic_with_mapping["mapping_fingerprint"] = "f" * 64
    with pytest.raises(
        RestorationActivationValidationError, match="mapping|SYNTHETIC|derived"
    ):
        build_afrr_activation_trajectory(synthetic_with_mapping)

    derived_without_mapping = _payload()
    derived_without_mapping["source_kind"] = "DERIVED_SIMULATION"
    with pytest.raises(
        RestorationActivationValidationError, match="mapping|DERIVED"
    ):
        build_afrr_activation_trajectory(derived_without_mapping)


def test_provenance_time_and_every_sample_are_covered_by_fingerprint() -> None:
    baseline = build_afrr_activation_trajectory(_payload())
    assert re.fullmatch(r"[0-9a-f]{64}", baseline.trajectory_fingerprint)
    assert AFRRActivationTrajectory.from_dict(baseline.to_dict()) == baseline
    assert build_afrr_activation_trajectory(_payload()) == baseline

    changed_time = _payload()
    changed_time["created_or_retrieved_at_utc"] = "2026-01-02T00:00:01Z"
    assert (
        build_afrr_activation_trajectory(changed_time).trajectory_fingerprint
        != baseline.trajectory_fingerprint
    )

    changed_power = _payload()
    changed_power["samples"][0]["requested_balancing_power_kw"] = -9.0
    assert (
        build_afrr_activation_trajectory(changed_power).trajectory_fingerprint
        != baseline.trajectory_fingerprint
    )

    corrupted = deepcopy(baseline.to_dict())
    corrupted["samples"][0]["requested_balancing_power_kw"] = -9.0
    with pytest.raises(RestorationActivationIntegrityError, match="fingerprint"):
        AFRRActivationTrajectory.from_dict(corrupted)


def test_trajectory_has_no_interpolation_or_upsampling_surface() -> None:
    trajectory = build_afrr_activation_trajectory(_payload())

    for forbidden in (
        "interpolate",
        "upsample",
        "resample",
        "to_points",
        "from_setpoints",
    ):
        assert not hasattr(trajectory, forbidden)


def test_rte_requested_need_uses_one_fixed_fraction_and_upward_sign() -> None:
    mapping = _mapping()
    trajectory = build_afrr_trajectory_from_rte_requested_need(
        trajectory_id="rte-derived-afrr-up-v1",
        semantics_version="afrr-interval-average-v1",
        period=CanonicalInterval.from_utc(START, END),
        resolution="PT15M",
        created_or_retrieved_at_utc="2026-08-23T12:00:00Z",
        mapping=mapping,
        intervals=tuple(_interval(index) for index in range(4)),
        upward_requested_need_mw=(425.0, 315.0, 290.0, 345.0),
        downward_requested_need_mw=(0.0, 0.0, 0.0, 0.0),
        committed_capacity_kw=(500.0, 500.0, 500.0, 500.0),
        source_observation_refs=tuple(
            (f"rte-afrr-up-row-{index}",) for index in range(4)
        ),
    )

    assert trajectory.source_kind is RestorationSourceKind.DERIVED_SIMULATION
    assert trajectory.mapping_fingerprint == mapping.mapping_fingerprint
    assert [sample.requested_balancing_power_kw for sample in trajectory.samples] == [
        -425.0,
        -315.0,
        -290.0,
        -345.0,
    ]
    assert trajectory.requested_upward_energy_kwh == pytest.approx(343.75)
    assert all(
        sample.direction is RestorationDirection.UPWARD
        for sample in trajectory.samples
    )


def test_rte_requested_need_rejects_opposing_need_in_one_interval() -> None:
    with pytest.raises(
        RestorationActivationValidationError,
        match="opposing|upward|downward|ambiguous|interval 0",
    ):
        build_afrr_trajectory_from_rte_requested_need(
            trajectory_id="ambiguous-rte-afrr-v1",
            semantics_version="afrr-interval-average-v1",
            period=CanonicalInterval.from_utc(START, END),
            resolution="PT15M",
            created_or_retrieved_at_utc="2026-08-23T12:00:00Z",
            mapping=_mapping(),
            intervals=tuple(_interval(index) for index in range(4)),
            upward_requested_need_mw=(425.0, 0.0, 0.0, 0.0),
            downward_requested_need_mw=(1.0, 0.0, 0.0, 0.0),
            committed_capacity_kw=(500.0, 500.0, 500.0, 500.0),
            source_observation_refs=tuple(
                (f"rte-afrr-row-{index}",) for index in range(4)
            ),
        )


def test_rte_mapping_rejects_capacity_excess_without_clipping() -> None:
    with pytest.raises(
        RestorationActivationValidationError,
        match="interval 0|425|400|capacity|fraction|UPWARD",
    ):
        build_afrr_trajectory_from_rte_requested_need(
            trajectory_id="capacity-excess-rte-afrr-v1",
            semantics_version="afrr-interval-average-v1",
            period=CanonicalInterval.from_utc(START, END),
            resolution="PT15M",
            created_or_retrieved_at_utc="2026-08-23T12:00:00Z",
            mapping=_mapping(),
            intervals=tuple(_interval(index) for index in range(4)),
            upward_requested_need_mw=(425.0, 315.0, 290.0, 345.0),
            downward_requested_need_mw=(0.0, 0.0, 0.0, 0.0),
            committed_capacity_kw=(400.0, 500.0, 500.0, 500.0),
            source_observation_refs=tuple(
                (f"rte-afrr-row-{index}",) for index in range(4)
            ),
        )
