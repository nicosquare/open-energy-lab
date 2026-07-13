# Dependency Policy

This policy classifies dependency families before future migrations add them to
`open_energy_lab`. The foundation stays importable without solver stacks,
experiment tracking, GPU tooling, notebook tooling, or legacy reference
toolchains.

## Classification Record

Future specs must record dependency decisions with a review trail like this:

```text
Dependency:
Requested by:
Target module:
Classification:
Import boundary:
Install mechanism:
Fallback or skip behavior:
External service, license, hardware, or scheduler assumptions:
Rationale:
Alternatives considered:
```

## Classification Types

`core`

Required for ordinary import and basic use of the library. Core dependencies
should stay small, stable, and portable.

`optional`

Required only for a named capability or adapter. Optional dependencies should
stay behind module-level imports, extras, or clear error messages.

`external-service-backed`

Requires a network service, account, credential, or API such as W&B or a
weather/data service. These capabilities need documented offline or disabled
behavior where practical.

`hardware-bound`

Requires GPU, SLURM/HPC, or another execution-environment assumption. These
capabilities must not block core imports or ordinary tests.

`legacy-only`

Needed only to run, compare, or validate legacy reference behavior. These
dependencies must not become required for the unified package.

## Import Boundary Rules

- `import open_energy_lab` must not require optional research stacks.
- Stable public API imports must not trigger W&B login, solver license checks,
  GPU initialization, SLURM commands, Rust compilation, or external data API
  calls.
- Optional capability modules may raise clear dependency errors when used
  without their required extras or environment.
- Tests that require unavailable services, hardware, or licenses must be
  marked or separated so the default test subset remains runnable locally.

## TPM-Backed Planning Classification

The `009-tpm-planning` feature now ships stable simulator export, TPM
fit/reload/query, planning dataset reload, planning assembly, and optional
solve entry points without widening the ordinary import boundary. The review
record for the shipped slice is:

```text
Dependency: Python standard library modules plus existing open_energy_lab simulator, demand, weather, and planning package modules
Requested by: 009-tpm-planning
Target module: src/open_energy_lab/simulator/planning_export.py, src/open_energy_lab/tpm/artifact.py, src/open_energy_lab/tpm/data.py, src/open_energy_lab/tpm/features.py, src/open_energy_lab/tpm/fit.py, src/open_energy_lab/tpm/query.py, src/open_energy_lab/tpm/piecewise.py, src/open_energy_lab/tpm/optional_spflow.py, src/open_energy_lab/planning/__init__.py, src/open_energy_lab/planning/dataset.py, src/open_energy_lab/planning/problem.py, src/open_energy_lab/planning/piecewise.py, src/open_energy_lab/planning/optional_solver.py
Classification: core
Import boundary: allowed at import time for open_energy_lab.simulator, open_energy_lab.tpm, and open_energy_lab.planning, with package-root exports resolved lazily so ordinary imports, persisted artifact loading, empirical query replay, and planning assembly stay import-light
Install mechanism: base project environment via conda plus uv
Fallback or skip behavior: none; simulator export, persisted artifact handling, empirical query replay, and offline planning assembly are part of the normal library surface
External service, license, hardware, or scheduler assumptions: none
Rationale: the shipped TPM-planning slice must remain portable, offline-reviewable, and layered on top of the current simulator and artifact contracts instead of making notebook, solver, or SPFlow installations part of ordinary imports
Alternatives considered: keeping the package roots unpromoted or making backend-bound workflows unconditional runtime dependencies were rejected because they weaken discoverability or violate the constitution's import-light boundary
```

```text
Dependency: SPFlow
Requested by: 009-tpm-planning TPM fit workflows and any future backend-backed TPM extensions
Target module: src/open_energy_lab/tpm/fit.py and src/open_energy_lab/tpm/optional_spflow.py
Classification: optional
Import boundary: lazy; excluded from open_energy_lab and open_energy_lab.tpm imports until a caller invokes fit_tpm_artifact without an injected backend
Install mechanism: documented environment add-on for TPM workflow execution
Fallback or skip behavior: package-root TPM imports, persisted artifact reload, typed-feature handling, and deterministic empirical query replay continue to work without SPFlow; fit workflows raise a clear dependency error when the backend is unavailable
External service, license, hardware, or scheduler assumptions: none inherent, but local package installation is required
Rationale: SPFlow is the canonical TPM fit backend, but the default review path must stay offline and import-light
Alternatives considered: making SPFlow a core dependency or hiding the fit boundary behind private APIs were rejected because they either widen imports or weaken the documented public workflow
```

