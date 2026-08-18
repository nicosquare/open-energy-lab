# Environment Assumptions

The foundation uses conda as the base environment and uv as the Python package
manager. That split keeps the project bootstrap simple while leaving ordinary
Python dependency resolution to uv.

## Base Environment

- Create the local research environment with conda.
- Keep the environment minimal: Python 3.11, uv, and pip are the bootstrap
  tools for the foundation.
- Keep research stacks out of the conda bootstrap; uv owns Python runtime
  dependencies, including the required SPFlow, Pyomo, and HiGHS packages.
- Do not manually add commercial solvers, RL frameworks, notebook tooling,
  W&B, GPU runtime packages, SLURM clients, or Rust toolchains to the base
  environment.

Example:

```bash
conda env create -f environment.yml
conda activate open-energy-lab
uv sync --dev
```

## Python Package Manager

uv is the Python package manager for project dependencies, editable installs,
locking, and command execution.

- Keep runtime dependencies limited to stable, specified project workflows in
  `pyproject.toml`.
- The promoted stochastic weather surface now treats `pvlib`,
  `timezonefinder`, and the pandas-backed PVGIS fetch path as part of the
  normal project environment rather than a separate optional install.
- The TPM-planning surface requires `spflow`, `pyomo`, and `highspy` in the
  normal project environment. Their imports remain lazy until TPM fit/query or
  planning solve workflows run.
- Put test tooling and other development-only packages in dependency groups.
- Defer optional extras until a capability spec explicitly requires them;
  Gurobi remains a separately installed supplemental solver.

## Capability Boundaries

Treat environment-sensitive capabilities as non-core until a spec promotes
them. The 009 feature promotes CPU-local SPFlow and Pyomo/HiGHS, while keeping
their imports lazy. The remaining environment-sensitive capabilities include:

- Commercial solver access beyond the required HiGHS path.
- W&B logging and sweep workflows.
- GPU and CUDA execution.
- SLURM/HPC orchestration.
- External data APIs and authenticated services.
- Notebook-based workflows.
- Rust reference tooling and parity builds.

These capabilities may be documented and prepared for later migration, but
they must not block ordinary library import or the foundation unit tests.

## TPM-Backed Planning Notes

The `009-tpm-planning` feature keeps the same minimal conda bootstrap while uv
installs the required SPFlow, Pyomo, and HiGHS stack. Simulator export,
persisted artifact reload, TPM fit/query, planning assembly, and the HiGHS
solve remain offline and CPU-local.

## Default Validation Environment For TPM Planning

- Run the default TPM-planning checks from the local `open-energy-lab` conda
  environment after `uv sync --dev`.
- Assume CPU-only execution with required SPFlow, Pyomo, and `highspy`, but no
  commercial solver license, W&B login, GPU or SLURM tooling, notebook runtime,
  or runtime imports from `legacy/*`.
- Use committed planning and TPM fixtures together with routine real-SPFlow
  and real-HiGHS checks so export/reload behavior stays deterministic and the
  required production backends are exercised offline.
- Keep the default validation surface limited to
  `open_energy_lab.simulator` planning export, `open_energy_lab.tpm`,
  `open_energy_lab.planning`, their unit/integration tests, import checks,
  and the `legacy` import scan documented in the feature quickstart.

Example TPM-planning validation bootstrap:

```bash
conda activate open-energy-lab
uv sync --dev
uv run pytest tests/unit/planning tests/unit/tpm tests/integration/planning tests/integration/tpm
uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.simulator; import open_energy_lab.tpm; import open_energy_lab.planning"
```

## Required TPM-Planning Backend Assumptions

- Standard `uv sync --dev` installs SPFlow, Pyomo, and `highspy`; package-root
  imports remain lazy and must not load them before their workflows run.
- Production `fit_tpm_artifact(...)` and query workflows require a compatible
  current-SPFlow installation.
- `solve_planning_problem(...)` uses the required license-free HiGHS path by
  default through Pyomo.
- Missing or incompatible SPFlow, Pyomo, or HiGHS is a failed required-backend
  check, not a successful skip. Only explicitly selected supplemental Gurobi
  checks may skip when their binary or license is unavailable.

## Controller Boundary MVP Notes

