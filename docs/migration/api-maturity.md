# API Maturity Policy

This policy defines how `open_energy_lab` import paths become stable, remain
experimental, or stay private while the project migrates selected behavior from
legacy references.

## Stable Public API

An import path is stable public API when all conditions hold:

- It is documented as an `open_energy_lab.*` import outside
  `open_energy_lab.experimental`.
- It has focused tests under `tests/unit`, `tests/integration`, or
  `tests/parity`.
- Its dependencies are classified and do not unexpectedly import optional
  research stacks.
- Its expected behavior and compatibility expectations are documented.
- A migration or capability spec explicitly reviews the promotion.

Stable public APIs should preserve import paths and documented behavior across
future migrations unless a deprecation decision is recorded.

## Experimental-v1 Stacked-Services Surface

Feature `010-bess-stacked-services` publishes an **experimental-v1** API. The
module locations below are the stable homes for this capability, but their
individual signatures and result fields may still evolve through a recorded
specification change before promotion to stable API:

```text
open_energy_lab.market.artifact
open_energy_lab.market.activation
open_energy_lab.market.entsoe
open_energy_lab.control.stacked_service
open_energy_lab.simulator.stacked_service
open_energy_lab.simulator.fcr_settlement
```

Source-independent market artifact and activation types, deterministic baseline
builders, replay entities/functions, and settlement entities/functions are
also resolved lazily from their package roots. ENTSO-E acquisition remains a
focused-module operation and is deliberately not exported from
`open_energy_lab.market` because it is transport- and credential-bearing.

The default contract is offline: package import, canonical artifact loading,
schedule construction, replay, settlement, manual-oracle validation, and
normalized activation-fixture validation never read a credential or open a
network connection. Fetch, refresh, the live ENTSO-E compatibility case, raw
RTE fixture regeneration, and the reference-host benchmark are explicit
operations. Missing gated inputs fail closed; they do not trigger fetch,
substitution, interpolation, trimming, or synthetic repair.

The fixed public maturity is intentionally narrower than robust bidding. These
APIs accept or build deterministic fixed schedules and replay one BESS; they do
not optimize bids, inspect future activation, or claim robust SOC feasibility.

## Stable Public v1 Reference Robust-FCR Bidding Surface

Feature `013-reference-robust-fcr-bidding` promotes its immutable contracts,
constructors, solve functions, and reference-comparison entry points as stable
lazy exports from `open_energy_lab.control`. The complete symbol list is pinned
by `specs/013-reference-robust-fcr-bidding/contracts/python-api.md` and the
exact package export contract tests.

The stable scope is one ordinary delivery day, the 24/96/6 non-intraday
restriction/relaxation, routine HiGHS solve evidence, explicitly selected
optional Gurobi cross-backend evidence, independent equation audit,
charge-positive `FixedFCRBidPlan` extraction, and bounded normalized-reference
comparison. Exact Gurobi is optional evidence. Rolling horizons, multi-day SOC
carry-over, intraday recourse, scenarios, TPM bid selection, degradation, live
data, and broader reserve products are not part of this API.

Feature 013 reuses Feature 009's locked Pyomo/HiGHS dependency versions but
does not extend or call `open_energy_lab.planning`, consume TPM artifacts, or
change planning solver behavior. Its only operational handoff is to Feature
012: an eligible restriction returns the already public bidder-neutral
`FixedFCRBidPlan`, after which the existing evaluator alone owns activation,
physics, and realized settlement.

Reference statuses are `exact`, `source_precision_compatible`,
`alternative_optimum_compatible`, `mismatch`, and `unavailable`. They are
evidence categories, not API maturity levels. The selected 3,600-second native
benchmark owns the complete `native-reference-benchmark-highs-v1` policy and
fingerprint
`d4d8934676fce6755f525ef8844f796669e0ec49158a2107515b2dee29b682ed`;
the source fixture owns no native policy.

## Stable Public v1 Rolling FCR Study Surface

Feature `015-fcr-rolling-backtest-parity` promotes additive immutable rolling
contracts, orchestration, reference comparison, activation slicing, and
segmented replay composition as stable lazy exports. The exact symbol set and
behavior are pinned by
`specs/015-fcr-rolling-backtest-parity/contracts/python-api.md` and package
import-contract tests.

The stable `open_energy_lab.control` scope includes:

- five fixed executable profiles for scripts 11–15;
- versioned study manifests, accepted-bid policy, date classifications,
  numeric/carry policy, daily inputs, revisions, envelopes, state links,
  continuity segments, aggregates, results, persistence, and fail-closed
  resume assessment;
