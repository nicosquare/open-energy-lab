# Data Model: Visualization And Trace Inspection MVP

This feature introduces the first reusable visualization package in
`open_energy_lab.visualization`. The model layers on top of deterministic run
outputs already produced by `open_energy_lab.simulator` and
`open_energy_lab.core`.

## Inspection View

**Fields**: `scenario_id`, `scenario_kind`, `trace_series`, `summary_outcomes`,
`available_sections`, `maturity`, `source_kind`.

**Relationships**: Produced from a supported simulator trace or
controller-evaluation result; exported through the stable visualization
package surface; may feed comparison and plotting requests.

**Validation rules**:

- `scenario_kind` must match a supported run family.
- `trace_series` must preserve timestep ordering from the underlying run
  output.
- `available_sections` must explicitly distinguish present versus unavailable
  optional sections such as weather.
- `maturity` must align with the documented stable inspection/reporting policy.

## Trace Series

**Fields**: `series_name`, `values`, `units`, `step_labels`,
`display_category`, `source_field`, `optional`.

**Relationships**: Belongs to one inspection view; may be selected for static
plotting; may participate in same-family comparison.

**Validation rules**:

- every series length must align to the underlying timestep count
- `units` must be explicit for numeric series
- `source_field` must map to one supported result attribute or derived weather
  reporting field already exposed by the simulator
- optional series must fail closed: unavailable is explicit, not inferred

## Summary Outcome

**Fields**: `summary_name`, `value`, `units`, `source_field`, `display_group`.

**Relationships**: Belongs to one inspection view; may be compared across two
  runs from the same scenario family.

**Validation rules**:

- summary values must be deterministic for the same underlying run output
- settlement-relevant totals must match the underlying result exactly within
  the documented numeric tolerance
- summary names must remain stable once promoted into the stable inspection
  surface

## Comparison View

**Fields**: `left_run`, `right_run`, `scenario_kind`, `aligned_series`,
`series_differences`, `summary_differences`, `unsupported_reason` (optional).

**Relationships**: Built from two inspection views from the same scenario
family; may feed textual review or later experimental presentation helpers.

**Validation rules**:

- both input runs must belong to the same supported scenario family
- aligned series must preserve shared timestep ordering
- unsupported comparison attempts must produce an explicit
  `unsupported_reason`
- comparison output must remain deterministic for repeated requests over the
  same two inputs

## Plot Request

**Fields**: `target_run`, `series_names`, `plot_kind`, `output_mode`,
`source_location`, `requires_optional_backend`.

**Relationships**: Consumes one inspection view or compatible persisted run
output; executed through the experimental plotting layer only.

**Validation rules**:

- `plot_kind` in the MVP is limited to basic static single-run plots
- `series_names` must reference supported available series
- the request must not require a fresh simulation run
- unsupported requested series combinations must fail deterministically

## Persisted Run Output

**Fields**: `scenario_id`, `scenario_kind`, `time_step_hours`,
`requested_power_kw` (optional), `realized_power_kw`, `step_settlement`,
`trace_payload`, `summary_payload`, `provenance_notes`.

**Relationships**: Stored representation of a supported run result that can be
loaded later for inspection or plotting; may originate from existing simulator
fixtures or dedicated visualization fixtures.

**Validation rules**:

- persisted outputs must contain enough information to reconstruct supported
  inspection views without rerunning simulation
- payload contents must be small enough for committed fixtures when stored in
  the repository
- scenario-family-specific optional fields such as `weather` or `pv` must be
  explicit when present and explicit when absent

## Visualization Package Surface

**Fields**: stable inspection/reporting exports, experimental plotting exports,
package-level maturity note, import boundary guarantees.

**Relationships**: Public entry point for users who want canonical run
inspection and bounded plotting support.

**Validation rules**:

- base package imports must resolve without optional plotting dependencies
- stable exports must not expose notebook-first or dashboard-only workflows
- experimental plotting exports must remain outside the stable root contract
  unless promoted by a later feature

## Deterministic Visualization Validation Case

**Fields**: `case_id`, `scenario_kind`, `input_reference`, `inspection_expectations`,
`comparison_expectations` (optional), `plot_expectations` (optional),
`numeric_tolerance`, `provenance_notes`.

**Relationships**: Defines evidence under `tests/fixtures/simulator` or
`tests/fixtures/visualization` and corresponding unit or integration tests.

**Validation rules**:

- there must be at least one inspection case per supported scenario family
- there must be at least one persisted-output case proving no-resimulation
  plotting or inspection
- comparison expectations apply only to same-family cases
- `numeric_tolerance` defaults to absolute `1e-6`
