import importlib
import sys
from pathlib import Path


OPTIONAL_RESEARCH_MODULES = {
    "citylearn",
    "docplex",
    "gurobipy",
    "jupyter",
    "pyomo",
    "spflow",
    "torch",
    "torchrl",
    "wandb",
}

EXPECTED_CONTROL_EXPORTS = [
    "AFRRBaselineConfig",
    "AFRRBaselineMode",
    "ArbitrageOnlyBaselineConfig",
    "BaselineScheduleBundle",
    "DirectionalCapacityCommitmentInterval",
    "DirectionalCapacitySchedule",
    "PVSelfConsumptionConfig",
    "PVSelfConsumptionController",
    "PriceThresholdConfig",
    "PriceThresholdController",
    "RegulationOnlyBaselineConfig",
    "RestorationBaselineBundle",
    "RestorationCapability",
    "RestorationControlValidationError",
    "RestorationEnergyBaselineInterval",
    "RestorationEnergyBaselineSchedule",
    "SocGuardrailConfig",
    "SocGuardrailController",
    "StackedBaselineValidationError",
    "StackedHeuristicConfig",
    "build_afrr_baseline",
    "build_afrr_baseline_config",
    "build_afrr_directional_capacity_schedule",
    "build_arbitrage_only_baseline",
    "build_regulation_only_baseline",
    "build_restoration_capability",
    "build_stacked_heuristic_baseline",
]
EXPECTED_VISUALIZATION_EXPORTS = [
    "build_inspection_view",
    "load_persisted_run_output",
    "summarize_inspection_view",
]
EXPECTED_WEATHER_EXPORTS = [
    "fit_weather_model",
    "fit_weather_dataset",
    "load_weather_artifact",
    "WeatherSamplingRequest",
    "sample_weather_family",
    "PVGISTMYRequestConfig",
    "WeatherCacheUnavailableError",
    "load_or_fetch_tmy_dataset",
]
EXPECTED_DEMAND_EXPORTS = [
    "fit_demand_model",
    "load_demand_artifact",
    "DemandSamplingRequest",
    "sample_demand_family",
    "SyntheticCommercialDemandConfig",
    "build_measured_demand_training_payload",
    "build_synthetic_demand_training_payload",
]
EXPECTED_PLANNING_EXPORTS = [
    "PlanningDatasetArtifact",
    "load_planning_dataset",
    "PlanningProblemAssembly",
    "PlanningProblemDefinition",
    "assemble_planning_problem",
    "PlanningSolveConfig",
    "PlanningSolveSummary",
    "PlanningSolverDependencyUnavailableError",
    "PlanningSolverUnavailableError",
    "solve_planning_problem",
    "AdequacyEventDefinition",
    "BatteryDesignOption",
    "ControllerStudyConfig",
    "GridAvailabilityPolicy",
    "PlanningStudyRequest",
    "SolarDesignOption",
    "PlanningStudyDatasetManifest",
    "iter_study_rows",
    "load_study_dataset_manifest",
    "CalibrationAssessment",
    "RecommendationAssessment",
    "SPNCandidateScore",
    "assess_calibration",
    "assess_recommendation",
    "brier_score_by_configuration",
    "select_spn_candidate",
    "CompiledPlanningStudyTPM",
    "PlanningStudyRunResult",
    "VerifiedPlanningStudySolution",
    "compile_planning_study_tpm",
    "fit_planning_study_tpm",
    "run_planning_study",
    "solve_planning_study",
]
EXPECTED_TPM_EXPORTS = [
    "LegacyTPMArtifactVersionError",
    "SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS",
    "SUPPORTED_TPM_EXECUTION_MODES",
    "TPMArtifact",
    "TPMArtifactIntegrityError",
    "UnsupportedTPMArtifactVersionError",
    "load_tpm_artifact",
    "TPMTrainingData",
    "normalize_training_data",
    "TPMFeatureSpec",
    "dump_feature_schema",
    "infer_feature_role",
    "load_feature_schema",
    "TPMFitConfig",
    "TPMFitMemoryError",
    "TPMArtifactBuildRequest",
    "fit_tpm_artifact",
    "fit_tpm_artifact_from_rows",
    "fit_tpm_artifact_from_study_manifest",
    "SPNModelingTerms",
    "SPNPiecewiseCurveSpec",
    "SPNSolveConfig",
    "SPNSolveSummary",
    "SPNSolverDependencyUnavailableError",
    "SPNSolverUnavailableError",
    "UnsupportedSPFlowModuleError",
    "build_spn_chance_model",
    "build_spn_chance_model_from_artifact",
    "build_spn_modeling_terms",
    "compile_spflow_model_to_mio",
    "evaluate_compiled_spflow_probability",
    "extract_spn_solution",
    "infer_max_sum_terms",
    "require_pyomo_backend",
    "solve_spn_chance_model",
    "solve_spn_chance_model_from_artifact",
    "CURRENT_SPFLOW_ADAPTER_NAME",
    "CURRENT_SPFLOW_BACKEND_GENERATION",
    "CurrentSPFlowCapabilities",
    "REQUIRED_SPFLOW_VERSION",
    "SPFlowBackendCompatibilityError",
    "SPFlowDependencyUnavailableError",
    "detect_spflow_backend_capabilities",
    "register_spflow_backend_adapter",
    "require_spflow_backend",
    "PiecewiseApproximationMetadata",
    "PiecewiseBreakpointPolicy",
    "build_piecewise_metadata",
    "load_piecewise_metadata",
    "TPMQueryRequest",
    "query_tpm_artifact",
    "unregister_spflow_backend_adapter",
]


