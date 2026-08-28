"""Post-acceptance Feature 012 bindings for Feature 013 integration tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
import hashlib
import json

from open_energy_lab.control import FixedFCRBidPlan
from open_energy_lab.market import (
    ActivationImportRequest,
    CanonicalInterval,
    RegulationActivationTrace,
    import_regulation_activation_trace,
)
from open_energy_lab.simulator import (
    BatteryComponent,
    EvaluationMarketContext,
    EvaluationPriceObservation,
    FCRBidEvaluationRequest,
    MultiRateTimeContract,
)


FIXED_ACTIVATION_CREATED_AT_UTC = datetime(2026, 8, 27, 12, tzinfo=UTC)


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_post_acceptance_time_contract(
    plan: FixedFCRBidPlan,
    *,
    activation_resolution: str = "PT15M",
) -> MultiRateTimeContract:
    """Bind a plan period to the existing Feature 012 multi-rate grid."""

    if not isinstance(plan, FixedFCRBidPlan):
        raise TypeError("plan must be an existing FixedFCRBidPlan")
    period = plan.energy_schedule.covered_period
    return MultiRateTimeContract(
        start_utc=period.start_utc,
        end_utc=period.end_utc,
        activation_resolution=activation_resolution,
        state_checkpoint_resolution="PT15M",
        energy_resolution="PT1H",
        fcr_resolution="PT4H",
        market_timezone="Europe/Paris",
        interval_convention="start-inclusive/end-exclusive",
    )


def build_post_acceptance_battery(
    *,
    capacity_kwh: float,
    maximum_charge_power_kw: float,
    maximum_discharge_power_kw: float,
    minimum_stored_energy_kwh: float,
    maximum_stored_energy_kwh: float,
    initial_stored_energy_kwh: float,
    charge_efficiency: float,
    discharge_efficiency: float,
) -> BatteryComponent:
    """Bind declared bidding battery values to the existing replay component."""

    return BatteryComponent(
        name="feature-013-post-acceptance-battery",
        capacity_kwh=capacity_kwh,
        max_charge_kw=maximum_charge_power_kw,
        max_discharge_kw=maximum_discharge_power_kw,
        charge_efficiency=charge_efficiency,
        discharge_efficiency=discharge_efficiency,
        initial_soc=initial_stored_energy_kwh / capacity_kwh,
        min_soc=minimum_stored_energy_kwh / capacity_kwh,
        max_soc=maximum_stored_energy_kwh / capacity_kwh,
    )


def build_post_acceptance_activation_trace(
    plan: FixedFCRBidPlan,
    *,
    time_contract: MultiRateTimeContract,
    activation_values: Sequence[float] | None = None,
) -> RegulationActivationTrace:
    """Bind authored realized activation only after a plan already exists."""

    intervals = time_contract.index.activation_intervals
    values = (
        tuple(activation_values)
        if activation_values is not None
        else tuple((1.0, -1.0, 0.0, 0.0)[index % 4] for index in range(len(intervals)))
    )
    if len(values) != len(intervals):
        raise ValueError("activation_values must match the evaluation grid")
    request = ActivationImportRequest(
        source_name="Feature 013 post-acceptance authored activation",
        source_locator="tests/integration/simulator/robust_fcr_replay_utils.py",
        source_revision="sha256:" + _fingerprint(list(values)),
        source_timezone="Europe/Paris",
        requested_start_utc=time_contract.start_utc,
        requested_end_utc=time_contract.end_utc,
        source_resolution=time_contract.activation_resolution,
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
            "source": "project-authored integration input",
            "terms": "Apache-2.0",
        },
    )
    return import_regulation_activation_trace(
        request,
        [
            {
                "start_utc": interval.start_utc,
                "end_utc": interval.end_utc,
                "value": float(value),
                "source_value": float(value),
                "source_unit": "dimensionless",
            }
            for interval, value in zip(intervals, values, strict=True)
        ],
        trace_id=f"{plan.plan_id}-post-acceptance-activation-v1",
        created_at_utc=FIXED_ACTIVATION_CREATED_AT_UTC,
    )


def build_post_acceptance_market_context(
    plan: FixedFCRBidPlan,
    *,
    day_ahead_prices_eur_per_mwh: Sequence[float] | None = None,
    fcr_capacity_prices_eur_per_kw_block: Sequence[float] | None = None,
) -> EvaluationMarketContext:
    """Bind accepted capacity and settlement prices to one existing plan."""

    energy = plan.energy_schedule.intervals
    fcr = plan.fcr_schedule.intervals
    day_prices = (
        tuple(day_ahead_prices_eur_per_mwh)
        if day_ahead_prices_eur_per_mwh is not None
        else (0.0,) * len(energy)
    )
    fcr_prices = (
        tuple(fcr_capacity_prices_eur_per_kw_block)
        if fcr_capacity_prices_eur_per_kw_block is not None
        else (0.0,) * len(fcr)
    )
    if len(day_prices) != len(energy) or len(fcr_prices) != len(fcr):
        raise ValueError("post-acceptance prices must match the plan schedules")
    day_observations = tuple(
        EvaluationPriceObservation(
            interval=item.interval,
            price_kind="day_ahead_energy",
            source_value=float(price),
            source_unit="EUR/MWh",
            canonical_value=float(price),
            canonical_unit="EUR/MWh",
            conversion_id="post-acceptance-identity-v1",
            source_ref=f"post_acceptance_day_ahead_price:{index}",
        )
        for index, (item, price) in enumerate(zip(energy, day_prices, strict=True))
    )
    fcr_observations = tuple(
        EvaluationPriceObservation(
            interval=item.interval,
            price_kind="fcr_capacity",
            source_value=float(price),
            source_unit="EUR/kW/block",
            canonical_value=float(price),
            canonical_unit="EUR/kW/block",
            conversion_id="post-acceptance-identity-v1",
            source_ref=item.price_observation_ref,
        )
        for item, price in zip(fcr, fcr_prices, strict=True)
    )
    accepted = {
        item.volume_observation_ref: {
            "capacity_kw": item.capacity_kw,
            "unit": "kW",
            "evidence_kind": "authored_post_acceptance",
        }
        for item in fcr
    }
    return EvaluationMarketContext(
        context_kind="reference_result",
        semantics_version="feature-013-post-acceptance-market-context-v1",
        period=CanonicalInterval.from_utc(
            plan.energy_schedule.covered_period.start_utc,
            plan.energy_schedule.covered_period.end_utc,
        ),
        day_ahead_prices=day_observations,
        fcr_capacity_prices=fcr_observations,
        accepted_bid_evidence=accepted,
        source_fingerprints={
            "post_acceptance_market": _fingerprint(
                {
                    "plan_fingerprint": plan.plan_fingerprint,
                    "day_ahead_prices_eur_per_mwh": list(day_prices),
                    "fcr_capacity_prices_eur_per_kw_block": list(fcr_prices),
                    "accepted_capacity_kw": [item.capacity_kw for item in fcr],
                }
            )
        },
    )


def build_post_acceptance_request(
    plan: FixedFCRBidPlan,
    *,
    battery: BatteryComponent,
    activation_trace: RegulationActivationTrace | None = None,
    activation_resolution: str = "PT15M",
    day_ahead_prices_eur_per_mwh: Sequence[float] | None = None,
    fcr_capacity_prices_eur_per_kw_block: Sequence[float] | None = None,
) -> FCRBidEvaluationRequest:
    """Bind evaluation-only evidence without copying or changing the plan."""

    time_contract = build_post_acceptance_time_contract(
        plan,
        activation_resolution=activation_resolution,
    )
    trace = activation_trace or build_post_acceptance_activation_trace(
        plan,
        time_contract=time_contract,
    )
    market = build_post_acceptance_market_context(
        plan,
        day_ahead_prices_eur_per_mwh=day_ahead_prices_eur_per_mwh,
        fcr_capacity_prices_eur_per_kw_block=(
            fcr_capacity_prices_eur_per_kw_block
        ),
    )
    return FCRBidEvaluationRequest(
        evaluation_id=f"{plan.plan_id}-post-acceptance-evaluation-v1",
        plan=plan,
        market_context=market,
        activation_trace=trace,
        battery=battery,
        time_contract=time_contract,
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
        penalty_rule=None,
        terminal_soc_target=None,
        comparison_fixture=None,
        numeric_tolerance=1e-6,
    )


__all__ = [
    "build_post_acceptance_activation_trace",
    "build_post_acceptance_battery",
    "build_post_acceptance_market_context",
    "build_post_acceptance_request",
    "build_post_acceptance_time_contract",
]