- additive exact-zero-FCR and 40-hour fixed-overlap problem/result contracts
  that reuse Feature 013's private formulation and solver machinery; and
- the normalized rolling fixture loader and source-precision/incumbent-aware
  comparison entry point.

`open_energy_lab.market.slice_regulation_activation_trace` is the stable
half-open realized-data slicing boundary.
`open_energy_lab.simulator.FCRAcceptedPlanSegment`,
`FCRSegmentedEvaluationReport`, and `evaluate_fixed_fcr_bid_segments` compose
Feature 012 replay without owning another transition or settlement model.
Every package root remains import-light; Pyomo, HiGHS, optional Gurobi, pandas,
baseline paths, and external data are absent until an explicit workflow asks
for their relevant boundary.

This maturity does not widen Feature 013's ordinary-day 24/96/6 public
contract. It also does not promote full-history execution, raw reference logs
or JSON, the external activation CSV, Julia, a licensed Gurobi environment, or
the source workbook into library API. The full four-date benchmark and
1,453-date workflow remain explicitly selected research commands.

Rolling comparison outcomes are evidence categories rather than maturity
levels. A time-limited source incumbent can be source-incumbent-equivalent or
an improved feasible incumbent compatible with its retained bound, but it is
never called an alternative optimum without sufficient two-sided optimality
and common-feasibility evidence. Unfinalized edges remain incomplete evidence,
and the bounded fixture makes no Table A1 or full-history parity claim.

### Feature 010 Single-Owner Matrix

| Responsibility ID | Responsibility | Single owner |
| --- | --- | --- |
| `OEL-F010-OWNER-RETRIEVAL` | ENTSO-E retrieval and market normalization | `open_energy_lab.market.entsoe` |
| `OEL-F010-OWNER-MARKET-ARTIFACT` | Market-artifact validity | `open_energy_lab.market.artifact` |
| `OEL-F010-OWNER-ACTIVATION` | Activation-artifact validity | `open_energy_lab.market.activation` |
| `OEL-F010-OWNER-SCHEDULES` | Deterministic fixed schedules | `open_energy_lab.control.stacked_service` |
| `OEL-F010-OWNER-PHYSICAL` | Battery-constrained physical delivery | `open_energy_lab.simulator.stacked_service` |
| `OEL-F010-OWNER-SETTLEMENT` | Day-ahead and FCR settlement | `open_energy_lab.simulator.fcr_settlement` |
| `OEL-F010-OWNER-ROBUST` | Robust bidding and optimization | later robust-bidding feature |

### TPM-Backed Planning Stable Surface

The `009-tpm-planning` feature now promotes the shipped simulator export,
planning dataset and assembly surface, and TPM fit/reload/query surface to
stable public API.

Stable simulator package-root imports:

```python
from open_energy_lab.simulator import (
    PlanningExportRequest,
    export_planning_dataset,
)
```

Stable planning package-root imports:

```python
from open_energy_lab.planning import (
    PlanningDatasetArtifact,
    PlanningProblemAssembly,
    PlanningProblemDefinition,
    PlanningSolveConfig,
    PlanningSolveSummary,
    PlanningSolverDependencyUnavailableError,
    PlanningSolverUnavailableError,
    assemble_planning_problem,
    load_planning_dataset,
    solve_planning_problem,
)
```

Stable TPM package-root imports:

```python
from open_energy_lab.tpm import (
    CURRENT_SPFLOW_ADAPTER_NAME,
    CURRENT_SPFLOW_BACKEND_GENERATION,
    REQUIRED_SPFLOW_VERSION,
    SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS,
    SUPPORTED_TPM_EXECUTION_MODES,
    CurrentSPFlowCapabilities,
    LegacyTPMArtifactVersionError,
    PiecewiseApproximationMetadata,
    PiecewiseBreakpointPolicy,
    SPFlowBackendCompatibilityError,
    SPFlowDependencyUnavailableError,
    SPNModelingTerms,
    SPNPiecewiseCurveSpec,
    SPNSolveConfig,
    SPNSolveSummary,
    SPNSolverDependencyUnavailableError,
    SPNSolverUnavailableError,
    TPMArtifact,
    TPMArtifactBuildRequest,
    TPMArtifactIntegrityError,
    TPMFeatureSpec,
    TPMFitConfig,
    TPMQueryRequest,
    TPMTrainingData,
    UnsupportedTPMArtifactVersionError,
    UnsupportedSPFlowModuleError,
    build_piecewise_metadata,
    build_spn_chance_model,
    build_spn_modeling_terms,
    compile_spflow_model_to_mio,
    detect_spflow_backend_capabilities,
    dump_feature_schema,
    evaluate_compiled_spflow_probability,
    extract_spn_solution,
    fit_tpm_artifact,
    fit_tpm_artifact_from_rows,
    infer_feature_role,
    infer_max_sum_terms,
    load_feature_schema,
    load_piecewise_metadata,
    load_tpm_artifact,
    normalize_training_data,
    query_tpm_artifact,
    register_spflow_backend_adapter,
    require_pyomo_backend,
    require_spflow_backend,
    solve_spn_chance_model,
    unregister_spflow_backend_adapter,
)
```

