# TPM-Backed Planning Migration Note

Status: Phase 2 foundational scaffolding in place

Spec `009-tpm-planning` reserves the target library, fixture, and validation
paths for a simulator-owned planning-dataset export workflow, a native
`open_energy_lab.tpm` package, and a planning assembly surface that remains
offline-reviewable by default.

## Target Module Paths

- `src/open_energy_lab/simulator/planning_export.py`
- `src/open_energy_lab/tpm/__init__.py`
- `src/open_energy_lab/tpm/artifact.py`
- `src/open_energy_lab/tpm/data.py`
- `src/open_energy_lab/tpm/features.py`
- `src/open_energy_lab/tpm/fit.py`
- `src/open_energy_lab/tpm/query.py`
- `src/open_energy_lab/tpm/piecewise.py`
- `src/open_energy_lab/tpm/optional_spflow.py`
- `src/open_energy_lab/planning/__init__.py`
- `src/open_energy_lab/planning/dataset.py`
- `src/open_energy_lab/planning/problem.py`
- `src/open_energy_lab/planning/piecewise.py`
- `src/open_energy_lab/planning/optional_solver.py`

## Planned Validation Paths

- `tests/unit/tpm/`
- `tests/unit/planning/`
- `tests/unit/simulator/test_planning_export.py`
- `tests/integration/planning/`
- `tests/fixtures/planning/`
- `tests/fixtures/tpm/`

## Reserved Legacy Evidence Paths

- `legacy/old_tpm/src_py/simulator/data_generation.py`
- `legacy/old_tpm/src_py/simulator/feature_engineering.py`
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
- `legacy/old_tpm/src_py/utils/densities.py`

## Preserve / Improve / Reject

### Preserve

- simulator-side ownership of family evaluation semantics and dataset export
- typed feature metadata concepts already validated in the legacy TPM code
- canonical piecewise SPN-to-planning encoding evidence where the spec names
  exact legacy paths
- import-light package roots and offline default validation

### Improve

- explicit versioned planning-dataset and TPM artifact contracts
- library-owned `shortfall` target semantics and reproducibility metadata
- stable package paths under `open_energy_lab.simulator`,
  `open_energy_lab.tpm`, and `open_energy_lab.planning`
- committed deterministic fixtures for export, artifact reload, query, and
  planning assembly review

### Reject

- notebook-only dataset assembly or planning workflows
- pickle-only artifact ownership without a documented schema contract
- runtime imports from `legacy/*`
- mandatory SPFlow, Pyomo, or solver installation in the routine review path

## Phase 1 Scaffolding

Phase 1 reserved these concrete paths so later tasks could fill them with
validated behavior:

- `src/open_energy_lab/tpm/__init__.py`
- `tests/unit/tpm/__init__.py`
- `tests/unit/planning/__init__.py`
- `tests/integration/planning/__init__.py`
- `tests/fixtures/planning/README.md`
- `tests/fixtures/planning/planning_dataset_export_case.json`
- `tests/fixtures/planning/planning_problem_case.json`
- `tests/fixtures/tpm/README.md`
- `tests/fixtures/tpm/planning_dataset_v1.json`
- `tests/fixtures/tpm/tpm_artifact_v1.json`
- `tests/fixtures/tpm/tpm_artifact_unsupported_version.json`
- `tests/fixtures/tpm/tpm_query_case.json`

These placeholders were intentionally non-runtime scaffolds. They made the
feature structure explicit before foundational tests and implementations
arrived in later phases.

## Phase 2 Foundational Scaffolds

Phase 2 now adds import-light module scaffolds at the reserved runtime paths:

- `src/open_energy_lab/simulator/planning_export.py`
- `src/open_energy_lab/tpm/artifact.py`
- `src/open_energy_lab/tpm/data.py`
- `src/open_energy_lab/tpm/features.py`
- `src/open_energy_lab/tpm/fit.py`
- `src/open_energy_lab/tpm/query.py`
- `src/open_energy_lab/tpm/piecewise.py`
- `src/open_energy_lab/tpm/optional_spflow.py`
- `src/open_energy_lab/planning/dataset.py`
- `src/open_energy_lab/planning/problem.py`
- `src/open_energy_lab/planning/piecewise.py`
- `src/open_energy_lab/planning/optional_solver.py`

At this stage the new modules establish:

- explicit file ownership for simulator export, TPM artifact/data/query
  handling, and planning problem assembly
- placeholder dataclasses and entry-point function names that later user-story
  tasks can implement without moving file boundaries
- lazy backend boundary helpers for SPFlow and Pyomo so package and submodule
  imports remain clear of optional research stacks until the fit or solve
  paths are invoked directly

These Phase 2 modules are still scaffolds. They intentionally reserve the
runtime and documentation surface without claiming that dataset export, TPM
artifact reload, backend-backed querying, or planning-model solve behavior is
already implemented.
