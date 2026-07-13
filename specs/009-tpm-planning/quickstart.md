# Quickstart: TPM-Backed Planning And Simulator Dataset Export

Use this quickstart to review the implemented User Story 1 simulator-export
slice and User Story 2 TPM fit/query slice. The current repository now
includes a stable simulator-owned planning-dataset export surface, a stable
planning-dataset reload surface, a stable TPM fit/reload/query surface, and
committed offline fixtures for deterministic export replay, artifact review,
and query inspection.

## Preserve / Improve / Reject

Keep these migration decisions in mind while reviewing or extending the
feature:

- Preserve: simulator-owned family evaluation semantics, offline fixture-backed
  review, import-light package roots, and the legacy TPM typed feature model
  where it is already structured.
- Improve: explicit versioned planning dataset and TPM artifact contracts,
  library-owned `shortfall` semantics, stable public APIs under
  `open_energy_lab.simulator`, `open_energy_lab.tpm`, and
  `open_energy_lab.planning`, and committed active US1 and US2 fixtures for
  export replay, artifact reload, and query review.
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
- the currently implemented stable slices are dataset export/reload and TPM
  fit/reload/query
- planning model assembly and optional solve remain the later user story

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
- lazy backend and solver boundaries

## Review The Current Library Surfaces

```bash
sed -n '1,220p' src/open_energy_lab/simulator/__init__.py
sed -n '1,320p' src/open_energy_lab/simulator/planning_export.py
sed -n '1,320p' src/open_energy_lab/simulator/stochastic_demand.py
sed -n '220,620p' src/open_energy_lab/simulator/scenario.py
sed -n '1,220p' src/open_energy_lab/demand/__init__.py
sed -n '1,220p' src/open_energy_lab/planning/__init__.py
sed -n '1,280p' src/open_energy_lab/planning/dataset.py
sed -n '1,260p' src/open_energy_lab/tpm/__init__.py
sed -n '1,320p' src/open_energy_lab/tpm/features.py
sed -n '1,280p' src/open_energy_lab/tpm/fit.py
sed -n '1,320p' src/open_energy_lab/tpm/query.py
sed -n '1,220p' src/open_energy_lab/tpm/optional_spflow.py
sed -n '1,220p' tests/unit/test_optional_dependency_boundaries.py
sed -n '1,220p' tests/unit/test_import_contract.py
```

Confirm from these files that:

- current simulator families already expose the signals needed for shortfall
  derivation and flattened export
- root packages are lazy and import-light
- `open_energy_lab.planning` now ships the persisted dataset reload surface
  while broader model assembly remains scaffolded
- `open_energy_lab.tpm` now ships the lazy root exports, typed feature
  handling, persisted artifact contract, fit configuration capture, and query
  workflow needed for the current TPM slice
- dependency-boundary checks already exist and should be extended rather
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

Default validation must remain offline and fixture-backed. SPFlow and Pyomo
are canonical TPM and planning backends, but they must be loaded lazily so
routine package-import review does not require them. Solver binaries remain
follow-up dependencies rather than routine review requirements.

## Review The Committed US1 And US2 Fixtures

The repository now includes these active TPM-planning fixtures:

- `tests/fixtures/planning/planning_dataset_export_case.json`
- `tests/fixtures/tpm/planning_dataset_v1.json`
- `tests/fixtures/tpm/tpm_artifact_v1.json`
- `tests/fixtures/tpm/tpm_artifact_unsupported_version.json`
- `tests/fixtures/tpm/tpm_query_case.json`

Use them to confirm that:

- the export request fixes deterministic `scenario_index`-ordered design rows
- the flattened series contract is limited to
  `global_horizontal_irradiance_w_per_m2`, `site_electric_load_kw`, and
  `unmet_load_kw`
- the committed artifact preserves top-level JSON rows plus metadata rather
  than a wrapped dataframe payload
- provenance records the shared family seed and the source export fixture path
- the supported TPM artifact preserves explicit typed feature ordering,
  required decision features, canonical piecewise metadata, and a documented
  fake-backend SPN payload summary
- the query fixture records one deterministic request plus its expected
  response from the empirical replay path

## Implemented US1 Workflow Shape

The stable simulator export and planning reload workflow is:

1. Evaluate one aligned simulator family result and matching weather family.
2. Build `PlanningExportRequest(...)` with one design row per scenario,
   deterministic flattened series fields, and `target_name="shortfall"`.
3. Call `open_energy_lab.simulator.export_planning_dataset(...)`.
4. Persist the returned `PlanningDatasetArtifact` as JSON or inspect it
   directly in memory.
5. Reload the same payload offline through
   `open_energy_lab.planning.load_planning_dataset(...)`.

The current root-level public entry points are:

- `open_energy_lab.simulator.PlanningExportRequest`
- `open_energy_lab.simulator.export_planning_dataset`
- `open_energy_lab.planning.PlanningDatasetArtifact`
- `open_energy_lab.planning.load_planning_dataset`

## Implemented US2 Workflow Shape

The stable TPM fit/reload/query workflow is:

1. Reload the committed planning-dataset artifact through
   `open_energy_lab.planning.load_planning_dataset(...)`.
2. Fit a TPM artifact with `open_energy_lab.tpm.fit_tpm_artifact(...)`.
3. Persist the returned `TPMArtifact` as JSON or inspect it directly in
   memory.
4. Reload the same payload offline through
   `open_energy_lab.tpm.load_tpm_artifact(...)`.
5. Evaluate a deterministic query with
   `open_energy_lab.tpm.query_tpm_artifact(...)`.

The current root-level TPM entry points are:

