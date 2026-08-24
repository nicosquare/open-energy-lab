"""Frozen public-contract snapshots for the closed Feature 010 FCR slice."""

from __future__ import annotations

from dataclasses import fields
import importlib
import inspect

import open_energy_lab.control as control
import open_energy_lab.market as market
import open_energy_lab.simulator as simulator
from tests.unit.control.test_stacked_service import _stacked_config
from tests.unit.market.test_artifact import _build_artifact
from tests.unit.simulator.test_stacked_service import (
    _activation_trace,
    _battery,
    _energy_schedule,
    _fcr_schedule,
    _replay_request,
)


FEATURE_010_PUBLIC_OWNERS = {
    market.CanonicalInterval: "open_energy_lab.market.time",
    market.MarketDataArtifact: "open_energy_lab.market.artifact",
    market.RegulationActivationTrace: "open_energy_lab.market.activation",
    market.build_market_data_artifact: "open_energy_lab.market.artifact",
    market.import_regulation_activation_trace: "open_energy_lab.market.activation",
    control.ArbitrageOnlyBaselineConfig: "open_energy_lab.control.stacked_service",
    control.RegulationOnlyBaselineConfig: "open_energy_lab.control.stacked_service",
    control.StackedHeuristicConfig: "open_energy_lab.control.stacked_service",
    control.BaselineScheduleBundle: "open_energy_lab.control.stacked_service",
    control.build_stacked_heuristic_baseline: "open_energy_lab.control.stacked_service",
    simulator.EnergyBaselineSchedule: "open_energy_lab.simulator.stacked_service",
    simulator.FCRCapacitySchedule: "open_energy_lab.simulator.stacked_service",
    simulator.MultiRateTimeContract: "open_energy_lab.simulator.stacked_service",
    simulator.TerminalSOCTarget: "open_energy_lab.simulator.stacked_service",
    simulator.StackedServiceReplayRequest: "open_energy_lab.simulator.stacked_service",
    simulator.StackedServiceReplayResult: "open_energy_lab.simulator.stacked_service",
    simulator.SettlementBreakdown: "open_energy_lab.simulator.fcr_settlement",
    simulator.build_energy_baseline_schedule: "open_energy_lab.simulator.stacked_service",
    simulator.build_fcr_capacity_schedule: "open_energy_lab.simulator.stacked_service",
    simulator.replay_stacked_services: "open_energy_lab.simulator.stacked_service",
    simulator.settle_stacked_services: "open_energy_lab.simulator.fcr_settlement",
}


FEATURE_010_CONSTRUCTOR_FIELDS = {
    market.CanonicalInterval: (
        "start_utc",
        "end_utc",
        "local_start",
        "local_end",
        "start_utc_offset_seconds",
        "end_utc_offset_seconds",
        "start_fold",
        "end_fold",
        "market_timezone",
        "interval_convention",
    ),
    market.MarketDataArtifact: (
        "schema_version",
        "artifact_id",
        "profile_id",
        "normalization_version",
        "created_at_utc",
        "requested_period",
        "actual_covered_period",
        "area",
        "series",
        "query_windows",
        "raw_responses",
        "source_documents",
        "content_fingerprint",
        "artifact_fingerprint",
        "predecessor_artifact_fingerprint",
        "retention_and_license",
    ),
    market.RegulationActivationTrace: (
        "schema_version",
        "trace_id",
        "created_at_utc",
        "covered_period",
        "resolution",
        "value_semantics",
        "sign_semantics",
        "source",
        "normalization",
        "samples",
        "content_fingerprint",
        "artifact_fingerprint",
        "retention_and_license",
    ),
    control.ArbitrageOnlyBaselineConfig: (
        "schedule_id",
        "semantics_version",
        "price_threshold_config",
    ),
    control.RegulationOnlyBaselineConfig: (
        "schedule_id",
        "semantics_version",
        "fcr_schedule",
    ),
    control.StackedHeuristicConfig: (
        "schedule_id",
        "semantics_version",
        "price_threshold_config",
        "fcr_schedule",
    ),
    control.BaselineScheduleBundle: (
        "builder_kind",
        "battery",
        "energy_schedule",
        "fcr_schedule",
        "initial_stored_energy_kwh",
        "recovery_dispatch_kw",
        "configuration_fingerprint",
    ),
    simulator.EnergyBaselineSchedule: (
        "schedule_id",
        "semantics_version",
        "covered_period",
        "intervals",
        "schedule_fingerprint",
    ),
    simulator.FCRCapacitySchedule: (
        "schedule_id",
        "semantics_version",
        "product_identity",
        "covered_period",
        "intervals",
        "schedule_fingerprint",
    ),
    simulator.MultiRateTimeContract: (
        "start_utc",
        "end_utc",
        "activation_resolution",
        "state_checkpoint_resolution",
        "energy_resolution",
        "fcr_resolution",
        "market_timezone",
        "interval_convention",
        "index",
    ),
    simulator.TerminalSOCTarget: (
        "target_kind",
        "target_value",
        "tolerance",
    ),
    simulator.StackedServiceReplayRequest: (
        "market_artifact",
        "activation_trace",
        "battery",
        "energy_schedule",
        "fcr_schedule",
        "time_contract",
        "penalty_rule",
        "terminal_soc_target",
        "numeric_tolerance",
        "simulation_semantics_version",
        "commitment_validation_mode",
        "commitment_validation_errors",
    ),
    simulator.StackedServiceReplayResult: (
        "simulation_semantics_version",
        "validation_status",
        "input_fingerprints",
        "samples",
        "state_checkpoints",
        "checkpoint_summaries",
        "energy_summaries",
        "fcr_summaries",
        "saturation_events",
        "tracking_summary",
        "throughput_kwh",
        "settlement",
        "terminal_soc_report",
        "trace_fingerprint",
        "result_fingerprint",
    ),
    simulator.SettlementBreakdown: (
        "energy_intervals",
        "fcr_blocks",
        "day_ahead_energy_revenue_eur",
        "fcr_capacity_revenue_eur",
        "non_delivery_energy_kwh",
        "penalty_rule_id",
        "penalty_eur",
        "charge_energy_kwh",
        "discharge_energy_kwh",
        "throughput_kwh",
        "activation_energy_settlement_status",
        "imbalance_settlement_status",
        "degradation_cost_status",
        "total_profit_eur",
    ),
}


