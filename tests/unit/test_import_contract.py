import importlib
import subprocess
import sys
import textwrap
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

EXPECTED_CONTROL_EXPORTS = sorted([
    "AGGREGATION_POLICY",
    "AFRRBaselineConfig",
    "AFRRBaselineMode",
    "ArbitrageOnlyBaselineConfig",
    "BaselineScheduleBundle",
    "BidPlanProducer",
    "AcceptedBidPolicy",
    "AggregateMetricEvidence",
    "CallerSuppliedRollingState",
    "ContinuitySegment",
    "ConstraintFamilyResidual",
    "DirectionalCapacityCommitmentInterval",
    "DirectionalCapacitySchedule",
    "DeliveryDateClassification",
    "DeliveryDateRecordEnvelope",
    "FAILURE_POLICY_COUPLED",
    "FAILURE_POLICY_INDEPENDENT",
    "FCRBidPlanValidationError",
    "FeasibilityAudit",
    "FixedFCRBidPlan",
    "HorizonWideActivationBudget",
    "JointReferenceCertificate",
    "MFRRBaselineConfig",
    "MFRRBaselineMode",
    "ObjectiveBreakdown",
    "OptimizationMetric",
    "PVSelfConsumptionConfig",
    "PVSelfConsumptionController",
    "PlanDiagnostic",
    "PriceThresholdConfig",
    "PriceThresholdController",
    "RegulationOnlyBaselineConfig",
    "RecoveryWindowActivationBudget",
    "RESUME_POLICY",
    "RestorationBaselineBundle",
    "RestorationCapability",
    "RestorationControlValidationError",
    "RestorationEnergyBaselineInterval",
    "RestorationEnergyBaselineSchedule",
    "RobustFCRBatteryParameters",
    "RobustFCRAcceptedDecisionFixings",
    "RobustFCRBiddingProblem",
    "RobustFCRBoundComparison",
    "RobustFCRDecisions",
    "RobustFCRFormulationProfile",
    "RobustFCRPriceInputs",
    "RobustFCRReferenceComparison",
    "RobustFCRReferenceFixture",
    "RobustFCRRollingBiddingProblem",
    "RobustFCRRollingSolveResult",
    "RobustFCRSolvePolicy",
    "RobustFCRSolveResult",
    "RobustFCRSolverDependencyUnavailableError",
    "RobustFCRSolverUnavailableError",
    "RobustFCRTimeContract",
    "RobustFCRUncertaintyProfile",
    "RobustFCRValidationError",
    "RollingFCRBatteryBinding",
    "RollingFCRDataDescriptor",
    "RollingFCRDayInput",
    "RollingFCRDayRevision",
    "RollingFCRExperimentProfile",
    "RollingFCRNumericPolicy",
    "RollingFCRReferenceComparison",
    "RollingFCRReferenceFieldResult",
    "RollingFCRReferenceFixture",
    "RollingFCRResumeEvidence",
    "RollingFCRStateCarryEvidence",
    "RollingFCRStateLink",
    "RollingFCRStudyManifest",
    "RollingFCRStudyResult",
    "RollingFCRValidationError",
    "SerializedScheduleReference",
    "SocGuardrailConfig",
    "SocGuardrailController",
    "StackedBaselineValidationError",
    "StackedHeuristicConfig",
    "TerminalStoredEnergyRule",
    "build_afrr_baseline",
    "build_afrr_baseline_config",
    "build_afrr_directional_capacity_schedule",
    "build_arbitrage_only_baseline",
    "build_fixed_fcr_bid_plan",
    "build_mfrr_baseline",
    "build_mfrr_baseline_config",
    "build_mfrr_directional_capacity_schedule",
    "build_regulation_only_baseline",
    "build_restoration_capability",
    "build_robust_fcr_bidding_problem",
    "build_robust_fcr_reference_problem",
    "build_robust_fcr_rolling_problem",
    "build_robust_fcr_time_contract",
    "build_rolling_fcr_experiment_profile",
    "build_rolling_fcr_study_manifest",
    "aggregate_rolling_fcr_records",
    "assess_rolling_fcr_resume",
    "build_stacked_heuristic_baseline",
    "compare_robust_fcr_bounds",
    "compare_robust_fcr_reference",
    "compare_rolling_fcr_reference",
    "derive_non_intraday_horizon_budget",
    "derive_rolling_fcr_state_carry",
    "load_rolling_fcr_study_result",
    "extract_accepted_predecessor_fixings",
    "load_robust_fcr_reference_fixture",
    "load_rolling_fcr_reference_fixture",
    "run_rolling_fcr_study",
    "solve_robust_fcr_bid",
    "solve_robust_fcr_rolling_bid",
])
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
    "TPMApproximationDomain",
    "TPMCompiledValidityRecord",
    "TPMFeatureDomain",
    "TPMNormalizationSpec",
    "TPMTrainingSupport",
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
    "build_compiled_spflow_decision_link_model",
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