def test_root_package_imports_from_source_tree_without_optional_stacks():
    before_import = set(sys.modules)

    package = importlib.import_module("open_energy_lab")

    assert package.__file__ is not None, "open_energy_lab must be a regular package"
    package_file = Path(package.__file__).resolve()
    assert package.__name__ == "open_energy_lab"
    assert package_file.name == "__init__.py"
    assert package_file.parent.name == "open_energy_lab"
    assert package_file.parent.parent.name == "src"

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
    assert newly_loaded_optional_modules == set()


def test_control_package_imports_from_source_tree_without_optional_stacks():
    before_import = set(sys.modules)

    module = importlib.import_module("open_energy_lab.control")

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module.__name__ == "open_energy_lab.control"
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "control"
    assert module_file.parent.parent.name == "open_energy_lab"
    assert module.__all__ == EXPECTED_CONTROL_EXPORTS
    assert module.PVSelfConsumptionConfig.__module__ == "open_energy_lab.control._config"
    assert (
        module.PVSelfConsumptionController.__module__
        == "open_energy_lab.control.pv_self_consumption"
    )
    assert module.PriceThresholdConfig.__module__ == "open_energy_lab.control._config"
    assert module.PriceThresholdController.__module__ == "open_energy_lab.control.price_threshold"
    assert module.SocGuardrailConfig.__module__ == "open_energy_lab.control._config"
    assert module.SocGuardrailController.__module__ == "open_energy_lab.control.soc_guardrail"
    assert module.ArbitrageOnlyBaselineConfig.__module__ == (
        "open_energy_lab.control.stacked_service"
    )
    assert module.StackedHeuristicConfig.__module__ == (
        "open_energy_lab.control.stacked_service"
    )
    assert module.build_stacked_heuristic_baseline.__module__ == (
        "open_energy_lab.control.stacked_service"
    )

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
    assert newly_loaded_optional_modules == set()


def test_feature_010_public_imports_resolve_from_owned_modules_without_optional_stacks():
    before_import = set(sys.modules)

    market = importlib.import_module("open_energy_lab.market")
    control = importlib.import_module("open_energy_lab.control")
    simulator = importlib.import_module("open_energy_lab.simulator")

    expected_owners = {
        market.RegulationActivationTrace: "open_energy_lab.market.activation",
        market.MarketDataArtifact: "open_energy_lab.market.artifact",
        control.StackedHeuristicConfig: "open_energy_lab.control.stacked_service",
        control.build_stacked_heuristic_baseline: (
            "open_energy_lab.control.stacked_service"
        ),
        simulator.StackedServiceReplayRequest: (
            "open_energy_lab.simulator.stacked_service"
        ),
        simulator.replay_stacked_services: (
            "open_energy_lab.simulator.stacked_service"
        ),
        simulator.SettlementBreakdown: (
            "open_energy_lab.simulator.fcr_settlement"
        ),
        simulator.settle_stacked_services: (
            "open_energy_lab.simulator.fcr_settlement"
        ),
    }
    for exported, owner in expected_owners.items():
        assert exported.__module__ == owner

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
    assert newly_loaded_optional_modules == set()


