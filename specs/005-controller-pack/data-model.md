# Data Model: Native Controller Pack

This feature introduces the first reusable controller package in
`open_energy_lab.control`. The model builds on the existing stable controller
contract in `open_energy_lab.core` and the simulator-owned runner in
`open_energy_lab.simulator`.

## Controller Definition

**Fields**: `controller_name`, `config_type`, `supported_scenario_kinds`,
`maturity`, `behavior_summary`.

**Relationships**: Exported from `open_energy_lab.control`; implements
`ControllerInterface`; evaluated through `evaluate_with_controller`.

**Validation rules**:

- `controller_name` must be stable and non-empty.
- `supported_scenario_kinds` must be explicit and finite.
- `maturity` must match the documented package policy for this feature.
- The definition must not require runtime imports from `legacy/*` or heavy
  optional research stacks.

## Price Threshold Config

**Fields**: `charge_below_import_price`, `discharge_above_import_price`,
`charge_request_kw`, `discharge_request_kw`, `controller_name` (optional
override).

**Relationships**: Consumed by `PriceThresholdController`; supports
`ArbitrageScenario`.

**Validation rules**:

- all price thresholds must be numeric
- `charge_below_import_price < discharge_above_import_price`
- requested power limits must be positive
- the controller idles when the current import price falls inside the neutral
  band or equals either threshold

## SOC Guardrail Config

**Fields**: `target_min_soc`, `target_max_soc`, `charge_request_kw`,
`discharge_request_kw`, `controller_name` (optional override).

**Relationships**: Consumed by `SocGuardrailController`; supports both
`ArbitrageScenario` and `BatteryLoadPVScenario`.

**Validation rules**:

- `0.0 <= target_min_soc < target_max_soc <= 1.0`
- requested power limits must be positive
- if current SOC is below `target_min_soc`, the controller requests charging
- if current SOC is above `target_max_soc`, the controller requests
  discharging
- if current SOC falls inside the configured band or exactly on a satisfied
  boundary, the controller idles

## PV Self-Consumption Config

**Fields**: `reserve_min_soc`, `reserve_max_soc`, `charge_request_kw`,
`discharge_request_kw`, `controller_name` (optional override).

**Relationships**: Consumed by `PVSelfConsumptionController`; supports
`BatteryLoadPVScenario`.

**Validation rules**:

- `0.0 <= reserve_min_soc < reserve_max_soc <= 1.0`
- requested power limits must be positive
- charging behavior may only use current-step `pv_generation_kw` and `load_kw`
  already exposed by the stable controller context
- if PV generation exceeds load and current SOC is below `reserve_max_soc`,
  the controller requests charging
- if load exceeds PV generation and current SOC is above `reserve_min_soc`,
  the controller requests discharging
- if load and PV are equal, or the battery is already at the relevant reserve
  boundary, the controller idles

## Controller Support Declaration

**Fields**: `controller_name`, `supported_scenario_kinds`,
`unsupported_reason_template`.

**Relationships**: Published alongside shipped controllers; used by tests and
documentation to verify the support matrix.

**Validation rules**:

- each shipped controller must have one support declaration
- unsupported scenario use must fail deterministically and use the documented
  unsupported reason
- support declarations must align with package-root exports and migration docs

## Controller Package Surface

**Fields**: exported controller classes, exported config types, package-level
`__all__`, package maturity note.

**Relationships**: Public entry point for library consumers who want native
controllers.

**Validation rules**:

- package-root exports must resolve without importing heavy optional research
  stacks
- exported names must match the documented controller pack surface
- the package must remain layered on top of `open_energy_lab.core` and
  `open_energy_lab.simulator` rather than replacing either boundary

## Deterministic Controller Validation Case

**Fields**: `case_id`, `controller_name`, `scenario_kind`, `config_reference`,
`fixture_source`, `expected_properties`, `numeric_tolerance`,
`legacy_references`, `provenance_notes`.

**Relationships**: Defines controller-specific evidence under
`tests/fixtures/simulator` and corresponding unit or integration tests.

**Validation rules**:

- there must be at least one deterministic validation case per shipped
  controller
- expected properties may include exact requests, exact realized traces, or
  invariant checks, but must always include repeated-run determinism
- `numeric_tolerance` defaults to absolute `1e-6`
- the case must identify whether it covers controller-pack behavior,
  preserved-path regression, or both

## Preserved Path Regression Case

**Fields**: `case_id`, `scenario_kind`, `preserved_path`, `expected_invariants`,
`fixture_reference`.

**Relationships**: Protects existing explicit-dispatch and built-in simulator
rule behavior while the control package is added.

**Validation rules**:

- preserved path must be either `explicit_dispatch` or `built_in_rule`
- each preserved path case must remain independent of the native control
  package implementation details
- failures in preserved-path tests must be attributable without depending on
  controller-specific fixtures
