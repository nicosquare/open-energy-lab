# Visualization And Trace Inspection Migration Note

Status: foundational scaffolding in progress

This note reserves the migration-documentation home for the visualization and
trace-inspection MVP under `src/open_energy_lab/visualization`.

## Target Module Paths

- `src/open_energy_lab/visualization/__init__.py`
- `src/open_energy_lab/visualization/inspection.py`
- `src/open_energy_lab/visualization/comparison.py`
- `src/open_energy_lab/visualization/plotting.py`
- `src/open_energy_lab/visualization/_persistence.py`

## Planned Validation Paths

- `tests/unit/visualization/`
- `tests/integration/visualization/`
- `tests/fixtures/visualization/inspection_arbitrage_case.json`
- `tests/fixtures/visualization/inspection_battery_load_pv_case.json`
- `tests/fixtures/visualization/comparison_arbitrage_case.json`
- `tests/fixtures/visualization/persisted_arbitrage_case.json`

## Current Boundary

The completed foundational phases currently add:

- visualization-specific test-package markers and fixture helpers
- import-boundary and no-legacy-import checks for runtime visualization modules
- reserved package-root exports for inspection, comparison, and persisted-output
  loading helpers
- placeholder `inspection.py`, `comparison.py`, and `plotting.py` modules that
  keep the intended stable-versus-experimental split explicit
- persisted-output normalization and validation rules in
  `src/open_energy_lab/visualization/_persistence.py`

The feature still does not implement inspection views, comparison outputs, or
plot rendering in this phase. The new runtime modules reserve those seams
without changing simulator ownership of execution.

## Upstream Result Sources

The feature is planned to adapt current library result shapes from:

- `src/open_energy_lab/simulator/scenario.py`
- `src/open_energy_lab/simulator/controller_runner.py`
- `src/open_energy_lab/simulator/weather.py`
- `src/open_energy_lab/simulator/pv.py`

Legacy repositories remain reference-only in this phase. Exact cited legacy
paths, if any, should be recorded only when a later task adds concrete
preserve/improve evidence.

## Planned Preserve / Improve / Reject Sections

Later implementation phases should expand this note with:

- preserved deterministic inspection/reporting behaviors
- improved package-surface and dependency-boundary decisions
- rejected runtime coupling to plotting backends, notebook workflows,
  dashboards, and `legacy/*` imports
- fixture provenance and validation outcomes

## Foundational Decisions Recorded Here

- `open_energy_lab.visualization` now uses lazy package-root exports so
  inspection/reporting helpers can be promoted later without making plotting a
  package-root dependency.
- Persisted-output inputs are normalized through explicit schema rules that
  preserve supported scenario kinds, timestep alignment, settlement totals, and
  present-versus-absent section declarations.
- `src/open_energy_lab/visualization/plotting.py` exists only as an
  experimental placeholder in this phase and is intentionally excluded from the
  package-root export list.
