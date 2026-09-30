"""Evaluate one authored fixed plan through the common Feature 012 environment."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import json

from open_energy_lab.simulator.fcr_bid_plan import (
    BidPlanProducer,
    OptimizationMetric,
    build_fixed_fcr_bid_plan,
)
from open_energy_lab.market import (
    ActivationImportRequest,
    CanonicalInterval,
    import_regulation_activation_trace,
)
from open_energy_lab.simulator import (
    BatteryComponent,
    EvaluationMarketContext,
    EvaluationPriceObservation,
    FCRBidEvaluationRequest,
    MultiRateTimeContract,
    build_energy_baseline_schedule,
    build_fcr_capacity_schedule,
    evaluate_fixed_fcr_bid,
)


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def build_manual_request(
    *,
    invalid_headroom: bool = False,
    producer_kind: str = "manual",
) -> FCRBidEvaluationRequest:
    """Build the deterministic authored request used by examples and notebooks."""

    supported_producer_kinds = {"manual", "heuristic", "robust", "tpm"}
    if producer_kind not in supported_producer_kinds:
        supported = ", ".join(sorted(supported_producer_kinds))
        raise ValueError(
            f"producer_kind must be one of {supported}; got {producer_kind!r}"
        )
    start = datetime(2023, 6, 17, 22, tzinfo=UTC)
    end = start + timedelta(hours=4)
    time_contract = MultiRateTimeContract(
        start_utc=start,
        end_utc=end,
        activation_resolution="PT30M",
        state_checkpoint_resolution="PT30M",
        energy_resolution="PT1H",
        fcr_resolution="PT4H",
        market_timezone="Europe/Paris",
        interval_convention="start-inclusive/end-exclusive",
    )
    baseline_values = (1.0, 0.0, 0.0, -1.0)
    capacity = 2.0 if invalid_headroom else 1.0
    energy_schedule = build_energy_baseline_schedule(
        schedule_id="manual-example-energy-v1",
        semantics_version="charge-positive-fixed-v1",
        covered_start_utc=start,
        covered_end_utc=end,
        intervals=[
            {
                "start_utc": interval.start_utc,
                "end_utc": interval.end_utc,
                "power_kw": power,
                "schedule_source": "fixed",
            }
            for interval, power in zip(
                time_contract.index.energy_intervals,
                baseline_values,
                strict=True,
            )
        ],
    )
    fcr_schedule = build_fcr_capacity_schedule(
        schedule_id="manual-example-fcr-v1",
        semantics_version="symmetric-fcr-fixed-v1",
        product_identity={
            "product": "symmetric-fcr",
            "tender": "daily",
            "block_duration": "PT4H",
        },
        covered_start_utc=start,
        covered_end_utc=end,
        intervals=[
            {
                "start_utc": start,
                "end_utc": end,
                "capacity_kw": capacity,
                "volume_observation_ref": "manual_accepted_fcr_bid:0",
                "price_observation_ref": "manual_fcr_capacity_price:0",
            }
        ],
    )
    activation_values = (1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0, -1.0)
    activation_request = ActivationImportRequest(
        source_name="authored manual activation",
        source_locator="examples/fcr_bid_evaluation/run_manual_plan.py",
        source_revision="example-v1",
        source_timezone="Europe/Paris",
        requested_start_utc=start,
        requested_end_utc=end,
        source_resolution="PT30M",
        source_value_kind="interval_average",
        source_sign_meaning="positive source activation means upward/discharge",
        normalization_rule={
            "conversion": "identity",
            "formula": "activation",
            "point_to_interval": "already_interval_average",
            "clip_min": -1.0,
            "clip_max": 1.0,
            "target_sign": "positive is upward/discharge",
        },
        redistribution_basis={
            "source": "project-authored example",
            "terms": "Apache-2.0",
        },
    )
    activation_trace = import_regulation_activation_trace(
        activation_request,
        [
            {
                "start_utc": interval.start_utc,
                "end_utc": interval.end_utc,
                "value": value,
                "source_value": value,
                "source_unit": "dimensionless",
            }
            for interval, value in zip(
                time_contract.index.activation_intervals,
                activation_values,
                strict=True,
            )
        ],
        trace_id="manual-example-activation-v1",
        created_at_utc=datetime(2026, 8, 26, 12, tzinfo=UTC),
    )
    day_prices = (50.0, 60.0, 70.0, 100.0)
    market_context = EvaluationMarketContext(
        context_kind="reference_result",
        semantics_version="manual-example-market-context-v1",
        period=CanonicalInterval.from_utc(start, end),
        day_ahead_prices=tuple(
            EvaluationPriceObservation(
                interval=interval,
                price_kind="day_ahead_energy",
                source_value=price,
                source_unit="EUR/MWh",
                canonical_value=price,
                canonical_unit="EUR/MWh",
                conversion_id="identity-v1",
                source_ref=f"manual_day_ahead_price:{index}",
            )
            for index, (interval, price) in enumerate(
                zip(time_contract.index.energy_intervals, day_prices, strict=True)
            )
        ),
        fcr_capacity_prices=(
            EvaluationPriceObservation(
                interval=time_contract.index.fcr_intervals[0],
                price_kind="fcr_capacity",
                source_value=0.08,
                source_unit="EUR/kW/block",
                canonical_value=0.08,
                canonical_unit="EUR/kW/block",
                conversion_id="identity-v1",
                source_ref="manual_fcr_capacity_price:0",
            ),
        ),
        accepted_bid_evidence={
            "manual_accepted_fcr_bid:0": {
                "capacity_kw": capacity,
                "unit": "kW",
                "evidence_kind": "authored_accepted_bid",
            }
        },
        source_fingerprints={
            "authored_market_context": _digest(
                {"day_prices": day_prices, "capacity": capacity}
            )
        },
    )
    unavailable_objective = OptimizationMetric(
        availability="unavailable",
        value=None,
        unit=None,
        unavailable_reason="manual example has no optimization objective",
        meaning="optimization_objective",
    )
    unavailable_bound = OptimizationMetric(
        availability="unavailable",
        value=None,
        unit=None,
        unavailable_reason="manual example has no optimization bound",
        meaning="optimization_bound",
    )
    plan = build_fixed_fcr_bid_plan(
        plan_id="manual-example-plan-v1",
        producer=BidPlanProducer(
            producer_id="manual-example",
            producer_kind=producer_kind,
            producer_version="v1",
            configuration_fingerprint=_digest("manual-example-v1"),
            configuration_unavailable_reason=None,
        ),
        information_cutoff_utc=start - timedelta(hours=1),
        energy_schedule=energy_schedule,
        fcr_schedule=fcr_schedule,
        producer_input_fingerprints={"authored_inputs": _digest("inputs-v1")},
        solve_status="not_applicable",
        objective=unavailable_objective,
        objective_bound=unavailable_bound,
    )
    battery = BatteryComponent(
        name="manual-example-battery",
        capacity_kwh=5.0,
        max_charge_kw=2.0,
        max_discharge_kw=2.0,
        charge_efficiency=0.8,
        discharge_efficiency=0.8,
        initial_soc=0.5,
        min_soc=0.0,
        max_soc=1.0,
    )
    return FCRBidEvaluationRequest(
        evaluation_id="manual-example-evaluation-v1",
        plan=plan,
        market_context=market_context,
        activation_trace=activation_trace,
        battery=battery,
        time_contract=time_contract,
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
        penalty_rule=None,
        terminal_soc_target=None,
        comparison_fixture=None,
        numeric_tolerance=1e-6,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--invalid-headroom",
        action="store_true",
        help="evaluate an intentionally invalid static reserve commitment",
    )
    args = parser.parse_args()
    request = build_manual_request(invalid_headroom=args.invalid_headroom)
    report = evaluate_fixed_fcr_bid(request)
    print("objective:", request.plan.objective.unavailable_reason)
    print("objective bound:", request.plan.objective_bound.unavailable_reason)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    expected = "validation_failed" if args.invalid_headroom else "settled"
    return 0 if report.status == expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
