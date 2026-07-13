# TPM Fixtures

This directory now holds the committed User Story 1 and User Story 2 TPM
fixtures for the `009-tpm-planning` feature. They are trimmed, deterministic,
and explicit about provenance so dataset reload, TPM artifact reload, and
query review can stay entirely offline.

## Active Fixture Set

- `planning_dataset_v1.json`
- `tpm_artifact_v1.json`
- `tpm_artifact_unsupported_version.json`
- `tpm_query_case.json`

`planning_dataset_v1.json` is a committed, loadable planning-dataset artifact.
It preserves the current-library export contract directly at the top level so
`open_energy_lab.planning.dataset.load_planning_dataset()` can reload it
without any wrapper transformation.

`tpm_artifact_v1.json` is a committed, loadable TPM artifact fixture derived
from the planning-dataset artifact fixture and a fake SPFlow backend summary.
It preserves typed feature metadata, fit configuration, piecewise metadata,
and query configuration in one reviewable JSON payload.

`tpm_artifact_unsupported_version.json` is the same committed artifact shape
with only `schema_version` changed to `v999` so offline fail-fast version
coverage remains explicit.

`tpm_query_case.json` stores one deterministic query request plus its expected
response. It replays the committed supported TPM artifact against the
committed planning-dataset artifact through the current-library empirical
query path.

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

Artifact fixtures keep the full persisted payload needed by
`open_energy_lab.tpm.load_tpm_artifact`, with fixture metadata left in place
so integration schema checks validate provenance and runtime compatibility at
the same time. Query fixtures keep the request payload and expected response
needed by `TPMQueryRequest` and `query_tpm_artifact`.

## Fixture Records

`planning_dataset_v1.json`

- purpose: supported planning-dataset artifact fixture for offline TPM fit
  and reload review
- status: active
- origin: current-library export replay derived from the committed planning
  export case
- expected validation target: deterministic dataset reload, row order, and
  flattened-column review
- random seed: paired family seed `13`
- access, license, or network notes: entirely offline
- refresh policy: update only when the planning-dataset schema or export
  provenance contract intentionally changes

`tpm_artifact_v1.json`

- purpose: supported TPM artifact fixture for offline reload and query review
- status: active
- origin: current-library artifact fixture derived from
  `tests/fixtures/tpm/planning_dataset_v1.json`
- expected validation target: supported artifact schema, typed feature reload,
  and query-metadata coverage
- SPN payload representation: fake backend summary stored directly as JSON
- random seed: training seed `13`
- access, license, or network notes: entirely offline
- refresh policy: update only when the TPM artifact schema, fit metadata,
  typed-feature ordering, or canonical piecewise contract intentionally
  changes

`tpm_artifact_unsupported_version.json`

- purpose: unsupported-version TPM artifact fixture
- status: active
- origin: copy of the supported artifact with only `schema_version` changed
- expected validation target: explicit unsupported-version fail-fast coverage
- random seed: training seed `13`
- access, license, or network notes: entirely offline
- refresh policy: update only when the explicit schema compatibility contract
  intentionally changes

`tpm_query_case.json`

- purpose: deterministic query request and expected response fixture
- status: active
- origin: current-library query replay against the committed supported TPM
  artifact
- expected validation target: conditional-probability replay, explicit
  marginalization, and decision-feature assignment coverage
- replay source: committed planning-dataset artifact referenced by TPM
  artifact provenance
- random seed: training seed `13`
- access, license, or network notes: entirely offline
- refresh policy: update only when the query request shape or expected
  response semantics intentionally change

## Working Rule

Keep active fixtures loadable without runtime imports from `legacy/*`. For
loadable artifact fixtures, retain both the common fixture provenance fields
and the runtime artifact keys in one top-level JSON object so schema checks
and offline loaders validate the same committed payload.
