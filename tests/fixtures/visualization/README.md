# Visualization Fixtures

This directory is reserved for deterministic visualization validation cases
that build on current `open_energy_lab.simulator` and `open_energy_lab.core`
outputs without adding new runtime behavior to `legacy/*`.

## Current Status

Active US1 fixtures:

- `inspection_arbitrage_case.json`
- `persisted_arbitrage_case.json`

Still-scaffolded later-story fixtures:

- `inspection_battery_load_pv_case.json`
- `comparison_arbitrage_case.json`

The active files record the shipped arbitrage inspection surface and the
supported persisted-output shape used for later inspection and experimental
plotting without re-simulation.

## Provenance Placeholders

Record the following for every committed visualization fixture as it becomes
active:

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

## Current Coverage

- `inspection_arbitrage_case.json`: stable single-run inspection coverage for
  arbitrage results across direct simulator traces and controller-driven
  evaluation outputs
- `inspection_battery_load_pv_case.json`: stable single-run inspection
  coverage for battery-load-PV results, including supported weather context;
  still a scaffold for US2
- `comparison_arbitrage_case.json`: same-family deterministic comparison
  coverage for arbitrage runs; still a scaffold for US3
- `persisted_arbitrage_case.json`: persisted-output reuse coverage for later
  inspection and plotting without re-simulation

## Active US1 Fixture Provenance

`inspection_arbitrage_case.json`

- source current-library fixture: `tests/fixtures/simulator/controller_arbitrage_case.json`
- scenario family: `ArbitrageScenario`
- generation command: `uv run pytest tests/integration/visualization/test_inspection_arbitrage.py tests/unit/visualization/test_inspection.py`
- random seed: none
- why it is committed: it is small, synthetic, reviewable, and records the
  shipped ordering, units, availability markers, and settlement expectations
  for the stable arbitrage inspection surface
- refresh policy: update only when the documented arbitrage inspection
  contract intentionally changes

`persisted_arbitrage_case.json`

- source current-library fixture: `tests/fixtures/simulator/controller_arbitrage_case.json`
- scenario family: `ArbitrageScenario`
- generation command: `uv run pytest tests/integration/visualization/test_persisted_outputs.py tests/integration/visualization/test_plotting.py`
- random seed: none
- why it is committed: it is small, synthetic, reviewable, and proves that
  supported persisted outputs can reconstruct inspection views and feed the
  experimental static plotting layer without rerunning simulation
- refresh policy: update only when the supported persisted-output schema or
  documented arbitrage inspection contract intentionally changes

## Working Rule

Keep visualization fixtures synthetic, small, and reviewable. Reuse existing
simulator fixtures where possible, and add visualization-specific payloads
only when the simulator fixtures do not already provide enough deterministic
inspection, comparison, or persisted-output evidence.