- `open_energy_lab.tpm.TPMArtifact`
- `open_energy_lab.tpm.load_tpm_artifact`
- `open_energy_lab.tpm.TPMFeatureSpec`
- `open_energy_lab.tpm.normalize_training_data`
- `open_energy_lab.tpm.TPMFitConfig`
- `open_energy_lab.tpm.fit_tpm_artifact`
- `open_energy_lab.tpm.TPMQueryRequest`
- `open_energy_lab.tpm.query_tpm_artifact`
- `open_energy_lab.tpm.PiecewiseApproximationMetadata`
- `open_energy_lab.tpm.build_piecewise_metadata`
- `open_energy_lab.tpm.SPFlowDependencyUnavailableError`

## Implemented Typed-Feature Migration

The current typed-feature slice preserves these first-release feature types:

- `continuous`
- `binary`
- `categorical`
- `mixed`

Keep these constraints in mind:

- feature ordering is persisted and must remain stable across fit and reload
- decision, context, and target roles stay explicit in artifact metadata
- categorical domains and numeric bounds are explicit because query validation
  depends on them
- the target feature remains `shortfall`

## Implemented `shortfall` Semantics

The first-release target is fixed as the horizon-level electric-energy ratio:

`shortfall = sum(unmet_load_kw * timestep_hours) / sum(site_electric_load_kw * timestep_hours)`

Keep these constraints in mind:

- `shortfall` is not a binary blackout label and is not mixed with cooling
  adequacy semantics.
- `threshold_default = 0.05` is recorded in dataset metadata for later TPM and
  planning workflows.
- the planning chance-limit `epsilon` is a later planning concern and remains
  distinct from the `shortfall` threshold itself.
- if total horizon load energy is effectively zero while unmet energy is
  non-zero, the dataset contract should fail fast rather than invent a ratio.

## Implemented Lazy SPFlow Boundary

The current TPM fit path treats SPFlow as canonical but lazy:

- importing `open_energy_lab.tpm` does not import SPFlow
- importing `open_energy_lab.tpm.fit` does not import SPFlow
- `fit_tpm_artifact(...)` only resolves the real backend when no injected
  backend is supplied
- unavailable real-backend behavior surfaces as
  `SPFlowDependencyUnavailableError`

This keeps routine review import-light while still documenting the real fit
boundary.

## After Implementation: Replay The Implemented US1 Export Workflow

Run the committed fixture-backed export integration path:

```bash
uv run pytest tests/integration/planning/test_dataset_export.py
```

Expected result:

- the export workflow replays entirely offline from committed weather and
  demand artifacts
- the produced dataset preserves deterministic row ordering and
  `<field>_<step>` flattened column naming
- the replayed artifact matches the committed
  `tests/fixtures/tpm/planning_dataset_v1.json` payload

## After Implementation: Reload The Committed US1 Artifact Offline

Use the committed planning-dataset artifact directly through the stable public
reload surface:

```bash
uv run python -c '
from pathlib import Path

from open_energy_lab.planning import load_planning_dataset

dataset = load_planning_dataset(Path("tests/fixtures/tpm/planning_dataset_v1.json"))

print(dataset.dataset_id)
print(tuple(dataset.column_order[:4]))
print(dataset.target_metadata["aggregation_rule"])
'
```

Expected result:

- dataset reload succeeds entirely offline from the committed JSON fixture
- the first columns remain `scenario_index`, `battery_capacity_kwh`,
  `solar_capacity_kw`, and `design_name`
- the aggregation rule stays explicit and reviewable without loading SPFlow,
  Pyomo, or solver binaries

## After Implementation: Reload The Committed US2 TPM Artifact Offline

Use the committed supported TPM artifact directly through the stable public
reload surface:

```bash
uv run python -c '
from pathlib import Path

from open_energy_lab.tpm import load_tpm_artifact

artifact = load_tpm_artifact(Path("tests/fixtures/tpm/tpm_artifact_v1.json"))

print(artifact.artifact_id)
print(tuple(artifact.query_configuration["required_decision_features"]))
print(artifact.spn_payload["backend_module"])
'
```

Expected result:

- TPM artifact reload succeeds entirely offline from the committed JSON fixture
- required decision features remain `battery_capacity_kwh`,
  `solar_capacity_kw`, and `design_name`
- the persisted SPN payload representation stays reviewable as
  `spflow.testing` metadata rather than an opaque pickle payload

## After Implementation: Replay The Committed US2 Query Fixture

Use the committed supported artifact and deterministic query fixture together:

```bash
uv run python -c '
import json
from pathlib import Path

from open_energy_lab.tpm import TPMQueryRequest, load_tpm_artifact, query_tpm_artifact

artifact = load_tpm_artifact(Path("tests/fixtures/tpm/tpm_artifact_v1.json"))
fixture = json.loads(Path("tests/fixtures/tpm/tpm_query_case.json").read_text())

result = query_tpm_artifact(
    artifact,
    TPMQueryRequest(
        decision_assignments=fixture["query_request"]["decision_assignments"],
        marginalized_features=tuple(fixture["query_request"]["marginalized_features"]),
        output_mode=fixture["query_request"]["output_mode"],
        target_name=fixture["query_request"]["target_name"],
    ),
)

print(result["source"])
print(result["matched_row_count"])
print(result["value"])
'
```

Expected result:

- the replay stays entirely offline from committed JSON fixtures
- the query result source is `empirical_fixture`
- the deterministic `baseline-a` request matches exactly one row and returns
  `0.0`

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
skipped backend-specific follow-up checks instead of widening the base
environment.
