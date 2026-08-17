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
    "PVSelfConsumptionConfig",
    "PVSelfConsumptionController",
    "PriceThresholdConfig",
    "PriceThresholdController",
    "SocGuardrailConfig",
    "SocGuardrailController",
]
EXPECTED_VISUALIZATION_EXPORTS = [
    "build_inspection_view",
    "load_persisted_run_output",
    "summarize_inspection_view",
]
EXPECTED_WEATHER_EXPORTS = [
    "fit_weather_model",
    "load_weather_artifact",
    "WeatherSamplingRequest",
    "sample_weather_family",
]
EXPECTED_DEMAND_EXPORTS = [
    "fit_demand_model",
    "load_demand_artifact",
    "DemandSamplingRequest",
    "sample_demand_family",
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
]
EXPECTED_TPM_EXPORTS = [
    "TPMArtifact",
    "UnsupportedTPMArtifactVersionError",
    "load_tpm_artifact",
    "TPMTrainingData",
    "normalize_training_data",
    "TPMFeatureSpec",
    "dump_feature_schema",
    "infer_feature_role",
    "load_feature_schema",
    "TPMFitConfig",
    "TPMArtifactBuildRequest",
    "fit_tpm_artifact",
    "fit_tpm_artifact_from_rows",
    "SPNModelingTerms",
    "SPNPiecewiseCurveSpec",
    "SPNSolveConfig",
    "SPNSolveSummary",
    "SPNSolverDependencyUnavailableError",
    "SPNSolverUnavailableError",
    "build_spn_chance_model",
    "build_spn_chance_model_from_artifact",
    "build_spn_modeling_terms",
    "extract_spn_solution",
    "infer_max_sum_terms",
    "require_pyomo_backend",
    "solve_spn_chance_model",
    "solve_spn_chance_model_from_artifact",
    "SPFlowDependencyUnavailableError",
    "detect_spflow_backend_capabilities",
    "register_spflow_backend_adapter",
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

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
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
