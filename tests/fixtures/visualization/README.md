# Visualization Fixtures

This directory is reserved for deterministic visualization validation cases
that build on current `open_energy_lab.simulator` and `open_energy_lab.core`
outputs without adding new runtime behavior to `legacy/*`.

## Phase 1 Scaffold Status

The current files are placeholders only:

- `inspection_arbitrage_case.json`
- `inspection_battery_load_pv_case.json`
- `comparison_arbitrage_case.json`
- `persisted_arbitrage_case.json`

They establish fixture names, intended scope, and provenance expectations for
later implementation tasks. They are not finalized validation evidence yet.

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

## Planned Coverage

- `inspection_arbitrage_case.json`: stable single-run inspection coverage for
  arbitrage results
- `inspection_battery_load_pv_case.json`: stable single-run inspection
  coverage for battery-load-PV results, including supported weather context
- `comparison_arbitrage_case.json`: same-family deterministic comparison
  coverage for arbitrage runs
- `persisted_arbitrage_case.json`: persisted-output reuse coverage for later
  inspection and plotting without re-simulation

## Working Rule

Keep visualization fixtures synthetic, small, and reviewable. Reuse existing
simulator fixtures where possible, and add visualization-specific payloads
only when the simulator fixtures do not already provide enough deterministic
inspection, comparison, or persisted-output evidence.