def test_feature_012_public_plan_and_evaluator_imports_have_exact_owners():
    control = importlib.import_module("open_energy_lab.control")
    simulator = importlib.import_module("open_energy_lab.simulator")
    reference = importlib.import_module("open_energy_lab.market.reference_fcr")
    expected = {
        control.BidPlanProducer: "open_energy_lab.control.fcr_bid_plan",
        control.FixedFCRBidPlan: "open_energy_lab.control.fcr_bid_plan",
        control.OptimizationMetric: "open_energy_lab.control.fcr_bid_plan",
        control.build_fixed_fcr_bid_plan: "open_energy_lab.control.fcr_bid_plan",
        simulator.FCRBidEvaluationRequest: (
            "open_energy_lab.simulator.fcr_bid_evaluation"
        ),
        simulator.DailyFCRBidEvaluationReport: (
            "open_energy_lab.simulator.fcr_bid_evaluation"
        ),
        simulator.InvalidCommitmentDiagnosticReport: (
            "open_energy_lab.simulator.fcr_bid_evaluation"
        ),
        simulator.DirectionalFCREnergy: (
            "open_energy_lab.simulator.fcr_settlement"
        ),
        simulator.ReferenceSettlementBreakdown: (
            "open_energy_lab.simulator.fcr_settlement"
        ),
        simulator.evaluate_fixed_fcr_bid: (
            "open_energy_lab.simulator.fcr_bid_evaluation"
        ),
        simulator.replay_invalid_fcr_bid_diagnostic: (
            "open_energy_lab.simulator.fcr_bid_evaluation"
        ),
        reference.load_golden_reference_fixture: (
            "open_energy_lab.market.reference_fcr"
        ),
        reference.load_reference_activation_trace: (
            "open_energy_lab.market.reference_fcr"
        ),
    }

    assert {value: value.__module__ for value in expected} == expected

    market = importlib.import_module("open_energy_lab.market")
    assert "load_golden_reference_fixture" not in market.__all__
    assert "load_reference_activation_trace" not in market.__all__


def test_feature_013_public_imports_have_exact_owners_and_stay_solver_lazy():
    before_import = set(sys.modules)
    control = importlib.import_module("open_energy_lab.control")
    bidding_owner = "open_energy_lab.control.robust_fcr_bidding"
    reference_owner = "open_energy_lab.control.robust_fcr_reference"
    expected = {
        control.ConstraintFamilyResidual: bidding_owner,
        control.FeasibilityAudit: bidding_owner,
        control.HorizonWideActivationBudget: bidding_owner,
        control.JointReferenceCertificate: reference_owner,
        control.ObjectiveBreakdown: bidding_owner,
        control.RecoveryWindowActivationBudget: bidding_owner,
        control.RobustFCRBatteryParameters: bidding_owner,
        control.RobustFCRBiddingProblem: bidding_owner,
        control.RobustFCRBoundComparison: bidding_owner,
        control.RobustFCRDecisions: bidding_owner,
        control.RobustFCRFormulationProfile: bidding_owner,
        control.RobustFCRPriceInputs: bidding_owner,
        control.RobustFCRReferenceComparison: reference_owner,
        control.RobustFCRReferenceFixture: reference_owner,
        control.RobustFCRSolvePolicy: bidding_owner,
        control.RobustFCRSolveResult: bidding_owner,
        control.RobustFCRSolverDependencyUnavailableError: bidding_owner,
        control.RobustFCRSolverUnavailableError: bidding_owner,
        control.RobustFCRTimeContract: bidding_owner,
        control.RobustFCRUncertaintyProfile: bidding_owner,
        control.RobustFCRValidationError: bidding_owner,
        control.TerminalStoredEnergyRule: bidding_owner,
        control.build_robust_fcr_bidding_problem: bidding_owner,
        control.build_robust_fcr_reference_problem: reference_owner,
        control.build_robust_fcr_time_contract: bidding_owner,
        control.compare_robust_fcr_bounds: bidding_owner,
        control.compare_robust_fcr_reference: reference_owner,
        control.derive_non_intraday_horizon_budget: bidding_owner,
        control.load_robust_fcr_reference_fixture: reference_owner,
        control.solve_robust_fcr_bid: bidding_owner,
    }

    assert {value: value.__module__ for value in expected} == expected
    newly_loaded = set(sys.modules) - before_import
    forbidden = {
        "gurobipy",
        "highspy",
        "julia",
        "juliacall",
        "pandas",
        "pyomo",
    }
    assert forbidden.isdisjoint(
        {name.split(".", 1)[0] for name in newly_loaded}
    )


