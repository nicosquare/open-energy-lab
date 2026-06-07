# Simulator Fixtures

Fixtures in this directory support deterministic simulator validation for the
battery arbitrage MVP and the battery + load + PV migration that builds on it.

Committed simulator fixtures currently include:

- `tests/fixtures/simulator/battery_arbitrage_case.json`
- `tests/fixtures/simulator/battery_load_pv_case.json`
- `tests/fixtures/simulator/controller_arbitrage_case.json`
- `tests/fixtures/simulator/controller_battery_load_pv_case.json`

Each committed simulator fixture must include:

- origin and author/source note
- legacy reference paths used as evidence
- generation command or manual construction note
- any seed used
- expected invariants or outputs
- numeric tolerance
- refresh policy

## Current Fixture

`tests/fixtures/simulator/battery_arbitrage_case.json` is the first active
simulator fixture.

- source: manually authored from the simulator contracts, then verified against
  the current implementation with `uv run python -c` trace calculations
- author: OpenAI Codex
- seed: none
- why it is committed: it is small, reviewable, deterministic, and exercises
  both explicit dispatch and built-in `price_threshold` execution paths
- exact legacy evidence:
  - `legacy/old_tpm/scripts/test_battery_consistency.py`
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
- expected invariants:
  - SOC stays within `[0.0, 1.0]`
  - realized power respects the configured limits
  - total settlement equals the sum of the step settlement values
  - export settlement uses the discounted export-price ratio
- numeric tolerance: absolute `1e-6`
- refresh policy: update only when the documented timestep, battery, policy, or
  discounted-settlement semantics intentionally change

## Controller Arbitrage Fixture

`tests/fixtures/simulator/controller_arbitrage_case.json` is the active
controller-driven arbitrage fixture for the controller boundary MVP.

- source: manually authored from the controller-boundary contracts, then
  verified against the current implementation with `uv run python -c`
  controller-evaluation calculations and the focused integration suite
- author: OpenAI Codex
- generation command: none; the fixture is manually maintained and checked
  against the implementation rather than generated from a separate script
- seed: none unless a future generator requires one
- why it is committed: it is small, reviewable, deterministic, and captures
  exact controller-driven proposals plus realized arbitrage-settlement results
- exact legacy evidence:
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
- expected validation target:
  - controller-driven evaluation for `ArbitrageScenario`
  - exact proposal and realized-trace values from the documented
    `sequence-controller`
  - repeated evaluation from the same inputs remains deterministic
- numeric tolerance: absolute `1e-6`
- refresh policy: update only when the documented controller boundary,
  controller sequence, timestep, battery, or settlement semantics
  intentionally change

## Controller Battery Load PV Fixture

`tests/fixtures/simulator/controller_battery_load_pv_case.json` is the active
controller-driven battery-load-PV fixture for the controller boundary MVP.

- source: manually authored from the controller-boundary contracts, then
  verified against the current implementation with `uv run python -c`
  controller-evaluation calculations and the focused integration suite
- author: OpenAI Codex
- generation command: none; the fixture is manually maintained and checked
  against the implementation rather than generated from a separate script
- seed: none unless a future generator requires one
- why it is committed: it is small, reviewable, deterministic, and captures
  exact controller-driven proposals, PV outputs, net-grid accounting, and
  discounted-settlement results
- exact legacy evidence:
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
  - `legacy/old_tpm/src_py/simulator/common/specs.py`
  - `legacy/fed_trpo/src/custom/building.py`
- expected validation target:
  - controller-driven evaluation for `BatteryLoadPVScenario`
  - exact proposal, PV, net-grid, and settlement values from the documented
    `sequence-controller`
  - repeated evaluation from the same inputs remains deterministic
- numeric tolerance: absolute `1e-6`
- refresh policy: update only when the documented controller boundary, weather
  to PV derivation, controller sequence, battery, timestep, or settlement
  semantics intentionally change

## Battery Load PV Fixture

`tests/fixtures/simulator/battery_load_pv_case.json` is the active shared
fixture for the deterministic battery + load + weather + PV MVP.

- source: manually authored from the `003-battery-load-pv` contracts and data
  model, then checked against the current implementation with `uv run python -c`
  trace calculations
- author: OpenAI Codex
- seed: none
- why it is committed: it is small, reviewable, deterministic, and exercises
  both explicit-dispatch and built-in `price_threshold` execution paths over
  the same weather-driven PV and one-net settlement rules
- exact legacy evidence:
  - `legacy/old_tpm/src_py/legacy/storage.py`
  - `legacy/old_tpm/scripts/test_battery_consistency.py`
  - `legacy/old_tpm/src_py/simulator/common/battery.py`
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/old_tpm/src_py/simulator/common/time.py`
  - `legacy/old_tpm/src_py/simulator/common/specs.py`
  - `legacy/fed_trpo/src/custom/building.py`
- schema and provenance expectations:
  - weather fields use human-readable names
  - each included weather field carries its canonical TMY source label
  - unused standard TMY fields are documented as deferred, not silently dropped
  - expected traces were verified against the current implementation rather than
    copied from a legacy runtime
- expected invariants:
  - SOC stays within `[0.0, 1.0]`
  - realized battery power respects the configured limits
  - `net_grid_power_kw == load_kw + realized_battery_power_kw - pv_generation_kw`
  - import/export direction follows the sign of the net-grid value
  - total settlement equals the sum of the step settlement values
  - export settlement uses the discounted export-price ratio
- numeric tolerance: absolute `1e-6`
- tolerance rationale: this matches the prior battery-arbitrage MVP and the
  cited legacy battery-consistency evidence, while still absorbing ordinary
  floating-point round-off from efficiency and temperature-adjusted PV math
- refresh policy: update only when the documented load, weather-to-PV, battery,
  price-threshold, or settlement semantics intentionally change
