# Planning Fixtures

This directory holds planning-domain fixtures for the
`009-tpm-planning` feature. The simulator export case is now active and points
to the committed planning-dataset artifact under `tests/fixtures/tpm/`, while
the planning-problem fixture remains a placeholder until the planning assembly
surface is implemented.

## Reserved Fixture Set

- `planning_dataset_export_case.json`
- `planning_problem_case.json`

`planning_dataset_export_case.json` is the active workflow fixture for User
Story 1. It records the fixture-backed weather and demand inputs, the design
metadata rows, the flattened series request, and the expected dataset artifact
path used to regenerate `tests/fixtures/tpm/planning_dataset_v1.json`.

## Required Provenance Fields

Every committed planning fixture in this directory should keep these top-level
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

Keep active fixtures small, deterministic, and reviewable in git. When a
workflow fixture references a committed artifact in another fixture directory,
update both files together so provenance, row counts, and contract references
stay aligned.