These imports are stable because they now have:

- focused unit and integration coverage for dataset export, persisted dataset
  reload, typed-feature normalization, real current-SPFlow fit/reload/query,
  sidecar integrity, compiler parity, planning problem validation, piecewise
  assembly, and required HiGHS optimal/infeasible solves
- deterministic committed fixtures for simulator export replay, persisted
  planning datasets, supported and unsupported TPM artifacts, explicit query
  replay, a real SPFlow 1.1 production sidecar, planning-problem assembly, and
  required HiGHS outcome expectations
- import-boundary, import-contract, lazy-dependency-boundary, and
  no-legacy-import coverage that names the simulator export, planning, and TPM
  roots explicitly
- migration documentation that records the simulator-owned export boundary,
  library-owned `shortfall` semantics, typed feature preservation,
  current-SPFlow artifact/compiler contracts, solver reproducibility
  expectations, and the offline review contract
- documented lazy dependency boundaries proving `open_energy_lab.simulator`,
  `open_energy_lab.planning`, and `open_energy_lab.tpm` stay import-light
  until callers explicitly invoke SPFlow-backed fit/query/compiler paths or
  Pyomo/HiGHS-backed solve paths

Stable API and required installation are separate promises. SPFlow 1.1.0,
Pyomo 6.10.1, and highspy 1.15.1 are standard project dependencies and are
loaded lazily at their workflow boundaries. Missing or incompatible versions
are workflow and validation failures, not supported skips. Gurobi is not part
of the required stable workflow; it is an explicitly selected supplemental
solver whose unavailable binary or license may produce a documented skip.

Focused module imports remain intentionally narrower in maturity:

```python
from open_energy_lab.simulator.planning_export import (
    PlanningExportRequest,
    export_planning_dataset,
)

from open_energy_lab.planning.dataset import PlanningDatasetArtifact, load_planning_dataset
from open_energy_lab.planning.problem import (
    PlanningProblemAssembly,
    PlanningProblemDefinition,
    assemble_planning_problem,
)
from open_energy_lab.planning.optional_solver import (
    PlanningSolveConfig,
    PlanningSolveSummary,
    PlanningSolverDependencyUnavailableError,
    PlanningSolverUnavailableError,
    solve_planning_problem,
)

from open_energy_lab.tpm.artifact import TPMArtifact, load_tpm_artifact
from open_energy_lab.tpm.data import TPMTrainingData, normalize_training_data
from open_energy_lab.tpm.features import TPMFeatureSpec
from open_energy_lab.tpm.fit import (
    TPMArtifactBuildRequest,
    TPMFitConfig,
    fit_tpm_artifact,
    fit_tpm_artifact_from_rows,
)
from open_energy_lab.tpm.mio import compile_spflow_model_to_mio
from open_energy_lab.tpm.piecewise import PiecewiseApproximationMetadata
from open_energy_lab.tpm.query import TPMQueryRequest, query_tpm_artifact
```

These focused imports host the shipped implementation and remain appropriate
for advanced callers and tests, but the stable user-facing contract for
ordinary use is the package-root surface shown above. The historical focused
module name `open_energy_lab.planning.optional_solver` describes lazy solver
loading; it does not make the default Pyomo/HiGHS solve an optional-install
capability.

### Weather-Conditioned Demand And Cooling-Aware Simulator Evaluation

The `008-weather-demand-modeling` feature now promotes the first shipped demand
workflow and simulator-side demand-family evaluation surface to stable public
API.

Stable demand package-root imports:

```python
from open_energy_lab.demand import (
    DemandSamplingRequest,
    fit_demand_model,
    load_demand_artifact,
    sample_demand_family,
)
```

Stable simulator package-root imports:

