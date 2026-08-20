# Feature Specification: TPM-Backed Planning And Simulator Dataset Export

**Feature Branch**: `009-tpm-planning`  
**Created**: 2026-06-24  
**Status**: Draft  
**Input**: User description: "Migrate the legacy TPM code closely enough to reuse its well-structured feature typing, SPN training, and planning-oriented encodings; add simulator output export so planning datasets can include horizon-indexed fields such as ghi_0, ghi_1, load_0, load_1, and shortfall; and formalize a planning exercise as an MILP over multiple simulation instances with SPFlow and Pyomo as required, lazily imported project dependencies."

## Purpose *(mandatory)*

Add a unified-library TPM and planning capability that turns simulator family
evaluations into stable tabular planning datasets, migrates the selected
tractable probabilistic model workflow from `legacy/old_tpm` into a native
`open_energy_lab` package, and uses the resulting artifacts to evaluate
chance-constrained design decisions across multiple simulated uncertainty
instances. The feature moves Open Energy Lab toward a reusable research library
by replacing notebook-only and legacy-only TPM workflows with versioned
artifacts, explicit dataset contracts, and a bounded planning surface with
lazy backend loading.

## Clarifications

### Session 2026-06-24

- Q: Should the legacy TPM code be treated as a close migration candidate or
  only as loose conceptual reference? → A: Treat it as a close migration
  candidate where behavior is already structured and can be validated with
  fixtures or existing legacy tests.
- Q: Should simulator export, TPM learning, and planning formulation be split
  into unrelated features? → A: No. The first planning-capable slice should
  cover the full end-to-end path from simulator family outputs to TPM-ready
  datasets and then to a planning problem that consumes those artifacts.
- Q: Should the default review path require live services, notebooks, or solver
  licenses? → A: No. Default validation remains offline and fixture-backed,
  with required SPFlow and Pyomo installations; checks needing separately
  managed solver binaries or licenses may remain follow-up validation.
- Q: Should the first release depend on ad hoc notebook column meanings such as
  `shortfall` or `y_blackout`? → A: No. The new library must define an
  explicit library-owned target contract for the planning adequacy event and
  document how it is derived from simulator outcomes.
- Q: Which legacy-style `shortfall` definition should the first release
  standardize on? → A: Use the horizon-level energy ratio: unmet electric load
  energy divided by total horizon electric load energy.
- Q: What should the first-release planning decision surface be? → A: Optimize
  native typed decision variables directly, including the supported binary,
  categorical, continuous, and mixed feature types within documented bounds.
- Q: How should the first-release adequacy threshold be handled? → A:
  Configure it per planning problem, with a documented default used only for
  fixtures, examples, and routine validation.
- Q: What should the first-release canonical solver-facing TPM formulation be?
  → A: Use a canonical piecewise approximation for the solver-facing planning
  path.
- Q: Which design variables should the first-release planning problem
  optimize? → A: Optimize battery and solar decision variables in the first
  release.
- Q: What adequacy constraint should the first-release planning MILP enforce?
  → A: Enforce a direct chance constraint `P(shortfall > threshold) <=
  epsilon`, with caller-configurable `epsilon`.

### Session 2026-08-17

- Q: How should SPFlow and Pyomo be installed while preserving lightweight
  imports? → A: Make SPFlow and Pyomo required project dependencies installed
  by default, but import them lazily at their workflow boundaries.
- Q: What solver availability should the standard installation and CI
  guarantee? → A: Require an open-source solver for routine end-to-end CI and
  support Gurobi additionally when it is available.
- Q: Which open-source solver should be required for routine Pyomo execution?
  → A: Require HiGHS through the `highspy` Python package as the default
  solver.
- Q: May TPM queries automatically fall back to empirical or metadata-only
  behavior when a real SPFlow payload is unavailable? → A: No. Require
  SPFlow by default and permit empirical replay only through an explicit
  fixture/test mode.
- Q: Which SPFlow API compatibility target should the first release require?
  → A: Preserve the validated TPM behavior from `legacy/old_tpm`, but port
  it to a current supported SPFlow release rather than constraining Python to
  the legacy `spn.*` package generation.

### Session 2026-08-19

- Q: How should multiple solar/storage designs be simulated? → A: Sweep a
  Cartesian grid of explicit equipment options and evaluate every design with
  the same absolute-indexed uncertainty samples.
- Q: How should large studies persist rows? → A: Use resumable,
  checksummed schema-v2 shards with required JSONL and Parquet support and no
  artificial row-count ceiling.
