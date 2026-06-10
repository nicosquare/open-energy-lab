# Visualization And Trace Inspection Migration Note

Status: US1 arbitrage inspection and persisted-output reuse shipped; plotting remains experimental

This note records the first shipped visualization and trace-inspection slice
under `src/open_energy_lab/visualization`.

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

The completed US1 slice now ships:

- stable package-root exports for `build_inspection_view`,
  `summarize_inspection_view`, and `load_persisted_run_output`
- stable arbitrage inspection over direct simulator traces,
  controller-driven evaluation results, and supported persisted outputs
- explicit present-versus-absent section reporting for the current arbitrage
  inspection surface
- persisted-output normalization plus stable loader metadata for later
  inspection reuse
- experimental static single-run plotting support through
  `open_energy_lab.visualization.plotting.plot_inspection_view`

The feature still defers:

- battery-load-PV and weather-aware inspection coverage
- same-family comparison behavior
- any package-root plotting export
- dashboards, notebooks, and visualization-owned execution flows

## Upstream Result Sources

The feature is planned to adapt current library result shapes from:

- `src/open_energy_lab/simulator/scenario.py`
- `src/open_energy_lab/simulator/controller_runner.py`
- `src/open_energy_lab/simulator/weather.py`
- `src/open_energy_lab/simulator/pv.py`

Legacy repositories remain reference-only in this phase. Exact cited legacy
paths, if any, should be recorded only when a later task adds concrete
preserve/improve evidence.

## Preserve / Improve / Defer

Preserved in US1:

- simulator and controller modules remain the only execution owners
- arbitrage timestep ordering, dispatch values, price values, and settlement
  totals remain deterministic within absolute tolerance `1e-6`
- supported persisted outputs can be loaded for later review without rerunning
  a scenario

Improved in US1:

- `open_energy_lab.visualization` now exposes a real stable inspection and
  reporting surface instead of placeholder behavior
- the stable package root no longer reserves unimplemented comparison helpers
- committed visualization fixtures now include active arbitrage inspection and
  persisted-output evidence instead of scaffolds only

Deferred beyond US1:

- battery-load-PV and weather-backed inspection details
- same-family comparison views and explicit unsupported cross-family behavior
- experimental comparison plots or richer rendering backends

## Shipped US1 Behavior

Stable package-root behavior:

```python
from open_energy_lab.visualization import (
    build_inspection_view,
    load_persisted_run_output,
    summarize_inspection_view,
)
```

These helpers now support arbitrage inspection from:

- direct `ArbitrageScenario.evaluate_trace()` outputs
- `evaluate_with_controller(... )` arbitrage results
- supported persisted arbitrage payloads

Experimental plotting behavior remains outside the stable root contract:

```python
from open_energy_lab.visualization.plotting import plot_inspection_view
```

This plotting helper:

- consumes an existing inspection view or supported persisted output
- requires an injected backend with `render_static_plot(...)`
- does not rerun the simulator

## Fixture Evidence

Active US1 visualization fixtures:

- `tests/fixtures/visualization/inspection_arbitrage_case.json`
- `tests/fixtures/visualization/persisted_arbitrage_case.json`

These fixtures are:

- synthetic, small, and reviewable
- based on the current-library arbitrage result shape rather than a legacy
  runtime import
- aligned with the focused US1 unit and integration suites

## Validation Outcomes

US1 was validated locally with:

```bash
uv run pytest tests/unit/visualization/test_inspection.py tests/unit/visualization/test_persistence_schema.py tests/integration/visualization/test_inspection_arbitrage.py tests/integration/visualization/test_persisted_outputs.py tests/integration/visualization/test_plotting.py
uv run pytest tests/unit/visualization/test_package_surface.py tests/unit/visualization/test_import_boundary.py tests/unit/visualization/test_no_legacy_imports.py
python -m compileall src/open_energy_lab/visualization
```

No optional plotting backend installation was required for these checks because
the current plotting coverage uses an injected recording backend double.