FEATURE_010_SERIALIZATION_KEYS = {
    market.MarketDataArtifact: FEATURE_010_CONSTRUCTOR_FIELDS[market.MarketDataArtifact],
    market.RegulationActivationTrace: FEATURE_010_CONSTRUCTOR_FIELDS[
        market.RegulationActivationTrace
    ],
    simulator.EnergyBaselineSchedule: FEATURE_010_CONSTRUCTOR_FIELDS[
        simulator.EnergyBaselineSchedule
    ],
    simulator.FCRCapacitySchedule: FEATURE_010_CONSTRUCTOR_FIELDS[
        simulator.FCRCapacitySchedule
    ],
    simulator.SettlementBreakdown: FEATURE_010_CONSTRUCTOR_FIELDS[
        simulator.SettlementBreakdown
    ],
}


def test_feature_010_public_symbols_keep_exact_names_types_and_module_owners() -> None:
    for exported, owner_name in FEATURE_010_PUBLIC_OWNERS.items():
        owner = importlib.import_module(owner_name)
        name = exported.__name__
        package = (
            market
            if owner_name.startswith("open_energy_lab.market")
            else control
            if owner_name.startswith("open_energy_lab.control")
            else simulator
        )
        assert name in package.__all__
        assert getattr(package, name) is exported
        assert getattr(owner, name) is exported
        assert exported.__module__ == owner_name


def test_feature_010_dataclass_constructor_and_stored_field_snapshots_are_exact() -> None:
    for contract, expected_fields in FEATURE_010_CONSTRUCTOR_FIELDS.items():
        actual_fields = tuple(field.name for field in fields(contract))
        assert actual_fields == expected_fields

        constructor_fields = tuple(inspect.signature(contract).parameters)
        stored_only = {
            simulator.MultiRateTimeContract: ("index",),
            simulator.StackedServiceReplayRequest: (
                "commitment_validation_errors",
            ),
        }.get(contract, ())
        assert constructor_fields == tuple(
            name for name in expected_fields if name not in stored_only
        )

    canonical_signature = inspect.signature(market.CanonicalInterval)
    assert canonical_signature.parameters["market_timezone"].default == "Europe/Paris"
    assert canonical_signature.parameters["interval_convention"].default == (
        "start-inclusive/end-exclusive"
    )
    replay_signature = inspect.signature(simulator.StackedServiceReplayRequest)
    assert replay_signature.parameters["commitment_validation_mode"].default == "strict"


def test_feature_010_builders_return_exact_closed_types_and_serialization_shapes() -> None:
    artifact = _build_artifact()
    activation = _activation_trace()
    energy = _energy_schedule()
    fcr = _fcr_schedule()
    baseline = control.build_stacked_heuristic_baseline(
        _stacked_config(),
        market_artifact=artifact,
        battery=_battery(max_charge_kw=10.0, max_discharge_kw=10.0),
    )
    request = _replay_request(
        market_artifact=artifact,
        activation_trace=activation,
        energy_schedule=energy,
        fcr_schedule=fcr,
    )
    replay = simulator.replay_stacked_services(request)

    exact_types = (
        (artifact, market.MarketDataArtifact),
        (activation, market.RegulationActivationTrace),
        (energy, simulator.EnergyBaselineSchedule),
        (fcr, simulator.FCRCapacitySchedule),
        (baseline, control.BaselineScheduleBundle),
        (request, simulator.StackedServiceReplayRequest),
        (replay, simulator.StackedServiceReplayResult),
        (replay.settlement, simulator.SettlementBreakdown),
    )
    for value, expected_type in exact_types:
        assert type(value) is expected_type

    serializable = (artifact, activation, energy, fcr, replay.settlement)
    for value in serializable:
        assert tuple(value.to_dict()) == FEATURE_010_SERIALIZATION_KEYS[type(value)]

    assert not hasattr(baseline, "to_dict")
    assert not hasattr(request, "to_dict")
    assert not hasattr(replay, "to_dict")