- Q: How should storage dispatch work? → A: Reuse the shipped named
  controllers through the controller runner, defaulting solar/storage studies
  to PV self-consumption. Equipment power values are request limits; the
  controller follows the current site-load/PV residual within those limits,
  while the simulator enforces battery and grid feasibility.
- Q: Which adequacy targets are supported? → A: One active binary event per
  artifact derived from a shortfall-ratio, absolute unmet-energy, or
  unmet-timestep-fraction threshold.
- Q: How is the encoded optimum trusted? → A: Solve the MIO directly, then
  validate only the selected design against native SPFlow; a material mismatch
  is a failed workflow result, not a warning or brute-force replacement.

## Scope Classification *(mandatory)*

- **Feature type**: Migration plus new library capability
- **Target surface**: Public library API, persisted data artifact, and TPM-backed
  optimization workflow
- **Legacy reference paths**:
  - `legacy/old_tpm/src_py/tpm/data/datahandler.py`
  - `legacy/old_tpm/src_py/tpm/data/encoding.py`
  - `legacy/old_tpm/src_py/tpm/data/features/feature.py`
  - `legacy/old_tpm/src_py/tpm/data/features/binary.py`
  - `legacy/old_tpm/src_py/tpm/data/features/categorical.py`
  - `legacy/old_tpm/src_py/tpm/data/features/contiguous.py`
  - `legacy/old_tpm/src_py/tpm/data/features/mixed.py`
  - `legacy/old_tpm/src_py/tpm/data/types.py`
  - `legacy/old_tpm/src_py/tpm/spn/main.py`
  - `legacy/old_tpm/src_py/tpm/spn/encoding.py`
  - `legacy/old_tpm/src_py/tpm/spn/utils_tangent.py`
  - `legacy/old_tpm/src_py/tpm/spn/test_tangent_lower_bound.py`
  - `legacy/old_tpm/src_py/utils/densities.py`
  - `legacy/old_tpm/src_py/simulator/feature_engineering.py`
- **New-code location**:
  - `src/open_energy_lab/tpm`
  - `src/open_energy_lab/planning`
  - `src/open_energy_lab/simulator`
  - matching validation under `tests/unit`, `tests/integration`, and
    `tests/fixtures`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Export TPM-Ready Planning Datasets From Simulator Families (Priority: P1)

As a library user, I need simulator family outputs to be exported into stable
tabular planning datasets so that I can train TPMs and inspect planning inputs
without rebuilding the data assembly logic in notebooks.

**Why this priority**: Without a stable dataset contract, TPM training and
planning remain notebook-owned workflows and cannot become reusable library
capabilities.

**Independent Test**: A reviewer can load committed weather and
weather-conditioned demand family fixtures plus associated design metadata,
export a planning dataset offline, and verify deterministic row counts,
documented flattened column names, explicit `shortfall` targets, and persisted
provenance metadata.

**Acceptance Scenarios**:

1. **Given** one evaluated simulator family, horizon-aligned weather and demand
   traces, and caller-provided design metadata, **When** the export workflow is
   executed, **Then** it produces a versioned planning dataset artifact with
   one row per simulation instance and stable flattened feature columns such as
   `ghi_0`, `ghi_1`, `load_0`, `load_1`, and `shortfall`.
2. **Given** per-step simulator outcomes that include unmet electric load and
   any needed adequacy thresholds, **When** the dataset export derives the
   planning target, **Then** the `shortfall` target is computed from an
   explicit documented library rule as the horizon-level unmet electric energy
   ratio rather than an implicit notebook-only convention.
3. **Given** the same simulator results, export configuration, and seed-backed
   fixtures, **When** the export workflow is rerun, **Then** it reproduces the
   same row ordering, column ordering, target values, and provenance metadata.

---

### User Story 2 - Fit, Reload, And Query TPM Artifacts (Priority: P2)

As a researcher, I need to fit and later reload a TPM artifact from exported
planning datasets so that I can evaluate conditional risk and likelihood
queries without retraining or rebuilding feature encodings every time.

**Why this priority**: The migrated TPM becomes reusable only when the SPN,
feature schema, and query semantics are owned by the library rather than by
legacy scripts or notebooks.

**Independent Test**: A reviewer can fit a real current-SPFlow model from the
committed planning dataset, persist and reload its model sidecar, and reproduce
conditional probability and log-likelihood results within the documented
tolerances. Explicit fixture replay is supplementary and cannot satisfy this
test by itself.

