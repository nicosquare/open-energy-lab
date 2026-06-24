# Contract: Simulator Export Workflow

## Purpose

Define the stable public workflow that turns evaluated simulator family outputs
into a versioned planning dataset artifact.

## Inputs

- one evaluated simulator family result, expected to expose deterministic
  scenario ordering, timestep metadata, and per-scenario traces
- the aligned weather-family reference needed for flattened weather columns
- caller-provided design metadata for every exported scenario row
- an export configuration that names flattened fields and one target
  definition

## Required Behavior

- validate that simulator results, weather traces, and design metadata align
  on scenario count, scenario ordering, timestep, and horizon length
- flatten requested per-step fields using the canonical `<field>_<step>`
  naming convention
- derive `shortfall` from simulator `unmet_load_kw`,
  `site_electric_load_kw`, and `timestep_hours`
- persist deterministic column ordering and row ordering
- record provenance, including family identifiers, seeds, and export options

## Failure Behavior

- fail fast when family horizons or timestep metadata do not align
- fail fast when design metadata is missing for any row or contains
  inconsistent feature names
- fail fast when requested flattened fields are unsupported
- fail fast when the configured target cannot be derived from the exported
  simulator outputs

## Output

- one versioned planning dataset artifact suitable for TPM fitting, reload,
  fixture validation, and manual inspection
