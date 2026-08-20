from __future__ import annotations

from dataclasses import replace

import pytest

from open_energy_lab.planning.study import (
    AdequacyEventDefinition,
    BatteryDesignOption,
    ControllerStudyConfig,
    GridAvailabilityPolicy,
    PlanningStudyRequest,
    SolarDesignOption,
    build_configuration_grid,
    derive_adequacy_metrics,
    generate_grid_availability_trace,
)


def _request() -> PlanningStudyRequest:
    return PlanningStudyRequest(
        study_id="unit-study",
        battery_options=(
            BatteryDesignOption("b-small", 5.0, 2.0, 2.0, 5000.0),
            BatteryDesignOption("b-large", 10.0, 4.0, 4.0, 9000.0),
        ),
        solar_options=(
            SolarDesignOption("s-small", 3.0, 3000.0),
            SolarDesignOption("s-large", 6.0, 5500.0),
        ),
        samples_per_configuration=100,
        horizon_steps=24,
        batch_size=10,
        random_seed=13,
        adequacy_event=AdequacyEventDefinition("shortfall_ratio", 0.05),
        grid_availability=GridAvailabilityPolicy(
            mode="markov",
            initial_grid_available=True,
            outage_start_probability=0.1,
            recovery_probability=0.4,
        ),
        controller=ControllerStudyConfig("PVSelfConsumptionController"),
    )


def test_configuration_grid_is_battery_major_and_has_explicit_costs() -> None:
    configurations = build_configuration_grid(_request())

    assert [item.configuration_id for item in configurations] == [
        "b-small__s-small",
        "b-small__s-large",
        "b-large__s-small",
        "b-large__s-large",
    ]
    assert configurations[-1].installed_cost == pytest.approx(14500.0)


def test_equipment_options_reject_invalid_physical_values_and_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="capacity_kwh"):
        BatteryDesignOption("bad", 0.0, 1.0, 1.0, 1.0)

    request = _request()
    with pytest.raises(ValueError, match="battery option ids must be unique"):
        replace(
            request,
            battery_options=(request.battery_options[0], request.battery_options[0]),
        )


def test_adequacy_metrics_and_each_event_kind_use_timestep_energy() -> None:
    metrics = derive_adequacy_metrics(
        site_electric_load_kw=(4.0, 4.0, 2.0, 0.0),
        unmet_load_kw=(0.0, 2.0, 1.0, 0.0),
        timestep_hours=0.5,
        numeric_tolerance=1e-9,
    )

    assert metrics.shortfall_ratio == pytest.approx(0.3)
    assert metrics.unmet_energy_kwh == pytest.approx(1.5)
    assert metrics.unmet_timestep_fraction == pytest.approx(0.5)
    assert AdequacyEventDefinition("shortfall_ratio", 0.2).evaluate(metrics) == 1
    assert AdequacyEventDefinition("unmet_energy_kwh", 2.0).evaluate(metrics) == 0
    assert AdequacyEventDefinition("unmet_timestep_fraction", 0.5).evaluate(metrics) == 0


def test_markov_grid_trace_is_absolute_sample_deterministic() -> None:
    policy = _request().grid_availability

    first = generate_grid_availability_trace(
        policy,
        study_seed=13,
        sample_id=25,
        horizon_steps=24,
    )
    repeated = generate_grid_availability_trace(
        policy,
        study_seed=13,
        sample_id=25,
        horizon_steps=24,
    )
    other = generate_grid_availability_trace(
        policy,
        study_seed=13,
        sample_id=26,
        horizon_steps=24,
    )

    assert first == repeated
    assert first != other


def test_islanded_and_supplied_grid_traces_are_explicit() -> None:
    assert generate_grid_availability_trace(
        GridAvailabilityPolicy(mode="islanded"),
        study_seed=13,
        sample_id=0,
        horizon_steps=3,
    ) == (False, False, False)

    supplied = GridAvailabilityPolicy(
        mode="supplied",
        supplied_traces={7: (True, False, True)},
    )
    assert generate_grid_availability_trace(
        supplied,
        study_seed=13,
        sample_id=7,
        horizon_steps=3,
    ) == (True, False, True)


def test_study_request_exposes_absolute_sample_batches_without_row_limit() -> None:
    request = _request()

    assert request.sample_batches() == tuple(
        tuple(range(start, start + 10)) for start in range(0, 100, 10)
    )
    assert request.expected_row_count == 400


def test_study_request_persists_hourly_local_start_step() -> None:
    request = replace(_request(), local_start_step=7)

    assert request.local_start_step == 7
    assert request.to_dict()["local_start_step"] == 7
    assert request.request_fingerprint != _request().request_fingerprint


@pytest.mark.parametrize("value", [-1, 24])
def test_study_request_rejects_local_start_outside_day(value: int) -> None:
    with pytest.raises(ValueError, match="local_start_step"):
        replace(_request(), local_start_step=value)