```python
from open_energy_lab.simulator import (
    DEMAND_SUPPORTED_SUMMARY_OUTPUT_FIELDS,
    DemandFamilyEvaluationRequest,
    DemandFamilyEvaluationResult,
    DemandScenarioEvaluationResult,
    evaluate_demand_family,
)
```

These imports are stable because they now have:

- focused unit and integration coverage for aligned-history validation,
  artifact schema and reload behavior, offline paired-family sampling,
  cooling-service configuration, paired-family alignment, and preserved
  deterministic `BatteryLoadPVScenario` behavior
- deterministic committed fixtures for aligned training history, supported and
  unsupported artifacts, offline sampled demand families, and local-electric
  versus district-cooling simulator-family baselines
- import-boundary, import-contract, and no-legacy-import coverage that names
  both `open_energy_lab.demand` and the demand-family simulator exports
  explicitly
- migration documentation that records the producer-versus-simulator
  ownership split, explicit non-thermal-versus-cooling separation, paired-seed
  replay contract, and simulator-side cooling settlement semantics
- documented dependency isolation proving package-root demand imports,
  offline artifact loading, offline demand sampling, and simulator-family
  evaluation remain import-light and clear of live-service assumptions

Focused imports remain intentionally narrower in maturity:

```python
from open_energy_lab.simulator.demand import (
    CoolingServiceConfiguration,
    DistrictCoolingTariff,
    LocalElectricCoolingConfiguration,
)
```

These cooling-service configuration types are part of the shipped workflow,
but they remain focused module imports instead of package-root simulator
exports so the stable root surface stays small.

Implementation-facing modules such as `open_energy_lab.demand._aligned_history`,
`open_energy_lab.demand._weather_response`,
`open_energy_lab.demand.fit`, `open_energy_lab.demand.artifact`,
`open_energy_lab.demand.sampling`, and
`open_energy_lab.simulator.stochastic_demand` remain the hosts for the
shipped logic. Callers may use those focused imports when needed, but the
stable user-facing contract for ordinary use is the package-root surface shown
above.

### Controller Boundary MVP

The `004-controller-boundary` feature promotes the following imports to stable
public API for the MVP:

```python
from open_energy_lab.core import (
    ControllerContext,
    ControllerEvaluationResult,
    ControllerInterface,
    DispatchProposal,
)

from open_energy_lab.simulator import evaluate_with_controller
```

These imports are stable because they now have:

- focused unit and integration coverage
- deterministic committed fixtures for both supported scenario families
- import-boundary checks proving they stay clear of optional research stacks
- no-legacy-import checks for the stable core package
- documented controller-boundary behavior, validation commands, and migration
  evidence

Supporting controller-boundary types that remain in
`open_energy_lab.core.controller` are intentionally narrower in maturity for
now. They may be used by package-internal code and focused validation, but
they are not yet promoted as root-level stable imports until a later spec
explicitly broadens the public surface.

### Native Controller Pack

The `005-controller-pack` feature promotes the following imports to stable
public API for the first shipped native controller surface:

```python
from open_energy_lab.control import (
    PVSelfConsumptionConfig,
    PVSelfConsumptionController,
    PriceThresholdConfig,
    PriceThresholdController,
    SocGuardrailConfig,
    SocGuardrailController,
)
```

These imports are stable because they now have:

- package-root export coverage tied to the documented support matrix
- typed configuration validation and `ControllerInterface` conformance tests
- deterministic controller-pack fixtures plus repeated-run runner checks
- import-boundary, import-contract, and no-legacy-import coverage that names
  `open_energy_lab.control` explicitly
- preserved-path regression evidence proving the controller pack does not
  replace explicit-dispatch or built-in simulator rule flows
- migration documentation that records behavior, dependency boundaries, and
  selective parity expectations

Supporting controller modules such as `open_energy_lab.control._config`,
`open_energy_lab.control.price_threshold`,
`open_energy_lab.control.soc_guardrail`, and
`open_energy_lab.control.pv_self_consumption` remain implementation-facing
modules. They are intentionally imported lazily through the package root so
ordinary `open_energy_lab.control` imports stay import-light while the stable
package-root surface remains fixed.

### Visualization Trace Inspection MVP

The `006-visualization-traces` feature now promotes the stable visualization
inspection/reporting root surface and keeps plotting explicitly experimental.

The package root now ships these stable public imports:

```python
from open_energy_lab.visualization import (
    build_inspection_view,
    load_persisted_run_output,
    summarize_inspection_view,
)
```

These imports are stable because they now have:

- focused unit and integration coverage for supported arbitrage and
  battery-load-PV inspection flows