The `004-controller-boundary` feature inherits the same minimal environment
shape and adds a few explicit assumptions for deterministic controller
validation.

## Default Validation Environment

- Run the controller-boundary checks from the local `open-energy-lab` conda
  environment after `uv sync --dev`.
- Assume CPU-only execution with no solver licenses, no W&B login, no GPU or
  SLURM tooling, no Rust compilation, and no external data credentials.
- Keep the validation surface limited to `open_energy_lab.core`,
  `open_energy_lab.simulator`, and their unit/integration tests.

Example validation bootstrap:

```bash
conda activate open-energy-lab
uv sync --dev
uv run pytest tests/unit/core tests/unit/simulator tests/integration/simulator
```

## Determinism and Validation Notes

- Validation is fixture-driven and should remain deterministic across repeated
  local runs.
- The controller-boundary quickstart assumes the default absolute numeric
  tolerance stays at `1e-6`.
- Import checks and legacy-import scans are part of the default evidence set
  because the feature promises an import-light stable API boundary.

## Skip Rules

- If the local environment does not have the dev dependencies needed for the
  pytest commands, record the missing setup in the feature quickstart instead
  of widening runtime dependencies.
- Do not treat solver stacks, RL frameworks, notebook tooling, W&B access,
  GPU runtimes, SLURM clients, or Rust parity tooling as prerequisites for
  this feature’s default validation path.

## Stochastic Weather Notes

The `007-stochastic-weather` feature keeps the same base environment shape and
adds explicit assumptions for weather fitting, offline sampling, and
simulator-family validation.

## Default Validation Environment For Weather

- Run the default weather and simulator-family checks from the local
  `open-energy-lab` conda environment after `uv sync --dev`.
- Assume CPU-only execution with no solver licenses, no W&B login, no GPU or
  SLURM tooling, no Rust compilation, and no live weather-service
  credentials.
- Treat recorded-response fixtures as the default fit-workflow evidence so the
  offline artifact-load, sampling, and simulator-family subset stays runnable
  without network access.
- Keep the default validation surface limited to `open_energy_lab.weather`,
  `open_energy_lab.simulator`, their unit/integration tests, import checks,
  and the `legacy` import scan documented in the feature quickstart.

Example weather validation bootstrap:

```bash
conda activate open-energy-lab
uv sync --dev
uv run pytest tests/unit/weather tests/integration/weather tests/integration/simulator
uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.weather; import open_energy_lab.simulator"
```

## Optional Live-Fetch Assumptions

- Live PVGIS fetches are outside the default validation subset even though the
  local dependency stack now ships with the project environment.
- If a reviewer exercises live fetch behavior, the run still depends on
  network access and the upstream PVGIS service.
- Any skipped live-fetch check should be documented as an optional follow-up,
  not reported as a failure of the default offline validation path.

## Weather-Conditioned Demand Notes

The `008-weather-demand-modeling` feature keeps the same base environment
shape and adds explicit assumptions for aligned-history fitting, offline
artifact replay, paired demand sampling, and cooling-aware simulator-family
validation.

## Default Validation Environment For Demand

- Run the default demand and simulator-family checks from the local
  `open-energy-lab` conda environment after `uv sync --dev`.
- Assume CPU-only execution with no solver licenses, no W&B login, no GPU or
  SLURM tooling, no CityLearn install, and no live weather-service
  credentials.
- Treat the committed demand and simulator fixtures as the default evidence so
  fit, reload, sampling, and cooling-accounting checks stay runnable offline.
- Keep the default validation surface limited to `open_energy_lab.demand`,
  the cooling-aware `open_energy_lab.simulator` family-evaluation path, their
  unit/integration tests, import checks, and the `legacy` import scan
  documented in the feature quickstart.

Example demand validation bootstrap:

```bash
conda activate open-energy-lab
uv sync --dev
uv run pytest tests/unit/demand tests/integration/demand tests/integration/simulator
uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.demand; import open_energy_lab.simulator"
```

## Optional Demand Follow-Up Assumptions

- The shipped demand review path does not require notebook execution, legacy
  runtime imports, or live weather fetches.
- If a reviewer exercises optional checks outside the default subset, record
  the blocked dependency or external assumption in the feature quickstart
  instead of widening runtime requirements.