**Acceptance Scenarios**:

1. **Given** a committed planning dataset and one explicit target definition,
   **When** the TPM fit workflow is executed, **Then** it produces a versioned
   artifact that preserves feature schema, target metadata, training
   configuration, and provenance needed for later offline use.
2. **Given** a persisted TPM artifact and a query that specifies decision
   features while marginalizing non-decision features, **When** the query is
   evaluated for the configured `shortfall` target, **Then** it returns
   reproducible conditional probability or log-likelihood outputs aligned with
   the documented TPM semantics.
3. **Given** a real current-SPFlow artifact whose graph belongs to the supported
   compiler subset, **When** the artifact is compiled by the
   current-SPFlow-to-piecewise-MIO compiler, **Then** its conditional
   probabilities differ from native SPFlow likelihood evaluation by at most
   `1e-6`, and repeated canonical-seed evaluations agree within `1e-9`.
   Fixture replay remains supplementary evidence only.

---

### User Story 3 - Solve Chance-Constrained Planning Problems From TPM Artifacts (Priority: P3)

As a planner or simulator maintainer, I need a formal planning surface that
chooses a design across multiple uncertainty instances using a fitted TPM and
deterministic cost data so that the design exercise is reproducible and no
longer hidden inside notebooks.

**Why this priority**: The planning capability is the consumer-facing reason to
promote simulator export and TPM migration into the unified library.

**Independent Test**: A reviewer can load a real current-SPFlow artifact,
compile its supported graph into the solver-neutral piecewise-MIO
representation, assemble the consuming Pyomo MILP, and solve both feasible and
infeasible cases with HiGHS, reproducing the selected design, objective, risk,
termination status, and solver metadata.

**Acceptance Scenarios**:

1. **Given** decision feature definitions, deterministic design costs, a fitted
   TPM artifact, a `shortfall` threshold, and a caller-configurable chance
   limit `epsilon`, **When** the planning problem is solved, **Then** it
   returns one minimum-cost feasible design from native battery and solar
   decision variables that satisfies the documented chance constraint
   `P(shortfall > threshold) <= epsilon`, together with estimated shortfall
   risk, objective value, and feasibility diagnostics.
2. **Given** the same planning problem data, the same TPM artifact, and the
   same solver configuration, **When** the solve is repeated, **Then** it
   returns the same selected design and the same risk and cost summary, or the
   same deterministic infeasibility diagnostics when no feasible design exists.
3. **Given** a standard project installation with HiGHS, **When** the planning
   surface is validated in the default review path, **Then** model assembly,
   input validation, fixture-backed checks, and a real Pyomo-backed solve all
   complete successfully without a commercial solver license.

### Edge Cases

- Export is requested for simulator results whose horizons, timestep labels, or
  scenario ordering do not align.
- Caller-provided design metadata is missing for some simulation instances or
  uses inconsistent feature names across rows.
- The first-release `shortfall` target is asked to mix electric adequacy and
  cooling-service adequacy without an explicit documented aggregation rule.
- A planning dataset contains feature values outside the fitted TPM feature
  bounds or unseen categorical values not covered by the persisted schema.
- A TPM query supplies an out-of-bound continuous value, unseen category, or
  invalid binary value; validation identifies the feature, expected domain,
  supplied value, and reason before invoking SPFlow.
- A TPM query omits a required decision feature; validation identifies the
  missing feature, expected domain, and reason before invoking SPFlow, with no
  supplied value.
- A TPM query requests multiple incompatible target definitions from one
  first-release single-target artifact.
- A production TPM query lacks a valid SPFlow payload; the workflow fails
  explicitly rather than silently substituting empirical or metadata-only
  results.
- A required SPFlow, Pyomo, or `highspy` dependency is missing or incompatible
  because the project installation is incomplete, or a separately managed
  supplemental solver backend is unavailable.
- The planning model is asked to optimize over unsupported continuous,
  categorical, or mixed decision variables beyond the migrated legacy feature
  support.
- The caller requests inverter or broader equipment decisions in the first
  release even though the canonical planning surface is limited to battery and
  solar variables.
- Notebook-only exploratory behavior, sweep configs, or experiment tracking are
  treated as required runtime behavior even though the feature keeps them out of
  the default validation path.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST add a library-owned workflow that exports
  simulator family outputs into persisted planning datasets without requiring
  notebook execution.