```text
Dependency: Pyomo plus downstream solver binaries or licenses
Requested by: 009-tpm-planning optional planning solve workflows
Target module: src/open_energy_lab/planning/optional_solver.py
Classification: optional for Pyomo and hardware-bound or external-service-backed for some solver backends depending on the solver family
Import boundary: lazy; excluded from open_energy_lab and open_energy_lab.planning imports until a caller invokes solve_planning_problem
Install mechanism: documented environment add-on for planning solve execution
Fallback or skip behavior: planning dataset reload and offline assembly remain available without Pyomo; solve workflows raise a clear dependency error or return a deterministic skipped summary when configured with skip_if_unavailable
External service, license, hardware, or scheduler assumptions: some solver choices may require commercial licenses or specialized local installations
Rationale: the feature treats Pyomo as the canonical planning-model backend while keeping solve-time dependencies out of routine imports and default review
Alternatives considered: making solver dependencies part of the base environment or deferring the solve surface until a solver is always present were rejected because they widen the default environment and weaken the shipped contract
```

```text
Dependency: pytest-based TPM/planning validation
Requested by: 009-tpm-planning
Target module: tests/unit/tpm, tests/unit/planning, tests/unit/simulator/test_planning_export.py, tests/integration/planning, tests/unit/test_optional_dependency_boundaries.py, tests/unit/test_import_contract.py, tests/unit/test_no_legacy_imports.py
Classification: optional
Import boundary: test-only; must not affect library runtime imports
Install mechanism: uv sync --dev
Fallback or skip behavior: if dev dependencies are unavailable, document TPM-planning validation as blocked rather than broadening runtime requirements
External service, license, hardware, or scheduler assumptions: none for the default fixture-backed subset; optional solve follow-ups may require extra local solver setup
Rationale: stable TPM-planning API promotion depends on deterministic unit, integration, import-boundary, and fixture evidence, but pytest remains non-runtime tooling
Alternatives considered: relying only on manual artifact inspection or optional backend-backed checks was rejected because it weakens repeatable review evidence for the shipped surface
```

## Weather-Conditioned Demand And Cooling-Aware Simulator Classification

The `008-weather-demand-modeling` feature now ships stable demand workflow
imports plus a cooling-aware simulator-family evaluation surface without
widening the ordinary runtime boundary. The review record for the shipped slice
is:

```text
Dependency: Python standard library modules plus existing open_energy_lab weather and simulator package modules
Requested by: 008-weather-demand-modeling
Target module: src/open_energy_lab/demand/__init__.py, src/open_energy_lab/demand/_aligned_history.py, src/open_energy_lab/demand/_weather_response.py, src/open_energy_lab/demand/fit.py, src/open_energy_lab/demand/artifact.py, src/open_energy_lab/demand/sampling.py, src/open_energy_lab/simulator/demand.py, src/open_energy_lab/simulator/stochastic_demand.py
Classification: core
Import boundary: allowed at import time for open_energy_lab.demand and open_energy_lab.simulator, with package-root exports resolved lazily so ordinary imports, offline artifact loading, offline demand sampling, and simulator-family evaluation stay import-light
Install mechanism: base project environment via conda plus uv
Fallback or skip behavior: none; the shipped demand workflow and simulator-family evaluation are part of the normal library surface
External service, license, hardware, or scheduler assumptions: none
Rationale: the first shipped demand feature must remain portable, offline-safe, and layered on top of the existing weather canonical contract and simulator execution surface instead of introducing notebook, service, or research-stack runtime assumptions
Alternatives considered: keeping the demand package root empty, forcing callers into focused implementation modules, or coupling the shipped workflow to live weather fetches or CityLearn-style runtime state were rejected because they weaken discoverability and violate the feature boundary
```

