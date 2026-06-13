# Visualization Fixtures

This directory is reserved for deterministic visualization validation cases
that build on current `open_energy_lab.simulator` and `open_energy_lab.core`
outputs without adding new runtime behavior to `legacy/*`.

## Shipped Fixture Set

The current visualization MVP ships five committed fixture records:

- `inspection_arbitrage_case.json`
- `persisted_arbitrage_case.json`
- `inspection_battery_load_pv_case.json`
- `persisted_battery_load_pv_case.json`
- `comparison_arbitrage_case.json`

Together they cover stable single-run inspection, supported persisted-output
reuse, weather-aware battery-load-PV reporting, and deterministic same-family
comparison without re-simulation.

## Required Provenance Record

Each committed visualization fixture should keep a nearby record with at least
these fields:

```text
Fixture path:
Purpose:
Status:
Origin:
Source current-library fixture or run output:
Exact legacy reference paths consulted, if any:
Generation command:
Random seed:
Scenario family:
Inspection expectations:
Comparison expectations:
Plot expectations:
Numeric tolerance:
Why the fixture is small enough to commit:
Refresh policy:
```

## Coverage Map

- `inspection_arbitrage_case.json`: stable single-run inspection coverage for
  arbitrage results across direct simulator traces and controller-driven
  evaluation outputs
- `inspection_battery_load_pv_case.json`: stable single-run inspection
  coverage for battery-load-PV results, including supported weather context
- `comparison_arbitrage_case.json`: same-family deterministic comparison
  coverage for arbitrage runs
- `persisted_arbitrage_case.json`: persisted-output reuse coverage for later
  inspection and plotting without re-simulation
- `persisted_battery_load_pv_case.json`: persisted-output reuse coverage for
  weather-aware battery-load-PV inspection and experimental plotting without
  re-simulation

## Fixture Provenance Records

`inspection_arbitrage_case.json`

- fixture path: `tests/fixtures/visualization/inspection_arbitrage_case.json`
- purpose: stable arbitrage inspection expectations across direct simulator
  traces and controller-driven evaluation results
- status: active
- origin: manually curated deterministic visualization fixture derived from
  current-library result shapes
- source current-library fixture: `tests/fixtures/simulator/controller_arbitrage_case.json`
- exact legacy reference paths consulted, if any: none
- generation command: `uv run pytest tests/integration/visualization/test_inspection_arbitrage.py tests/unit/visualization/test_inspection.py`
- random seed: none
- scenario family: `ArbitrageScenario`
- inspection expectations: stable series ordering, units, summary outcomes,
  and explicit availability markers for unavailable optional sections
- comparison expectations: none
- plot expectations: none
- numeric tolerance: `1e-6`
- why it is committed: it is small, synthetic, reviewable, and records the
  shipped ordering, units, availability markers, and settlement expectations
  for the stable arbitrage inspection surface
- refresh policy: update only when the documented arbitrage inspection
  contract intentionally changes

`persisted_arbitrage_case.json`

- fixture path: `tests/fixtures/visualization/persisted_arbitrage_case.json`
- purpose: persisted-output reconstruction for stable arbitrage inspection and
  experimental plotting without re-simulation
- status: active
- origin: manually curated persisted-output fixture aligned to the supported
  loader schema
- source current-library fixture: `tests/fixtures/simulator/controller_arbitrage_case.json`
- exact legacy reference paths consulted, if any: none
- generation command: `uv run pytest tests/integration/visualization/test_persisted_outputs.py tests/integration/visualization/test_plotting.py`
- random seed: none
- scenario family: `ArbitrageScenario`
- inspection expectations: reconstructs the same stable arbitrage inspection
  view fields and summary outcomes as the supported in-memory source
- comparison expectations: none
- plot expectations: supports experimental single-run plotting from a
  persisted source without rerunning simulation
- numeric tolerance: `1e-6`
- why it is committed: it is small, synthetic, reviewable, and proves that
  supported persisted outputs can reconstruct inspection views and feed the
  experimental static plotting layer without rerunning simulation
- refresh policy: update only when the supported persisted-output schema or
  documented arbitrage inspection contract intentionally changes

`inspection_battery_load_pv_case.json`

- fixture path: `tests/fixtures/visualization/inspection_battery_load_pv_case.json`
- purpose: stable battery-load-PV inspection expectations including supported
  weather-backed context
