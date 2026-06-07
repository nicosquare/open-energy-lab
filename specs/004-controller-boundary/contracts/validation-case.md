# Contract: Deterministic Controller Boundary Validation

This contract defines the evidence required to trust the controller-boundary
migration.

## Required Fixture Shape

The primary validation set must include deterministic cases covering:

- one `ArbitrageScenario` controller-driven episode
- one `BatteryLoadPVScenario` controller-driven episode
- one typed controller implementation or fixture-driven stub controller
- exact or property-based expectations for controller proposals and realized
  simulator outputs
- one preserved explicit-dispatch regression case for a supported scenario
- one preserved built-in `price_threshold` regression case for a supported
  scenario
- one named incomplete-context rejection case
- exact legacy reference paths used as supporting evidence

The fixtures may live as tiny committed artifacts under
`tests/fixtures/simulator` if provenance notes are included.

## Minimum Assertions

Validation must check:

- repeated evaluation from the same inputs reproduces the same proposals,
  realized trace, and aggregate result
- controller proposals preserve the documented sign convention
- proposal validation rejects wrong-shape or wrong-semantic requests
- controller evaluation rejects incomplete required current-step context as a
  named pre-evaluation failure mode
- simulator clamping behavior is visible when requested power exceeds feasible
  limits
- the underlying simulator trace still satisfies its documented invariants for
  the active scenario
- preserved explicit-dispatch and built-in `price_threshold` execution paths
  remain available and behaviorally unchanged
- imports of `open_energy_lab.core` and `open_energy_lab.simulator` do not
  load heavy optional stacks
- runtime library code does not import `legacy/*`

## Evidence Standard

The controller-boundary MVP does not require end-to-end legacy RL replay. It
requires targeted evidence tied to preserved semantics and rejected
abstractions:

- battery and timestep semantics from
  `legacy/old_tpm/src_py/legacy/storage.py`,
  `legacy/old_tpm/src_py/simulator/common/battery.py`,
  `legacy/old_tpm/src_py/simulator/common/pricing.py`, and
  `legacy/old_tpm/src_py/simulator/common/time.py`
- single-net scenario context direction from
  `legacy/fed_trpo/src/custom/building.py`
- rejected action-space and training-environment abstractions from
  `legacy/fed_trpo/src/custom/citylearn.py` and
  `legacy/fed_trpo/src/utils/cl_torchrl_helper.py`

## Provenance Requirements

If a committed fixture artifact is used, record:

- fixture path
- author or manual-construction note
- generation command if applicable
- any seed used
- why the fixture is small enough to commit
- refresh or update policy

## Environment Assumptions

Default validation must run:

- on CPU
- inside the minimal conda plus uv environment
- without solver licenses
- without W&B access
- without GPU or SLURM tooling
- without Rust compilation
- without external data credentials
