"""Deterministic authored inputs shared by Feature 015 tests.

The module contains no solver or simulator imports at import time. Builders
resolve existing public Open Energy Lab contracts only when called, so import
boundary tests can use this helper without eagerly loading Pyomo or HiGHS.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
import hashlib
import json
from typing import Any
from zoneinfo import ZoneInfo


AUTHORED_DELIVERY_DATES = tuple(date(2023, 6, day) for day in range(17, 21))
AUTHORED_MARKET_TIMEZONE = "Europe/Paris"
AUTHORED_ACTIVATION_CREATED_AT_UTC = datetime(2026, 8, 28, 12, tzinfo=UTC)


def fingerprint(value: object) -> str:
    """Return the repository's deterministic canonical authored-data digest."""

    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def authored_battery_mapping(
    *,
    initial_stored_energy_kwh: float = 10.0,
) -> dict[str, float]:
    """Return the bounded battery values shared by authored rolling cases."""

    return {
        "maximum_charge_power_kw": 10.0,
        "maximum_discharge_power_kw": 10.0,
        "minimum_stored_energy_kwh": 0.0,
        "maximum_stored_energy_kwh": 20.0,
        "initial_stored_energy_kwh": float(initial_stored_energy_kwh),
        "charge_efficiency": 0.92,
        "discharge_efficiency": 0.92,
    }


def build_authored_battery(
    *,
    initial_stored_energy_kwh: float = 10.0,
) -> Any:
    """Build one Feature 013 battery through its public contract."""

    from open_energy_lab.control import RobustFCRBatteryParameters

    return RobustFCRBatteryParameters(
        **authored_battery_mapping(
            initial_stored_energy_kwh=initial_stored_energy_kwh
        )
    )


def authored_price_mapping(
    delivery_date: date = AUTHORED_DELIVERY_DATES[1],
) -> dict[str, tuple[float, ...]]:
    """Return deterministic 24/6 prices with a visible date-dependent shift."""

    if delivery_date not in AUTHORED_DELIVERY_DATES:
        raise ValueError("delivery_date must belong to the authored four-date window")
    day_offset = float((delivery_date - AUTHORED_DELIVERY_DATES[0]).days)
    energy = (
        0.050,
        0.045,
        0.040,
        0.035,
        0.030,
        0.025,
        0.040,
        0.055,
        0.070,
        0.085,
        0.100,
        0.090,
        0.075,
        0.060,
        0.050,
        0.045,
        0.055,
        0.070,
        0.095,
        0.120,
        0.110,
        0.090,
        0.070,
        0.055,
    )
    fcr = (0.060, 0.055, 0.050, 0.052, 0.058, 0.065)
    return {
        "day_ahead_energy_prices_eur_per_kwh": tuple(
            value + 0.001 * day_offset for value in energy
        ),
        "fcr_capacity_prices_eur_per_kw_block": tuple(
            value + 0.002 * day_offset for value in fcr
        ),
    }


def build_authored_prices(
    delivery_date: date = AUTHORED_DELIVERY_DATES[1],
) -> Any:
    """Build one Feature 013 24/6 price input through its public contract."""

    from open_energy_lab.control import RobustFCRPriceInputs

    values = authored_price_mapping(delivery_date)
    return RobustFCRPriceInputs(
        **values,
        energy_interval_refs=tuple(
            f"authored:{delivery_date.isoformat()}:day_ahead:{index}"
            for index in range(24)
        ),
        fcr_interval_refs=tuple(
            f"authored:{delivery_date.isoformat()}:fcr:{index}"
            for index in range(6)
        ),
    )


def build_authored_zero_prices(
    delivery_date: date = AUTHORED_DELIVERY_DATES[1],
) -> Any:
    """Build a presolve-friendly zero-price 24/6 oracle."""

    from open_energy_lab.control import RobustFCRPriceInputs

    return RobustFCRPriceInputs(
        day_ahead_energy_prices_eur_per_kwh=(0.0,) * 24,
        fcr_capacity_prices_eur_per_kw_block=(0.0,) * 6,
        energy_interval_refs=tuple(
            f"authored-zero:{delivery_date}:day_ahead:{index}"
            for index in range(24)
        ),
        fcr_interval_refs=tuple(
            f"authored-zero:{delivery_date}:fcr:{index}" for index in range(6)
        ),
    )