- status: active
- origin: manually curated deterministic visualization fixture derived from
  current-library result shapes
- source current-library fixture: `tests/fixtures/simulator/controller_battery_load_pv_case.json`
- exact legacy reference paths consulted, if any: none
- generation command: `uv run pytest tests/integration/visualization/test_inspection_battery_load_pv.py tests/unit/visualization/test_weather_reporting.py`
- random seed: none
- scenario family: `BatteryLoadPVScenario`
- inspection expectations: stable load, PV, net-grid, settlement, and
  simulator-exposed weather series with explicit availability markers
- comparison expectations: none
- plot expectations: covered indirectly by the battery-load-PV plotting
  integration suite
- numeric tolerance: `1e-6`
- why it is committed: it is small, synthetic, reviewable, and captures the
  shipped weather-aware inspection contract without depending on notebooks,
  external weather services, or re-simulation
- refresh policy: update only when the documented battery-load-PV inspection
  contract or supported weather field set intentionally changes

`persisted_battery_load_pv_case.json`

- fixture path: `tests/fixtures/visualization/persisted_battery_load_pv_case.json`
- purpose: persisted-output reconstruction for weather-aware battery-load-PV
  inspection and experimental plotting without re-simulation
- status: active
- origin: manually curated persisted-output fixture aligned to the supported
  loader schema
- source current-library fixture: `tests/fixtures/simulator/controller_battery_load_pv_case.json`
- exact legacy reference paths consulted, if any: none
- generation command: `uv run pytest tests/integration/visualization/test_persisted_outputs.py tests/integration/visualization/test_plotting_battery_load_pv.py`
- random seed: none
- scenario family: `BatteryLoadPVScenario`
- inspection expectations: reconstructs the supported load, PV, net-grid,
  weather, and settlement sections from persisted data only
- comparison expectations: none
- plot expectations: supports experimental single-run plotting from a
  persisted source without rerunning simulation
- numeric tolerance: `1e-6`
- why it is committed: it is small, synthetic, reviewable, and proves the
  shipped persisted-output schema carries enough weather-aware context for
  later inspection and plotting
- refresh policy: update only when the supported persisted-output schema, the
  documented battery-load-PV inspection contract, or supported weather field
  set intentionally changes

`comparison_arbitrage_case.json`

- fixture path: `tests/fixtures/visualization/comparison_arbitrage_case.json`
- purpose: deterministic same-family arbitrage comparison expectations over
  aligned canonical inspection series and summary deltas
- status: active
- origin: manually curated comparison fixture built from supported inspection
  outputs
- source current-library fixture: `tests/fixtures/simulator/controller_arbitrage_case.json`
- exact legacy reference paths consulted, if any: none
- generation command: `uv run pytest tests/integration/visualization/test_comparison.py tests/integration/visualization/test_comparison_failures.py tests/unit/visualization/test_comparison.py`
- random seed: none
- scenario family: `ArbitrageScenario`
- inspection expectations: inputs preserve the canonical arbitrage inspection
  ordering used by the comparison layer
- comparison expectations: deterministic aligned-series and summary-delta
  expectations for supported same-family comparisons, plus explicit failure
  coverage in the paired integration suites
- plot expectations: none; comparison plotting is deferred
- numeric tolerance: `1e-6`
- why it is committed: it is small, synthetic, reviewable, and records the
  shipped same-family comparison surface without inventing cross-family
  alignment behavior
- refresh policy: update only when the documented same-family comparison
  contract, canonical arbitrage inspection ordering, or supported summary
  delta set intentionally changes

## Refresh Guidance

- Refresh a visualization fixture only when the documented inspection,
  comparison, or persisted-output contract changes intentionally.
- Regenerate or revalidate the touched fixture with the focused `uv run pytest`
  command listed in its provenance record before updating expected values.
- Update this README in the same change when a fixture gains a new scenario
  family, series, summary field, provenance source, or refresh rule.
- Keep fixtures synthetic, small, and reviewable; prefer extending the
  simulator fixture source only when the visualization contract genuinely
  needs new deterministic evidence.

## Working Rule

Keep visualization fixtures synthetic, small, and reviewable. Reuse existing
simulator fixtures where possible, and add visualization-specific payloads
only when the simulator fixtures do not already provide enough deterministic
inspection, comparison, or persisted-output evidence.