def test_feature_011_afrr_public_imports_resolve_from_exact_owned_modules():
    before_import = set(sys.modules)

    market = importlib.import_module("open_energy_lab.market")
    control = importlib.import_module("open_energy_lab.control")
    simulator = importlib.import_module("open_energy_lab.simulator")

    expected_owners = {
        market.RestorationProduct: (
            "open_energy_lab.market.restoration_activation"
        ),
        market.AFRRActivationSample: (
            "open_energy_lab.market.restoration_activation"
        ),
        market.AFRRActivationTrajectory: (
            "open_energy_lab.market.restoration_activation"
        ),
        market.build_afrr_activation_trajectory: (
            "open_energy_lab.market.restoration_activation"
        ),
        market.build_afrr_trajectory_from_rte_requested_need: (
            "open_energy_lab.market.restoration_activation"
        ),
        control.DirectionalCapacitySchedule: (
            "open_energy_lab.control.restoration_service"
        ),
        control.AFRRBaselineConfig: (
            "open_energy_lab.control.restoration_service"
        ),
        control.RestorationBaselineBundle: (
            "open_energy_lab.control.restoration_service"
        ),
        control.build_afrr_baseline: (
            "open_energy_lab.control.restoration_service"
        ),
        simulator.RestorationIntegrationGrid: (
            "open_energy_lab.simulator.restoration_service"
        ),
        simulator.AFRRReplayRequest: (
            "open_energy_lab.simulator.restoration_service"
        ),
        simulator.AFRRReplayResult: (
            "open_energy_lab.simulator.restoration_service"
        ),
        simulator.replay_afrr: (
            "open_energy_lab.simulator.restoration_service"
        ),
    }
    for exported, owner in expected_owners.items():
        assert exported.__module__ == owner

    newly_loaded = set(sys.modules) - before_import
    assert "open_energy_lab.market.rte" not in newly_loaded
    assert "open_energy_lab.market.entsoe" not in newly_loaded
    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & newly_loaded
    assert newly_loaded_optional_modules == set()


def test_core_package_imports_from_source_tree_without_optional_stacks():
    before_import = set(sys.modules)

    module = importlib.import_module("open_energy_lab.core")

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module.__name__ == "open_energy_lab.core"
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "core"
    assert module_file.parent.parent.name == "open_energy_lab"
    assert module.__all__ == [
        "ControllerContext",
        "ControllerEvaluationResult",
        "ControllerInterface",
        "DispatchProposal",
    ]
    assert module.ControllerContext.__module__ == "open_energy_lab.core.controller"
    assert module.ControllerEvaluationResult.__module__ == "open_energy_lab.core.controller"
    assert module.ControllerInterface.__module__ == "open_energy_lab.core.controller"
    assert module.DispatchProposal.__module__ == "open_energy_lab.core.controller"

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
    assert newly_loaded_optional_modules == set()


def test_visualization_package_imports_from_source_tree_without_optional_stacks():
    before_import = set(sys.modules)

    module = importlib.import_module("open_energy_lab.visualization")

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module.__name__ == "open_energy_lab.visualization"
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "visualization"
    assert module_file.parent.parent.name == "open_energy_lab"
    assert module.__all__ == EXPECTED_VISUALIZATION_EXPORTS
    assert module.build_inspection_view.__module__ == "open_energy_lab.visualization.inspection"
    assert (
        module.load_persisted_run_output.__module__
        == "open_energy_lab.visualization._persistence"
    )
    assert (
        module.summarize_inspection_view.__module__
        == "open_energy_lab.visualization.inspection"
    )
    assert "plot_inspection_view" not in module.__all__

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
    assert newly_loaded_optional_modules == set()


