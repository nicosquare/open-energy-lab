# Contract: Canonical Inspection Views

This contract defines the minimum behavior of the stable inspection/reporting
surface for supported deterministic runs.

## Purpose

Inspection views must give maintainers and library consumers one consistent
way to review supported run outputs without bespoke traversal code.

## Supported Inputs

The stable inspection surface must accept:

- supported arbitrage run outputs
- supported battery + load + PV run outputs
- supported controller-driven evaluation results
- supported persisted outputs that contain enough data to reconstruct the same
  inspection view later

## Required Inspection Content

When the underlying run provides them, inspection views must surface:

- battery-state traces
- requested and realized dispatch traces
- price traces
- settlement-relevant per-step and total outcomes
- load, PV, and net-grid traces for supported battery + load + PV runs
- weather variables already exposed by the simulator for supported
  weather-backed runs

## Availability Rules

Inspection must:

- preserve timestep ordering
- make missing optional sections explicit
- keep field naming and units stable once promoted into the stable surface
- avoid inventing simulator data that was not present in the input run

Weather reporting must:

- appear only for scenario families that already expose supported weather
  fields
- never expand weather-model scope beyond reporting those fields

## Determinism

For the same supported input, repeated inspection requests must produce:

- the same trace ordering
- the same summary values within absolute tolerance `1e-6`
- the same explicit availability markers for optional sections
