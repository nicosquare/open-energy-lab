# TPM Fixtures

This directory holds deterministic, offline fixtures for the
`009-tpm-planning` dataset, TPM artifact, and query contracts. Schema-v2 and
schema-v3 artifacts separate their JSON manifest from a project-relative
sidecar and record a SHA-256 digest.

## Active Fixture Set

- `declared_feature_domains_v1.json`: reviewable U-Bounds declarations,
  physical training rows, and exact domain/compiler probes without fitted
  model output.
- `tpm_artifact_domains_v3.json`: reproducibly fitted schema-v3 production
  manifest carrying declared domains, observed support, normalization meaning,
  and native-query evidence.
- `sidecars/tpm_artifact_domains_v3.spn_payload.pkl`: real current-SPFlow model
  sidecar referenced by the declared-domain v3 manifest.
- `planning_dataset_v1.json`: supported planning-dataset artifact.
- `tpm_artifact_spflow_v1.json`: reproducibly fitted schema-v2 production
  manifest for required current SPFlow 1.1 validation.
- `sidecars/tpm_artifact_spflow_v1.spn_payload.pkl`: real current-SPFlow
  model sidecar referenced by the production manifest.
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

`tpm_artifact_spflow_v1.json` records `schema_version=v2`,
`backend_generation=current-spflow`, `backend_api_version=1.1.0`, and
`execution_mode=production`. Its model sidecar was fitted from the 36
deterministic generic rows defined by
`examples/tpm_planning/run_generic_rows_pipeline.py::_training_rows` with seed
`13`. The manifest records the complete source-row configuration, translated
fit configuration, Torch determinism settings, stable fit summary, compiler
version, supported module types, five canonical breakpoints, MIO epsilon
`1e-6`, and the sidecar SHA-256 digest.

Regeneration verifies stable structure, parameters, likelihoods, native query
results, compiler output, and canonical-point probability parity within the
documented tolerances. It deliberately does not require pickle-byte equality;
the newly written sidecar digest is persisted and subsequently verified by the
artifact loader.

`tpm_artifact_v2.json` separately records `backend_generation=current-spflow`,
`backend_api_version=1.1.0`, `execution_mode=fixture_replay`, a relative
sidecar locator, and the sidecar SHA-256 digest. Loading the manifest by path
verifies that the sidecar exists inside the manifest directory and matches the
digest.

The replay v2 sidecar is contract evidence, not a serialized production model.
It sets `production_model=false`; it remains only to validate explicit
empirical replay without weakening the separate required production fixture.

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

`declared_feature_domains_v1.json` is the source-input contract for feature
`014-declared-feature-domains`. It declares scalar decision $x\in[40,160]$,
fully unbounded demand support, an ordered binary decision, and a complete
categorical decision whose `priority` value is deliberately unobserved. Its
physical rows cover only $x\in[60,140]$. Endpoint, adjacent-outside, identity,
unobserved-category, and compiler-validity probes are mathematical expectations,
not generated SPFlow or MIO results.

`tpm_artifact_domains_v3.json` is the corresponding generated production
evidence. It was fitted offline on CPU with seed `13`, schema `v3`, current
SPFlow `1.1.0`, Torch `2.13.0`, and the manifest-recorded CPython version. The
current sidecar SHA-256 is
`4b3a9fcf0b5cfbcade6c2ae09e52ada8bbbf3b091323cebce13c6d99da438273`.
The fixture records exact membership checks at $x=40$ and $x=160$ plus their
adjacent representable outside values, caller-coordinate checks for the
unobserved `priority` category, identity normalization at demand `250`, and
real queries at both decision endpoints and the unobserved category. Domain
membership has no tolerance; model-coordinate comparisons use `1e-12`, and
native-probability repeatability uses `1e-6`. The probability for an
unobserved declared value is evidence produced by the backend, not a
theoretical claim or fabricated observation.

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

`declared_feature_domains_v1.json`

- status: active model-output-free input fixture
- validation target: declaration resolution, physical support, exact domain
  membership, stable transforms, native querying, and explicit compiler
  validity
- seed: fitting seed `13`; the committed physical rows themselves are
  reviewable source evidence rather than generated output
- refresh policy: update only with an intentional U-Bounds contract change;
  review declarations, rows, probes, and assertion-tolerance purposes together
- domain membership: exact, with no borrowed numerical tolerance
- future production refresh command:
  `uv run --locked --no-sync python examples/tpm_planning/run_declared_domains_pipeline.py --regenerate-fixture`