def test_weather_package_import_contract_stays_reserved_and_import_light():
    before_import = set(sys.modules)
    module_spec = importlib.util.find_spec("open_energy_lab.weather")

    if module_spec is None:
        assert "open_energy_lab.weather" not in sys.modules
        return

    module = importlib.import_module("open_energy_lab.weather")

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module.__name__ == "open_energy_lab.weather"
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "weather"
    assert module_file.parent.parent.name == "open_energy_lab"
    assert module.__all__ == EXPECTED_WEATHER_EXPORTS
    assert module.fit_weather_model.__module__ == "open_energy_lab.weather.fit"
    assert module.load_weather_artifact.__module__ == "open_energy_lab.weather.artifact"
    assert module.WeatherSamplingRequest.__module__ == "open_energy_lab.weather.sampling"
    assert module.sample_weather_family.__module__ == "open_energy_lab.weather.sampling"

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
    assert newly_loaded_optional_modules == set()


def test_demand_package_import_contract_stays_reserved_and_import_light():
    before_import = set(sys.modules)
    module_spec = importlib.util.find_spec("open_energy_lab.demand")

    if module_spec is None:
        assert "open_energy_lab.demand" not in sys.modules
        return

    module = importlib.import_module("open_energy_lab.demand")

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module.__name__ == "open_energy_lab.demand"
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "demand"
    assert module_file.parent.parent.name == "open_energy_lab"
    assert module.__all__ == EXPECTED_DEMAND_EXPORTS
    assert module.DemandSamplingRequest.__module__ == "open_energy_lab.demand.sampling"
    assert module.fit_demand_model.__module__ == "open_energy_lab.demand.fit"
    assert module.load_demand_artifact.__module__ == "open_energy_lab.demand.artifact"
    assert module.sample_demand_family.__module__ == "open_energy_lab.demand.sampling"

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
    assert newly_loaded_optional_modules == set()


def test_tpm_package_imports_from_source_tree_without_optional_stacks():
    before_import = set(sys.modules)
    module_spec = importlib.util.find_spec("open_energy_lab.tpm")

    if module_spec is None:
        assert "open_energy_lab.tpm" not in sys.modules
        return

    module = importlib.import_module("open_energy_lab.tpm")

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module.__name__ == "open_energy_lab.tpm"
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "tpm"
    assert module_file.parent.parent.name == "open_energy_lab"
    assert module.__all__ == EXPECTED_TPM_EXPORTS
    assert all("." not in export_name for export_name in module.__all__)
    assert all(not export_name.startswith("_") for export_name in module.__all__)

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
    assert newly_loaded_optional_modules == set()


def test_planning_package_imports_from_source_tree_without_optional_stacks():
    before_import = set(sys.modules)
    module_spec = importlib.util.find_spec("open_energy_lab.planning")

    if module_spec is None:
        assert "open_energy_lab.planning" not in sys.modules
        return

    module = importlib.import_module("open_energy_lab.planning")

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module.__name__ == "open_energy_lab.planning"
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "planning"
    assert module_file.parent.parent.name == "open_energy_lab"
    assert module.__all__ == EXPECTED_PLANNING_EXPORTS
    assert module.PlanningDatasetArtifact.__module__ == "open_energy_lab.planning.dataset"
    assert module.load_planning_dataset.__module__ == "open_energy_lab.planning.dataset"
    assert module.PlanningProblemAssembly.__module__ == "open_energy_lab.planning.problem"
    assert module.PlanningProblemDefinition.__module__ == "open_energy_lab.planning.problem"
    assert module.assemble_planning_problem.__module__ == "open_energy_lab.planning.problem"
    assert module.PlanningSolveConfig.__module__ == "open_energy_lab.planning.optional_solver"
    assert module.PlanningSolveSummary.__module__ == "open_energy_lab.planning.optional_solver"
    assert (
        module.PlanningSolverDependencyUnavailableError.__module__
        == "open_energy_lab.planning.optional_solver"
    )
    assert (
        module.PlanningSolverUnavailableError.__module__
        == "open_energy_lab.planning.optional_solver"
    )
    assert module.solve_planning_problem.__module__ == "open_energy_lab.planning.optional_solver"

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
    assert newly_loaded_optional_modules == set()
