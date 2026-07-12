# Contract: Planning Problem Assembly And Optional Solve

## Purpose

Define the stable first-release planning surface that consumes a fitted TPM
artifact and deterministic cost metadata to evaluate direct chance-constrained
design decisions.

## Problem Definition

- decision variables are native typed variables derived from the persisted
  feature schema
- the first release supports battery and solar decision variables only
- deterministic cost metadata, `shortfall` threshold, and chance limit
  `epsilon` are explicit inputs
- the canonical solver-facing approximation path is piecewise

## Assembly Requirements

- model assembly must validate feature types, bounds, and target compatibility
- model assembly must succeed without solving when solver backends are
  unavailable
- model metadata must record approximation settings and solver assumptions

## Solve Requirements

- when a supported solver backend is available, the workflow may solve for one
  minimum-cost feasible design
- the first-release adequacy rule is
  `P(shortfall > threshold) <= epsilon`
- outputs include selected design values, objective value, estimated risk, and
  deterministic feasibility diagnostics

## Failure Behavior

- unsupported decision-variable requests outside first-release scope fail fast
- incompatible target definitions or missing cost terms fail fast
- unavailable solver backends surface only when the solve path is invoked
  explicitly