def test_feature_015_public_imports_have_exact_owners_and_stay_solver_lazy():
    before_import = set(sys.modules)
    control = importlib.import_module("open_energy_lab.control")
    market = importlib.import_module("open_energy_lab.market")
    simulator = importlib.import_module("open_energy_lab.simulator")
    study_owner = "open_energy_lab.control.fcr_rolling_backtest"
    rolling_owner = "open_energy_lab.control.robust_fcr_rolling"
    reference_owner = "open_energy_lab.control.fcr_rolling_reference"
    expected = {
        control.AcceptedBidPolicy: study_owner,
        control.AggregateMetricEvidence: study_owner,
        control.CallerSuppliedRollingState: study_owner,
        control.ContinuitySegment: study_owner,
        control.DeliveryDateClassification: study_owner,
        control.DeliveryDateRecordEnvelope: study_owner,
        control.RollingFCRBatteryBinding: study_owner,
        control.RollingFCRDataDescriptor: study_owner,
        control.RollingFCRDayInput: study_owner,
        control.RollingFCRDayRevision: study_owner,
        control.RollingFCRExperimentProfile: study_owner,
        control.RollingFCRNumericPolicy: study_owner,
        control.RollingFCRResumeEvidence: study_owner,
        control.RollingFCRStateCarryEvidence: study_owner,
        control.RollingFCRStateLink: study_owner,
        control.RollingFCRStudyManifest: study_owner,
        control.RollingFCRStudyResult: study_owner,
        control.RollingFCRValidationError: study_owner,
        control.aggregate_rolling_fcr_records: study_owner,
        control.assess_rolling_fcr_resume: study_owner,
        control.build_rolling_fcr_experiment_profile: study_owner,
        control.build_rolling_fcr_study_manifest: study_owner,
        control.derive_rolling_fcr_state_carry: study_owner,
        control.load_rolling_fcr_study_result: study_owner,
        control.run_rolling_fcr_study: study_owner,
        control.RobustFCRAcceptedDecisionFixings: rolling_owner,
        control.RobustFCRRollingBiddingProblem: rolling_owner,
        control.RobustFCRRollingSolveResult: rolling_owner,
        control.build_robust_fcr_rolling_problem: rolling_owner,
        control.extract_accepted_predecessor_fixings: rolling_owner,
        control.solve_robust_fcr_rolling_bid: rolling_owner,
        control.RollingFCRReferenceComparison: reference_owner,
        control.RollingFCRReferenceFieldResult: reference_owner,
        control.RollingFCRReferenceFixture: reference_owner,
        control.compare_rolling_fcr_reference: reference_owner,
        control.load_rolling_fcr_reference_fixture: reference_owner,
        market.slice_regulation_activation_trace: (
            "open_energy_lab.market.activation"
        ),
        simulator.FCRAcceptedPlanSegment: (
            "open_energy_lab.simulator.fcr_rolling_evaluation"
        ),
        simulator.FCRSegmentedEvaluationReport: (
            "open_energy_lab.simulator.fcr_rolling_evaluation"
        ),
        simulator.evaluate_fixed_fcr_bid_segments: (
            "open_energy_lab.simulator.fcr_rolling_evaluation"
        ),
        simulator.build_accepted_plan_market_context: (
            "open_energy_lab.simulator.fcr_bid_evaluation"
        ),
    }

    assert {value: value.__module__ for value in expected} == expected
    assert control.AGGREGATION_POLICY == "coverage-labelled-no-zero-fill-v1"
    assert control.RESUME_POLICY == "exact-semantic-evidence-v1"
    newly_loaded = set(sys.modules) - before_import
    forbidden = {
        "baselines",
        "gurobipy",
        "highspy",
        "julia",
        "juliacall",
        "legacy",
        "pandas",
        "pyomo",
    }
    assert forbidden.isdisjoint(
        {name.split(".", 1)[0] for name in newly_loaded}
    )


