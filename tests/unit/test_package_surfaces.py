"""Public surface of each library package root (consolidation A4a).

Replaces the per-package lazy-export tests. Package roots now use plain
imports, so these checks pin what the lazy tests actually protected:

- each root exports exactly its curated names, all defined inside the library;
- importing a root in a fresh interpreter loads no solver, ML, notebook,
  legacy, baseline, or validation code, and none of the credentialed
  ENTSO-E/RTE adapters.

Names that are not exported stay importable from their submodules.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

EXPECTED_EXPORTS = {
    "core": [
        "ControllerContext",
        "ControllerEvaluationResult",
        "ControllerInterface",
        "DispatchProposal",
    ],
    "market": [
        "AFRRActivationTrajectory",
        "ActivationImportRequest",
        "CanonicalInterval",
        "DerivedSimulationMapping",
        "MFRRActivationKind",
        "MFRRActivationSequence",
        "MarketArtifactValidationError",
        "MarketDataArtifact",
        "MarketTimeValidationError",
        "RegulationActivationTrace",
        "RestorationArtifactValidationError",
        "RestorationDirection",
        "RestorationMarketArtifact",
        "RestorationProduct",
        "build_afrr_trajectory_from_rte_requested_need",
        "build_derived_simulation_mapping",
        "build_local_delivery_day",
        "build_market_data_artifact",
        "build_mfrr_sequence_from_rte_sa_requested_volume",
        "build_restoration_market_artifact",
        "import_regulation_activation_trace",
        "load_market_data_artifact",
        "load_regulation_activation_trace",
        "load_restoration_market_artifact",
        "parse_iso8601_duration",
        "slice_regulation_activation_trace",
        "write_market_data_artifact",
        "write_regulation_activation_trace",
        "write_restoration_market_artifact",
    ],
    "simulator": [
        "ArbitrageScenario",
        "BatteryComponent",
        "BatteryLoadPVScenario",
        "DailyFCRBidEvaluationReport",
        "DemandFamilyEvaluationRequest",
        "DirectionalCapacitySchedule",
        "DispatchRequestSeries",
        "EnergyBaselineSchedule",
        "EvaluationMarketContext",
        "EvaluationPriceObservation",
        "FCRBidEvaluationRequest",
        "FCRCapacitySchedule",
        "FixedFCRBidPlan",
        "LoadComponent",
        "MultiRateTimeContract",
        "PVComponent",
        "PlanningExportRequest",
        "PriceSignal",
        "RestorationCapability",
        "RestorationEnergyBaselineSchedule",
        "StackedServiceReplayRequest",
        "TerminalSOCTarget",
        "TimeGrid",
        "WeatherComponent",
        "WeatherFamilyEvaluationRequest",
        "build_afrr_replay_request",
        "build_energy_baseline_schedule",
        "build_fcr_capacity_schedule",
        "build_fixed_fcr_bid_plan",
        "build_mfrr_replay_request",
        "evaluate_demand_family",
        "evaluate_fixed_fcr_bid",
        "evaluate_fixed_fcr_bid_segments",
        "evaluate_weather_family",
        "evaluate_with_controller",
        "export_planning_dataset",
        "generate_planning_study_dataset",
        "replay_afrr",
        "replay_mfrr",
        "replay_stacked_services",
        "settle_restoration_services",
        "settle_stacked_services",
    ],
    "control": [
        "AFRRBaselineMode",
        "MFRRBaselineMode",
        "PVSelfConsumptionConfig",
        "PVSelfConsumptionController",
        "PriceThresholdConfig",
        "PriceThresholdController",
        "RecoveryWindowActivationBudget",
        "RobustFCRBatteryParameters",
        "RobustFCRPriceInputs",
        "RobustFCRSolvePolicy",
        "RobustFCRSolveResult",
        "RobustFCRUncertaintyProfile",
        "RobustFCRValidationError",
        "RollingFCRDayInput",
        "RollingFCRStudyResult",
        "RollingFCRValidationError",
        "SocGuardrailConfig",
        "SocGuardrailController",
        "StackedHeuristicConfig",
        "TerminalStoredEnergyRule",
        "aggregate_rolling_fcr_records",
        "build_afrr_baseline",
        "build_afrr_baseline_config",
        "build_arbitrage_only_baseline",
        "build_mfrr_baseline",
        "build_mfrr_baseline_config",
        "build_regulation_only_baseline",
        "build_robust_fcr_bidding_problem",
        "build_robust_fcr_time_contract",
        "build_rolling_fcr_experiment_profile",
        "build_rolling_fcr_study_manifest",
        "build_stacked_heuristic_baseline",
        "compare_robust_fcr_bounds",
        "derive_non_intraday_horizon_budget",
        "load_rolling_fcr_study_result",
        "run_rolling_fcr_study",
        "solve_robust_fcr_bid",
    ],
}
# Unchanged by A4a; pinned here so any change is deliberate.
UNCHANGED_SURFACES = ("planning", "weather", "demand", "visualization")

# Union of the module roots the superseded per-package tests forbade.
FORBIDDEN_ROOTS = {
    "IPython", "aiohttp", "baselines", "boto3", "citylearn", "cupy", "docplex",
    "gurobipy", "highspy", "http", "httpx", "ipykernel", "julia", "juliacall",
    "jupyter", "keyring", "legacy", "matplotlib", "mlflow", "nbclient", "nbformat",
    "notebook", "oel_validation", "pandas", "pvlib", "pyomo", "requests", "socket",
    "spflow", "ssl", "submitit", "tensorboard", "torch", "torchrl", "wandb", "xml",
}
# Network-capable stdlib modules, checked by full name: urllib.parse (pure string parsing) is allowed; pathlib imports it on Python <= 3.12.
FORBIDDEN_MODULES = {"urllib.request", "urllib.response"}
CREDENTIALED_ADAPTERS = {
    "open_energy_lab.market.entsoe",
    "open_energy_lab.market.entsoe_restoration",
    "open_energy_lab.market.rte",
}
ALL_ROOTS = (*EXPECTED_EXPORTS, *UNCHANGED_SURFACES)


@pytest.mark.parametrize("package", list(EXPECTED_EXPORTS))
def test_root_exports_exactly_the_curated_names(package: str) -> None:
    module = importlib.import_module(f"open_energy_lab.{package}")
    assert sorted(module.__all__) == EXPECTED_EXPORTS[package]


@pytest.mark.parametrize("package", ALL_ROOTS)
def test_every_export_resolves_and_is_defined_in_the_library(package: str) -> None:
    module = importlib.import_module(f"open_energy_lab.{package}")
    assert module.__file__ is not None
    assert Path(module.__file__).parts[-3:] == ("open_energy_lab", package, "__init__.py")
    assert len(module.__all__) == len(set(module.__all__))
    for name in module.__all__:
        exported = getattr(module, name)
        owner = getattr(exported, "__module__", None)
        if owner is not None:
            assert owner.startswith(f"open_energy_lab.{package}."), (name, owner)


@pytest.mark.parametrize("package", ALL_ROOTS)
def test_root_import_loads_no_optional_research_or_adapter_code(package: str) -> None:
    source = textwrap.dedent(
        f"""
        import json
        import sys

        before = set(sys.modules)
        import open_energy_lab.{package}
        loaded = sorted(set(sys.modules) - before)
        print(json.dumps(loaded))
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", source], capture_output=True, text=True, check=True
    )
    loaded = set(json.loads(completed.stdout.strip().splitlines()[-1]))
    assert {name.split(".")[0] for name in loaded} & FORBIDDEN_ROOTS == set()
    assert loaded & CREDENTIALED_ADAPTERS == set()
    assert loaded & FORBIDDEN_MODULES == set()


def test_persisted_simulator_semantics_constants_are_unchanged() -> None:
    """Values the superseded simulator surface test pinned; they label persisted outputs."""

    from open_energy_lab.simulator.planning_study import (
        PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION,
    )
    from open_energy_lab.simulator.stochastic_demand import (
        SUPPORTED_SUMMARY_OUTPUT_FIELDS as DEMAND_SUMMARY_FIELDS,
    )
    from open_energy_lab.simulator.stochastic_weather import (
        SUPPORTED_SUMMARY_OUTPUT_FIELDS as WEATHER_SUMMARY_FIELDS,
    )

    assert PLANNING_STUDY_SIMULATION_SEMANTICS_VERSION == "grid-balanced-dispatch-v2"
    assert WEATHER_SUMMARY_FIELDS == (
        "pv_generation_kw",
        "net_grid_power_kw",
        "unmet_load_kw",
        "step_settlement",
    )
    assert DEMAND_SUMMARY_FIELDS == (
        "site_electric_load_kw",
        "local_cooling_electric_kw",
        "served_cooling_rt",
        "unserved_cooling_rt",
        "net_grid_power_kw",
        "step_settlement",
        "district_cooling_settlement",
    )
