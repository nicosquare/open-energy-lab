# Data Model: Battery Arbitrage Simulator MVP

This feature defines runtime simulator entities for a single deterministic
battery arbitrage case. The model is intentionally narrow and excludes weather,
PV, building envelopes, RL state, and optimizer inputs.

## Time Grid

**Fields**: `start_step`, `num_steps`, `time_step_hours`, `step_labels`
(optional), `horizon_hours`.

**Relationships**: Owns the ordered index used by Price Signal, Dispatch
Request Series, Simulation Trace, and Validation Case.

**Validation rules**:

- `num_steps` must be positive.
- `time_step_hours` must be positive.
- `horizon_hours` equals `num_steps * time_step_hours`.
- All time-indexed scenario series must match `num_steps`.

## Battery Component

**Fields**: `name`, `capacity_kwh`, `max_charge_kw`, `max_discharge_kw`,
`charge_efficiency`, `discharge_efficiency`, `initial_soc`, `min_soc`
(default `0.0`), `max_soc` (default `1.0`).

**Relationships**: Belongs to an Arbitrage Scenario. Produces Battery State
records across the Simulation Trace.

**Validation rules**:

- `capacity_kwh` must be positive.
- `max_charge_kw` and `max_discharge_kw` must be positive.
- `charge_efficiency` and `discharge_efficiency` must be in `(0.0, 1.0]`.
- `initial_soc`, `min_soc`, and `max_soc` must be fractions in `[0.0, 1.0]`.
- `min_soc <= initial_soc <= max_soc`.

## Battery State

**Fields**: `step_index`, `soc`, `stored_energy_kwh`, `available_charge_kwh`,
`available_discharge_kwh`.

**Relationships**: Produced by Battery Component transitions. Recorded in the
Simulation Trace and checked by Validation Case expectations.

**Validation rules**:

- `soc` remains within `[min_soc, max_soc]` up to configured tolerance.
- `stored_energy_kwh == soc * capacity_kwh` up to tolerance.
- `available_charge_kwh >= 0.0` and `available_discharge_kwh >= 0.0`.

**State transitions**:

- Charging increases stored energy subject to charge efficiency, power limit,
  timestep duration, and remaining capacity.
- Discharging decreases stored energy subject to discharge efficiency, power
  limit, timestep duration, and available energy.

## Price Signal

**Fields**: `currency`, `unit_rate_name`, `import_prices`, `export_price_ratio`,
`interpretation`, `time_alignment`.

**Relationships**: Aligned to Time Grid. Used by Arbitrage Objective
Representation and Validation Case expectations.

**Validation rules**:

- `import_prices` length must equal `num_steps`.
- `export_price_ratio` must be present for the MVP and must define discounted
  export settlement relative to import prices.
- `interpretation` must state that export settlement is discounted relative to
  import pricing for the MVP.
- `time_alignment` is step-start aligned for this MVP.

## Dispatch Request Series

**Fields**: `requested_power_kw`, `sign_convention`, `source`.

**Relationships**: Aligned to Time Grid. Consumed by the scenario evaluator and
converted into a feasible dispatch trace.

**Validation rules**:

- Length must equal `num_steps`.
- Sign convention must be explicit. For this MVP, positive values request
  charging and negative values request discharging.
- The evaluator must clamp infeasible requests to battery limits and record the
  realized feasible power.

## Deterministic Rule Policy

**Fields**: `policy_name`, `price_threshold`, `below_threshold_action`,
`above_threshold_action`, `at_threshold_action`.

**Relationships**: Optional alternative to Dispatch Request Series for an
Arbitrage Scenario. Uses Price Signal and Battery Component state to generate a
deterministic requested-power sequence.

**Validation rules**:

- The only built-in MVP policy is `price_threshold`.
- Below threshold, the policy requests charging.
- Above threshold, the policy requests discharging.
- At threshold, the policy holds state.
- Policy evaluation must be deterministic from the same inputs.

## Arbitrage Objective Representation

**Fields**: `settlement_basis`, `allow_export`, `export_price_ratio`,
`objective_name`.

**Relationships**: Uses Price Signal and realized dispatch from the Simulation
Trace to compute value.

**Validation rules**:

- Must be computable from the deterministic trace without an optimizer.
- Must document discounted export settlement relative to import price.
- Must expose enough detail to verify total objective value from per-step
  settlement terms.

## Arbitrage Scenario

**Fields**: `scenario_id`, `time_grid`, `battery`, `price_signal`,
`dispatch_requests` (optional), `rule_policy` (optional), `objective`,
`components`, `connections`, `notes` (optional).

**Relationships**: Central aggregate root tying the MVP components into one
component graph.

**Validation rules**:

- Must include exactly one battery for the MVP.
- Must include a price signal and an arbitrage objective.
- Must include exactly one of `dispatch_requests` or `rule_policy` for a given
  validation path, though the overall MVP supports both modes.
- `components` and `connections` must make the battery-price-objective
  relationship explicit even if the graph is minimal.
- Scenario assembly must not require weather, PV, building, CityLearn, or RL
  components.

## Simulation Trace

**Fields**: `states`, `requested_power_kw`, `realized_power_kw`,
`energy_delta_kwh`, `step_settlement`, `total_settlement`,
`constraint_events`.

**Relationships**: Produced by evaluating an Arbitrage Scenario. Verified by
the Validation Case.

**Validation rules**:

- One trace record per time step.
- `total_settlement` equals the sum of `step_settlement`.
- Constraint events are empty in the nominal deterministic fixture or are
  explicitly expected when clamping behavior is under test.

## Validation Case

**Fields**: `case_id`, `fixture_source`, `expected_properties`,
`numeric_tolerance`, `legacy_references`, `provenance_notes`.

**Relationships**: References one Arbitrage Scenario and one expected
Simulation Trace or a set of invariant/property assertions.

**Validation rules**:

- Must cite exact legacy references used as evidence.
- Must state whether it checks exact numbers, bounded tolerances, or structural
  properties.
- Default `numeric_tolerance` is absolute `1e-6` unless stricter requirements
  are documented.
- Must be reproducible without external data services or optional research
  stacks.
