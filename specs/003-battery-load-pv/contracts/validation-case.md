# Contract: Deterministic Battery Load PV Validation Case

This contract defines the minimum evidence required to trust the battery + load
+ PV simulator migration.

## Required Fixture Shape

The primary validation case must define:

- one time grid with explicit `time_step_hours`
- one battery with explicit capacity, power, efficiency, and initial SOC
- one load profile aligned to the time grid
- one weather input series aligned to the time grid
- one PV component definition used to derive generation from the weather inputs
- one aligned import-price series with discounted export settlement ratio
- one aligned dispatch request series or one deterministic `price_threshold`
  rule policy
- one expected trace or one expected property table
- exact legacy reference paths used as supporting evidence

The fixture may live as Python data or as a tiny committed artifact under
`tests/fixtures/simulator` if provenance notes are included.

## Minimum Assertions

The validation case must check:

- deterministic repeated execution from the same inputs
- battery SOC remains within bounds
- realized battery power never exceeds configured limits
- weather-to-PV derivation produces the documented per-step PV values
- net-grid balance matches
  `load_kw + realized_battery_power_kw - pv_generation_kw`
- per-step import/export direction matches the sign of the net-grid value
- total settlement equals the sum of per-step settlement values
- export settlement uses the documented discounted export-price ratio
- both execution modes remain valid if the feature provides both a dispatch case
  and a built-in-rule case

## Evidence Standard

The first multi-component MVP does not require broad end-to-end parity against
the legacy simulator. It requires targeted evidence tied to selected legacy
semantics:

- battery constraints and tolerance behavior from
  `legacy/old_tpm/scripts/test_battery_consistency.py`
- battery update semantics from
  `legacy/old_tpm/src_py/legacy/storage.py` and
  `legacy/old_tpm/src_py/simulator/common/battery.py`
- price and timestep alignment semantics from
  `legacy/old_tpm/src_py/simulator/common/pricing.py` and
  `legacy/old_tpm/src_py/simulator/common/time.py`
- PV metadata direction from
  `legacy/old_tpm/src_py/simulator/common/specs.py`
- single-net electricity accounting direction from
  `legacy/fed_trpo/src/custom/building.py`

## Provenance Requirements

If the validation case uses a committed fixture artifact, record:

- fixture path
- author or manual-construction note
- generation command if applicable
- any seed used
- why the fixture is small enough to commit
- refresh or update policy

Large generated outputs, real weather downloads, real tariff data, and notebook
artifacts are out of scope.

## Environment Assumptions

Default validation must run:

- on CPU
- inside the minimal conda plus uv environment
- without solver licenses
- without W&B access
- without GPU or SLURM tooling
- without Rust compilation
- without external data credentials

Default numeric comparison tolerance is absolute `1e-6` unless a stricter case
is explicitly documented.
