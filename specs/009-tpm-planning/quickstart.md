# Quickstart: TPM-Backed Planning And Simulator Dataset Export

Use this quickstart to review the planned simulator-export, TPM, and planning
feature before implementation and to confirm the expected validation boundary.

## Preserve / Improve / Reject

Keep these migration decisions in mind:

- Preserve: simulator-owned family evaluation semantics, the legacy TPM typed
  feature model where it is already structured, and optional solver-facing
  SPN encodings validated by fixtures.
- Improve: explicit versioned planning dataset and TPM artifact contracts,
  library-owned `shortfall` semantics, and stable public APIs under
  `open_energy_lab.simulator`, `open_energy_lab.tpm`, and
  `open_energy_lab.planning`.
- Reject: notebook-only dataset assembly, pickle-only artifact ownership,
  runtime imports from `legacy/*`, and mandatory SPFlow or solver installs in
  the routine review path.

## Review The Feature

```bash
sed -n '1,360p' specs/009-tpm-planning/spec.md
sed -n '1,360p' specs/009-tpm-planning/plan.md
sed -n '1,360p' specs/009-tpm-planning/research.md
sed -n '1,360p' specs/009-tpm-planning/data-model.md
```

Confirm the intended split:

- simulator export is owned by `open_energy_lab.simulator`
- TPM feature typing, fit, reload, and query are owned by
  `open_energy_lab.tpm`
- planning problem assembly and optional solving are owned by
  `open_energy_lab.planning`
- `shortfall` is one horizon-level energy-ratio target, not an implicit
  notebook variable
- battery and solar are the only first-release planning decision sets

## Review The Contracts

```bash
sed -n '1,240p' specs/009-tpm-planning/contracts/simulator-export-contract.md
sed -n '1,240p' specs/009-tpm-planning/contracts/planning-dataset-contract.md
sed -n '1,240p' specs/009-tpm-planning/contracts/tpm-artifact-contract.md
sed -n '1,240p' specs/009-tpm-planning/contracts/planning-solve-contract.md
sed -n '1,240p' specs/009-tpm-planning/contracts/validation-contract.md
```

Before implementation, make sure the contracts agree on:

- stable `<field>_<step>` flattened naming
- exact `shortfall` derivation from simulator unmet-load signals
- explicit feature typing and ordering
- canonical piecewise approximation metadata
- direct chance-constraint semantics
- optional dependency and solver boundaries

## Review The Current Library Surfaces

```bash
sed -n '1,220p' src/open_energy_lab/simulator/__init__.py
sed -n '1,320p' src/open_energy_lab/simulator/stochastic_demand.py
sed -n '220,620p' src/open_energy_lab/simulator/scenario.py
sed -n '1,220p' src/open_energy_lab/demand/__init__.py
sed -n '1,220p' src/open_energy_lab/planning/__init__.py
sed -n '1,220p' tests/unit/test_optional_dependency_boundaries.py
sed -n '1,220p' tests/unit/test_import_contract.py
```

Confirm from these files that:

- current simulator families already expose the signals needed for shortfall
  derivation and flattened export
- root packages are lazy and import-light
- `open_energy_lab.planning` is still a scaffold and can now be expanded
  under an explicit spec
- optional-dependency boundaries already exist and should be extended rather
  than relaxed

## Review The Legacy Evidence

```bash
sed -n '1,240p' legacy/old_tpm/src_py/tpm/data/datahandler.py
sed -n '1,240p' legacy/old_tpm/src_py/tpm/data/encoding.py
sed -n '1,280p' legacy/old_tpm/src_py/tpm/spn/main.py
sed -n '1,280p' legacy/old_tpm/src_py/tpm/spn/encoding.py
sed -n '1,240p' legacy/old_tpm/src_py/tpm/spn/utils_tangent.py
sed -n '1,220p' legacy/old_tpm/src_py/utils/densities.py
sed -n '1,260p' legacy/old_tpm/src_py/simulator/feature_engineering.py
```

Use these files to confirm:

- typed feature classes and data handling are the main close-migration
  candidates
- SPN fit and query semantics come from the legacy `main.py` direction
- solver-facing encodings must be preserved selectively and documented
  explicitly
- legacy feature engineering is evidence for dataset-shaping ideas, not a
  direct runtime dependency

## Environment

The feature uses the current base library environment:

```bash
conda activate open-energy-lab
uv sync --dev
```

Default validation must remain offline and fixture-backed. SPFlow, Pyomo, and
solver binaries are optional follow-up dependencies, not routine review
requirements.

## Planned Review Checks

Run the checks relevant to the files changed:

```bash
uv run pytest tests/unit/planning tests/unit/tpm tests/integration/planning
uv run pytest tests/unit/test_optional_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run pytest tests/unit/demand tests/unit/simulator tests/integration/demand tests/integration/simulator
uv run python -c "import open_energy_lab; import open_energy_lab.simulator; import open_energy_lab.tpm; import open_energy_lab.planning"
rg "from legacy|import legacy" src/open_energy_lab/tpm src/open_energy_lab/planning src/open_energy_lab/simulator tests/unit/planning tests/unit/tpm tests/integration/planning docs/migration
```

Optional follow-up checks when dependencies are available:

```bash
cd legacy/old_tpm && pytest src_py/tpm/spn/test_tangent_lower_bound.py
```

If SPFlow, Pyomo, or a supported solver backend is unavailable, document the
skipped follow-up checks instead of widening the base environment.