- persisted-output validation and reuse checks that avoid re-simulation
- package-root import-boundary, import-contract, and no-legacy-import
  coverage naming `open_energy_lab.visualization` explicitly
- direct smoke coverage proving experimental plotting stays outside the stable
  root import path
- migration documentation that records stable inspection/reporting behavior,
  same-family comparison scope, and the experimental plotting split

Same-family comparison is also shipped user-facing behavior, but it remains a
focused module import rather than a package-root export:

```python
from open_energy_lab.visualization.comparison import compare_inspection_views
```

This comparison helper is intentionally not promoted into the package root
because the stable root contract for this MVP is inspection/reporting only,
while comparison remains discoverable through its dedicated module.

Experimental plotting remains outside the stable root contract:

```python
from open_energy_lab.visualization.plotting import plot_inspection_view
```

This plotting helper remains experimental because rendered output shape,
backend conventions, and future comparison-plot scope are still expected to
evolve. The package root now rejects root-level plotting access explicitly so
ordinary imports remain import-light and callers must opt in through the
focused plotting module.

### Stochastic Weather And Simulator Family Evaluation

The `007-stochastic-weather` feature now promotes the first shipped weather
workflow and simulator-side stochastic family evaluation to stable public API.

Stable weather package-root imports:

```python
from open_energy_lab.weather import (
    WeatherSamplingRequest,
    fit_weather_model,
    load_weather_artifact,
    sample_weather_family,
)
```

Stable simulator package-root imports:

```python
from open_energy_lab.simulator import (
    SUPPORTED_SUMMARY_OUTPUT_FIELDS,
    WeatherFamilyEvaluationRequest,
    WeatherFamilyEvaluationResult,
    WeatherScenarioEvaluationResult,
    evaluate_weather_family,
)
```

These imports are stable because they now have:

- focused unit and integration coverage for canonical normalization, artifact
  schema and reload behavior, offline family sampling, simulator family
  evaluation, blackout semantics, and preserved deterministic
  `BatteryLoadPVScenario` debugging
- deterministic committed fixtures for recorded fetch responses, fitted
  artifacts, sampled weather families, and simulator family baselines
- import-boundary, import-contract, and no-legacy-import coverage that names
  both `open_energy_lab.weather` and stochastic simulator exports explicitly
- migration documentation that records the stable fit/load/sample workflow,
  blackout semantics, summary-field limits, and the explicit boundary between
  artifact-preserved fields and simulator-consumed fields
- documented dependency isolation proving offline artifact loading, sampling,
  and simulator-family imports remain usable without live weather-service
  dependencies

Focused module imports remain intentionally narrower in maturity:

```python
from open_energy_lab.weather.fit import WeatherFitConfig
```

`WeatherFitConfig` is part of the shipped fit workflow, but it remains a
focused module import instead of a package-root export so the stable root
surface stays small.

Implementation-facing modules such as `open_energy_lab.weather._canonical`,
`.tmy`, `.fit`, `.artifact`, `.sampling`, `.events`, and
`open_energy_lab.simulator.stochastic_weather` remain the hosts for the shipped
logic. Callers may use those focused imports when needed, but the stable
user-facing contract for ordinary use is the package-root surface shown above.

## Experimental API

`open_energy_lab.experimental.*` is for immature migrations and incubating APIs.
Experimental APIs may change or move while behavior is being migrated,
validated, and reviewed.

Experimental placement does not remove quality requirements. Experimental code
still needs appropriate tests or smoke checks, dependency classification, and
clear documentation before users rely on it.

## Private API

Private modules and objects use a leading underscore or are undocumented
implementation details. They are not user-facing contracts and may change
without deprecation.

Examples:

```text
open_energy_lab.simulator._internal
open_energy_lab.core._legacy_adapter
```

## Promotion Rules

Promotion from private or experimental to stable requires:

- Target import path and user-facing purpose.
- Validation evidence, including parity cases when migrated from `legacy/*`.
- Dependency classification.
- Documentation update.
- Explicit review in the migration or capability spec.

Promotion must not make solver licenses, W&B accounts, GPU/SLURM tooling,
notebooks, Rust builds, or external data APIs required for ordinary package
imports unless a later spec explicitly accepts that tradeoff.

## Deprecation Rules

Deprecating stable public API requires:

- A recorded reason in the relevant spec, changelog, or migration note.
- A replacement path or explicit statement that no replacement exists.
- A compatibility expectation for how long the old path remains available.
- Tests or documentation updates that make the transition visible.

Experimental and private APIs may change faster, but changes should still be
documented when users or future migration specs are expected to notice them.
