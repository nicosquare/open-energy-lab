import importlib
import sys
from pathlib import Path


OPTIONAL_RESEARCH_MODULES = {
    "IPython",
    "citylearn",
    "docplex",
    "gurobipy",
    "highspy",
    "ipykernel",
    "jupyter",
    "nbclient",
    "nbformat",
    "notebook",
    "pyomo",
    "spflow",
    "torch",
    "torchrl",
    "wandb",
}

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
    "fit_tpm_artifact",
    "fit_tpm_artifact_from_study_manifest",
    "CompiledPlanningStudyTPM",
    "PlanningStudyRunResult",
    "VerifiedPlanningStudySolution",
    "compile_planning_study_tpm",
    "fit_planning_study_tpm",
    "run_planning_study",
    "solve_planning_study",
]
EXPECTED_TPM_EXPORTS = [
    "CONDITIONAL_COMPILER_FIDELITY_RECORD_KIND",
    "CONDITIONAL_EMBEDDING_PARITY_RECORD_KIND",
    "CONDITIONAL_EVIDENCE_EVALUATOR_VERSION",
    "CONDITIONAL_EVIDENCE_SCHEMA_VERSION",
    "CONDITIONAL_PAIR_COMPILER_VERSION",
    "CONDITIONAL_PAIR_RECORD_KIND",
    "CONDITIONAL_PAIR_SCHEMA_VERSION",
    "LegacyTPMArtifactVersionError",
    "SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS",
    "SUPPORTED_TPM_EXECUTION_MODES",
    "TPMArtifact",
    "TPMArtifactIntegrityError",
    "TPMBinaryDecisionLink",
    "TPMBinaryDecisionMapping",
    "TPMCategoricalDecisionLink",
    "TPMCategoricalDecisionMapping",
    "TPMConditionalAttachment",
    "TPMConditionalAttachmentDiagnostics",
    "TPMConditionalAttachmentFormulation",
    "TPMConditionalCircuit",
    "TPMConditionalCircuitNode",
    "TPMConditionalCompilationRequest",
    "TPMConditionalDecisionLink",
    "TPMConditionalEncodingPolicy",
    "TPMConditionalEvaluation",
    "TPMConditionalDiagnosticsError",
    "TPMConditionalEvaluationError",
    "TPMConditionalEvent",
    "TPMConditionalFeatureValidity",
    "TPMConditionalNumericalPolicy",
    "TPMConditionalPair",
    "TPMConditionalPublication",
    "TPMConditionalSourceReference",
    "TPMCompilerFidelityEvidence",
    "TPMContinuousDecisionMapping",
    "TPMIntegerDecisionMapping",
    "TPMEmbeddingParityEvidence",
    "TPMNativeConditionalEvaluation",
    "UnsupportedTPMArtifactVersionError",
    "load_tpm_artifact",
    "TPMTrainingData",
    "normalize_training_data",
    "TPMApproximationDomain",
    "TPMCompiledValidityRecord",
    "TPMFeatureDomain",
    "TPMNormalizationSpec",
    "TPMTrainingSupport",
    "TPMFeatureSpec",
    "dump_feature_schema",
    "infer_feature_role",
    "load_feature_schema",
    "canonical_conditional_json_bytes",
    "load_conditional_evidence",
    "load_conditional_pair",
    "publish_conditional_evidence",
    "publish_conditional_pair",
    "resolve_conditional_attachment_formulation",
    "TPMFitConfig",
    "learn_bounded_prometheus",
    "validate_refinement_spn",
    "project_spn_gaussian_widths",
    "spn_binary_conditional_logs",
    "spn_refinement_loss",
    "refine_spn_step",
    "save_spn_refinement_state",
    "load_spn_refinement_state",
    "save_supported_spn_model",
    "TPMFitMemoryError",
    "TPMArtifactBuildRequest",
    "fit_tpm_artifact_from_rows",
    "SPNModelingTerms",
    "SPNPiecewiseCurveSpec",
    "SPNSolveConfig",
    "SPNSolveSummary",
    "SPNSolverDependencyUnavailableError",
    "SPNSolverUnavailableError",
    "UnsupportedSPFlowModuleError",
    "build_spn_chance_model",
    "build_spn_chance_model_from_artifact",
    "build_compiled_spflow_decision_link_model",
    "build_spn_modeling_terms",
    "compile_spflow_model_to_mio",
    "compile_conditional_mio_pair",
    "attach_conditional_mio_pair",
    "build_compiler_fidelity_evidence",
    "build_embedding_parity_evidence",
    "evaluate_conditional_mio_pair",
    "initialize_conditional_mio_attachment",
    "inspect_conditional_mio_attachment",
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
    "resolve_guarded_exponential_spec",
    "TPMQueryRequest",
    "evaluate_native_conditional_pair",
    "query_tpm_artifact",
    "unregister_spflow_backend_adapter",
    "TPMNativeMixtureConfig",
    "initialize_native_mixture",
    "native_joint_conditional_log_values",
    "native_full_gradient_step",
    "capture_native_training_state",
    "restore_native_training_state",
    "restore_native_mixture_for_inference",
    "materialize_native_mixture",
    "export_native_mixture_scalar",
    "CategoricalMixtureConfig",
    "lower_linsum_einet",
    "enable_linsum_contraction",
    "build_categorical_mixture",
    "initialize_categorical_mixture",
    "initialize_categorical_mixture_streaming",
    "categorical_mixture_step",
    "save_categorical_mixture_state",
    "load_categorical_mixture_state",
    "load_categorical_mixture_for_inference",
    "compile_categorical_log_ratio",
    "evaluate_categorical_log_ratio",
    "attach_categorical_log_ratio",
    "categorical_attachment_witness",
    "CategoricalGroupSeparator",
    "restrict_categorical_domains",
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
