"""Exhaustive reserve-product substitution gates across closed public APIs."""

from __future__ import annotations

from pathlib import Path

import pytest

from examples.restoration_services.generate_reference_results import (
    AFRR_SCENARIO_FILENAME,
    MFRR_SCENARIO_FILENAME,
    build_reference_case,
    load_reference_scenario,
)
from open_energy_lab.control import (
    AFRRBaselineMode,
    MFRRBaselineMode,
    build_afrr_baseline_config,
    build_mfrr_baseline_config,
)
from open_energy_lab.simulator.restoration_contracts import RestorationControlValidationError
from open_energy_lab.control.stacked_service import (
    RegulationOnlyBaselineConfig,
    StackedBaselineValidationError,
)
from open_energy_lab.simulator import (
    build_afrr_replay_request,
    build_mfrr_replay_request,
    replay_afrr,
    replay_mfrr,
    replay_stacked_services,
    settle_restoration_services,
    settle_stacked_services,
)
from open_energy_lab.simulator.fcr_settlement import FCRSettlementValidationError
from open_energy_lab.simulator.restoration_service import RestorationReplayValidationError
from open_energy_lab.simulator.restoration_settlement import RestorationSettlementValidationError
from open_energy_lab.simulator.stacked_service import StackedServiceValidationError
from tests.unit.control.test_stacked_service import _regulation_config
from tests.unit.simulator.test_stacked_service import (
    _activation_trace,
    _fcr_schedule,
    _replay_request,
)


FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "restoration"


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


def _restoration_replay_kwargs(request) -> dict[str, object]:
    return {
        "semantics_version": request.semantics_version,
        "battery": request.battery,
        "initial_state": request.initial_state,
        "capability": request.capability,
        "commitments": request.commitments,
        "baseline": request.baseline,
        "integration_grid": request.integration_grid,
        "tolerance": request.tolerance,
    }


@pytest.mark.parametrize("wrong_product", ("AFRR", "MFRR"))
def test_fcr_replay_rejects_every_restoration_activation_before_dispatch(
    product_cases,
    wrong_product: str,
) -> None:
    afrr_scenario, _, mfrr_scenario, _ = product_cases
    wrong_activation = (
        afrr_scenario.activation if wrong_product == "AFRR" else mfrr_scenario.activation
    )

    with pytest.raises(StackedServiceValidationError, match="activation_trace|wrong type"):
        _replay_request(activation_trace=wrong_activation)


@pytest.mark.parametrize("wrong_product", ("AFRR", "MFRR"))
def test_fcr_replay_rejects_every_restoration_commitment_before_dispatch(
    product_cases,
    wrong_product: str,
) -> None:
    afrr_scenario, _, mfrr_scenario, _ = product_cases
    wrong_commitment = (
        afrr_scenario.commitments
        if wrong_product == "AFRR"
        else mfrr_scenario.commitments
    )

    with pytest.raises(StackedServiceValidationError, match="fcr_schedule|wrong type"):
        _replay_request(fcr_schedule=wrong_commitment)


@pytest.mark.parametrize("wrong_activation", ("FCR", "MFRR"))
def test_afrr_builder_rejects_every_non_afrr_activation_before_dispatch(
    product_cases,
    wrong_activation: str,
) -> None:
    _, afrr_case, mfrr_scenario, _ = product_cases
    request = afrr_case.replay.request
    activation = (
        _activation_trace()
        if wrong_activation == "FCR"
        else mfrr_scenario.activation
    )
    state_before = request.initial_state

    with pytest.raises(
        RestorationReplayValidationError,
        match="exactly an AFRRActivationTrajectory",
    ):
        build_afrr_replay_request(
            request_id="wrong-afrr-activation",
            activation_trajectory=activation,
            **_restoration_replay_kwargs(request),
        )
    assert request.initial_state == state_before


@pytest.mark.parametrize("wrong_activation", ("FCR", "AFRR"))
def test_mfrr_builder_rejects_every_non_mfrr_activation_before_dispatch(
    product_cases,
    wrong_activation: str,
) -> None:
    afrr_scenario, _, _, mfrr_case = product_cases
    request = mfrr_case.replay.request
    activation = (
        _activation_trace()
        if wrong_activation == "FCR"
        else afrr_scenario.activation
    )
    state_before = request.initial_state

    with pytest.raises(
        RestorationReplayValidationError,
        match="exactly an MFRRActivationSequence",
    ):
        build_mfrr_replay_request(
            request_id="wrong-mfrr-activation",
            activation_sequence=activation,
            **_restoration_replay_kwargs(request),
        )
    assert request.initial_state == state_before


@pytest.mark.parametrize("wrong_commitment", ("FCR", "MFRR"))
def test_afrr_builder_rejects_every_non_afrr_commitment_before_dispatch(
    product_cases,
    wrong_commitment: str,
) -> None:
    _, afrr_case, mfrr_scenario, _ = product_cases
    request = afrr_case.replay.request
    commitment = (
        _fcr_schedule()
        if wrong_commitment == "FCR"
        else mfrr_scenario.commitments
    )
    kwargs = _restoration_replay_kwargs(request)
    kwargs["commitments"] = commitment

    with pytest.raises(
        RestorationReplayValidationError,
        match="commitments|exact replay product|DirectionalCapacitySchedule",
    ):
        build_afrr_replay_request(
            request_id="wrong-afrr-commitment",
            activation_trajectory=request.activation_trajectory,
            **kwargs,
        )