def build_authored_time_contract(
    delivery_date: date = AUTHORED_DELIVERY_DATES[1],
) -> Any:
    """Build an ordinary 24/96/6 Feature 013 time contract."""

    from open_energy_lab.control import build_robust_fcr_time_contract

    return build_robust_fcr_time_contract(
        delivery_date=delivery_date,
        market_timezone=AUTHORED_MARKET_TIMEZONE,
    )


def authored_solve_policy_mapping(
    *,
    time_limit_seconds: float = 30.0,
    allow_feasible_incumbent_plan: bool = False,
) -> dict[str, object]:
    """Return the deterministic required-HiGHS policy for bounded cases."""

    return {
        "solver_name": "highs",
        "time_limit_seconds": float(time_limit_seconds),
        "threads": 1,
        "random_seed": 15,
        "primal_feasibility_tolerance": 1e-7,
        "dual_feasibility_tolerance": 1e-7,
        "mip_feasibility_tolerance": 1e-6,
        "relative_mip_gap": 1e-6,
        "objective_comparison_absolute_tolerance_eur": 1e-6,
        "objective_comparison_relative_tolerance": 1e-9,
        "allow_feasible_incumbent_plan": allow_feasible_incumbent_plan,
        "decision_canonicalization_id": "solver-output-kw-1e-9-half-even-v1",
    }


def build_authored_solve_policy(
    *,
    time_limit_seconds: float = 30.0,
    allow_feasible_incumbent_plan: bool = False,
) -> Any:
    """Build the bounded policy through Feature 013's public contract."""

    from open_energy_lab.control import RobustFCRSolvePolicy

    return RobustFCRSolvePolicy(
        **authored_solve_policy_mapping(
            time_limit_seconds=time_limit_seconds,
            allow_feasible_incumbent_plan=allow_feasible_incumbent_plan,
        )
    )


def build_authored_uncertainty() -> Any:
    """Build Feature 013's separate recovery and horizon uncertainty sets."""

    from open_energy_lab.control import (
        RecoveryWindowActivationBudget,
        RobustFCRUncertaintyProfile,
        derive_non_intraday_horizon_budget,
    )

    recovery = RecoveryWindowActivationBudget(
        recovery_activation_budget_hours=0.25,
        recovery_window_hours=2.25,
        pointwise_activation_lower=-1.0,
        pointwise_activation_upper=1.0,
    )
    return RobustFCRUncertaintyProfile(
        recovery_window=recovery,
        horizon_wide=derive_non_intraday_horizon_budget(
            recovery,
            horizon_hours=24.0,
        ),
    )


def build_authored_terminal_rule() -> Any:
    """Build the bounded terminal stored-energy requirement."""

    from open_energy_lab.control import TerminalStoredEnergyRule

    return TerminalStoredEnergyRule(
        minimum_terminal_stored_energy_kwh=10.0,
        allow_penalized_shortfall=True,
        shortfall_penalty_eur_per_kwh=100.0,
        rule_id="feature-015-authored-terminal-v1",
    )


def build_authored_data_descriptor(kind: str) -> Any:
    """Build one governed fingerprint-only rolling data descriptor."""

    from open_energy_lab.control import RollingFCRDataDescriptor

    values = {
        "day_ahead_price": (
            "EUR/kWh",
            "positive is a payment for source-positive discharge",
            "PT1H",
            "hourly-delivery-interval-v1",
        ),
        "fcr_capacity_price": (
            "EUR/kW/4h-block",
            "non-negative symmetric capacity payment",
            "PT4H",
            "six-four-hour-delivery-blocks-v1",
        ),
        "regulation_activation": (
            "dimensionless",
            "positive requests upward discharge",
            "PT10S",
            "ten-second-half-open-activation-v1",
        ),
    }
    unit, sign, resolution, mapping = values[kind]
    content = fingerprint({"kind": kind, "window": "2023-06-15/2023-06-22"})
    return RollingFCRDataDescriptor(
        descriptor_id=f"feature-015-authored-{kind}-v1",
        kind=kind,
        schema_version="authored-fixture-v1",
        unit=unit,
        sign_convention=sign,
        timezone=AUTHORED_MARKET_TIMEZONE,
        temporal_resolution=resolution,
        mapping_rule_id=mapping,
        coverage_start_utc=datetime(2023, 6, 15, tzinfo=UTC),
        coverage_end_utc=datetime(2023, 6, 23, tzinfo=UTC),
        source_organization="Open Energy Lab",
        source_document_id=f"project-authored-{kind}",
        acquisition_cutoff_utc=datetime(2023, 6, 15, tzinfo=UTC),
        content_sha256=content,
        normalized_data_fingerprint=fingerprint(
            {"content": content, "mapping": mapping}
        ),
        provenance={
            "kind": "project_authored",
            "license": "Apache-2.0",
            "purpose": "deterministic Feature 015 validation",
        },
    )


