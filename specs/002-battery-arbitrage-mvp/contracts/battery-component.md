# Contract: Battery Component

This contract defines the battery behavior the simulator MVP must preserve,
improve, and reject.

## Preserved Legacy Semantics

The MVP battery component preserves the following behavior from
`legacy/old_tpm/src_py/legacy/storage.py`,
`legacy/old_tpm/src_py/simulator/common/battery.py`, and
`legacy/old_tpm/scripts/test_battery_consistency.py`:

- capacity-limited stored energy
- explicit charge and discharge power limits
- explicit charge and discharge efficiencies
- bounded state of charge
- tolerance-aware full and empty checks
- deterministic update of battery state from requested energy movement

## Improved Semantics

The MVP should improve on the legacy references by:

- using one explicit SOC convention: fraction in `[0.0, 1.0]`
- separating component specification from per-step state
- making timestep scaling explicit in the contract
- documenting sign conventions instead of inferring them from calling code
- exposing feasible realized power separately from requested power

## Rejected Semantics

The MVP rejects:

- implicit dependence on solar/load policy helpers
- broad building or CityLearn coupling
- stochastic behavior in the default battery trace
- undocumented grid-credit accounting as a core requirement
- multiple incompatible SOC conventions at the public API boundary

## Required Fields

- `capacity_kwh`
- `max_charge_kw`
- `max_discharge_kw`
- `charge_efficiency`
- `discharge_efficiency`
- `initial_soc`
- optional `min_soc`
- optional `max_soc`

## Transition Rules

For each time step:

1. Convert the requested power into requested energy using `time_step_hours`.
2. Clamp the request to charge/discharge power limits.
3. Clamp again to available capacity or available stored energy.
4. Apply the relevant efficiency.
5. Update stored energy and SOC.
6. Record both requested and realized values in the trace.

The exact clamp order must be consistent across implementation and tests.

## Invariants

The component must maintain:

- `0.0 <= soc <= 1.0` within configured tolerance
- `0.0 <= stored_energy_kwh <= capacity_kwh` within configured tolerance
- no realized charge power above `max_charge_kw`
- no realized discharge power above `max_discharge_kw`
- deterministic replay from the same initial state and input series

## Tolerance Guidance

Validation should use absolute tolerance `1e-6` by default, consistent with
the deterministic battery math expected from the legacy consistency checks. A
case may be stricter, but should not be looser without explicit justification.
