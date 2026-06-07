# Environment Assumptions

The foundation uses conda as the base environment and uv as the Python package
manager. That split keeps the project bootstrap simple while leaving ordinary
Python dependency resolution to uv.

## Base Environment

- Create the local research environment with conda.
- Keep the environment minimal: Python 3.11, uv, and pip are the bootstrap
  tools for the foundation.
- Avoid adding solver stacks, RL frameworks, notebook tooling, W&B, GPU
  runtime packages, SLURM clients, or Rust toolchains to the base environment.

Example:

```bash
conda env create -f environment.yml
conda activate open-energy-lab
uv sync --dev
```

## Python Package Manager

uv is the Python package manager for project dependencies, editable installs,
locking, and command execution.

- Keep runtime dependencies empty or minimal in `pyproject.toml`.
- Put test tooling and other development-only packages in dependency groups.
- Defer optional extras until a future capability spec explicitly requires
  them.

## Capability Boundaries

Treat environment-sensitive capabilities as non-core until a later spec
promotes them:

- Solver-backed optimization and commercial solver access.
- W&B logging and sweep workflows.
- GPU and CUDA execution.
- SLURM/HPC orchestration.
- External data APIs and authenticated services.
- Notebook-based workflows.
- Rust reference tooling and parity builds.

These capabilities may be documented and prepared for later migration, but
they must not block ordinary library import or the foundation unit tests.

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