@pytest.mark.parametrize("wrong_commitment", ("FCR", "AFRR"))
def test_mfrr_builder_rejects_every_non_mfrr_commitment_before_dispatch(
    product_cases,
    wrong_commitment: str,
) -> None:
    afrr_scenario, _, _, mfrr_case = product_cases
    request = mfrr_case.replay.request
    commitment = (
        _fcr_schedule()
        if wrong_commitment == "FCR"
        else afrr_scenario.commitments
    )
    kwargs = _restoration_replay_kwargs(request)
    kwargs["commitments"] = commitment

    with pytest.raises(
        RestorationReplayValidationError,
        match="commitments|exact replay product|DirectionalCapacitySchedule",
    ):
        build_mfrr_replay_request(
            request_id="wrong-mfrr-commitment",
            activation_sequence=request.activation_sequence,
            **kwargs,
        )


def test_product_specific_control_configs_reject_fcr_and_the_other_restoration_product(
    product_cases,
) -> None:
    afrr_scenario, _, mfrr_scenario, _ = product_cases
    common_afrr = {
        "config_id": "wrong-afrr-control",
        "semantics_version": "product-separation-v1",
        "period": afrr_scenario.commitments.period,
        "resolution": "PT15M",
        "battery": afrr_scenario.battery,
        "capability": afrr_scenario.capability,
        "mode": AFRRBaselineMode.ZERO,
        "fixed_power_kw": None,
    }
    common_mfrr = {
        "config_id": "wrong-mfrr-control",
        "semantics_version": "product-separation-v1",
        "period": mfrr_scenario.commitments.period,
        "resolution": "PT15M",
        "battery": mfrr_scenario.battery,
        "capability": mfrr_scenario.capability,
        "mode": MFRRBaselineMode.ZERO,
        "fixed_power_kw": None,
        "declared_service_duration_seconds": 900.0,
    }

    for commitment in (_fcr_schedule(), mfrr_scenario.commitments):
        with pytest.raises(RestorationControlValidationError, match="commitments|AFRR"):
            build_afrr_baseline_config(commitments=commitment, **common_afrr)
    for commitment in (_fcr_schedule(), afrr_scenario.commitments):
        with pytest.raises(RestorationControlValidationError, match="commitments|MFRR"):
            build_mfrr_baseline_config(commitments=commitment, **common_mfrr)

    for commitment in (afrr_scenario.commitments, mfrr_scenario.commitments):
        with pytest.raises(
            StackedBaselineValidationError,
            match="FCRCapacitySchedule|fcr_schedule",
        ):
            RegulationOnlyBaselineConfig(
                schedule_id="wrong-fcr-control",
                semantics_version="product-separation-v1",
                fcr_schedule=commitment,
            )


def test_each_replay_entry_point_rejects_both_other_product_requests(
    product_cases,
) -> None:
    _, afrr_case, _, mfrr_case = product_cases
    fcr_request = _replay_request()

    with pytest.raises(RestorationReplayValidationError, match="AFRRReplayRequest"):
        replay_afrr(mfrr_case.replay.request)
    with pytest.raises(RestorationReplayValidationError, match="AFRRReplayRequest"):
        replay_afrr(fcr_request)
    with pytest.raises(RestorationReplayValidationError, match="MFRRReplayRequest"):
        replay_mfrr(afrr_case.replay.request)
    with pytest.raises(RestorationReplayValidationError, match="MFRRReplayRequest"):
        replay_mfrr(fcr_request)
    with pytest.raises(StackedServiceValidationError, match="StackedServiceReplayRequest"):
        replay_stacked_services(afrr_case.replay.request)
    with pytest.raises(StackedServiceValidationError, match="StackedServiceReplayRequest"):
        replay_stacked_services(mfrr_case.replay.request)


def test_fcr_and_restoration_settlement_reject_cross_product_results_and_samples(
    product_cases,
) -> None:
    _, afrr_case, _, mfrr_case = product_cases
    fcr_request = _replay_request()
    fcr_result = replay_stacked_services(fcr_request)

    with pytest.raises(RestorationSettlementValidationError, match="AFRRReplayResult|MFRRReplayResult"):
        settle_restoration_services(
            settlement_id="wrong-restoration-result",
            semantics_version="product-separation-v1",
            replay_result=fcr_result,
            day_ahead_prices=(),
            capacity_prices=(),
            activation_prices=(),
            penalty_rule=None,
            degradation_rule=None,
            require_day_ahead_prices=False,
            require_capacity_prices=False,
            require_activation_prices=False,
        )

    for restoration_case in (afrr_case, mfrr_case):
        with pytest.raises(FCRSettlementValidationError, match="StackedServiceReplayRequest"):
            settle_stacked_services(
                restoration_case.replay.request,
                restoration_case.replay.samples,
            )
        with pytest.raises(FCRSettlementValidationError, match="ReplaySample"):
            wrong_samples = (restoration_case.replay.samples[0],) * len(
                fcr_request.time_contract.index.activation_intervals
            )
            settle_stacked_services(fcr_request, wrong_samples)


def test_closed_fcr_control_fixture_still_constructs_only_with_fcr_commitments() -> None:
    config = _regulation_config()
    assert type(config.fcr_schedule) is type(_fcr_schedule())
