# Visualization And Trace Inspection Migration Note

Status: scaffold

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

Phase 1 adds scaffolding only:

- visualization-specific test-package markers
- reserved visualization fixture paths plus provenance placeholders
- this migration-note shell for later preserve/improve/reject details

No new runtime visualization behavior is implemented in this phase.

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