- **FR-002**: The dataset export workflow MUST accept caller-provided design
  metadata for every simulation instance and MUST validate that those design
  features align with the exported simulator rows.
- **FR-003**: The dataset export workflow MUST define a stable flattened
  feature naming convention for horizon-indexed weather, demand, and outcome
  series, including documented aliases such as `ghi_<step>`, `load_<step>`,
  and `shortfall`.
- **FR-004**: The feature MUST define the first-release `shortfall` target as
  an explicit library-owned planning target equal to unmet electric load energy
  divided by total horizon electric load energy, with documented threshold and
  aggregation semantics, and MUST NOT leave its meaning implicit in notebooks
  or ad hoc scripts.
- **FR-005**: The feature MUST add a TPM capability that fits, persists,
  reloads, and queries SPN artifacts from exported planning datasets.
- **FR-006**: The TPM capability MUST preserve typed feature-schema handling
  for continuous, binary, categorical, and mixed features where that behavior
  is supported by the selected legacy TPM sources.
- **FR-006a**: The first-release current-SPFlow compiler MUST support sum and
  product composition with one output channel and one repetition; Normal leaves
  for continuous features; Bernoulli leaves for binary features; Categorical
  leaves for categorical features; and models that mix these concrete leaf
  types across separate scopes. It MUST reject arbitrary Torch modules,
  unsupported custom leaves, multiple channels or repetitions, uncompileable
  shared subgraphs, and legacy histogram payloads without explicit conversion,
  reporting the unsupported module type and scope.
- **FR-007**: The TPM query surface MUST support marginalization of
  non-decision variables and conditional probability or log-likelihood
  evaluation for the configured planning target.
- **FR-007a**: Production TPM fit-query workflows MUST use the real SPFlow
  backend and MUST fail explicitly when a valid SPFlow payload is unavailable.
  Empirical replay MAY be retained only behind an explicit fixture/test mode
  and MUST NOT activate automatically as a production fallback.
- **FR-008**: The feature MUST define versioned planning dataset and TPM
  artifact contracts that preserve provenance, training configuration, feature
  schema, target metadata, and reproducibility inputs.
- **FR-009**: The planning capability MUST formalize a deterministic
  cost-minimization problem over native typed decision variables evaluated
  against multiple simulated or learned uncertainty instances.
- **FR-010**: The planning capability MUST report chosen design values,
  objective value, estimated risk, and feasibility diagnostics for adequacy-
  or chance-constrained planning problems driven by the explicit `shortfall`
  target.
- **FR-010a**: The first release MUST support direct optimization over the
  selected native decision-variable types required by the first-release battery
  and solar planning surface, and MUST defer any additional categorical or
  mixed decision support unless it is covered by explicit fixtures and tests,
  rather than limiting planning to pre-enumerated catalog selection.
- **FR-010b**: The adequacy threshold for `shortfall` MUST be configurable per
  planning problem, while fixture-backed validation and examples MAY define a
  documented default threshold.
- **FR-010c**: The first-release canonical solver-facing TPM formulation MUST
  use the documented current-SPFlow-to-piecewise-MIO compiler. Its
  solver-neutral MIO representation MUST be consumed by the Pyomo MILP, and
  any non-canonical approximations MUST be explicitly marked as deferred or
  secondary.
- **FR-010d**: The first-release planning surface MUST optimize battery and
  solar decision variables only, and MUST defer inverter or broader equipment
  decision sets unless a later spec expands the planning scope.
- **FR-010e**: The first-release planning adequacy rule MUST enforce a direct
  chance constraint `P(shortfall > threshold) <= epsilon`, where `epsilon` is
  configurable per planning problem and remains distinct from the configurable
  `shortfall` threshold.
- **FR-011**: The first release MUST treat SPFlow as the canonical TPM
  fit-query backend and Pyomo as the canonical planning-model backend. Both
  MUST be declared as required project dependencies installed by default while
  remaining lazily imported at their TPM and planning workflow boundaries. The
  supported SPFlow contract MUST target a current supported SPFlow API and
  MUST port the validated fit, marginalization, query, persistence, and
  solver-facing behavior from `legacy/old_tpm` without retaining a runtime
  dependency on the obsolete `spn.*` package generation.
- **FR-012**: The default validation path MUST remain offline and
  fixture-backed and MUST NOT require notebooks, W&B, live weather fetches,
  GPU or SLURM tooling, or commercial solver licenses. It MUST exercise a real
  SPFlow fit-query path and a real Pyomo solve with HiGHS through `highspy`;
  follow-up validation guidance MUST document Gurobi-backed planning checks as
  an additional supported workflow.