def build_authored_acceptance_policy() -> Any:
    from open_energy_lab.control import AcceptedBidPolicy

    return AcceptedBidPolicy(
        policy_id="feature-015-authored-assumed-acceptance-v1",
        kind="assumed_accepted",
        assumption_statement=(
            "optimizer-selected schedules are assumed accepted for authored research"
        ),
    )


def build_authored_numeric_policy(
    solve_policy: Any,
    *,
    state_carry_policy: str = "source_three_decimal",
) -> Any:
    from open_energy_lab.control import RollingFCRNumericPolicy

    return RollingFCRNumericPolicy(
        solve_policy_fingerprint=solve_policy.solve_policy_fingerprint,
        state_carry_policy=state_carry_policy,
        decimal_places=3 if state_carry_policy == "source_three_decimal" else 0,
    )


def build_authored_battery_binding(
    *,
    initial_stored_energy_kwh: float = 10.0,
) -> Any:
    from open_energy_lab.control import RollingFCRBatteryBinding

    return RollingFCRBatteryBinding(
        optimization_battery=build_authored_battery(
            initial_stored_energy_kwh=initial_stored_energy_kwh
        ),
        capacity_kwh=20.0,
        component_name="feature-015-authored-battery",
        replay_timestep_seconds=900,
    )


def authored_date_classifications(profile_id: str) -> tuple[Any, ...]:
    from open_energy_lab.control import DeliveryDateClassification

    values = []
    for index, delivery_date in enumerate(AUTHORED_DELIVERY_DATES):
        if profile_id == "script-14-restriction-rolling-0800-v1":
            if index == 0:
                role, eligible, reasons = "warm-up", False, ("initialization_only",)
            elif index == len(AUTHORED_DELIVERY_DATES) - 1:
                role, eligible, reasons = "close-out", False, ("closes_predecessor",)
            else:
                role, eligible, reasons = "included", True, ()
        else:
            role, eligible, reasons = "included", True, ()
        values.append(
            DeliveryDateClassification(
                delivery_date=delivery_date,
                execution_role=role,
                comparison_eligible=eligible,
                reason_codes=reasons,
            )
        )
    return tuple(values)


def build_authored_manifest(
    profile_id: str = "script-12-restriction-reset-midnight-v1",
    *,
    state_carry_policy: str = "source_three_decimal",
    solve_policy: Any | None = None,
) -> Any:
    from open_energy_lab.control import (
        AGGREGATION_POLICY,
        FAILURE_POLICY_COUPLED,
        FAILURE_POLICY_INDEPENDENT,
        RESUME_POLICY,
        build_rolling_fcr_experiment_profile,
        build_rolling_fcr_study_manifest,
    )

    profile = build_rolling_fcr_experiment_profile(profile_id)
    policy = solve_policy or build_authored_solve_policy()
    return build_rolling_fcr_study_manifest(
        study_id=f"feature-015-authored-{profile_id}",
        profile=profile,
        dates=authored_date_classifications(profile_id),
        day_ahead_descriptor=build_authored_data_descriptor("day_ahead_price"),
        fcr_capacity_descriptor=build_authored_data_descriptor("fcr_capacity_price"),
        activation_descriptor=build_authored_data_descriptor(
            "regulation_activation"
        ),
        battery_binding=build_authored_battery_binding(),
        uncertainty_profile=build_authored_uncertainty(),
        terminal_rule=build_authored_terminal_rule(),
        solve_policy=policy,
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
        acceptance_policy=build_authored_acceptance_policy(),
        numeric_policy=build_authored_numeric_policy(
            policy,
            state_carry_policy=state_carry_policy,
        ),
        failure_policy=(
            FAILURE_POLICY_INDEPENDENT
            if profile.is_independent
            else FAILURE_POLICY_COUPLED
        ),
        aggregation_policy=AGGREGATION_POLICY,
        resume_policy=RESUME_POLICY,
        reference_lineage={
            "reference_revision": (
                "7e44738bb30e5c8204efe40103b9be4c2203685c"
            ),
            "fixture_status": "not_required_for_authored_case",
        },
    )


