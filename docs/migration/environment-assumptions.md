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
