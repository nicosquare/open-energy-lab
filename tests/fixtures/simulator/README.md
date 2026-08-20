# Simulator Fixtures

Fixtures in this directory support deterministic simulator validation for the
battery arbitrage MVP, the battery + load + PV migration that builds on it,
and the cooling-aware paired demand-family simulator path for spec
`008-weather-demand-modeling`.

Spec `008-weather-demand-modeling` now ships these active paired-demand
fixtures:

- `tests/fixtures/simulator/demand_local_electric_family_case.json`
- `tests/fixtures/simulator/demand_district_cooling_family_case.json`
- `tests/fixtures/simulator/demand_invalid_mixed_cooling_case.json`

Current status:

- all three files are active deterministic validation artifacts
- the local-electric and district-cooling cases point to the committed sampled
  weather and demand family fixtures under `tests/fixtures/weather/` and
  `tests/fixtures/demand/`
- the invalid case records the expected fail-fast mixed-path validation error
- all three files record exact cooling-path evidence, scenario ordering,
  numeric tolerance, and refresh policy

## Stochastic Weather Active Fixtures

The `007-stochastic-weather` feature now ships these active simulator family
fixtures:

- `tests/fixtures/simulator/stochastic_weather_family_case.json`
- `tests/fixtures/simulator/blackout_weather_family_case.json`

Current status:

- both files are active deterministic regression baselines
- both fixtures point back to the committed weather artifact and sampled-family
  fixtures under `tests/fixtures/weather/`
- one fixture records the preserved no-blackout simulator family path and the
  other records explicit grid-outage blackout behavior

Both fixture paths record:

- family seed and scenario ordering assumptions
- scenario count and timestep expectations
- supported simulator summary fields
- blackout interval semantics when present
- numeric tolerance and refresh policy

`stochastic_weather_family_case.json`

- source: verified against the shipped simulator family-evaluation path with
  the committed sampled weather family fixture
- author: OpenAI Codex
- random seed: family seed `13`
- expected validation target: preserved deterministic `BatteryLoadPVScenario`
  semantics under sampled weather substitution plus fixed family summaries
- exact legacy evidence:
  - `legacy/old_tpm/src_py/simulator/common/weather.py`
  - `legacy/old_tpm/src_py/simulator/common/pv.py`
- expected invariants:
  - scenario ordering stays `[0, 1]`
  - `unmet_load_kw` remains zero without blackout traces
  - built-in summaries stay limited to PV generation, net-grid power, unmet
    load, and settlement series
- numeric tolerance: absolute `1e-6`
- refresh policy: update only when the documented simulator family-evaluation
  contract, baseline scenario inputs, or summary semantics intentionally
  change

`blackout_weather_family_case.json`

- source: verified against the shipped blackout-aware simulator family path
  with explicit grid-outage traces for each sampled scenario
- author: OpenAI Codex
- random seed: family seed `13`
- expected validation target: grid-outage-only blackout semantics with
  explicit unmet load and zeroed grid exchange
- exact legacy evidence:
  - `legacy/old_tpm/src_py/simulator/common/weather.py`
  - `legacy/old_tpm/src_py/simulator/common/pv.py`
- expected invariants:
  - `blackout_active` is explicit at every step
  - `net_grid_power_kw` and `step_settlement` are zero during blackout
    intervals
  - unmet load equals the positive portion of the no-blackout net-grid demand
- numeric tolerance: absolute `1e-6`
- refresh policy: update only when the documented blackout contract, baseline
  scenario inputs, or summary semantics intentionally change

## Cooling-Aware Demand Family Fixtures

`demand_local_electric_family_case.json`

- source: verified against the shipped demand-aware simulator family-evaluation
  path with the committed sampled weather and sampled demand family fixtures
- author: OpenAI Codex
- random seed: paired family seed `13`
- exact legacy evidence:
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/fed_trpo/src/notebooks/citylearn_ccai_tutorial.ipynb`
- expected validation target:
  - local-electric cooling converts served cooling demand in `RT` into site
    electric load only through the documented `kW`-per-`RT` factor
  - district settlement remains zero for every step
  - scenario ordering stays `[0, 1]`
- numeric tolerance: absolute `1e-6`
- refresh policy: update only when the documented local-electric conversion,
  paired-family ordering, or one-net settlement semantics intentionally change

`demand_district_cooling_family_case.json`

- source: verified against the shipped demand-aware simulator family-evaluation
  path with the committed sampled weather and sampled demand family fixtures
- author: OpenAI Codex
- random seed: paired family seed `13`
- exact legacy evidence:
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/fed_trpo/src/notebooks/citylearn_ccai_tutorial.ipynb`
- expected validation target:
  - served district cooling stays out of site electric load
  - district settlement equals served `RT-hour` multiplied by the configured
    deterministic tariff
  - scenario ordering stays `[0, 1]`
- numeric tolerance: absolute `1e-6`
- refresh policy: update only when the documented district-cooling tariff,
  paired-family ordering, or one-net settlement semantics intentionally change

`demand_invalid_mixed_cooling_case.json`

- source: verified against the current cooling-service configuration
  validation path rather than a generated simulator trace
- author: OpenAI Codex
- random seed: paired family seed `13`
- exact legacy evidence:
  - `legacy/old_tpm/src_py/simulator/common/pricing.py`
  - `legacy/fed_trpo/src/notebooks/citylearn_ccai_tutorial.ipynb`
- expected validation target:
  - exactly one cooling service path must be configured
  - mixed local-electric plus district-cooling configuration fails fast before
    paired-family evaluation begins
- numeric tolerance: absolute `1e-6`
- refresh policy: update only when the documented one-path cooling-service
  contract or validation message wording intentionally change

Committed simulator fixtures currently include:

- `tests/fixtures/simulator/battery_arbitrage_case.json`
- `tests/fixtures/simulator/battery_load_pv_case.json`
- `tests/fixtures/simulator/controller_arbitrage_case.json`
- `tests/fixtures/simulator/controller_battery_load_pv_case.json`

Committed controller-pack fixtures for the native control package include:

- `tests/fixtures/simulator/price_threshold_controller_case.json`
- `tests/fixtures/simulator/soc_guardrail_arbitrage_case.json`
- `tests/fixtures/simulator/pv_self_consumption_case.json`

Each committed simulator fixture must include:

- origin and author/source note
- legacy reference paths used as evidence
- generation command or manual construction note
- any seed used
- expected invariants or outputs
- numeric tolerance
- refresh policy

## Controller-Pack Active Fixtures

The three controller-pack fixture files listed above are now active
deterministic validation artifacts for spec `005-controller-pack`.

They should be used as shipped-controller evidence, not as preserved-path
regression baselines:

- `price_threshold_controller_case.json` records the exact arbitrage trace for
  `PriceThresholdController`
- `soc_guardrail_arbitrage_case.json` records the exact low-SOC correction
  trace for `SocGuardrailController`
- `pv_self_consumption_case.json` records the exact residual-following PV
  proposals, PV derivation outputs, net-grid accounting, and discounted
  settlement trace for `PVSelfConsumptionController`

All three controller-pack fixtures are:

- synthetic, small, and reviewable
- backed by runner-verified `expected_trace` data
- explicit about cited legacy evidence paths and refresh policy
- distinct from preserved explicit-dispatch and built-in simulator-rule
  regression evidence

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
