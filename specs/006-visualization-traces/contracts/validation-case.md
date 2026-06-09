# Contract: Deterministic Visualization Validation

This contract defines the evidence required to trust the first visualization
and trace-inspection package.

## Required Validation Set

The validation set must include:

- at least one deterministic inspection case for an arbitrage run
- at least one deterministic inspection case for a battery + load + PV run
- at least one same-family comparison case
- at least one explicit unsupported cross-family comparison case
- at least one persisted-output case proving inspection or plotting without
  rerunning simulation
- import-boundary checks for `open_energy_lab.visualization`
- no-legacy-import checks for new runtime visualization modules

## Minimum Assertions

Validation must check:

- repeated inspection requests over the same input produce identical trace
  ordering and summary values within absolute tolerance `1e-6`
- weather variables appear only for supported simulator-backed weather cases
- same-family comparisons remain deterministic
- cross-family comparisons fail deterministically
- the optional plotting layer can render from existing supported outputs
  without re-simulation
- base visualization imports do not require optional plotting dependencies
- runtime library code does not import `legacy/*`

## Evidence Standard

The feature does not require new simulator parity work. It requires targeted
evidence tied to supported current library outputs:

- deterministic result shapes from
  `src/open_energy_lab/simulator/scenario.py`
- controller-driven evaluation results from
  `src/open_energy_lab/simulator/controller_runner.py`
- weather-backed scenario inputs from `src/open_energy_lab/simulator/weather.py`
- PV-driving weather interpretation from `src/open_energy_lab/simulator/pv.py`

## Fixture Provenance

Each committed visualization or persisted-output fixture must record:

- fixture path
- source run or manual construction note
- generation command if applicable
- any seed used
- exact expected inspection outputs or invariants
- why the fixture is small enough to commit
- refresh policy

## Environment Assumptions

Default validation must run:

- on CPU
- with the repository's Python 3.11+ uv environment
- without solver licenses
- without W&B access
- without GPU or SLURM tooling
- without notebook execution
- without external data credentials