- **FR-013**: The feature MUST identify exact legacy TPM files whose behavior
  is preserved, improved, or rejected, and MUST avoid runtime imports from
  `legacy/*`.
- **FR-014**: The feature MUST define numeric tolerances, random-seed behavior,
  solver-configuration reproducibility expectations, and deterministic fixture
  baselines for export, TPM query, and planning workflows.
- **FR-014a**: Canonical fixtures MUST use seed `13` for Python, NumPy, Torch,
  SPFlow, and solver randomness; `1e-9` fit, query, repeated-HiGHS-solve,
  objective, and risk repeatability tolerances; `1e-6` MIO epsilon and maximum absolute
  native-SPFlow-versus-compiled probability error; `5` piecewise breakpoints;
  and HiGHS settings of one thread and a 30-second per-fixture time limit. A
  robustness check MUST additionally exercise fixed seeds `37` and `101`
  without treating them as canonical fixture baselines.
  When Gurobi is available, comparison against HiGHS is supplementary evidence
  and MUST use a tolerance documented for the tested formulation; it is not a
  completion requirement.
- **FR-015**: The first release MUST bound scope to one explicit planning
  target and one horizon-flattened planning dataset contract per artifact,
  deferring broader multi-target or notebook-driven experimentation.

### Legacy Reference Requirements *(include for migration features)*

- **Source paths**:
  - `legacy/old_tpm/src_py/tpm/data/datahandler.py`
  - `legacy/old_tpm/src_py/tpm/data/encoding.py`
  - `legacy/old_tpm/src_py/tpm/data/features/feature.py`
  - `legacy/old_tpm/src_py/tpm/data/features/binary.py`
  - `legacy/old_tpm/src_py/tpm/data/features/categorical.py`
  - `legacy/old_tpm/src_py/tpm/data/features/contiguous.py`
  - `legacy/old_tpm/src_py/tpm/data/features/mixed.py`
  - `legacy/old_tpm/src_py/tpm/data/types.py`
  - `legacy/old_tpm/src_py/tpm/spn/main.py`
  - `legacy/old_tpm/src_py/tpm/spn/encoding.py`
  - `legacy/old_tpm/src_py/tpm/spn/utils_tangent.py`
  - `legacy/old_tpm/src_py/tpm/spn/test_tangent_lower_bound.py`
  - `legacy/old_tpm/src_py/utils/densities.py`
  - `legacy/old_tpm/src_py/simulator/feature_engineering.py`
- **Behavior to preserve**:
  - typed feature metadata and normalization semantics for continuous, binary,
    categorical, and mixed variables
  - SPN training, artifact reload, marginalization, and conditional query
    workflows
  - decision-variable encoding and the selected piecewise SPN-to-solver
    approximation behavior where validated by fixtures
- **Behavior to improve or drop**:
  - duplicate helper definitions, implicit global assumptions, and pickle-only
    workflows should be replaced by versioned artifact contracts
  - notebook-only orchestration, sweep configs, and experiment-service hooks
    should not be preserved as core runtime behavior
  - implicit target-name or target-position assumptions should become explicit
    library contracts
  - lower-tangent solver-facing formulations should not define the canonical
    first-release planning contract
- **Parity evidence**:
  - committed planning dataset fixtures and TPM artifact fixtures
  - fixture-backed conditional-probability and marginalization query cases
  - focused piecewise-approximation planning fixtures and solver-assembly
    checks

### Key Entities *(include if feature involves data or API design)*

- **Planning Dataset Artifact**: A versioned persisted artifact consisting of a
  tabular row set plus explicit metadata, with one row per simulation
  instance, caller-provided design metadata, flattened horizon-indexed weather
  and demand fields, derived planning targets, and provenance metadata tying
  the dataset back to simulator families and seeds. The first release stores
  this artifact as JSON with a documented schema that preserves row ordering,
  column ordering, feature metadata, target semantics, and provenance.
- **TPM Artifact**: A versioned persisted probabilistic model artifact that
  stores feature schema, target definition, query assumptions, and
  reproducibility metadata together with the documented SPN payload
  representation or payload locator defined by the artifact schema version,
  enabling offline reload and risk evaluation.
  Current-SPFlow production artifacts use schema v2 with backend name,
  generation and API version, execution mode, payload format, project-relative
  payload locator, SHA-256 payload digest, compiler version, supported module
  types, training seed, and Torch determinism metadata. Schema-v1 legacy model
  payloads are retained only for incompatibility/refit validation.
