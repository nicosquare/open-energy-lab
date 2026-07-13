# Planning Fixtures

This directory holds planning-domain fixtures for the
`009-tpm-planning` feature. The simulator export case is now active and points
to the committed planning-dataset artifact under `tests/fixtures/tpm/`. The
planning-problem fixture is now also active and records the first-release
planning definition, deterministic assembly baseline, and optional-solve
expectations used by the offline US3 review path.

## Reserved Fixture Set

- `planning_dataset_export_case.json`
- `planning_problem_case.json`

`planning_dataset_export_case.json` is the active workflow fixture for User
Story 1. It records the fixture-backed weather and demand inputs, the design
metadata rows, the flattened series request, and the expected dataset artifact
path used to regenerate `tests/fixtures/tpm/planning_dataset_v1.json`.

`planning_problem_case.json` is the active workflow fixture for User Story 3.
It records:

- the committed TPM artifact fixture path consumed by planning assembly
- the exact `PlanningProblemDefinition` payload for the first-release
  battery-and-solar scope
- solver-configuration and approximation-contract provenance
- the deterministic candidate baseline used to validate offline assembly
- the expected optimal and skipped summaries for fake-backend optional solve
  checks

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

Active planning-problem fixtures should additionally record any artifact or
dataset fixture paths, solver backend names, and generation commands needed to
replay the deterministic assembly or optional-solve workflow offline.

## Working Rule

Keep active fixtures small, deterministic, and reviewable in git. When a
workflow fixture references a committed artifact in another fixture directory,
update both files together so provenance, row counts, and contract references
stay aligned.