def build_authored_day_input(manifest: Any, delivery_date: date) -> Any:
    from open_energy_lab.control import RollingFCRDayInput

    classification = next(
        item for item in manifest.dates if item.delivery_date == delivery_date
    )
    time_contract = build_authored_time_contract(delivery_date)
    if manifest.profile.state_mode == "rolling_0800":
        cutoff = datetime.combine(
            delivery_date - timedelta(days=1),
            time(8),
            tzinfo=ZoneInfo(AUTHORED_MARKET_TIMEZONE),
        ).astimezone(UTC)
    else:
        cutoff = time_contract.delivery_period.start_utc - timedelta(hours=12)
    prices = build_authored_prices(delivery_date)
    return RollingFCRDayInput(
        manifest_fingerprint=manifest.manifest_fingerprint,
        profile_fingerprint=manifest.profile.profile_fingerprint,
        date_classification=classification,
        time_contract=time_contract,
        battery=manifest.battery_binding.optimization_battery,
        prices=prices,
        decision_cutoff_utc=cutoff,
        information_cutoff_utc=cutoff,
        producer_input_fingerprints={
            "market_prices": prices.price_input_fingerprint,
            "battery_binding": manifest.battery_binding.binding_fingerprint,
            "uncertainty_profile": (
                manifest.uncertainty_profile.uncertainty_profile_fingerprint
            ),
        },
        provenance={
            "source_kind": "project_authored",
            "information_boundary": "pre_delivery_only",
        },
    )


def build_authored_accepted_fixings(
    *,
    public_energy_charge_positive_kw: Sequence[float] = (0.0,) * 16,
    fcr_capacity_kw: Sequence[float] = (0.0,) * 4,
) -> Any:
    from open_energy_lab.control import RobustFCRAcceptedDecisionFixings

    public = tuple(float(value) for value in public_energy_charge_positive_kw)
    fcr = tuple(float(value) for value in fcr_capacity_kw)
    return RobustFCRAcceptedDecisionFixings(
        predecessor_plan_fingerprint=fingerprint(
            {"kind": "authored-predecessor-plan", "energy": public, "fcr": fcr}
        ),
        predecessor_problem_fingerprint=fingerprint(
            {"kind": "authored-predecessor-problem"}
        ),
        predecessor_result_fingerprint=fingerprint(
            {"kind": "authored-predecessor-result", "energy": public, "fcr": fcr}
        ),
        energy_source_indices=tuple(range(-15, 1)),
        energy_public_charge_positive_kw=public,
        source_energy_positive_discharge_kw=tuple(-value for value in public),
        energy_interval_refs=tuple(
            f"authored:predecessor:energy:{index}" for index in range(8, 24)
        ),
        fcr_source_indices=tuple(range(-3, 1)),
        fcr_capacity_kw=fcr,
        fcr_interval_refs=tuple(
            f"authored:predecessor:fcr:{index}" for index in range(2, 6)
        ),
    )


def build_authored_0800_day_input(
    manifest: Any,
    delivery_date: date,
    *,
    accepted_fixings: Any | None = None,
) -> Any:
    """Build one 08:00 successor input with explicit accepted predecessor data."""

    from dataclasses import replace

    original = build_authored_day_input(manifest, delivery_date)
    return replace(
        original,
        predecessor_prices=build_authored_prices(
            delivery_date - timedelta(days=1)
        ),
        accepted_fixings=accepted_fixings or build_authored_accepted_fixings(),
        predecessor_cutoff_utc=original.information_cutoff_utc - timedelta(days=1),
    )


