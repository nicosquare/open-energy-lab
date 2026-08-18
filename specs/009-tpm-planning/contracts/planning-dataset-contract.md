# Contract: Planning Dataset Artifact

## Purpose

Define the persisted artifact that stores simulator-derived planning data in a
stable, TPM-ready format.

## Schema Expectations

- artifact metadata includes `dataset_id`, `schema_version`, `created_at`,
  `row_count`, `horizon_steps`, `timestep_hours`, and provenance
- dataset schema includes deterministic `column_order`, typed design-feature
  metadata, flattened-series field metadata, and one explicit target
  definition
- rows preserve one simulation instance per row and retain deterministic
  `scenario_index`

## Column Rules

- horizon-indexed columns use `<field>_<step>`
- `shortfall` is reserved for the documented horizon-level unmet-electric-load
  energy ratio
- aliases such as `ghi_<step>` and `load_<step>` are stable and reviewable
- first-release artifacts contain one explicit planning target only

## Reload Expectations

- unsupported schema versions fail fast
- reloading preserves row ordering, column ordering, target metadata, and
  provenance
- artifact contents are sufficient for offline TPM fitting and inspection

## Scope Boundaries

- the artifact is a stable library-owned contract, not a notebook export
- inspection and reload do not import or invoke SPFlow, Pyomo, or a solver;
  this execution boundary does not make the required project dependencies
  optional at installation time