```text
Dependency: pytest-based demand, simulator, import-boundary, and fixture validation commands
Requested by: 008-weather-demand-modeling
Target module: tests/unit/demand, tests/unit/simulator, tests/integration/demand, tests/integration/simulator, tests/unit/test_optional_dependency_boundaries.py, tests/unit/test_import_contract.py, tests/unit/test_no_legacy_imports.py
Classification: optional
Import boundary: test-only; must not affect library runtime imports
Install mechanism: uv sync --dev
Fallback or skip behavior: if dev dependencies are unavailable, document demand-feature validation as blocked rather than broadening runtime requirements
External service, license, hardware, or scheduler assumptions: none
Rationale: stable demand API promotion depends on deterministic unit, integration, import-boundary, and fixture evidence, but pytest remains non-runtime tooling
Alternatives considered: relying only on ad hoc scripts or fixture inspection was rejected because it weakens repeatable evidence for the shipped surface
```

```text
Dependency: live weather fetches, CityLearn, notebooks, solver stacks, W&B, GPU/SLURM tooling, and legacy reference runtimes
Requested by: none for the shipped demand workflow and cooling-aware simulator slice
Target module: none in the stable open_energy_lab.demand package root or the stable demand-family simulator exports
Classification: external-service-backed, optional, hardware-bound, or legacy-only depending on family
Import boundary: excluded from open_energy_lab.demand package-root imports, offline artifact loading, offline demand sampling, and cooling-aware simulator-family evaluation
Install mechanism: none for this feature
Fallback or skip behavior: the default demand-feature review path remains fixture-backed and offline without them; any future blocked checks must be documented explicitly
External service, license, hardware, or scheduler assumptions: network access, credentials, commercial licenses, GPU runtime, SLURM access, notebook execution, or legacy checkout context may be required only outside the shipped default validation subset
Rationale: the feature deliberately keeps producer-side fitting, offline artifact replay, and simulator-side cooling accounting inside the lightweight library boundary rather than reopening the heavier research environment
Alternatives considered: treating live services or legacy runtime stacks as default prerequisites was rejected because it would violate the constitution’s dependency boundary and the spec’s offline-review requirement
```

## Known Dependency Families

Future specs should classify these before use:

- Solver and optimization: Pyomo, Gurobi, CPLEX/docplex.
- Probabilistic modeling: SPFlow and SPN/MIO support libraries.
- RL libraries and environment tooling: PyTorch, TorchRL.
- Legacy-only environment references: CityLearn.
- Experiment workflow: W&B, notebooks, sweep configs.
- Execution environment: GPU, CUDA, SLURM/HPC scripts.
- Rust parity and performance: Rust toolchain, cargo, binding generators.

## Controller Boundary MVP Classification

The `004-controller-boundary` feature keeps the stable controller surface and
simulator runner inside the existing lightweight library boundary. The review
record for this feature is:

```text
Dependency: Python standard library typing/dataclass support and existing open_energy_lab package modules
Requested by: 004-controller-boundary
Target module: src/open_energy_lab/core/controller.py, src/open_energy_lab/simulator/controller_runner.py, src/open_energy_lab/simulator/scenario.py
Classification: core
Import boundary: allowed at import time for open_energy_lab.core and open_energy_lab.simulator
Install mechanism: base project environment via conda plus uv
Fallback or skip behavior: none; these are part of the normal library surface
External service, license, hardware, or scheduler assumptions: none
Rationale: the stable controller contract and simulator-owned evaluation loop must stay import-light and portable
Alternatives considered: introducing Gym, TorchRL, CityLearn, solver, or Rust-backed runtime requirements was rejected for this MVP
```

```text
Dependency: pytest-based validation commands
Requested by: 004-controller-boundary
Target module: tests/unit/core, tests/unit/simulator, tests/integration/simulator
Classification: optional
Import boundary: test-only; must not affect library runtime imports
Install mechanism: uv sync --dev
Fallback or skip behavior: if dev dependencies are unavailable, document validation as blocked rather than broadening runtime requirements
External service, license, hardware, or scheduler assumptions: none
Rationale: controller-boundary evidence depends on deterministic unit and integration checks, but pytest is not a runtime dependency
Alternatives considered: ad hoc scripts were rejected because they weaken reproducible review evidence
```

