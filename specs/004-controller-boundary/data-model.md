# Data Model: External Controller Boundary MVP

This feature introduces the first stable controller contract for Open Energy
Lab and a simulator-owned deterministic evaluation path that consumes it. The
model is intentionally small, typed, and current-step only.

## Controller Context

**Fields**: `scenario_id`, `scenario_kind`, `step_index`, `time_step_hours`,
`battery_state`, `price_input`, `step_inputs`, `notes` (optional).

**Relationships**: Constructed by the simulator for one step of a supported
scenario and passed to a controller contract in `open_energy_lab.core`.

**Validation rules**:

- `step_index` must refer to one valid simulator step.
- `time_step_hours` must be positive.
- `battery_state` must reflect the pre-decision battery state for the current
  step.
- `step_inputs` must contain only current-step aligned values allowed by the
  active scenario.
- The context must not expose full scenario objects or future horizon series.

## Battery State Snapshot

**Fields**: `soc_fraction`, `min_soc`, `max_soc`, `max_charge_kw`,
`max_discharge_kw`.

**Relationships**: Embedded in `ControllerContext`. Derived from the current
simulator battery state and component metadata.

**Validation rules**:

- `0.0 <= min_soc <= soc_fraction <= max_soc <= 1.0`.
- Power limits must be positive.
- Sign conventions remain aligned with the simulator core.

## Price Input

**Fields**: `import_price`, `export_price`, `currency`, `time_alignment`.

**Relationships**: Embedded in `ControllerContext`. Derived from the active
scenario’s `PriceSignal` for the current step.

**Validation rules**:

- Price values must be numeric.
- `time_alignment` must stay aligned with simulator step semantics.
- Export price must preserve the scenario’s discounted export rule.

## Step Inputs

**Fields**: canonical current-step exogenous inputs, potentially including
`load_kw`, `pv_generation_kw`, and scenario-specific flags or metadata that
remain current-step only.

**Relationships**: Embedded in `ControllerContext`. The exact fields depend on
scenario type, but the public model must stay stable across supported
scenarios.

**Validation rules**:

- Each included value must be interpretable without accessing scenario
  internals.
- Arbitrage contexts may omit load and PV inputs.
- Battery-load-PV contexts may include load and current-step available PV
  generation, but they must not require controllers to derive PV from raw
  weather internals.

## Dispatch Proposal

**Fields**: `requested_power_kw`, `sign_convention`, `controller_name`,
`metadata` (optional).

**Relationships**: Produced by a controller from one `ControllerContext`.
Validated by the simulator before step evaluation.

**Validation rules**:

- `sign_convention` must document that positive dispatch means charge.
- `requested_power_kw` must be numeric.
- The proposal is one step only.
- The controller name or source identifier must be present for traceability.

## Controller Interface

**Fields**: one callable method such as `propose_dispatch(context) ->
DispatchProposal`.

**Relationships**: Implemented by user-provided or library-provided
controllers. Consumes `ControllerContext` and produces `DispatchProposal`.

**Validation rules**:

- The method must be deterministic from the same context when the controller
  itself is deterministic.
- The interface must not assume responsibility for physics, settlement, or
  scenario stepping.
- The interface must remain free of optional research-stack types.

## Controller Step Record

**Fields**: `step_index`, `context`, `proposal`, `realized_power_kw`,
`energy_delta_kwh`, `step_settlement`, `constraint_events`.

**Relationships**: Produced by the simulator runner for each step of a
controller-driven episode.

**Validation rules**:

- `step_index` ordering must match the scenario time grid.
- `proposal` and `realized_power_kw` may differ only when simulator-side
  feasibility enforcement clamps the request.
- `constraint_events` must be empty unless clamping or rejection behavior is
  expected.

## Controller Evaluation Result

**Fields**: `scenario_id`, `scenario_kind`, `controller_name`, `step_records`,
`requested_power_kw`, `realized_power_kw`, `total_settlement`,
`final_battery_state`, `underlying_trace`.

**Relationships**: Aggregate result produced by the simulator-owned controller
runner. Links controller proposals to realized simulator behavior.

**Validation rules**:

- One `step_record` per simulator step.
- `requested_power_kw` and `realized_power_kw` lengths must equal the scenario
  horizon.
- `underlying_trace` must preserve the existing simulator trace semantics for
  the active scenario family.
- `total_settlement` must agree with the underlying simulator trace within the
  configured tolerance.

## Scenario Compatibility

**Supported scenario kinds**:

- `ArbitrageScenario`
- `BatteryLoadPVScenario`

**Compatibility rules**:

- Both scenarios must be evaluable through the same controller runner API.
- The controller context shape must remain stable even when some step inputs
  are absent for simpler scenarios.
- Scenario-specific extras must remain additive rather than changing the core
  proposal contract.

## Validation Case

**Fields**: `case_id`, `scenario_kind`, `controller_name`, `fixture_source`,
`expected_properties`, `numeric_tolerance`, `legacy_references`,
`provenance_notes`.

**Relationships**: Defines deterministic evidence that one controller-driven
episode works end to end for a supported scenario.

**Validation rules**:

- Must cite exact legacy source paths used as evidence.
- Must state whether exact proposals, exact realized traces, invariant
  properties, or both are checked.
- Must run without optional research stacks, network access, or GPU/SLURM
  tooling.
