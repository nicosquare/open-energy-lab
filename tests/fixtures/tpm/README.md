# TPM Fixtures

This directory holds TPM-domain fixtures for the `009-tpm-planning` feature.
The planning-dataset artifact fixture is now active for User Story 1, while
the TPM artifact and query fixtures remain placeholders until the fit, reload,
and query contracts are implemented.

## Reserved Fixture Set

- `planning_dataset_v1.json`
- `tpm_artifact_v1.json`
- `tpm_artifact_unsupported_version.json`
- `tpm_query_case.json`

`planning_dataset_v1.json` is a committed, loadable planning-dataset artifact.
It preserves the current-library export contract directly at the top level so
`open_energy_lab.planning.dataset.load_planning_dataset()` can reload it
without any wrapper transformation.

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

Keep active fixtures loadable without runtime imports from `legacy/*`. For
loadable artifact fixtures, retain both the common fixture provenance fields
and the runtime artifact keys in one top-level JSON object so schema checks
and offline loaders validate the same committed payload.
