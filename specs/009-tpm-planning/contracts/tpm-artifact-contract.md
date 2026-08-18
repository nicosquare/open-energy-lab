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
- production fitting uses the current supported SPFlow API and records its
  backend generation, API version, PyTorch seed/configuration, and model
  sidecar integrity metadata
- production output uses schema v2 with a project-relative sidecar locator and
  SHA-256 digest; manifest and sidecar replacement use atomic sibling-file
  writes

## Reload Contract

- reloading works offline from the persisted artifact contract
- unsupported schema versions fail fast; schema-v1 legacy artifacts return an
  explicit incompatibility/refit error
- reloading reconstructs enough metadata to validate feature assignments,
  marginalization requests, and target semantics
- pre-1.0 SPFlow payloads are rejected as incompatible and must be rebuilt by
  refitting their source planning dataset with the current backend

## Query Contract

- callers can provide decision-feature assignments while marginalizing
  non-decision features
- the query surface returns conditional probability or log-likelihood outputs
  for the configured `shortfall` target
- numeric tolerances, approximation assumptions, and any backend dependency
  requirements are documented in the artifact metadata
- production queries require a valid current-SPFlow model payload and fail
  explicitly if it is unavailable or incompatible
- empirical replay is accepted only when callers explicitly request
  `fixture_replay` mode; it never activates as an automatic fallback

## Scope Boundaries

- runtime imports from `legacy/*` are forbidden
- required SPFlow fit or query code stays behind lazy adapters so ordinary
  package imports remain light; lazy import does not mean optional installation
- the current-SPFlow-to-piecewise-MIO compiler declares and validates its supported module
  and leaf types, and compiled probabilities are checked against native SPFlow
  likelihood evaluation
- the first-release compiler accepts sum/product structure with one output
  channel and repetition plus Normal, Bernoulli, and Categorical leaves on
  separate typed scopes; all other modules and graph shapes fail with explicit
  type/scope diagnostics
- native-versus-compiled probability error is at most `1e-6`, and repeated
  canonical evaluations agree within `1e-9`
- canonical fixtures use five piecewise breakpoints; explicit overrides are
  recorded in artifact metadata
- lower-tangent-only behavior is not the canonical first-release planning
  contract
