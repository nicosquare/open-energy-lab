# Contract: Typed Controller Configurations

This contract defines the minimum expectations for the native controller
configuration surfaces.

## Purpose

Controller configurations must be typed, deterministic, and small enough to
review without external schemas or framework dependencies.

## Shared Rules

Every shipped controller configuration must:

- use explicit typed fields rather than free-form dictionaries
- validate invalid threshold or guardrail combinations before controller
  evaluation
- contain only deterministic values needed for current-step behavior
- avoid references to full-horizon forecasts, training metadata, or solver
  objects

## Price Threshold Configuration

The price-threshold config must define:

- a charge threshold
- a discharge threshold
- positive request magnitudes for charge and discharge behavior

The config must reject:

- `charge_threshold >= discharge_threshold`
- non-numeric threshold values
- non-positive request magnitudes

## SOC Guardrail Configuration

The SOC guardrail config must define:

- a lower SOC guardrail
- an upper SOC guardrail
- positive request magnitudes for corrective charge and discharge behavior

The config must reject:

- guardrails outside `[0.0, 1.0]`
- `lower_guardrail >= upper_guardrail`
- non-positive request magnitudes

## PV Self-Consumption Configuration

The PV self-consumption config must define:

- a reserve floor SOC
- a reserve ceiling SOC
- positive request magnitudes for charging and discharging behavior

The config must reject:

- reserve values outside `[0.0, 1.0]`
- `reserve_floor >= reserve_ceiling`
- non-positive request magnitudes

## Public Reviewability

Configuration defaults, field meanings, and validation failures must be
documented in the migration note and covered by focused tests so users can
understand controller behavior without reading implementation internals.