def build_authored_rolling_problem(
    profile_id: str,
    *,
    delivery_date: date = AUTHORED_DELIVERY_DATES[1],
    initial_stored_energy_kwh: float = 10.0,
    accepted_fixings: Any | None = None,
    solve_policy: Any | None = None,
) -> Any:
    from open_energy_lab.control import (
        build_robust_fcr_rolling_problem,
        build_rolling_fcr_experiment_profile,
    )

    profile = build_rolling_fcr_experiment_profile(profile_id)
    policy = solve_policy or build_authored_solve_policy(time_limit_seconds=30.0)
    time_contract = build_authored_time_contract(delivery_date)
    cutoff = time_contract.delivery_period.start_utc - timedelta(hours=12)
    common = {
        "problem_id": f"feature-015-authored-{profile_id}-{delivery_date}",
        "profile": profile,
        "current_time_contract": time_contract,
        "battery": build_authored_battery(
            initial_stored_energy_kwh=initial_stored_energy_kwh
        ),
        "current_prices": build_authored_prices(delivery_date),
        "uncertainty": build_authored_uncertainty(),
        "terminal_rule": build_authored_terminal_rule(),
        "solve_policy": policy,
        "information_cutoff_utc": cutoff,
        "producer_input_fingerprints": {
            "authored_prices": build_authored_prices(
                delivery_date
            ).price_input_fingerprint,
            "authored_case": fingerprint(
                {"profile": profile_id, "delivery_date": delivery_date.isoformat()}
            ),
        },
        "provenance": {
            "source_kind": "project_authored",
            "information_boundary": "pre_delivery_only",
        },
    }
    if profile.state_mode == "rolling_0800":
        predecessor_date = delivery_date - timedelta(days=1)
        common.update(
            {
                "predecessor_prices": build_authored_prices(predecessor_date),
                "accepted_fixings": (
                    accepted_fixings or build_authored_accepted_fixings()
                ),
                "predecessor_cutoff_utc": cutoff - timedelta(days=1),
            }
        )
    return build_robust_fcr_rolling_problem(**common)


def authored_activation_values(
    *,
    sample_count: int,
    phase: int = 0,
) -> tuple[float, ...]:
    """Return a balanced deterministic signal without external data."""

    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    pattern = (0.0, 0.25, 0.5, 0.25, 0.0, -0.25, -0.5, -0.25)
    return tuple(pattern[(index + phase) % len(pattern)] for index in range(sample_count))


def build_authored_activation_trace(
    delivery_date: date = AUTHORED_DELIVERY_DATES[1],
    *,
    resolution: str = "PT15M",
    values: Sequence[float] | None = None,
) -> Any:
    """Build a complete authored trace through the public market importer."""

    from open_energy_lab.market import (
        ActivationImportRequest,
        import_regulation_activation_trace,
    )
    from open_energy_lab.market.time import parse_iso8601_duration

    time_contract = build_authored_time_contract(delivery_date)
    period = time_contract.delivery_period
    step = parse_iso8601_duration(resolution)
    duration = period.end_utc - period.start_utc
    count_float = duration / step
    if count_float != int(count_float):
        raise ValueError("resolution must exactly divide the ordinary delivery day")
    sample_count = int(count_float)
    activation_values = tuple(values) if values is not None else authored_activation_values(
        sample_count=sample_count,
        phase=(delivery_date - AUTHORED_DELIVERY_DATES[0]).days,
    )
    if len(activation_values) != sample_count:
        raise ValueError("activation values must exactly cover the delivery day")
    request = ActivationImportRequest(
        source_name="Feature 015 project-authored activation",
        source_locator="tests/fcr_rolling_case_utils.py",
        source_revision="sha256:" + fingerprint(list(activation_values)),
        source_timezone=AUTHORED_MARKET_TIMEZONE,
        requested_start_utc=period.start_utc,
        requested_end_utc=period.end_utc,
        source_resolution=resolution,
        source_value_kind="interval_average",
        source_sign_meaning="positive source activation means upward/discharge",
        normalization_rule={
            "conversion": "identity",
            "formula": "activation = source_value",
            "point_to_interval": "already_interval_average",
            "clip_min": -1.0,
            "clip_max": 1.0,
            "target_sign": "positive is upward/discharge",
        },
        redistribution_basis={
            "source": "project-authored deterministic input",
            "terms": "Apache-2.0",
            "attribution": "Open Energy Lab Feature 015 tests",
        },
    )
    samples = []
    cursor = period.start_utc
    for value in activation_values:
        next_cursor = cursor + step
        samples.append(
            {
                "start_utc": cursor,
                "end_utc": next_cursor,
                "value": float(value),
                "source_value": float(value),
                "source_unit": "dimensionless",
            }
        )
        cursor = next_cursor
    assert cursor == period.end_utc
    return import_regulation_activation_trace(
        request,
        samples,
        trace_id=f"feature-015-authored-{delivery_date.isoformat()}-activation-v1",
        created_at_utc=AUTHORED_ACTIVATION_CREATED_AT_UTC,
    )