```text
Dependency: PyTorch, TorchRL, CityLearn
Requested by: possible future controller adapters only for PyTorch/TorchRL; CityLearn remains legacy-only reference evidence
Target module: none in the stable MVP surface
Classification: optional for PyTorch/TorchRL; legacy-only for CityLearn
Import boundary: excluded from open_energy_lab.core and open_energy_lab.simulator import paths
Install mechanism: defer PyTorch/TorchRL to a future adapter-specific extra if ever adopted; do not define a CityLearn install path for product integration
Fallback or skip behavior: stable controller-boundary validation proceeds without them
External service, license, hardware, or scheduler assumptions: may imply larger local environments, but none are accepted as default assumptions here
Rationale: the spec preserves only the repeated observation-to-action idea, rejects training-environment wrappers and action-space abstractions from the stable core, and treats CityLearn as historical evidence rather than a future compatibility target
Alternatives considered: making RL stacks core dependencies or positioning CityLearn as an integration target was rejected because it would violate the import-light constitution boundary and the product direction
```

```text
Dependency: Solver stacks, W&B, GPU/SLURM tooling, Rust parity toolchains, legacy reference packages
Requested by: none for 004-controller-boundary runtime; only possible future parity or adapter workflows
Target module: none in the stable MVP surface
Classification: hardware-bound, external-service-backed, or legacy-only depending on family
Import boundary: excluded from open_energy_lab.core and open_energy_lab.simulator import paths
Install mechanism: none for this feature
Fallback or skip behavior: document skipped checks when those environments are unavailable; do not make them prerequisites for default validation
External service, license, hardware, or scheduler assumptions: commercial licenses, credentials, GPU runtime, SLURM access, Rust toolchains, or legacy checkout context may be required outside this MVP
Rationale: the controller boundary is validated on CPU with deterministic fixtures and does not reopen solver, experiment-service, HPC, or Rust migrations
Alternatives considered: coupling Phase 6 validation to these stacks was rejected as out of scope and brittle
```

## Native Controller Pack Classification

The `005-controller-pack` feature extends the stable control surface without
widening runtime dependencies beyond the existing lightweight library
boundary. The review record for this feature is:

```text
Dependency: Python standard library importlib/typing support and existing open_energy_lab core and simulator modules
Requested by: 005-controller-pack
Target module: src/open_energy_lab/control/__init__.py, src/open_energy_lab/control/_config.py, src/open_energy_lab/control/price_threshold.py, src/open_energy_lab/control/soc_guardrail.py, src/open_energy_lab/control/pv_self_consumption.py
Classification: core
Import boundary: allowed at import time for open_energy_lab.control, with package-root exports resolved lazily so ordinary imports stay import-light
Install mechanism: base project environment via uv-managed Python
Fallback or skip behavior: none; shipped native controllers are part of the normal library surface
External service, license, hardware, or scheduler assumptions: none
Rationale: the first shipped controller pack must remain portable, deterministic, and layered on top of open_energy_lab.core and open_energy_lab.simulator instead of introducing new runtime stacks
Alternatives considered: eager package-root imports, CityLearn adapters, RL frameworks, solver-backed planning, and notebook-first controller dependencies were rejected because they would weaken the ordinary import boundary
```

```text
Dependency: pytest-based controller-pack validation commands
Requested by: 005-controller-pack
Target module: tests/unit/control, tests/integration/control, tests/integration/simulator, tests/unit/test_optional_dependency_boundaries.py, tests/unit/test_no_legacy_imports.py, tests/unit/test_import_contract.py
Classification: optional
Import boundary: test-only; must not affect library runtime imports
Install mechanism: uv sync --dev
Fallback or skip behavior: if dev dependencies are unavailable, document validation as blocked rather than broadening runtime requirements
External service, license, hardware, or scheduler assumptions: none
Rationale: shipped-controller promotion depends on deterministic unit, integration, import-boundary, and preserved-path regression evidence, but pytest remains non-runtime tooling
Alternatives considered: relying only on ad hoc scripts or informal fixture review was rejected because it would weaken repeatable evidence for stable API promotion
```

