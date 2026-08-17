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
examples/
src/open_energy_lab/
tests/unit/
tests/integration/
tests/parity/
tests/fixtures/
docs/architecture/
docs/migration/
```

Current library package areas under `src/open_energy_lab`:

- `weather`: fitted weather artifacts and offline sampling flows.
- `demand`: fitted demand artifacts and weather-conditioned demand sampling.
- `simulator`: scenario components, family evaluation, and planning-dataset
  export.
- `tpm`: typed-feature TPM artifacts, fit/query flows, optional SPFlow-backed
  runtime payloads, and SPN-to-MIO helpers.
- `planning`: planning-dataset reload, planning assembly, and optional
  Pyomo-backed solve flows.
- `experimental`, `control`, and `visualization`: incubating or still-thin
  areas.

The repository still treats `legacy/*` as reference material rather than
runtime code. Optional TPM/planning backends now exist, but they remain behind
lazy workflow boundaries instead of becoming mandatory root-import
dependencies.

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
- [Dependency policy](docs/migration/dependency-policy.md)
- [Environment assumptions](docs/migration/environment-assumptions.md)
- [TPM planning migration note](docs/migration/tpm-planning.md)
- [Tracked TPM planning examples](examples/tpm_planning/README.md)
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