def build_authored_fixed_plan(
    delivery_date: date = AUTHORED_DELIVERY_DATES[0],
    *,
    energy_charge_positive_kw: Sequence[float] = (0.0,) * 24,
    fcr_capacity_kw: Sequence[float] = (0.0,) * 6,
) -> Any:
    """Build one full-precision accepted robust plan without loading a solver."""

    from open_energy_lab.control import (
        BidPlanProducer,
        OptimizationMetric,
        build_fixed_fcr_bid_plan,
    )
    from open_energy_lab.simulator import (
        build_energy_baseline_schedule,
        build_fcr_capacity_schedule,
    )

    time_contract = build_authored_time_contract(delivery_date)
    energy_values = tuple(float(value) for value in energy_charge_positive_kw)
    fcr_values = tuple(float(value) for value in fcr_capacity_kw)
    if len(energy_values) != 24 or len(fcr_values) != 6:
        raise ValueError("authored fixed plan requires exact 24/6 decisions")
    energy = build_energy_baseline_schedule(
        schedule_id=f"feature-015-authored-{delivery_date}-energy-v1",
        semantics_version="charge-positive-fixed-v1",
        covered_start_utc=time_contract.delivery_period.start_utc,
        covered_end_utc=time_contract.delivery_period.end_utc,
        intervals=tuple(
            {
                "start_utc": interval.start_utc,
                "end_utc": interval.end_utc,
                "power_kw": value,
                "schedule_source": "fixed",
            }
            for interval, value in zip(
                time_contract.energy_intervals,
                energy_values,
                strict=True,
            )
        ),
    )
    fcr = build_fcr_capacity_schedule(
        schedule_id=f"feature-015-authored-{delivery_date}-fcr-v1",
        semantics_version="symmetric-fcr-fixed-v1",
        product_identity={
            "product": "symmetric-fcr",
            "tender": "daily",
            "block_duration": "PT4H",
        },
        covered_start_utc=time_contract.delivery_period.start_utc,
        covered_end_utc=time_contract.delivery_period.end_utc,
        intervals=tuple(
            {
                "start_utc": interval.start_utc,
                "end_utc": interval.end_utc,
                "capacity_kw": value,
                "volume_observation_ref": f"authored:accepted:{index}",
                "price_observation_ref": f"authored:fcr-price:{index}",
            }
            for index, (interval, value) in enumerate(
                zip(time_contract.fcr_intervals, fcr_values, strict=True)
            )
        ),
    )
    return build_fixed_fcr_bid_plan(
        plan_id=f"feature-015-authored-{delivery_date}-accepted-plan-v1",
        producer=BidPlanProducer(
            producer_id="feature-015-authored-robust-producer",
            producer_kind="robust",
            producer_version="authored-full-precision-v1",
            configuration_fingerprint=fingerprint(
                {"energy": energy_values, "fcr": fcr_values}
            ),
            configuration_unavailable_reason=None,
        ),
        information_cutoff_utc=(
            time_contract.delivery_period.start_utc - timedelta(hours=12)
        ),
        energy_schedule=energy,
        fcr_schedule=fcr,
        producer_input_fingerprints={"authored_inputs": "7" * 64},
        solve_status="optimal",
        objective=OptimizationMetric(
            availability="available",
            value=0.0,
            unit="EUR",
            unavailable_reason=None,
            meaning="optimization_objective",
        ),
        objective_bound=OptimizationMetric(
            availability="available",
            value=0.0,
            unit="EUR",
            unavailable_reason=None,
            meaning="optimization_bound",
        ),
        diagnostics=(),
    )


def authored_date_window() -> tuple[date, ...]:
    """Return a detached copy of the ordered bounded authored dates."""

    return tuple(AUTHORED_DELIVERY_DATES)


__all__ = [
    "AUTHORED_ACTIVATION_CREATED_AT_UTC",
    "AUTHORED_DELIVERY_DATES",
    "AUTHORED_MARKET_TIMEZONE",
    "authored_activation_values",
    "authored_battery_mapping",
    "authored_date_window",
    "authored_price_mapping",
    "authored_solve_policy_mapping",
    "build_authored_activation_trace",
    "build_authored_acceptance_policy",
    "build_authored_accepted_fixings",
    "build_authored_0800_day_input",
    "build_authored_battery",
    "build_authored_battery_binding",
    "build_authored_data_descriptor",
    "build_authored_day_input",
    "build_authored_fixed_plan",
    "build_authored_manifest",
    "build_authored_numeric_policy",
    "build_authored_prices",
    "build_authored_rolling_problem",
    "build_authored_solve_policy",
    "build_authored_terminal_rule",
    "build_authored_time_contract",
    "build_authored_uncertainty",
    "build_authored_zero_prices",
    "authored_date_classifications",
    "fingerprint",
]
