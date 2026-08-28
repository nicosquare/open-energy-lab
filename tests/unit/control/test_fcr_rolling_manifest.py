"""Pure manifest, policy, descriptor, and bidder-boundary contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest

from open_energy_lab.control import (
    AcceptedBidPolicy,
    DeliveryDateClassification,
    RollingFCRDataDescriptor,
    RollingFCRDayInput,
    RollingFCRValidationError,
    build_rolling_fcr_experiment_profile,
)
from tests.fcr_rolling_case_utils import (
    AUTHORED_DELIVERY_DATES,
    authored_date_classifications,
    build_authored_battery_binding,
    build_authored_data_descriptor,
    build_authored_day_input,
    build_authored_manifest,
)


def test_manifest_is_frozen_deeply_immutable_and_semantically_stable() -> None:
    first = build_authored_manifest()
    second = build_authored_manifest()

    assert first == second
    assert first.manifest_fingerprint == second.manifest_fingerprint
    assert len(first.dates) == 4
    assert first.profile.profile_id == "script-12-restriction-reset-midnight-v1"
    assert first.decision_cutoff_rule == "pre-delivery-midnight-local-v1"
    assert first.information_cutoff_rule == "pre-delivery-midnight-local-v1"
    assert first.acceptance_policy.kind == "assumed_accepted"
    assert first.battery_binding.maximum_charge_power_kw == 10.0
    assert first.battery_binding.maximum_stored_energy_kwh == 20.0
    assert first.to_dict()["reference_revision"] == (
        "7e44738bb30e5c8204efe40103b9be4c2203685c"
    )
    with pytest.raises(FrozenInstanceError):
        first.study_id = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        first.reference_lineage["changed"] = True  # type: ignore[index]


@pytest.mark.parametrize(
    ("kind", "unit", "resolution", "mapping"),
    (
        ("day_ahead_price", "EUR/kWh", "PT1H", "hourly-delivery-interval-v1"),
        (
            "fcr_capacity_price",
            "EUR/kW/4h-block",
            "PT4H",
            "six-four-hour-delivery-blocks-v1",
        ),
        (
            "regulation_activation",
            "dimensionless",
            "PT10S",
            "ten-second-half-open-activation-v1",
        ),
    ),
)
def test_data_descriptors_have_exact_units_temporal_mappings_and_fingerprints(
    kind: str,
    unit: str,
    resolution: str,
    mapping: str,
) -> None:
    descriptor = build_authored_data_descriptor(kind)

    assert descriptor.kind == kind
    assert descriptor.unit == unit
    assert descriptor.temporal_resolution == resolution
    assert descriptor.mapping_rule_id == mapping
    assert len(descriptor.descriptor_fingerprint) == 64
    assert "path" not in descriptor.to_dict()["provenance"]


def test_descriptor_rejects_new_market_document_kinds_and_local_paths() -> None:
    descriptor = build_authored_data_descriptor("day_ahead_price")

    with pytest.raises(RollingFCRValidationError, match="descriptor kind"):
        replace(descriptor, kind="system_wide_contracted_reserve_volume")
    with pytest.raises(RollingFCRValidationError, match="forbidden evidence"):
        replace(descriptor, provenance={"local_path": "/tmp/price.csv"})


def test_acceptance_policy_is_mandatory_explicit_and_rejects_system_volume() -> None:
    assumed = AcceptedBidPolicy(
        policy_id="assumed-v1",
        kind="assumed_accepted",
        assumption_statement="optimizer-selected bids are assumed accepted",
    )
    backed = AcceptedBidPolicy(
        policy_id="award-v1",
        kind="evidence_backed_accepted",
        evidence_descriptor={
            "kind": "individual_bid_award",
            "content_fingerprint": "1" * 64,
        },
    )

    assert assumed.evidence_descriptor is None
    assert backed.assumption_statement is None
    assert assumed.policy_fingerprint != backed.policy_fingerprint
    with pytest.raises(RollingFCRValidationError, match="system-wide"):
        AcceptedBidPolicy(
            policy_id="invalid-v1",
            kind="evidence_backed_accepted",
            evidence_descriptor={
                "kind": "system_wide_contracted_reserve_volume",
                "content_fingerprint": "2" * 64,
            },
        )


def test_dates_are_strictly_ordered_unique_and_roles_are_separate_from_comparison() -> None:
    manifest = build_authored_manifest()
    duplicate = (manifest.dates[0], manifest.dates[0], *manifest.dates[2:])
    reversed_dates = tuple(reversed(manifest.dates))

    with pytest.raises(RollingFCRValidationError, match="strictly ordered"):
        replace(manifest, dates=duplicate)
    with pytest.raises(RollingFCRValidationError, match="strictly ordered"):
        replace(manifest, dates=reversed_dates)
    with pytest.raises(RollingFCRValidationError, match="only included"):
        DeliveryDateClassification(
            delivery_date=AUTHORED_DELIVERY_DATES[0],
            execution_role="warm-up",
            comparison_eligible=True,
        )


def test_0800_manifest_requires_warmup_closeout_and_source_rounding() -> None:
    manifest = build_authored_manifest(
        "script-14-restriction-rolling-0800-v1"
    )

    assert manifest.dates[0].execution_role == "warm-up"
    assert manifest.dates[-1].execution_role == "close-out"
    assert manifest.decision_cutoff_rule == "previous-delivery-day-0800-local-v1"
    with pytest.raises(RollingFCRValidationError, match="first warm-up"):
        replace(
            manifest,
            dates=authored_date_classifications(
                "script-12-restriction-reset-midnight-v1"
            ),
        )
    with pytest.raises(RollingFCRValidationError, match="three-decimal"):
        build_authored_manifest(
            "script-14-restriction-rolling-0800-v1",
            state_carry_policy="native_full_precision",
        )


def test_only_midnight_restriction_profile_allows_native_full_precision() -> None:
    source = build_authored_manifest(
        "script-15-restriction-rolling-midnight-v1"
    )
    native = build_authored_manifest(
        "script-15-restriction-rolling-midnight-v1",
        state_carry_policy="native_full_precision",
    )

    assert source.manifest_fingerprint != native.manifest_fingerprint
    assert source.numeric_policy.state_carry_policy == "source_three_decimal"
    assert native.numeric_policy.state_carry_policy == "native_full_precision"
    source_input = build_authored_day_input(source, AUTHORED_DELIVERY_DATES[1])
    native_input = build_authored_day_input(native, AUTHORED_DELIVERY_DATES[1])
    assert source_input.day_input_fingerprint != native_input.day_input_fingerprint
    assert source_input.producer_input_fingerprints["numeric_policy"] != (
        native_input.producer_input_fingerprints["numeric_policy"]
    )
    from open_energy_lab.control._fcr_rolling_orchestrator import _ordinary_problem

    assert _ordinary_problem(source, source_input).problem_fingerprint != (
        _ordinary_problem(native, native_input).problem_fingerprint
    )
    with pytest.raises(RollingFCRValidationError, match="incompatible"):
        build_authored_manifest(
            "script-12-restriction-reset-midnight-v1",
            state_carry_policy="native_full_precision",
        )


def test_day_input_preserves_separate_cutoffs_and_rejects_evaluation_information() -> None:
    manifest = build_authored_manifest()
    original = build_authored_day_input(manifest, AUTHORED_DELIVERY_DATES[1])
    earlier_information = original.information_cutoff_utc - timedelta(hours=1)
    valid = RollingFCRDayInput(
        manifest_fingerprint=original.manifest_fingerprint,
        profile_fingerprint=original.profile_fingerprint,
        date_classification=original.date_classification,
        time_contract=original.time_contract,
        battery=original.battery,
        prices=original.prices,
        decision_cutoff_utc=original.decision_cutoff_utc,
        information_cutoff_utc=earlier_information,
        producer_input_fingerprints=original.producer_input_fingerprints,
        provenance=original.provenance,
    )

    assert valid.information_cutoff_utc < valid.decision_cutoff_utc
    with pytest.raises(RollingFCRValidationError, match="violates"):
        replace(
            original,
            producer_input_fingerprints={
                **original.producer_input_fingerprints,
                "activation_trace": "3" * 64,
            },
        )
    with pytest.raises(RollingFCRValidationError, match="forbidden evidence"):
        replace(original, provenance={"future_replay_result": "unavailable"})


def test_battery_binding_rejects_replay_capacity_below_optimization_bound() -> None:
    binding = build_authored_battery_binding()

    with pytest.raises(RollingFCRValidationError, match="must cover"):
        replace(binding, capacity_kwh=19.0)


@pytest.mark.parametrize("profile_id", (
    "script-11-relaxation-reset-midnight-v1",
    "script-12-restriction-reset-midnight-v1",
    "script-13-arbitrage-only-midnight-v1",
    "script-14-restriction-rolling-0800-v1",
    "script-15-restriction-rolling-midnight-v1",
))
def test_exactly_one_supported_profile_is_selected(profile_id: str) -> None:
    profile = build_rolling_fcr_experiment_profile(profile_id)
    assert profile.profile_id == profile_id
    assert len(profile.profile_fingerprint) == 64


def test_profile_builder_rejects_unknown_or_composite_profile() -> None:
    with pytest.raises(RollingFCRValidationError, match="unsupported"):
        build_rolling_fcr_experiment_profile("script-11+script-12")