- **Shortfall Target Definition**: A documented planning-target contract that
  names the target field, defines it as the horizon-level unmet electric energy
  ratio, states the threshold semantics, and records the simulator-side source
  signals used to derive the target.
- **Planning Problem Definition**: A bounded problem statement that defines
  battery and solar decision features, deterministic design costs, admissible
  bounds or categories, a caller-configurable `shortfall` threshold, a
  caller-configurable chance limit `epsilon`, TPM or dataset input references,
  and solver configuration metadata for direct typed-variable optimization.

### Dependency and Environment Requirements *(include if relevant)*

- **Core dependencies**: Python standard library, SPFlow, Pyomo, plus existing
  `open_energy_lab.simulator`, `open_energy_lab.weather`, and
  `open_energy_lab.demand` surfaces used to build fixture-backed planning
  datasets
- **Workflow backends**: A tested current SPFlow release for TPM fit-query,
  Pyomo for planning-model assembly, required HiGHS through `highspy` for
  routine solve execution, and Gurobi as an additionally supported backend
  when available
- **Python compatibility**: Initial CI MUST cover Python 3.11, 3.12, 3.13, and
  3.14. If the required locked stack cannot resolve on one version, the project
  MUST narrow `requires-python` using recorded compatibility evidence rather
  than skipping the failing required-backend job.
- **External services**: None in the default review workflow; the configurable
  notebook may explicitly fetch PVGIS 5.3 when no compatible canonical cache is
  present
- **Hardware assumptions**: CPU-only local validation by default; no GPU or
  scheduler requirement accepted for the routine review path

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can export at least one committed fixture-backed
  planning dataset from simulator family results and obtain deterministic row
  counts, column ordering, and target values across repeated runs.
- **SC-002**: A reloaded real current-SPFlow artifact reproduces conditional
  probability and log-likelihood query outputs within `1e-9` across repeated
  canonical-seed runs, and its compiled probability differs from native SPFlow
  by at most `1e-6` absolute error.
- **SC-003**: The planning surface either selects the same feasible
  minimum-cost design across repeated fixture-backed runs with fixed inputs and
  solver configuration, or returns the same deterministic infeasibility
  diagnostics when no feasible design exists.
  Repeated objectives and reported risk values MUST differ by no more than
  `1e-9` for the canonical fixture configuration.
- **SC-003a**: Routine offline CI completes at least one real SPFlow fit-query
  cycle and one real Pyomo-backed optimization with HiGHS through `highspy`;
  neither path is replaced solely by fake-backend validation.
- **SC-004**: Ordinary `open_energy_lab` imports do not eagerly import SPFlow or
  Pyomo, while a correctly installed project includes both dependencies and
  exposes installation or compatibility failures when the corresponding TPM or
  planning workflow is invoked. Ordinary imports remain independent of any
  separately managed solver binary or license.
- **SC-005**: The configurable autonomy notebook exposes the 24-hour Abu Dhabi
  defaults, produces independent 16,000/4,000/4,000-row manifests in a full
  acceptance run, compiles real SPFlow candidates, executes HiGHS, and blocks
  recommendation whenever calibration, parity, or the one-sided 95% held-out
  risk bound fails.

## Assumptions

- Researchers will use the first release through library-owned workflows. A
  notebook may configure and present those workflows but does not own event,
  simulation, TPM, calibration, or solve semantics.
- The first release planning dataset is built from current deterministic or
  family-evaluation simulator surfaces and caller-provided design metadata
  rather than from a new full design-sweep simulator subsystem.
- The first-release planning target is one explicit adequacy target derived
  from simulator outcomes; broader multi-target planning remains future work.
- The first-release planning problem uses direct native decision variables,
  although exported datasets may still be generated from design sweeps or
  sampled design metadata during TPM fitting.
- The first-release planning scope is intentionally limited to battery and
  solar decisions; inverter and broader equipment planning remain future work.
- The first-release adequacy rule is a direct chance constraint on threshold
  exceedance probability, with the acceptable exceedance probability
  (`epsilon`) configured separately from the `shortfall` threshold itself.
- Gurobi-backed validation may be skipped in environments without its solver
  binary or license, but the required HiGHS validation MUST pass.
