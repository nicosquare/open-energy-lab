"""Run the explicitly selected 2023-06-18 aggregate reference comparison."""

from __future__ import annotations

import argparse
from datetime import timedelta
import hashlib
import json
from pathlib import Path

from open_energy_lab.simulator.fcr_bid_plan import (
    BidPlanProducer,
    OptimizationMetric,
    build_fixed_fcr_bid_plan,
)
from oel_validation.reference_schedule_mapping import map_reference_decisions_to_schedules
from oel_validation.reference_fcr import (
    GoldenReferenceFixture,
    build_reference_market_context,
    load_golden_reference_fixture,
    load_reference_activation_trace,
)
from open_energy_lab.core.serialization import fingerprint
from open_energy_lab.market.activation import RegulationActivationTrace
from open_energy_lab.simulator import (
    BatteryComponent,
    FCRBidEvaluationRequest,
    MultiRateTimeContract,
    evaluate_fixed_fcr_bid,
)
from oel_validation.fcr_bid_evaluation import compare_reference_evaluation


DEFAULT_FIXTURE = Path(
    "tests/fixtures/fcr_bid_evaluation/"
    "robust_storage_bidding_2023-06-18_aggregate_v1.json"
)


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_reference_request(
    *,
    fixture_path: Path,
    activation_path: Path,
) -> FCRBidEvaluationRequest:
    fixture = load_golden_reference_fixture(fixture_path)
    activation_trace = load_reference_activation_trace(
        activation_path,
        descriptor=fixture.external_activation,
    )
    return assemble_reference_request(
        fixture=fixture,
        activation_trace=activation_trace,
    )


def assemble_reference_request(
    *,
    fixture: GoldenReferenceFixture,
    activation_trace: RegulationActivationTrace,
) -> FCRBidEvaluationRequest:
    """Assemble a request from already validated fixture and activation evidence."""

    mapped = map_reference_decisions_to_schedules(fixture)
    market_context = build_reference_market_context(
        fixture,
        energy_schedule=mapped.energy_schedule,
        fcr_schedule=mapped.fcr_schedule,
    )
    configuration = fixture.reference_configuration
    battery = BatteryComponent(
        name="robust-storage-bidding-reference-battery",
        capacity_kwh=float(configuration["capacity_kwh"]),
        max_charge_kw=float(configuration["max_charge_kw"]),
        max_discharge_kw=float(configuration["max_discharge_kw"]),
        charge_efficiency=float(configuration["charge_efficiency"]),
        discharge_efficiency=float(configuration["discharge_efficiency"]),
        initial_soc=(
            float(configuration["initial_stored_energy_kwh"])
            / float(configuration["capacity_kwh"])
        ),
        min_soc=(
            float(configuration["minimum_stored_energy_kwh"])
            / float(configuration["capacity_kwh"])
        ),
        max_soc=(
            float(configuration["maximum_stored_energy_kwh"])
            / float(configuration["capacity_kwh"])
        ),
    )
    period = fixture.mapping.target_period
    time_contract = MultiRateTimeContract(
        start_utc=period.start_utc,
        end_utc=period.end_utc,
        activation_resolution="PT10S",
        state_checkpoint_resolution="PT15M",
        energy_resolution="PT1H",
        fcr_resolution="PT4H",
        market_timezone="Europe/Paris",
        interval_convention="start-inclusive/end-exclusive",
    )
    expected_by_id = {item.field_id: item for item in fixture.expected_fields}
    objective = expected_by_id["plan.objective"]
    objective_bound = expected_by_id["plan.objective_bound"]
    producer_configuration = {
        "reference_commit": fixture.reference_provenance["reference_commit"],
        "model_type": configuration["model_type"],
        "energy_payment": configuration["energy_payment"],
        "intraday_trading": configuration["intraday_trading"],
    }
    plan = build_fixed_fcr_bid_plan(
        plan_id=f"{fixture.fixture_id}-fixed-plan",
        producer=BidPlanProducer(
            producer_id="robust-storage-bidding-pinned-result",
            producer_kind="robust",
            producer_version=str(fixture.reference_provenance["reference_commit"]),
            configuration_fingerprint=_fingerprint(producer_configuration),
            configuration_unavailable_reason=None,
        ),
        information_cutoff_utc=period.start_utc - timedelta(hours=24),
        energy_schedule=mapped.energy_schedule,
        fcr_schedule=mapped.fcr_schedule,
        producer_input_fingerprints={
            "model_configuration": _fingerprint(producer_configuration),
            "market_prices": _fingerprint(
                {
                    "p0": fixture.p0_eur_per_kwh,
                    "pr": fixture.pr_eur_per_kw_block,
                }
            ),
        },
        solve_status="optimal",
        objective=OptimizationMetric(
            availability="available",
            value=float(objective.expected_value),
            unit=str(objective.unit),
            unavailable_reason=None,
            meaning="optimization_objective",
        ),
        objective_bound=OptimizationMetric(
            availability="available",
            value=float(objective_bound.expected_value),
            unit=str(objective_bound.unit),
            unavailable_reason=None,
            meaning="optimization_bound",
        ),
    )
    return FCRBidEvaluationRequest(
        evaluation_id=f"{fixture.fixture_id}-evaluation",
        plan=plan,
        market_context=market_context,
        activation_trace=activation_trace,
        battery=battery,
        time_contract=time_contract,
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
        penalty_rule=None,
        terminal_soc_target=None,
        comparison_fixture=fixture,
        numeric_tolerance=1e-6,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the pinned fixed plan using a caller-installed regulation CSV"
        )
    )
    parser.add_argument(
        "--activation-path",
        type=Path,
        required=True,
        help="explicit path to the digest-matched regulation_signal.csv",
    )
    parser.add_argument(
        "--fixture-path",
        type=Path,
        default=DEFAULT_FIXTURE,
        help="normalized Golden Reference Fixture",
    )
    args = parser.parse_args()

    request = build_reference_request(
        fixture_path=args.fixture_path,
        activation_path=args.activation_path,
    )
    report = evaluate_fixed_fcr_bid(request)
    if report.status != "settled":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 2
    comparison = compare_reference_evaluation(request, report)
    output = {
        "status": report.status,
        "overall_comparison_status": comparison.overall_status,
        "mapping": {
            "energy_interval_count": len(request.energy_schedule.intervals),
            "fcr_interval_count": len(request.fcr_schedule.intervals),
            "checkpoint_interval_count": len(
                request.time_contract.index.checkpoint_intervals
            ),
            "activation_interval_count": len(request.activation_trace.samples),
            "reference_sign": "positive is discharge",
            "library_sign": "positive is charge",
        },
        "lineage": {
            "fixture_fingerprint": request.comparison_fixture.fixture_fingerprint,
            "plan_fingerprint": request.plan.plan_fingerprint,
            "activation_fingerprint": request.activation_trace.artifact_fingerprint,
            "trace_fingerprint": fingerprint(report.to_dict()["physical_trace"]),
            "settlement_fingerprint": fingerprint(report.to_dict()["settlement"]),
            "comparison_fingerprint": comparison.comparison_fingerprint,
            "result_fingerprint": fingerprint(report.to_dict()),
        },
        "physical_metrics": report.to_dict()["physical_metrics"],
        "settlement": report.to_dict()["settlement"],
        "comparison": comparison.to_dict(),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 2 if comparison.overall_status == "mismatch" else 0


if __name__ == "__main__":
    raise SystemExit(main())
