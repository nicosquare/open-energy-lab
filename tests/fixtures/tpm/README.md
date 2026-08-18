# TPM Fixtures

This directory holds deterministic, offline fixtures for the
`009-tpm-planning` dataset, TPM artifact, and query contracts. Schema-v2
artifacts separate their JSON manifest from a project-relative sidecar and
record a SHA-256 digest.

## Active Fixture Set

- `planning_dataset_v1.json`: supported planning-dataset artifact.
- `tpm_artifact_v2.json`: supported schema-v2 current-SPFlow-generation
  manifest in explicit `fixture_replay` mode.
- `sidecars/tpm_artifact_v2.fixture.json`: deterministic replay-only sidecar
  referenced by the schema-v2 manifest.
- `tpm_artifact_v1.json`: legacy schema-v1 rejection and refit evidence.
- `tpm_artifact_unsupported_version.json`: schema-v2-shaped unsupported
  version fixture.
- `tpm_query_case.json`: explicit fixture-replay query and expected response.

`planning_dataset_v1.json` remains loadable without SPFlow, Pyomo, or HiGHS.
It preserves deterministic row and column ordering plus the simulator-derived
`shortfall` target.

`tpm_artifact_v2.json` records `backend_generation=current-spflow`,
`backend_api_version=1.1.0`, `execution_mode=fixture_replay`, a relative
sidecar locator, and the sidecar SHA-256 digest. Loading the manifest by path
verifies that the sidecar exists inside the manifest directory and matches the
digest.

The v2 sidecar is contract evidence, not a serialized production model. It
sets `production_model=false`, and the manifest does not claim real fit/query
validation. T041 owns replacing production examples with reproducibly fitted
current-SPFlow sidecars while retaining clearly labeled replay evidence.

`tpm_artifact_v1.json` is intentionally unsupported. It preserves the prior
inline fake-backend payload only to prove that schema-v1 artifacts fail with
explicit current-SPFlow refit guidance.

`tpm_artifact_unsupported_version.json` mirrors the v2 manifest shape but
uses `schema_version=v999` so unsupported versions fail before sidecar,
feature, or query validation.

`tpm_query_case.json` references the supported v2 manifest and declares
`execution_mode=fixture_replay`. Its `source=empirical_fixture` result is
supplementary deterministic evidence and must never be reported as production
current-SPFlow evidence.

## Required Provenance Fields

Every top-level TPM fixture keeps:

```text
fixture_name
fixture_status
purpose
spec_feature
provenance
```

The `provenance` mapping records:

- `author`
- `origin`
- `legacy_evidence_paths`
- `generation_command`
- `random_seed`
- `refresh_policy`

Artifact manifests retain the complete persisted payload accepted or rejected
by `open_energy_lab.tpm.load_tpm_artifact`. Query fixtures retain the
`TPMQueryRequest` fields and exact expected response.

## Fixture Records

`planning_dataset_v1.json`

- status: supported
- validation target: deterministic reload, row order, flattened columns, and
  simulator-derived `shortfall`
- seed: paired family seed `13`
- refresh policy: only when the planning-dataset or export provenance contract
  intentionally changes

`tpm_artifact_v2.json`

- status: supported schema-v2 replay manifest
- backend contract: current-SPFlow generation, API `1.1.0`
- execution mode: `fixture_replay`
- sidecar serialization: `fixture-replay-evidence-json`
- validation target: schema, backend/mode metadata, safe locator, SHA-256
  integrity, typed feature reload, and query metadata
- seed: training seed `13`
- refresh policy: update the manifest and digest together whenever its sidecar
  or schema-v2 contract changes

`tpm_artifact_v1.json`

- status: active negative-case fixture
- validation target: explicit legacy incompatibility and refit guidance
- production/query use: forbidden
- refresh policy: do not migrate in place

`tpm_artifact_unsupported_version.json`

- status: active negative-case fixture
- origin: v2 manifest shape with `schema_version=v999`
- validation target: fail-fast unsupported-version diagnostics
- refresh policy: keep aligned with the supported v2 manifest shape

`tpm_query_case.json`

- status: supported explicit replay case
- execution mode: `fixture_replay`
- validation target: conditional probability, explicit marginalization,
  decision assignment, and `empirical_fixture` source labeling
- seed: training seed `13`
- refresh policy: only when replay request or response semantics intentionally
  change

## Integrity Refresh

After intentionally changing the replay sidecar, compute its digest offline:

```bash
sha256sum tests/fixtures/tpm/sidecars/tpm_artifact_v2.fixture.json
```

Update `tpm_artifact_v2.json` and the schema-v2-shaped unsupported fixture
with that exact digest. Never weaken verification or use an absolute,
parent-traversing, or network sidecar locator.

## Working Rule

Keep fixtures loadable or rejectable without runtime imports from `legacy/*`,
network access, notebook execution, or commercial solver licenses. Preserve
the boundary between simulator-owned datasets, TPM-owned artifact/query
metadata, and planning-owned solve behavior.
