"""Feature 012 rejects every aFRR/mFRR substitution at its FCR boundaries."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from examples.restoration_services.generate_reference_results import (
    AFRR_SCENARIO_FILENAME,
    MFRR_SCENARIO_FILENAME,
    build_reference_case,
    load_reference_scenario,
)
from open_energy_lab.control.fcr_bid_plan import FCRBidPlanValidationError
from oel_validation.reference_fcr import (
    ReferenceFCRValidationError,
    build_reference_market_context,
    load_golden_reference_fixture,
)
from open_energy_lab.simulator.fcr_bid_evaluation import (
    FCRBidEvaluationValidationError,
    evaluate_fixed_fcr_bid,
    replay_invalid_fcr_bid_diagnostic,
)
from oel_validation.fcr_bid_evaluation import compare_reference_evaluation
from open_energy_lab.simulator.fcr_settlement import (
    FCRSettlementValidationError,
    settle_reference_fcr_bid,
)
from tests.integration.simulator.fcr_bid_evaluation_fixture_utils import (
    build_test_evaluation_case,
)


FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "restoration"
REFERENCE_FIXTURE = Path(
    "tests/fixtures/fcr_bid_evaluation/"
    "robust_storage_bidding_2023-06-18_aggregate_v1.json"
)


@pytest.fixture(scope="module")
def product_cases():
    afrr_scenario = load_reference_scenario(
        FIXTURE_DIR / AFRR_SCENARIO_FILENAME,
        fixture_directory=FIXTURE_DIR,
    )
    mfrr_scenario = load_reference_scenario(
        FIXTURE_DIR / MFRR_SCENARIO_FILENAME,
        fixture_directory=FIXTURE_DIR,
    )
    return (
        afrr_scenario,
        build_reference_case(afrr_scenario),
        mfrr_scenario,
        build_reference_case(mfrr_scenario),
    )


@pytest.mark.parametrize("product_index", (0, 2))
def test_fixed_plan_rejects_restoration_commitment_and_baseline_types(
    product_cases,
    product_index: int,
) -> None:
    scenario = product_cases[product_index]
    valid = build_test_evaluation_case()
    restoration_baseline = product_cases[product_index + 1].replay.request.baseline

    with pytest.raises(FCRBidPlanValidationError, match="FCRCapacitySchedule"):
        replace(valid.plan, fcr_schedule=scenario.commitments)
    with pytest.raises(FCRBidPlanValidationError, match="EnergyBaselineSchedule"):
        replace(valid.plan, energy_schedule=restoration_baseline)


def test_reference_market_context_rejects_afrr_and_mfrr_commitments(
    product_cases,
) -> None:
    fixture = load_golden_reference_fixture(REFERENCE_FIXTURE)
    valid = build_test_evaluation_case()

    for scenario in (product_cases[0], product_cases[2]):
        with pytest.raises(
            ReferenceFCRValidationError,
            match="fcr_schedule.*wrong product type",
        ):
            build_reference_market_context(
                fixture,
                energy_schedule=valid.plan.energy_schedule,
                fcr_schedule=scenario.commitments,
            )


def test_evaluation_request_rejects_restoration_trajectories_sequences_and_events(
    product_cases,
) -> None:
    afrr_scenario, _, mfrr_scenario, _ = product_cases
    valid = build_test_evaluation_case(
        settlement_profile="robust-storage-bidding-reference-settlement-v1"
    )
    wrong_activation_inputs = (
        afrr_scenario.activation,
        mfrr_scenario.activation,
        mfrr_scenario.activation.events[0],
    )

    for activation in wrong_activation_inputs:
        with pytest.raises(
            FCRBidEvaluationValidationError,
            match="RegulationActivationTrace|activation",
        ):
            replace(valid.request, activation_trace=activation)


def test_evaluation_request_rejects_restoration_market_artifacts(product_cases) -> None:
    valid = build_test_evaluation_case()

    for scenario in (product_cases[0], product_cases[2]):
        with pytest.raises(
            FCRBidEvaluationValidationError,
            match="EvaluationMarketContext|market context",
        ):
            replace(valid.request, market_context=scenario.market)


def test_evaluator_and_diagnostic_reject_restoration_replay_requests_and_results(
    product_cases,
) -> None:
    _, afrr_case, _, mfrr_case = product_cases

    for request in (afrr_case.replay.request, mfrr_case.replay.request):
        with pytest.raises(FCRBidEvaluationValidationError, match="FCRBidEvaluationRequest"):
            evaluate_fixed_fcr_bid(request)
        with pytest.raises(FCRBidEvaluationValidationError, match="FCRBidEvaluationRequest"):
            replay_invalid_fcr_bid_diagnostic(request)

    fixture = load_golden_reference_fixture(REFERENCE_FIXTURE)
    valid = build_test_evaluation_case(comparison_fixture=fixture)
    for result in (afrr_case.replay, mfrr_case.replay):
        with pytest.raises(FCRBidEvaluationValidationError, match="settled evaluation report"):
            compare_reference_evaluation(valid.request, result)


def test_reference_settlement_rejects_restoration_requests_samples_and_settlements(
    product_cases,
) -> None:
    _, afrr_case, _, mfrr_case = product_cases
    valid = build_test_evaluation_case(
        settlement_profile="robust-storage-bidding-reference-settlement-v1"
    )
    sample_count = len(valid.request.time_contract.index.activation_intervals)

    for case in (afrr_case, mfrr_case):
        with pytest.raises(FCRSettlementValidationError, match="FCRBidEvaluationRequest"):
            settle_reference_fcr_bid(case.replay.request, case.replay.samples)
        wrong_samples = (case.replay.samples[0],) * sample_count
        with pytest.raises(FCRSettlementValidationError, match="non-ReplaySample"):
            settle_reference_fcr_bid(valid.request, wrong_samples)
        with pytest.raises(FCRSettlementValidationError, match="replay-sample sequence"):
            settle_reference_fcr_bid(valid.request, case.settlement)