```text
Dependency: PyTorch, TorchRL, CityLearn, solver stacks, W&B, notebook tooling, GPU/SLURM helpers, Rust parity toolchains, and legacy reference packages
Requested by: none for 005-controller-pack runtime; only possible future adapters, parity workflows, or legacy reference checks
Target module: none in the stable open_energy_lab.control surface
Classification: optional, external-service-backed, hardware-bound, or legacy-only depending on family
Import boundary: excluded from open_energy_lab.control package-root and controller module imports
Install mechanism: none for this feature
Fallback or skip behavior: controller-pack validation proceeds without them; any blocked future checks must be documented explicitly
External service, license, hardware, or scheduler assumptions: may require commercial licenses, credentials, GPU runtime, SLURM access, Rust toolchains, or legacy checkout context outside this feature
Rationale: the controller pack is intentionally current-step, CPU-default, and deterministic, so ordinary imports must not trigger research-stack initialization or legacy runtime coupling
Alternatives considered: making these stacks default dependencies or treating CityLearn as a compatibility target was rejected because it would violate the constitution’s dependency boundary
```

## Visualization Trace Inspection MVP Classification

The `006-visualization-traces` feature now ships stable inspection/reporting,
focused same-family comparison, and experimental plotting without widening the
ordinary import boundary. The review record for the shipped slice is:

```text
Dependency: Python standard library importlib plus collections/mapping validation support and existing open_energy_lab core and simulator modules
Requested by: 006-visualization-traces
Target module: src/open_energy_lab/visualization/__init__.py, src/open_energy_lab/visualization/inspection.py, src/open_energy_lab/visualization/comparison.py, src/open_energy_lab/visualization/_persistence.py
Classification: core
Import boundary: allowed at import time for open_energy_lab.visualization and open_energy_lab.visualization.comparison, with package-root helpers resolved lazily so ordinary imports stay import-light
Install mechanism: base project environment via uv-managed Python
Fallback or skip behavior: none; shipped inspection/reporting and same-family comparison are part of the normal library surface
External service, license, hardware, or scheduler assumptions: none
Rationale: visualization must remain a lightweight consumer of existing simulator and controller outputs rather than introducing new runtime stacks or a second execution path
Alternatives considered: eager package-root imports, visualization-owned execution behavior, and mandatory rendering dependencies were rejected because they would weaken the import boundary and confuse simulator ownership
```

```text
Dependency: pytest-based visualization validation
Requested by: 006-visualization-traces
Target module: tests/unit/visualization, tests/integration/visualization, tests/unit/test_optional_dependency_boundaries.py, tests/unit/test_import_contract.py
Classification: optional
Import boundary: test-only; must not affect library runtime imports
Install mechanism: uv sync --dev
Fallback or skip behavior: if dev dependencies are unavailable, document visualization validation as blocked rather than broadening runtime requirements
External service, license, hardware, or scheduler assumptions: none
Rationale: inspection/reporting promotion depends on deterministic unit, integration, import-boundary, import-contract, and no-legacy-import evidence, but pytest remains non-runtime tooling
Alternatives considered: relying on ad hoc fixture review or manual plotting checks was rejected because it weakens deterministic evidence for the shipped surface
```

```text
Dependency: concrete plotting backends plus notebook tooling, dashboards, W&B, GPU/SLURM helpers, solver stacks, and legacy reference packages
Requested by: optional experimental plotting workflows only
Target module: src/open_energy_lab/visualization/plotting.py and future visualization integrations only
Classification: optional, external-service-backed, hardware-bound, or legacy-only depending on family
Import boundary: excluded from open_energy_lab.visualization package-root imports; callers must opt in through open_energy_lab.visualization.plotting or later integrations
Install mechanism: defer any concrete plotting backend to a future extra or caller-managed dependency; the current plotting API relies on backend injection rather than a required runtime package
Fallback or skip behavior: base visualization imports, comparison imports, and persisted-output inspection proceed without them; blocked experimental-backend checks must be documented explicitly
External service, license, hardware, or scheduler assumptions: may require larger local environments, credentials, commercial licenses, or schedulers outside this feature
Rationale: plotting remains experimental and optional, so rendered output capabilities must not become prerequisites for ordinary inspection or comparison imports
Alternatives considered: making a plotting backend mandatory at package import time or re-exporting plotting from the package root was rejected because it violates the core dependency boundary for the unified library
```

## Stochastic Weather And Simulator Family Evaluation Classification

