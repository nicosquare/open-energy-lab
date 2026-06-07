# Quickstart: Unified Library Foundation

Use this quickstart to review the foundation plan and to guide the later
foundation implementation tasks. This feature defines architecture and
governance; it does not migrate algorithms.

## Review the Foundation

```bash
sed -n '1,240p' specs/001-library-foundation/spec.md
sed -n '1,260p' specs/001-library-foundation/plan.md
sed -n '1,240p' specs/001-library-foundation/research.md
```

Confirm the foundation decisions:

- New reusable code targets `src/open_energy_lab`.
- Tests target `tests/unit`, `tests/integration`, `tests/parity`, and
  `tests/fixtures`.
- `legacy/old_tpm` and `legacy/fed_trpo` are reference-only by default.
- Algorithm migrations are out of scope for this feature.

## Expected Scaffold After Foundation Implementation

```text
environment.yml
pyproject.toml
uv.lock
src/open_energy_lab/
tests/unit/
tests/integration/
tests/parity/
tests/fixtures/
docs/architecture/
docs/migration/
```

The scaffold may include empty package modules, README files, and import tests,
but it must not contain simulator, TPM, RL, optimization, weather, planning, or
control implementations.

## Create the Foundation Environment

```bash
conda env create -f environment.yml
conda activate open-energy-lab
uv sync --dev
```

The conda environment should include only Python, uv, and bootstrapping tools.
Python project dependencies, dev dependencies, editable installs, locking, and
command execution are handled by uv.

If your local conda configuration still points at default Anaconda channels and
blocks `conda env create`, create the same minimal environment directly from
conda-forge and then continue with `uv sync --dev`:

```bash
conda create -y -n open-energy-lab --override-channels -c conda-forge python=3.11 uv pip
conda activate open-energy-lab
uv sync --dev
```

## Verify the Scaffold After Tasks Are Implemented

```bash
uv run pytest tests/unit
uv run python -c "import open_energy_lab"
rg "from legacy|import legacy" src/open_energy_lab tests/unit
```

These checks should pass without installing solver stacks, TorchRL, PyTorch,
CityLearn, SPFlow, W&B, Jupyter, Rust tooling, GPU support, SLURM tooling, or
external data API credentials.

Expected result for the legacy-import scan: no matches.

## Checks Intentionally Not Run

The foundation feature does not run or require:

- Solver-backed optimization checks that depend on commercial licenses.
- W&B, notebook, GPU, SLURM, or external data API workflows.
- Rust parity or legacy simulator execution.
- Parity cases for migrated behavior, because no algorithms are migrated in
  this feature.

The dedicated unit test for legacy-import isolation is not part of the current
completed scaffold and remains a separate task if you want that guardrail
implemented directly in `tests/unit`.

## Prepare a Future Migration Spec

Before migrating behavior from `legacy/*`, fill the relevant contracts:

```text
specs/001-library-foundation/contracts/migration-spec.md
specs/001-library-foundation/contracts/dependency-classification.md
specs/001-library-foundation/contracts/fixture-provenance.md
```

Each future migration should identify:

- Exact legacy source paths.
- Behavior to preserve, improve, and reject.
- Target module path under `src/open_energy_lab`.
- Public API maturity: private, experimental, or stable.
- Dependency classifications and import boundaries.
- Validation evidence, optional focused parity checks, fixtures, seeds,
  tolerances, and environment assumptions.

## Prepare the Next Simulator Migration

Use [contracts/simulator-preparation.md](./contracts/simulator-preparation.md)
for the next simulator spec. The simulator migration should start with battery
arbitrage, synthetic data, and a component graph containing batteries, price
signals, market interaction, time grids, units, and minimal load/PV components
only where needed for the validation case.
