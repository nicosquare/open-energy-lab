# Contract: Planning Problem Assembly And Solve

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
- model assembly remains independently inspectable without invoking a solver
- model metadata must record approximation settings and solver assumptions

## Solve Requirements

- omission of solver configuration selects Pyomo `SolverFactory("highs")`
  backed by the required `highspy` installation
- routine validation solves for one minimum-cost feasible design with HiGHS
- the first-release adequacy rule is
  `P(shortfall > threshold) <= epsilon`
- outputs include selected design values, objective value, estimated risk, and
  deterministic feasibility diagnostics

## Failure Behavior

- unsupported decision-variable requests outside first-release scope fail fast
- incompatible target definitions or missing cost terms fail fast
- a missing or incompatible Pyomo/HiGHS installation is an explicit project
  installation error and cannot produce a successful or skipped routine check
- an unavailable explicitly selected supplemental solver such as Gurobi may
  produce a documented skip when its binary or license is absent