The `007-stochastic-weather` feature now ships the weather workflow and
simulator-family evaluation surface. The dependency review record for the
shipped slice is:

```text
Dependency: Python standard library modules plus existing open_energy_lab simulator/weather modules
Requested by: 007-stochastic-weather
Target module: src/open_energy_lab/weather/__init__.py, src/open_energy_lab/weather/_canonical.py, src/open_energy_lab/weather/tmy.py, src/open_energy_lab/weather/fit.py, src/open_energy_lab/weather/artifact.py, src/open_energy_lab/weather/sampling.py, src/open_energy_lab/weather/events.py, src/open_energy_lab/simulator/stochastic_weather.py
Classification: core
Import boundary: allowed at import time for open_energy_lab.weather and open_energy_lab.simulator, with both package roots resolving documented exports lazily
Install mechanism: base project environment via uv-managed Python
Fallback or skip behavior: none for the shipped offline load/sample/evaluate path
External service, license, hardware, or scheduler assumptions: none
Rationale: the shipped feature stays CPU-local, fixture-driven, and import-light while providing fit configuration, artifact loading, offline sampling, and simulator-family evaluation without widening the default runtime stack
Alternatives considered: eager package-root imports, moving fit/fetch into open_energy_lab.simulator, or deferring all public exports to focused modules were rejected because they weaken the intended stable user-facing boundary
```

```text
Dependency: pvlib and timezonefinder, with dataframe-style provider results typically supplied through pvlib's pandas-backed fetch path
Requested by: 007-stochastic-weather fit/fetch workflow
Target module: src/open_energy_lab/weather/tmy.py and live-fetch callers of src/open_energy_lab/weather/fit.py
Classification: core local dependencies for the promoted weather workflow plus external-service-backed when live PVGIS fetch is exercised
Import boundary: excluded from open_energy_lab.weather package-root imports, offline artifact loading, offline sampling, and open_energy_lab.simulator imports
Install mechanism: base project environment via uv-managed Python
Fallback or skip behavior: recorded-response fixtures remain the default review path when PVGIS network access is unavailable
External service, license, hardware, or scheduler assumptions: PVGIS network access for live fetches; no solver, GPU, scheduler, or account requirement accepted
Rationale: the promoted weather surface should work in a standard project environment without a second install step, while still keeping ordinary imports and offline artifact workflows service-free
Alternatives considered: keeping live-fetch tooling as a separate optional install was rejected because it weakens the first-class status of the shipped weather capability; treating network access as part of the default validation subset remains rejected because it harms reproducibility
```

```text
Dependency: pytest-based weather and simulator stochastic validation
Requested by: 007-stochastic-weather
Target module: tests/unit/weather, tests/unit/simulator, tests/integration/weather, tests/integration/simulator, tests/unit/test_optional_dependency_boundaries.py, tests/unit/test_import_contract.py, tests/unit/test_no_legacy_imports.py
Classification: optional
Import boundary: test-only; must not affect library runtime imports
Install mechanism: uv sync --dev
Fallback or skip behavior: if dev dependencies are unavailable, document validation as blocked rather than broadening runtime requirements
External service, license, hardware, or scheduler assumptions: none for the default subset
Rationale: stable API promotion depends on deterministic unit, integration, fixture-schema, import-boundary, and legacy-import evidence, but pytest remains non-runtime tooling
Alternatives considered: ad hoc scripts alone were rejected because they weaken repeatable validation evidence
```

```text
Dependency: legacy weather and simulator reference files under legacy/old_tpm
Requested by: 007-stochastic-weather migration evidence
Target module: docs, fixtures, and tests that cite legacy paths as preserve/improve/reject evidence
Classification: legacy-only
Import boundary: excluded from src/open_energy_lab runtime imports
Install mechanism: checked-out repo submodule only; no packaging path into the unified library
Fallback or skip behavior: if legacy reference material is unavailable, document the missing evidence source rather than importing or copying runtime code wholesale
External service, license, hardware, or scheduler assumptions: none
Rationale: the feature cites exact legacy files for selective evidence while keeping the shipped library runtime free of legacy coupling
Alternatives considered: runtime coupling to legacy reference code or whole-file migration was rejected by the repository constitution and feature spec
```
