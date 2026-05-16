# Contract: Deterministic Validation Case

This contract defines the minimum evidence required to trust the first battery
arbitrage simulator migration.

## Required Fixture Shape

The primary validation case must define:

- one time grid with explicit `time_step_hours`
- one battery with explicit power, capacity, and efficiency assumptions
- one aligned import-price series with discounted export settlement ratio
- one aligned dispatch request series or one deterministic price-threshold
  policy
- one expected trace or one expected property table
- exact legacy reference paths used as supporting evidence

The fixture may live as a Python test fixture or as a tiny committed artifact
under `tests/fixtures/simulator` if provenance notes are included.

## Minimum Assertions

The validation case must check:

- deterministic repeated execution from the same inputs
- battery SOC remains within bounds
- stored energy follows charge/discharge efficiency rules
- realized power never exceeds configured limits
- timestep alignment matches the documented convention
- total objective value equals the sum of per-step settlement values
- export settlement uses the documented discounted export-price ratio
- low-price charging and high-price discharging behavior is reflected in the
  provided trace or deterministic dispatch schedule

## Evidence Standard

The first MVP does not require broad end-to-end parity against the legacy
simulator. It requires targeted evidence tied to selected legacy semantics:

- battery constraints and tolerance behavior from
  `legacy/old_tpm/scripts/test_battery_consistency.py`
- battery update semantics from
  `legacy/old_tpm/src_py/legacy/storage.py` and
  `legacy/old_tpm/src_py/simulator/common/battery.py`
- time-step and price alignment semantics from
  `legacy/old_tpm/src_py/simulator/common/time.py` and
  `legacy/old_tpm/src_py/simulator/common/pricing.py`

## Provenance Requirements

If the validation case uses a committed fixture artifact, record:

- fixture path
- author/source
- generation command or manual construction note
- any seed used
- why the fixture is small enough to commit
- refresh/update policy

Large generated outputs, real tariff downloads, and notebook artifacts are out
of scope.

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
