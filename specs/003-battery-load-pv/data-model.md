# Data Model: Deterministic Battery Load PV Scenario MVP

This feature extends the existing battery-arbitrage simulator with explicit
load, minimal weather-driven PV behavior, and one-net grid accounting. Battery
transition semantics remain unchanged from the completed arbitrage MVP.

## Time Grid

**Fields**: `start_step`, `num_steps`, `time_step_hours`, `step_labels`
(optional), `horizon_hours`.

**Relationships**: Owns the ordered index used by load, weather, PV, prices,
dispatch inputs, and all trace outputs.

**Validation rules**:

- `num_steps` must be positive.
- `time_step_hours` must be positive.
- `horizon_hours == num_steps * time_step_hours`.
- All time-indexed scenario series must match `num_steps`.

## Battery Component

**Fields**: `name`, `capacity_kwh`, `max_charge_kw`, `max_discharge_kw`,
`charge_efficiency`, `discharge_efficiency`, `initial_soc`, `min_soc`,
`max_soc`.

**Relationships**: Reused from the battery-arbitrage MVP. Produces battery
state records across the extended simulation trace.

**Validation rules**:

- Preserve the previous feature's invariants and `1e-6` default tolerance.
- Positive realized battery power still means charging.
- Negative realized battery power still means discharging.

## Load Component

**Fields**: `name`, `demand_kw`, `interpretation`, `time_grid`, `source`
(optional).

**Relationships**: Aligned to the Time Grid. Contributes directly to the
per-step net-grid balance.

**Validation rules**:

- `demand_kw` length must equal `num_steps`.
- Load values must be non-negative for the MVP.
- `interpretation` must document that values represent exogenous consumption in
  `kW`.

## Weather Component

**Fields**: `name`, `timestamp_utc` (TMY label: `Date & time (UTC)`),
`dry_bulb_air_temperature_c` (TMY label: `T2m [°C]`), one or more
human-readable irradiance fields such as `global_horizontal_irradiance_w_per_m2`
(TMY label: `G(h) [W/m2]`), `direct_beam_irradiance_w_per_m2` (TMY label:
`Gb(n) [W/m2]`), or `diffuse_horizontal_irradiance_w_per_m2` (TMY label:
`Gd(h) [W/m2]`), plus optional deferred fields for later migrations such as
`relative_humidity_pct` (TMY label: `RH [%]`),
`infrared_radiation_downwards_w_per_m2` (TMY label: `IR(h) [W/m2]`),
`windspeed_10m_m_per_s` (TMY label: `WS10m [m/s]`),
`wind_direction_10m_deg` (TMY label: `WD10m [°]`), and
`surface_air_pressure_pa` (TMY label: `SP [Pa]`), `time_grid`, `source`
(optional), `notes` (optional).

**Relationships**: Aligned to the Time Grid. Drives deterministic PV output
through the PV component.

**Validation rules**:

- All included weather series lengths must equal `num_steps`.
- Each included field must document its canonical TMY source label.
- Irradiance values must be non-negative.
- `dry_bulb_air_temperature_c` values may vary freely but must be numeric.
- The component must stay limited to the PV-driving subset only for this MVP.
- Standard TMY fields not required by the chosen PV derivation remain deferred.

## PV Component

**Fields**: `name`, `rated_power_kw`, `temperature_coefficient_pct_per_c`,
`reference_irradiance_w_per_m2`, `reference_temperature_c`,
`generation_cap_kw` (optional), `derivation_name`.

**Relationships**: Uses Weather Component inputs to produce a deterministic
available generation series aligned to the Time Grid.

**Validation rules**:

- `rated_power_kw` must be positive.
- `reference_irradiance_w_per_m2` must be positive.
- The derived PV generation series length must equal `num_steps`.
- Derived PV generation must be non-negative.
- The derivation must be deterministic from the same weather inputs and PV
  metadata.

**State transitions**:

- For each step, derive an irradiance scaling factor from the chosen included
  irradiance field or documented combination of irradiance fields, each with a
  documented TMY source label.
- Apply the configured temperature coefficient relative to the reference
  temperature using `dry_bulb_air_temperature_c`.
