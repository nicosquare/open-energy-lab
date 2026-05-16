# Open Energy Lab

Open Energy Lab is being shaped into a unified Python research library for
energy-system simulation, optimization, learning, planning, control, and
analysis workflows.

The current `legacy/old_tpm` and `legacy/fed_trpo` directories are reference
material. New reusable product code belongs under `src/open_energy_lab`, with
tests under `tests`.

## Foundation Layout

```text
environment.yml
pyproject.toml
src/open_energy_lab/
tests/unit/
tests/integration/
tests/parity/
tests/fixtures/
docs/architecture/
docs/migration/
```

Roadmap package areas are scaffolded under `src/open_energy_lab`:

- `experimental`: immature migrations and incubating APIs.
- `simulator`: first likely migration area for simulator components.
- `core`: future reusable methods such as TPM, RL, MPC, optimization, and rules.
- `planning`: future interfaces or contracts only.
- `control`: future interfaces or contracts only.
- `visualization`: future inspection tools.

This foundation does not migrate algorithms, training loops, optimization
models, simulator internals, notebooks, W&B workflows, GPU/SLURM workflows, Rust
bindings, or legacy behavior.

## Environment

Create the minimal conda environment and let uv manage Python dependencies:

```bash
conda env create -f environment.yml
conda activate open-energy-lab
uv sync --dev
```

The foundation import path must not require solver stacks, TorchRL, PyTorch,
CityLearn, SPFlow, W&B, Jupyter, Rust tooling, GPU support, SLURM tooling, or
external data APIs.

## Documentation

- [Foundation architecture](docs/architecture/foundation.md)
- [API maturity policy](docs/migration/api-maturity.md)
- [Fixture provenance rules](tests/fixtures/README.md)
- [Active Spec Kit plan](specs/001-library-foundation/plan.md)

## Local Checks

Run the scaffold validation checks from the repository root:

```bash
uv run pytest tests/unit/test_import_contract.py tests/unit/test_module_scaffold.py
uv run python -c "import open_energy_lab"
```

After the legacy-isolation test is added, include:

```bash
uv run pytest tests/unit/test_no_legacy_imports.py
```

Do not add new reusable code to `legacy/*` unless a future migration,
reference-fix, or submodule-maintenance spec explicitly authorizes it.
