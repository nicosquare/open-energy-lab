# Contract: TPM Artifact And Query Workflow

## Purpose

Define the artifact and public workflow for fitting, loading, and querying a
tractable probabilistic model from planning datasets.

## Fit Contract

- fitting consumes one planning dataset artifact and one explicit target
  definition
- typed feature metadata for continuous, binary, categorical, and mixed
  features is persisted explicitly
- fit configuration, provenance, and approximation metadata are recorded in a
  versioned artifact contract

## Reload Contract

- reloading works offline from the persisted artifact contract
- unsupported schema versions fail fast
- reloading reconstructs enough metadata to validate feature assignments,
  marginalization requests, and target semantics

## Query Contract

- callers can provide decision-feature assignments while marginalizing
  non-decision features
- the query surface returns conditional probability or log-likelihood outputs
  for the configured `shortfall` target
- numeric tolerances, approximation assumptions, and any backend dependency
  requirements are documented in the artifact metadata

## Scope Boundaries

- runtime imports from `legacy/*` are forbidden
- SPFlow-backed fit or query code must stay behind lazy adapters so ordinary
  package imports remain light
- lower-tangent-only behavior is not the canonical first-release planning
  contract
