# Contract: Validation And Review Boundary

## Default Review Path

- review remains offline and fixture-backed
- simulator export, dataset reload, TPM metadata validation, query fixtures,
  and planning model assembly checks must run without notebooks, live
  services, GPUs, or commercial solver licenses
- package-root import checks must continue to pass without backend
  dependencies installed

## Required Fixture Coverage

- committed planning-dataset export fixture
- committed TPM artifact or metadata fixture
- committed conditional-query fixture
- committed planning-problem assembly fixture
- import-boundary and no-legacy-import checks

## Optional Follow-Up Checks

- solver-backed planning solve checks when supported solver binaries or
  licenses are available
- SPFlow-backed fit or query follow-up checks when the backend dependency is
  installed
- legacy tangent test comparisons when Pyomo and a supported solver are
  available

## Documentation Requirements

- skipped optional checks must be documented in quickstart notes or final
  implementation review output
- validation commands must list only checks relevant to changed files
