# Contract: Deterministic Native Controller Validation

This contract defines the evidence required to trust the first native
controller pack.

## Required Validation Set

The validation set must include:

- at least one deterministic case for `PriceThresholdController`
- at least one deterministic case for `SocGuardrailController`
- at least one deterministic case for `PVSelfConsumptionController`
- repeated-run checks for every shipped controller
- preserved explicit-dispatch regression coverage
- preserved built-in simulator rule regression coverage where relevant
- import-boundary checks for `open_energy_lab.control`
- no-legacy-import checks for new runtime library modules

## Minimum Assertions

Validation must check:

- the same controller config and same scenario inputs produce identical
  requested dispatch sequences on repeated runs
- realized dispatch and total settlement are identical on repeated runs within
  absolute tolerance `1e-6`
- unsupported scenario use fails deterministically for controllers that do not
  claim support
- invalid controller configs fail before evaluation
- simulator-side clamping remains visible when requests exceed feasible limits
- preserved explicit-dispatch and built-in simulator rule paths remain
  behaviorally unchanged
- `open_energy_lab.control` imports without heavy optional stacks
- runtime library code does not import `legacy/*`

## Evidence Standard

The feature does not require broad legacy controller parity. It requires
targeted evidence tied to shipped native controller behavior and preserved
simulator semantics:

- battery, timestep, and settlement semantics from
  `legacy/old_tpm/src_py/legacy/storage.py`,
  `legacy/old_tpm/src_py/simulator/common/battery.py`,
  `legacy/old_tpm/src_py/simulator/common/pricing.py`, and
  `legacy/old_tpm/src_py/simulator/common/time.py`
- current-step battery-plus-PV context direction from
  `legacy/fed_trpo/src/custom/building.py`
- rejected CityLearn and TorchRL abstractions from
  `legacy/fed_trpo/src/custom/citylearn.py` and
  `legacy/fed_trpo/src/utils/cl_torchrl_helper.py`

## Fixture Provenance

Each committed controller-pack fixture must record:

- fixture path
- author or manual construction note
- generation command if applicable
- any seed used
- exact expected outputs or invariants
- why the fixture is small enough to commit
- refresh policy

## Environment Assumptions

Default validation must run:

- on CPU
- with the repository’s Python 3.11+ uv environment
- without solver licenses
- without W&B access
- without GPU or SLURM tooling
- without notebook execution
- without external data credentials
