"""Deterministic builders shared by Feature 012 integration tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
from typing import Sequence

from open_energy_lab.control.fcr_bid_plan import (
    BidPlanProducer,
    FixedFCRBidPlan,
    OptimizationMetric,
    build_fixed_fcr_bid_plan,
)
from open_energy_lab.market.activation import (
    ActivationImportRequest,
    RegulationActivationTrace,
    import_regulation_activation_trace,
)
from open_energy_lab.market.time import CanonicalInterval
from open_energy_lab.simulator.fcr_bid_evaluation import (
    EvaluationMarketContext,
    EvaluationPriceObservation,
    FCRBidEvaluationRequest,
)
from open_energy_lab.simulator.scenario import BatteryComponent
from open_energy_lab.simulator.stacked_service import (
    EnergyBaselineSchedule,
    FCRCapacitySchedule,
    MultiRateTimeContract,
    build_energy_baseline_schedule,
    build_fcr_capacity_schedule,
)


DEFAULT_START = datetime(2023, 6, 17, 22, tzinfo=UTC)
DEFAULT_END = DEFAULT_START + timedelta(hours=4)
FIXED_CREATED_AT = datetime(2026, 8, 26, 12, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class FCRBidEvaluationTestCase:
    plan: FixedFCRBidPlan
    market_context: EvaluationMarketContext
    activation_trace: RegulationActivationTrace
    battery: BatteryComponent
    time_contract: MultiRateTimeContract
    request: FCRBidEvaluationRequest


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_test_time_contract(
    *,
    start_utc: datetime = DEFAULT_START,
    end_utc: datetime = DEFAULT_END,
    activation_resolution: str = "PT30M",
    checkpoint_resolution: str = "PT30M",
) -> MultiRateTimeContract:
    return MultiRateTimeContract(
        start_utc=start_utc,
        end_utc=end_utc,
        activation_resolution=activation_resolution,
        state_checkpoint_resolution=checkpoint_resolution,
        energy_resolution="PT1H",
        fcr_resolution="PT4H",
        market_timezone="Europe/Paris",
        interval_convention="start-inclusive/end-exclusive",
    )


def build_test_energy_schedule(
    powers_kw: Sequence[float],
    *,
    time_contract: MultiRateTimeContract,
    schedule_id: str = "feature-012-test-energy-v1",
) -> EnergyBaselineSchedule:
    if len(powers_kw) != len(time_contract.index.energy_intervals):
        raise ValueError("powers_kw must match the test energy grid")
    return build_energy_baseline_schedule(
        schedule_id=schedule_id,
        semantics_version="charge-positive-fixed-v1",
        covered_start_utc=time_contract.start_utc,
        covered_end_utc=time_contract.end_utc,
        intervals=[
            {
                "start_utc": interval.start_utc,
                "end_utc": interval.end_utc,
                "power_kw": float(power),
                "schedule_source": "fixed",
            }
            for interval, power in zip(
                time_contract.index.energy_intervals,
                powers_kw,
                strict=True,
            )
        ],
    )


def build_test_fcr_schedule(
    capacities_kw: Sequence[float],
    *,
    time_contract: MultiRateTimeContract,
    schedule_id: str = "feature-012-test-fcr-v1",
) -> FCRCapacitySchedule:
    if len(capacities_kw) != len(time_contract.index.fcr_intervals):
        raise ValueError("capacities_kw must match the test FCR grid")
    return build_fcr_capacity_schedule(
        schedule_id=schedule_id,
        semantics_version="symmetric-fcr-fixed-v1",
        product_identity={
            "product": "symmetric-fcr",
            "tender": "daily",
            "block_duration": "PT4H",
        },
        covered_start_utc=time_contract.start_utc,
        covered_end_utc=time_contract.end_utc,
        intervals=[
            {
                "start_utc": interval.start_utc,
                "end_utc": interval.end_utc,
                "capacity_kw": float(capacity),
                "volume_observation_ref": f"test_accepted_fcr_bid:{index}",
                "price_observation_ref": f"test_fcr_capacity_price:{index}",
            }
            for index, (interval, capacity) in enumerate(
                zip(
                    time_contract.index.fcr_intervals,
                    capacities_kw,
                    strict=True,
                )
            )
        ],
    )


def build_test_battery(
    *,
    capacity_kwh: float = 100.0,
    max_charge_kw: float = 50.0,
    max_discharge_kw: float = 50.0,
    charge_efficiency: float = 0.92,
    discharge_efficiency: float = 0.92,
    initial_soc: float = 0.5,
    min_soc: float = 0.1,
    max_soc: float = 0.9,
) -> BatteryComponent:
    return BatteryComponent(
        name="feature-012-test-battery",
        capacity_kwh=capacity_kwh,
        max_charge_kw=max_charge_kw,
        max_discharge_kw=max_discharge_kw,
        charge_efficiency=charge_efficiency,
        discharge_efficiency=discharge_efficiency,
        initial_soc=initial_soc,
        min_soc=min_soc,
        max_soc=max_soc,
    )


def build_test_activation_trace(
    values: Sequence[float],
    *,
    time_contract: MultiRateTimeContract,
    trace_id: str = "feature-012-test-activation-v1",
) -> RegulationActivationTrace:
    intervals = time_contract.index.activation_intervals
    if len(values) != len(intervals):
        raise ValueError("activation values must match the test activation grid")
    request = ActivationImportRequest(
        source_name="Feature 012 authored activation",
        source_locator="tests/fixtures/fcr_bid_evaluation/authored",
        source_revision="sha256:" + _digest(list(values)),
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
            "source": "project-authored synthetic input",
            "terms": "Apache-2.0",
            "attribution": "Open Energy Lab tests",
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
        trace_id=trace_id,
        created_at_utc=FIXED_CREATED_AT,
    )


def build_test_market_context(
    *,
    time_contract: MultiRateTimeContract,
    day_ahead_prices_eur_per_mwh: Sequence[float],
    fcr_capacity_prices_eur_per_kw_block: Sequence[float],
    accepted_fcr_capacities_kw: Sequence[float],
    context_kind: str = "reference_result",
) -> EvaluationMarketContext:
    energy_intervals = time_contract.index.energy_intervals
    fcr_intervals = time_contract.index.fcr_intervals
    if len(day_ahead_prices_eur_per_mwh) != len(energy_intervals):
        raise ValueError("day-ahead prices must match the test energy grid")
    if len(fcr_capacity_prices_eur_per_kw_block) != len(fcr_intervals):
        raise ValueError("FCR prices must match the test FCR grid")
    if len(accepted_fcr_capacities_kw) != len(fcr_intervals):
        raise ValueError("accepted capacities must match the test FCR grid")
    day_ahead = tuple(
        EvaluationPriceObservation(
            interval=interval,
            price_kind="day_ahead_energy",
            source_value=float(price),
            source_unit="EUR/MWh",
            canonical_value=float(price),
            canonical_unit="EUR/MWh",
            conversion_id="authored-identity-v1",
            source_ref=f"test_day_ahead_price:{index}",
        )
        for index, (interval, price) in enumerate(
            zip(energy_intervals, day_ahead_prices_eur_per_mwh, strict=True)
        )
    )
    fcr_prices = tuple(
        EvaluationPriceObservation(
            interval=interval,
            price_kind="fcr_capacity",
            source_value=float(price),
            source_unit="EUR/kW/block",
            canonical_value=float(price),
            canonical_unit="EUR/kW/block",
            conversion_id="authored-identity-v1",
            source_ref=f"test_fcr_capacity_price:{index}",
        )
        for index, (interval, price) in enumerate(
            zip(
                fcr_intervals,
                fcr_capacity_prices_eur_per_kw_block,
                strict=True,
            )
        )
    )
    source_payload = {
        "day_ahead": list(day_ahead_prices_eur_per_mwh),
        "fcr_capacity": list(fcr_capacity_prices_eur_per_kw_block),
        "accepted_fcr": list(accepted_fcr_capacities_kw),
    }
    return EvaluationMarketContext(
        context_kind=context_kind,
        semantics_version="feature-012-authored-market-context-v1",
        period=CanonicalInterval.from_utc(
            time_contract.start_utc,
            time_contract.end_utc,
        ),
        day_ahead_prices=day_ahead,
        fcr_capacity_prices=fcr_prices,
        accepted_bid_evidence={
            f"test_accepted_fcr_bid:{index}": {
                "capacity_kw": float(capacity),
                "unit": "kW",
                "evidence_kind": "authored_accepted_bid",
            }
            for index, capacity in enumerate(accepted_fcr_capacities_kw)
        },
        source_fingerprints={"authored_market_context": _digest(source_payload)},
    )


def build_test_plan(
    *,
    energy_schedule: EnergyBaselineSchedule,
    fcr_schedule: FCRCapacitySchedule,
    information_cutoff_utc: datetime,
    producer_kind: str = "manual",
) -> FixedFCRBidPlan:
    producer = BidPlanProducer(
        producer_id=f"feature-012-{producer_kind}-producer",
        producer_kind=producer_kind,
        producer_version="fixture-v1",
        configuration_fingerprint=_digest(
            {"producer_kind": producer_kind, "version": "fixture-v1"}
        ),
        configuration_unavailable_reason=None,
    )
    return build_fixed_fcr_bid_plan(
        plan_id="feature-012-test-plan-v1",
        producer=producer,
        information_cutoff_utc=information_cutoff_utc,
        energy_schedule=energy_schedule,
        fcr_schedule=fcr_schedule,
        producer_input_fingerprints={"authored_inputs": _digest("fixture-v1")},
        solve_status="not_applicable",
        objective=OptimizationMetric(
            availability="unavailable",
            value=None,
            unit=None,
            unavailable_reason="authored plan has no optimization objective",
            meaning="optimization_objective",
        ),
        objective_bound=OptimizationMetric(
            availability="unavailable",
            value=None,
            unit=None,
            unavailable_reason="authored plan has no optimization bound",
            meaning="optimization_bound",
        ),
    )


def build_test_evaluation_case(
    *,
    powers_kw: Sequence[float] = (0.0, 0.0, 0.0, 0.0),
    capacities_kw: Sequence[float] = (1.0,),
    activation_values: Sequence[float] = (1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0, -1.0),
    day_ahead_prices_eur_per_mwh: Sequence[float] = (50.0, 60.0, 70.0, 80.0),
    fcr_capacity_prices_eur_per_kw_block: Sequence[float] = (0.08,),
    time_contract: MultiRateTimeContract | None = None,
    battery: BatteryComponent | None = None,
    settlement_profile: str = "feature-010-default-v1",
    producer_kind: str = "manual",
) -> FCRBidEvaluationTestCase:
    contract = time_contract or build_test_time_contract()
    component = battery or build_test_battery()
    energy_schedule = build_test_energy_schedule(
        powers_kw,
        time_contract=contract,
    )
    fcr_schedule = build_test_fcr_schedule(
        capacities_kw,
        time_contract=contract,
    )
    activation_trace = build_test_activation_trace(
        activation_values,
        time_contract=contract,
    )
    market_context = build_test_market_context(
        time_contract=contract,
        day_ahead_prices_eur_per_mwh=day_ahead_prices_eur_per_mwh,
        fcr_capacity_prices_eur_per_kw_block=(
            fcr_capacity_prices_eur_per_kw_block
        ),
        accepted_fcr_capacities_kw=capacities_kw,
    )
    plan = build_test_plan(
        energy_schedule=energy_schedule,
        fcr_schedule=fcr_schedule,
        information_cutoff_utc=contract.start_utc - timedelta(hours=1),
        producer_kind=producer_kind,
    )
    request = FCRBidEvaluationRequest(
        evaluation_id="feature-012-test-evaluation-v1",
        plan=plan,
        market_context=market_context,
        activation_trace=activation_trace,
        battery=component,
        time_contract=contract,
        settlement_profile=settlement_profile,
        penalty_rule=None,
        terminal_soc_target=None,
        comparison_fixture=None,
        numeric_tolerance=1e-6,
    )
    return FCRBidEvaluationTestCase(
        plan=plan,
        market_context=market_context,
        activation_trace=activation_trace,
        battery=component,
        time_contract=contract,
        request=request,
    )


__all__ = [
    "DEFAULT_END",
    "DEFAULT_START",
    "FCRBidEvaluationTestCase",
    "build_test_activation_trace",
    "build_test_battery",
    "build_test_energy_schedule",
    "build_test_evaluation_case",
    "build_test_fcr_schedule",
    "build_test_market_context",
    "build_test_plan",
    "build_test_time_contract",
]