def test_feature_011_restoration_public_imports_resolve_from_exact_owned_modules():
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
        market.MFRRActivationEvent: (
            "open_energy_lab.market.restoration_activation"
        ),
        market.MFRRActivationSequence: (
            "open_energy_lab.market.restoration_activation"
        ),
        market.build_mfrr_activation_sequence: (
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
        control.MFRRBaselineConfig: (
            "open_energy_lab.control.restoration_service"
        ),
        control.build_mfrr_baseline: (
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
        simulator.MFRRReplayRequest: (
            "open_energy_lab.simulator.restoration_service"
        ),
        simulator.MFRREventPerformance: (
            "open_energy_lab.simulator.restoration_service"
        ),
        simulator.MFRRReplayResult: (
            "open_energy_lab.simulator.restoration_service"
        ),
        simulator.replay_mfrr: (
            "open_energy_lab.simulator.restoration_service"
        ),
        simulator.RestorationSettlement: (
            "open_energy_lab.simulator.restoration_settlement"
        ),
        simulator.AFRRRestorationSettlement: (
            "open_energy_lab.simulator.restoration_settlement"
        ),
        simulator.MFRRRestorationSettlement: (
            "open_energy_lab.simulator.restoration_settlement"
        ),
        simulator.settle_restoration_services: (
            "open_energy_lab.simulator.restoration_settlement"
        ),
    }
    for exported, owner in expected_owners.items():
        assert exported.__module__ == owner

    newly_loaded = set(sys.modules) - before_import
    assert "open_energy_lab.market.rte" not in newly_loaded
    assert "open_energy_lab.market.entsoe" not in newly_loaded
    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & newly_loaded
    assert newly_loaded_optional_modules == set()


def test_feature_011_package_roots_resolve_offline_owners_without_adapter_or_credential_access():
    source = textwrap.dedent(
        """
        import os
        import sys

        credential_keys = {
            "RTE_CLIENT_ID",
            "RTE_CLIENT_SECRET",
            "RTE_ACCESS_TOKEN",
            "ENTSOE_API_TOKEN",
        }
        adapters = {
            "open_energy_lab.market.rte",
            "open_energy_lab.market.entsoe",
        }

        class GuardedEnvironment(dict):
            def __getitem__(self, key):
                if key in credential_keys:
                    raise AssertionError(f"credential read: {key}")
                return super().__getitem__(key)

            def get(self, key, default=None):
                if key in credential_keys:
                    raise AssertionError(f"credential read: {key}")
                return super().get(key, default)

            def __contains__(self, key):
                if key in credential_keys:
                    raise AssertionError(f"credential inspected: {key}")
                return super().__contains__(key)

        os.environ = GuardedEnvironment(os.environ)
        import open_energy_lab.control as control
        import open_energy_lab.market as market
        import open_energy_lab.simulator as simulator

        expected_owners = {
            market.RestorationMarketArtifact:
                "open_energy_lab.market.restoration_artifact",
            market.RestorationStudyBundle:
                "open_energy_lab.market.restoration_artifact",
            market.AFRRActivationTrajectory:
                "open_energy_lab.market.restoration_activation",
            market.MFRRActivationSequence:
                "open_energy_lab.market.restoration_activation",
            control.DirectionalCapacitySchedule:
                "open_energy_lab.control.restoration_service",
            control.RestorationBaselineBundle:
                "open_energy_lab.control.restoration_service",
            simulator.AFRRReplayResult:
                "open_energy_lab.simulator.restoration_service",
            simulator.MFRRReplayResult:
                "open_energy_lab.simulator.restoration_service",
            simulator.RestorationSettlement:
                "open_energy_lab.simulator.restoration_settlement",
            simulator.settle_restoration_services:
                "open_energy_lab.simulator.restoration_settlement",
        }
        for exported, owner in expected_owners.items():
            assert exported.__module__ == owner
        assert adapters.isdisjoint(sys.modules)
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", source],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


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
