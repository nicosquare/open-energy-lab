# Visualization And Trace Inspection Migration Note

Status: US1 arbitrage inspection, US2 weather-aware inspection, and US3 same-family comparison shipped; plotting remains experimental

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
- `tests/fixtures/visualization/persisted_battery_load_pv_case.json`

## Current Boundary

The completed US1, US2, and US3 slice now ships:

- stable package-root exports for `build_inspection_view`,
  `summarize_inspection_view`, and `load_persisted_run_output`
- stable arbitrage inspection over direct simulator traces,
  controller-driven evaluation results, and supported persisted outputs
- stable battery-load-PV inspection over direct simulator traces,
  controller-driven evaluation results, and supported persisted outputs
- stable same-family comparison through
  `open_energy_lab.visualization.comparison.compare_inspection_views`
- explicit present-versus-absent section reporting for arbitrage and
  battery-load-PV inspection surfaces
- persisted-output normalization plus stable loader metadata for later
  inspection reuse
- experimental static single-run plotting support through
  `open_energy_lab.visualization.plotting.plot_inspection_view`, including
  explicit plot-request metadata for in-memory versus persisted inputs

The feature still defers:

- any package-root plotting export
- rendered comparison plots
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

Preserved in US1, US2, and US3:

- simulator and controller modules remain the only execution owners
- arbitrage timestep ordering, dispatch values, price values, and settlement
  totals remain deterministic within absolute tolerance `1e-6`
- battery-load-PV load, PV, net-grid, weather-backed context, and settlement
  totals remain deterministic within absolute tolerance `1e-6`
- same-family comparison requests preserve the canonical inspection ordering
  and produce deterministic summary and trace deltas within absolute
  tolerance `1e-6`
- supported persisted outputs can be loaded for later review without rerunning
  a scenario

Improved in US1, US2, and US3:

- `open_energy_lab.visualization` now exposes a real stable inspection and
  reporting surface instead of placeholder behavior
- the visualization comparison module no longer reserves an unimplemented
  entry point for same-family comparisons
- committed visualization fixtures now include active arbitrage and
  battery-load-PV inspection evidence, arbitrage comparison evidence, and
  persisted-output coverage instead of scaffolds only
- weather-backed plotting requests now carry explicit `target_run`,
  `source_location`, and `requires_optional_backend` metadata without
  weakening the no-resimulation rule

Deferred beyond US3:

- experimental comparison plots or richer rendering backends
- any package-root comparison re-export if the stable root surface is widened
  later

## Shipped Stable Inspection Behavior

Stable package-root behavior:

```python
from open_energy_lab.visualization import (
    build_inspection_view,
    load_persisted_run_output,
    summarize_inspection_view,
)
```

These helpers now support inspection from:

- direct `ArbitrageScenario.evaluate_trace()` outputs
- direct `BatteryLoadPVScenario.evaluate_trace()` outputs
- `evaluate_with_controller(... )` arbitrage results
- `evaluate_with_controller(... )` battery-load-PV results
- supported persisted arbitrage payloads
- supported persisted battery-load-PV payloads

Experimental plotting behavior remains outside the stable root contract:

```python
from open_energy_lab.visualization.plotting import plot_inspection_view
```

This plotting helper:

- consumes an existing inspection view or supported persisted output
- requires an injected backend with `render_static_plot(...)`
- does not rerun the simulator
- reports whether the input came from `in_memory` or `persisted_output`
- keeps optional weather-backed plotting bounded to series already exposed by
  the simulator-backed inspection view

## Same-Family Comparison Scope

US3 adds a deterministic comparison surface in the focused comparison module:

```python
from open_energy_lab.visualization.comparison import compare_inspection_views
```

This helper now:

- consumes two supported inspection views, or other supported deterministic
  inputs through the same inspection builder
- allows same-family comparisons only
- preserves the canonical left-run inspection series ordering in the aligned
  comparison output
- computes numeric trace deltas and summary deltas without rerunning
  simulation
- returns an explicit unsupported response when the scenario families differ,
  when a canonical series is absent, or when timestep alignment is not exact

Unsupported comparison behavior is intentionally explicit:

- `ArbitrageScenario` versus `BatteryLoadPVScenario` returns an immediate
  cross-family unsupported response
- same-family requests fail deterministically when a canonical series is
  missing from one run
- same-family requests fail deterministically when a canonical series has
  incompatible lengths or timestep labels

Rendered comparison plots remain deferred. The MVP comparison output is the
structured data returned by `compare_inspection_views`, not a plotting API.

## Weather-Aware Inspection Scope

The US2 battery-load-PV inspection surface includes:

- battery state, requested dispatch, and realized dispatch
- load, PV generation, net-grid power, net-grid energy, and direction
- import prices and settlement outcomes
- simulator-exposed weather context limited to `timestamp_utc`,
  `dry_bulb_air_temperature_c`, and
  `global_horizontal_irradiance_w_per_m2`

Weather reporting remains intentionally narrow:

- visualization does not derive new weather fields beyond the simulator-owned
  scenario surface
- arbitrage inspection continues to report `"weather": false` and does not
  invent weather, load, PV, or net-grid sections
- battery-load-PV persisted outputs must carry weather-backed series
  explicitly so later inspection and plotting do not depend on the original
  simulation process

## No-Weather Fallback

The shipped fallback behavior is explicit rather than inferred:

- `ArbitrageScenario` inspection views always keep `load`, `pv`, `net_grid`,
  and `weather` sections marked unavailable
- arbitrage plotting requests fail deterministically if callers request
  battery-load-PV or weather-only series names
- battery-load-PV plotting remains optional and experimental, but it accepts
  the same weather-backed inspection surface whether the input is an
  in-memory result or a supported persisted output

## Fixture Evidence

Active US1, US2, and US3 visualization fixtures:

- `tests/fixtures/visualization/inspection_arbitrage_case.json`
- `tests/fixtures/visualization/persisted_arbitrage_case.json`
- `tests/fixtures/visualization/inspection_battery_load_pv_case.json`
- `tests/fixtures/visualization/persisted_battery_load_pv_case.json`
- `tests/fixtures/visualization/comparison_arbitrage_case.json`

These fixtures are:

- synthetic, small, and reviewable
- based on current-library simulator and controller result shapes rather than
  a legacy runtime import
- aligned with the focused US1, US2, and US3 unit and integration suites

## Validation Outcomes

US1, US2, and US3 were validated locally with:

```bash
uv run pytest tests/unit/visualization/test_inspection.py tests/unit/visualization/test_persistence_schema.py tests/integration/visualization/test_inspection_arbitrage.py tests/integration/visualization/test_persisted_outputs.py tests/integration/visualization/test_plotting.py
uv run pytest tests/unit/visualization/test_weather_reporting.py tests/integration/visualization/test_inspection_battery_load_pv.py tests/integration/visualization/test_plotting_battery_load_pv.py
uv run pytest tests/unit/visualization/test_comparison.py tests/integration/visualization/test_comparison.py tests/integration/visualization/test_comparison_failures.py tests/integration/visualization/test_fixture_schema.py
uv run pytest tests/unit/visualization/test_package_surface.py tests/unit/visualization/test_import_boundary.py tests/unit/visualization/test_no_legacy_imports.py
uv run pytest tests/integration/simulator/test_controller_evaluation.py
python -m compileall src/open_energy_lab/visualization
```

No optional plotting backend installation was required for these checks because
the current plotting coverage uses an injected recording backend double.
