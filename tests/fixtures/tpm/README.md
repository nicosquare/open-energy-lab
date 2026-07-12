# TPM Fixtures

This directory currently holds Phase 1 placeholder fixtures for the
`009-tpm-planning` feature. Active deterministic artifacts and query payloads
are introduced in later tasks once the TPM fit, reload, and query contracts
are implemented.

## Reserved Fixture Set

- `planning_dataset_v1.json`
- `tpm_artifact_v1.json`
- `tpm_artifact_unsupported_version.json`
- `tpm_query_case.json`

## Required Provenance Fields

Every committed TPM fixture in this directory should keep these top-level
fields:

```text
fixture_name
fixture_status
purpose
spec_feature
provenance
```

The `provenance` mapping should always record:

- `author`
- `origin`
- `legacy_evidence_paths`
- `generation_command`
- `random_seed`
- `refresh_policy`

## Working Rule

Replace placeholders with active offline fixtures only when the corresponding
artifact or query workflow is implemented, and keep the final payloads
loadable without runtime imports from `legacy/*`.
