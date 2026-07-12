# Planning Fixtures

This directory currently holds Phase 1 placeholder fixtures for the
`009-tpm-planning` feature. Active deterministic payloads are introduced in
later tasks once the simulator export and planning assembly contracts are
implemented.

## Reserved Fixture Set

- `planning_dataset_export_case.json`
- `planning_problem_case.json`

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

Replace placeholders with active offline fixtures only when the corresponding
workflow is implemented, and keep the final payloads small, deterministic, and
reviewable in git.