`tpm_artifact_domains_v3.json`

- status: supported schema-v3 production manifest
- backend contract: current SPFlow `1.1.0`, Torch `2.13.0`, CPU, seed `13`
- source: `declared_feature_domains_v1.json` and its recorded SHA-256
- sidecar: `sidecars/tpm_artifact_domains_v3.spn_payload.pkl`
- sidecar SHA-256:
  `4b3a9fcf0b5cfbcade6c2ae09e52ada8bbbf3b091323cebce13c6d99da438273`
- validation target: declared versus observed support, persisted transforms,
  exact boundary behavior, sidecar/manifest semantic agreement, reload,
  endpoint queries outside observed support, and an unobserved category query
- tolerances: exact domain membership, `1e-12` model coordinates, `1e-6`
  native probability repeatability
- generation command:
  `uv run --locked --no-sync python examples/tpm_planning/run_declared_domains_pipeline.py --regenerate-fixture`
- verification command:
  `uv run --locked --no-sync python examples/tpm_planning/run_declared_domains_pipeline.py --verify-fixture`
- refresh policy: compare semantic and numeric evidence rather than pickle-byte
  identity; regenerate only after an intentional input or contract change

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

`tpm_artifact_spflow_v1.json`

- status: supported schema-v2 production manifest
- backend contract: required current SPFlow `1.1.0`
- execution mode: `production`
- sidecar serialization: `spflow-model-sidecar`
- compiler contract: `spflow-v1-mio-v1`, Normal/Bernoulli/Categorical leaves,
  sum/product composition, one channel/repetition, five breakpoints, and MIO
  epsilon `1e-6`
- validation target: real fit, reload, sidecar hash verification, native query,
  compiler parity, and `1e-9` semantic repeatability
- seed: training seed `13`
- refresh policy: run the checked-in regeneration command only when the source
  rows, fit configuration, required backend, compiler, or artifact contract
  intentionally changes

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

## Production Regeneration And Verification

Regenerate the real production manifest and sidecar offline from the repository
root:

```bash
uv run python examples/tpm_planning/run_generic_rows_pipeline.py --regenerate-fixture
```

Verify sidecar integrity and refit the same model in a temporary directory to
compare stable semantic evidence:

```bash
uv run python examples/tpm_planning/run_generic_rows_pipeline.py --verify-fixture
```

Both commands require the locked SPFlow 1.1 installation. They do not use the
network, notebooks, legacy runtimes, Pyomo, HiGHS, Gurobi, or external data.

Regenerate or verify the separate declared-domain schema-v3 production
evidence with:

```bash
uv run --locked --no-sync python \
  examples/tpm_planning/run_declared_domains_pipeline.py --regenerate-fixture
uv run --locked --no-sync python \
  examples/tpm_planning/run_declared_domains_pipeline.py --verify-fixture
```

These commands consume `declared_feature_domains_v1.json` and verify the
manifest-recorded source digest. They run offline on CPU after dependencies are
installed; notebook, network, GPU, and commercial-solver paths are not part of
this fixture.

## U-Bounds Compatibility Freeze

The following pre-feature evidence files are immutable compatibility anchors:

- `tpm_artifact_v1.json`
- `tpm_artifact_v2.json`
- `sidecars/tpm_artifact_v2.fixture.json`
- `tpm_artifact_spflow_v1.json`
- `sidecars/tpm_artifact_spflow_v1.spn_payload.pkl`
- `tpm_artifact_unsupported_version.json`

U-Bounds tests may snapshot, load, query, and compare these files, but must not
rewrite or regenerate them into schema v3. A changed byte requires a separate,
explicit compatibility review; loading alone never authorizes a refresh.

## Replay Integrity Refresh

After intentionally changing the replay sidecar, compute its digest offline:

```bash
sha256sum tests/fixtures/tpm/sidecars/tpm_artifact_v2.fixture.json
```

Update the replay `tpm_artifact_v2.json` and the schema-v2-shaped unsupported
fixture with that exact digest. Never weaken verification or use an absolute,
parent-traversing, or network sidecar locator.

## Working Rule

Keep fixtures loadable or rejectable without runtime imports from `legacy/*`,
network access, notebook execution, or commercial solver licenses. Preserve
the boundary between simulator-owned datasets, TPM-owned artifact/query
metadata, and planning-owned solve behavior.