- Multiply by rated power and clamp to zero or optional `generation_cap_kw`.

## Price Signal

**Fields**: `currency`, `unit_rate_name`, `import_prices`,
`export_price_ratio`, `interpretation`, `time_alignment`, `time_grid`.

**Relationships**: Reused from the battery-arbitrage MVP. Prices import and
export settlement for the net-grid trace.

**Validation rules**:

- Preserve the prior feature's length, discount, and step-start alignment
  requirements.

## Dispatch Request Series

**Fields**: `requested_power_kw`, `sign_convention`, `source`.

**Relationships**: Optional explicit control boundary for the battery. Reused
from the battery-arbitrage MVP.

**Validation rules**:

- Length must equal `num_steps`.
- Positive values request charging.
- Exactly one of explicit dispatch or built-in rule policy must drive a given
  scenario evaluation path.

## Deterministic Rule Policy

**Fields**: `policy_name`, `price_threshold`, `below_threshold_action`,
`above_threshold_action`, `at_threshold_action`.

**Relationships**: Optional built-in alternative to explicit dispatch. Uses
only Price Signal inputs even when load and PV are present.

**Validation rules**:

- Preserve the prior feature's `price_threshold`-only restriction.
- The policy must not consume load or PV inputs for this MVP.

## Net Grid Trace

**Fields**: `net_grid_power_kw`, `net_grid_energy_kwh`, `direction`,
`step_settlement`, `total_settlement`.

**Relationships**: Derived from Load Component, PV Component output, realized
battery power, Price Signal, and settlement rules.

**Validation rules**:

- One record per step.
- Positive `net_grid_power_kw` means import.
- Negative `net_grid_power_kw` means export.
- `total_settlement == sum(step_settlement)` within tolerance.
- Import and export cannot both be nonzero in the same step.

**State transitions**:

- For each step, compute
  `net_grid_power_kw = load_kw + realized_battery_power_kw - pv_generation_kw`.
- Convert to `net_grid_energy_kwh` using `time_step_hours`.
- Apply import price when the value is positive and discounted export price
  when the value is negative.

## Battery Load PV Scenario

**Fields**: `scenario_id`, `time_grid`, `battery`, `load`, `weather`, `pv`,
`price_signal`, `objective`, `dispatch_requests` (optional), `rule_policy`
(optional), `numeric_tolerance`, `notes` (optional).

**Relationships**: Aggregate root for the new multi-component simulator case.
Reuses the battery and pricing surfaces while adding load, weather, PV, and
net-grid accounting.

**Validation rules**:

- Must include exactly one time grid, battery, load component, weather
  component, PV component, price signal, and settlement objective.
- Must include exactly one of `dispatch_requests` or `rule_policy`.
- All aligned series must share the same `time_grid`.
- Scenario assembly must define explicit component relationships and must not
  rely on hidden case logic.

## Extended Simulation Trace

**Fields**: `battery_states`, `requested_power_kw`, `realized_power_kw`,
`battery_energy_delta_kwh`, `load_kw`, `weather_inputs` (using human-readable
field names with documented TMY source labels), `pv_generation_kw`,
`net_grid_power_kw`, `net_grid_energy_kwh`, `step_settlement`,
`total_settlement`, `constraint_events`.

**Relationships**: Produced by evaluating a Battery Load PV Scenario.
References all runtime components needed for the deterministic invariants.

**Validation rules**:

- One trace record per step.
- Derived PV generation, net-grid values, and settlement values must be
  reproducible from the same inputs.
- `constraint_events` are empty in nominal fixtures or explicitly expected when
  clamping behavior is under test.

## Validation Case

**Fields**: `case_id`, `fixture_source`, `expected_properties`,
`numeric_tolerance`, `legacy_references`, `provenance_notes`.

**Relationships**: References one Battery Load PV Scenario and one expected
Extended Simulation Trace or invariant table.

**Validation rules**:

- Must cite exact legacy references used as evidence.
- Must state whether it checks exact numeric traces, invariant properties, or
  both.
- Default `numeric_tolerance` is absolute `1e-6` unless stricter requirements
  are documented.
- Must run without external data services or optional research stacks.
