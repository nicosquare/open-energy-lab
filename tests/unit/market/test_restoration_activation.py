"""Shared restoration activation identities and derived-scenario mapping tests."""

from __future__ import annotations

from copy import deepcopy
import re

import pytest

from open_energy_lab.market.restoration_activation import (
    DerivedSimulationMapping,
    MFRRActivationKind,
    RestorationActivationValidationError,
    RestorationDirection,
    RestorationProduct,
    RestorationSourceKind,
    build_derived_simulation_mapping,
)


def _mapping_input() -> dict[str, object]:
    return {
        "mapping_id": "rte-afrr-up-0.001-v1",
        "source_artifact_fingerprint": "a" * 64,
        "source_series_fingerprints": ["b" * 64],
        "product": "AFRR",
        "direction": "UPWARD",
        "asset_allocation_fraction": 0.001,
        "unit_scale_kw_per_mw": 1000.0,
        "capacity_commitment_ref": "c" * 64,
        "driver_semantics": "afrr_requested_need",
        "comparison_series": ["d" * 64, "e" * 64],
        "assumptions": [
            "one fixed fraction applies throughout the scenario",
            "area need is a simulation driver, not an asset command",
        ],
        "created_at_utc": "2026-08-23T11:00:00Z",
        "output_label": "derived_simulation",
    }


def _build(payload: dict[str, object] | None = None):
    return build_derived_simulation_mapping(
        _mapping_input() if payload is None else payload,
        driver_values_mw=(425.0, 315.0, 0.0),
        committed_capacity_kw=500.0,
    )


def test_shared_product_direction_kind_and_source_values_are_closed() -> None:
    assert tuple(item.value for item in RestorationProduct) == ("AFRR", "MFRR")
    assert tuple(item.value for item in RestorationDirection) == (
        "UPWARD",
        "DOWNWARD",
    )
    assert tuple(item.value for item in MFRRActivationKind) == (
        "SCHEDULED",
        "DIRECT",
    )
    assert tuple(item.value for item in RestorationSourceKind) == (
        "ASSET_SUPPLIED",
        "SYNTHETIC",
        "DERIVED_SIMULATION",
    )

    fcr = _mapping_input()
    fcr["product"] = "FCR"
    with pytest.raises(RestorationActivationValidationError, match="product|AFRR|MFRR"):
        _build(fcr)


def test_mapping_preserves_exact_lineage_creation_time_and_fixed_fraction() -> None:
    mapping = _build()

    assert mapping.product is RestorationProduct.AFRR
    assert mapping.direction is RestorationDirection.UPWARD
    assert mapping.source_kind is RestorationSourceKind.DERIVED_SIMULATION
    assert mapping.source_artifact_fingerprint == "a" * 64
    assert mapping.source_series_fingerprints == ("b" * 64,)
    assert mapping.comparison_series == ("d" * 64, "e" * 64)
    assert mapping.capacity_commitment_ref == "c" * 64
    assert mapping.created_at_utc == "2026-08-23T11:00:00Z"
    assert mapping.output_label == "derived_simulation"
    assert mapping.asset_allocation_fraction == 0.001
    assert mapping.unit_scale_kw_per_mw == 1000.0
    assert re.fullmatch(r"[0-9a-f]{64}", mapping.mapping_fingerprint)


def test_mapping_uses_direct_mw_to_kw_formula_and_charge_positive_direction() -> None:
    upward = _build()
    downward_input = _mapping_input()
    downward_input["mapping_id"] = "rte-afrr-down-0.001-v1"
    downward_input["direction"] = "DOWNWARD"
    downward = _build(downward_input)

    assert upward.map_area_value_kw(425.0) == pytest.approx(-425.0)
    assert downward.map_area_value_kw(425.0) == pytest.approx(425.0)
    assert upward.map_area_value_kw(0.0) == 0.0


@pytest.mark.parametrize("fraction", [-0.001, 1.001, float("nan"), float("inf")])
def test_mapping_rejects_invalid_or_non_fixed_allocation_fraction(fraction: float) -> None:
    payload = _mapping_input()
    payload["asset_allocation_fraction"] = fraction

    with pytest.raises(
        RestorationActivationValidationError,
        match=r"fraction|finite|\[0, 1\]",
    ):
        _build(payload)

    payload["asset_allocation_fraction"] = [0.001, 0.002]
    with pytest.raises(RestorationActivationValidationError, match="fraction|finite|fixed"):
        _build(payload)


def test_creation_rejects_capacity_excess_instead_of_clipping_or_normalizing() -> None:
    with pytest.raises(
        RestorationActivationValidationError,
        match="425|capacity|500|allocation|AFRR|UPWARD",
    ):
        build_derived_simulation_mapping(
            _mapping_input(),
            driver_values_mw=(600.0,),
            committed_capacity_kw=500.0,
        )

    mapping = _build()
    assert mapping.map_area_value_kw(600.0) == -600.0
    assert not hasattr(mapping, "clip")
    assert not hasattr(mapping, "normalization")


def test_mapping_rejects_missing_lineage_hidden_driver_and_invalid_scale() -> None:
    no_driver = _mapping_input()
    no_driver["source_series_fingerprints"] = []
    with pytest.raises(RestorationActivationValidationError, match="source_series|non-empty"):
        _build(no_driver)

    overlap = _mapping_input()
    overlap["comparison_series"] = ["b" * 64]
    with pytest.raises(RestorationActivationValidationError, match="comparison|driver"):
        _build(overlap)

    wrong_scale = _mapping_input()
    wrong_scale["unit_scale_kw_per_mw"] = 1.0
    with pytest.raises(RestorationActivationValidationError, match="1000|scale"):
        _build(wrong_scale)

    negative_driver = _mapping_input()
    with pytest.raises(RestorationActivationValidationError, match="driver|non-negative"):
        build_derived_simulation_mapping(
            negative_driver,
            driver_values_mw=(-1.0,),
            committed_capacity_kw=500.0,
        )


def test_mapping_fingerprint_is_deterministic_and_covers_semantic_inputs() -> None:
    baseline = _build()
    assert _build().mapping_fingerprint == baseline.mapping_fingerprint
    assert DerivedSimulationMapping.from_dict(baseline.to_dict()) == baseline

    changed = _mapping_input()
    changed["created_at_utc"] = "2026-08-23T11:00:01Z"
    assert _build(changed).mapping_fingerprint != baseline.mapping_fingerprint

    changed = deepcopy(_mapping_input())
    changed["assumptions"].append("additional disclosed assumption")
    assert _build(changed).mapping_fingerprint != baseline.mapping_fingerprint
