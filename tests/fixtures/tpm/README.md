# TPM Fixtures

## Conditional MIO embedding input (`conditional_mio_embedding_v1.json`)

`conditional_mio_embedding_v1.json` is the authoritative, human-reviewable source input for
feature `016-conditional-mio-embedding`. The rows were written and reviewed directly; they are not
generated model output and do not come from a legacy repository. Each row contains physical values
for one continuous decision (`x`), one binary decision (`activation`), one ordered categorical
decision (`service_tier`), one unbounded marginalized uncertainty (`demand`), and the explicit
binary event `violation = 1[demand > x]`.

The continuous observations are deliberately nonuniform: most source rows lie below `x = 90`, even
though the declared decision domain and compiler interval are `[40, 160]`. This makes the learned
denominator scientifically material and prevents a uniform-density shortcut from passing the
reviewed case accidentally. Both binary states, all three categories, and both event values occur
in the source table.

The fixture fixes one fit seed and one set of SPFlow structure-learning options. The current-SPFlow
minimum/default `min_features_slice=2` is recorded explicitly. A maintainer refresh performs
exactly one fit and fails if the retained graph and conditioned circuits do not contain a
genuine learned Sum node; it does not change seeds, retry, or adapt fitting options. The three
representative assignments cover both continuous boundaries, one interior point, both binary states,
and all categories without enumerating their Cartesian product.

The JSON also declares the max and PWL compiler policies, the physical approximation interval, and
purpose-labelled numerical tolerances. Those are source inputs rather than hand-edited derived
evidence. The active feature evidence is:

- `tpm_artifact_conditional_mio_v3.json` and its sidecar are the reviewed real-fit source artifact;
- `conditional_pair_max_v1.json` and `conditional_pair_pwl_v1.json` are the immutable max and PWL
  pairs compiled from that artifact after mixed symbolic continuous/binary/categorical support was
  implemented; and
- `conditional_mio_evidence_v1.json` contains separate immutable direct/HiGHS parity and
  native/compiler fidelity records for both pairs.

Committed source or derived evidence is never repaired or overwritten in place. A refresh writes to
a fresh staging directory, records row/configuration digests and backend/compiler versions, and is
reviewed as an ordinary source-control change. Normal verification is read-only and fails on any
mismatch.

The reviewed source artifact was fitted offline on CPU with CPython `3.14.6`, current SPFlow
`1.1.0`, Torch `2.13.0+cu130`, fit seed `16028`, and the options in the source JSON. Its compiler
contracts are base MIO compiler `spflow-v1-mio-v2` and conditional-pair compiler
`conditional-mio-v1`. Current exact byte digests and pair identities are:

- source JSON: `394f4ab76de48457f36ea03e451fbb608b66b8660ca1374b92f6260396b110bd`;
- artifact manifest: `58e56e7adf850d604e41933479260cce22e90da4f40ac5838fab7578d88dac44`;
- current-SPFlow sidecar: `2157d35ec4d18c230e8c01a074dae271c0cb161af1520582325420361bb7bc6f`;
- max pair: SHA-256 `73a7cc0c4e6736e3f84c699ef9279fc88345b8349e92c3add630394e8811d8f7`,
  pair ID `17e45b6b387b637a0444bf021c7ea3b2d3d2703635d8fd83b4250cdc6363dea9`;
  and
- PWL pair: SHA-256 `87eeaff775dfc3ec0f276cd5080d90e5d5dcce71e20e5ae1f82b5f03e19c1a3f`,
  pair ID `f51291a32167baa744bbc7ba0232a50d2bc5f2be941c990c40a7c39b52774a83`;
- evidence bundle: SHA-256
  `8a80c32139b25d8c97de2d654a131031c4df59cf91a96fbbfd012c78433f533b`;
- max/PWL parity evidence IDs:
  `830d50d24483d512fdc4952306186adb8eea6b77bbcbb3e96be8405353fa16e2` and
  `547c580da250fbc593ec09e45ee97c5d017eb73dc3213a34c14235eed3ec44df`; and
- max/PWL fidelity evidence IDs:
  `5792a07a8b5f6e7c1089d174cfb7c08225a3441e966e92233ed4246d95faaea9` and
  `c61869f3a8dfda6f65eb73deb898f062b0148a1e77685cca943f491fc6c86f3b`.

Maintainers create candidate evidence only in a fresh directory:

```bash
uv run --offline --locked --no-sync python \
  examples/tpm_planning/run_conditional_mio_embedding.py \
  --stage-fixtures /tmp/oel-conditional-mio-review
```

Final pairs can be restaged from the already-reviewed committed artifact without refitting it:

```bash
uv run --offline --locked --no-sync python \
  examples/tpm_planning/run_conditional_mio_embedding.py \
  --stage-pairs /tmp/oel-conditional-mio-pairs-review
```

Separate parity and fidelity evidence can be staged from the immutable pairs:

```bash
uv run --offline --locked --no-sync python \
  examples/tpm_planning/run_conditional_mio_embedding.py \
  --stage-evidence /tmp/oel-conditional-mio-evidence-review
```

Routine verification is read-only and includes a one-shot temporary semantic refit:

```bash
uv run --offline --locked --no-sync python \
  examples/tpm_planning/run_conditional_mio_embedding.py --verify-fixtures
```

This directory holds deterministic, offline fixtures for the
`009-tpm-planning` dataset, TPM artifact, and query contracts. Schema-v2 and
schema-v3 artifacts separate their JSON manifest from a project-relative
sidecar and record a SHA-256 digest.

## Active Fixture Set

- `conditional_mio_embedding_v1.json`: reviewed nonuniform mixed-feature source rows and fixed
  fit/compiler inputs for feature 016.
- `tpm_artifact_conditional_mio_v3.json`: reviewed schema-v3 production source artifact for
  conditional compilation.
- `sidecars/tpm_artifact_conditional_mio_v3.spn_payload.pkl`: real current-SPFlow model sidecar
  referenced by the feature-016 source artifact.
- `conditional_pair_max_v1.json`: immutable mixed-decision conditional pair using the declared max
  sum encoding.
- `conditional_pair_pwl_v1.json`: immutable mixed-decision conditional pair using the declared PWL
  sum encoding.
- `conditional_mio_evidence_v1.json`: reviewed six-case evidence bundle containing independent
  max/PWL embedding-parity and compiler-fidelity records.
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

`conditional_mio_embedding_v1.json`

- status: active human-reviewable input fixture
- validation target: deliberate nonuniformity, declared continuous/binary/categorical domains,
  explicit event direction, fixed fit/compiler inputs, representative non-Cartesian assignments,
  and purpose-labelled tolerances
- seed: fitting seed `16028`; the physical rows are manually reviewed rather than randomly
  generated
- refresh policy: one reviewed source change followed by one fresh staging run; no retries,
  adaptive candidates, or in-place overwrite

`tpm_artifact_conditional_mio_v3.json`

- status: supported schema-v3 production source artifact
- backend contract: current SPFlow `1.1.0`, Torch `2.13.0+cu130`, CPU, seed `16028`
- compiler contracts: `spflow-v1-mio-v2` and `conditional-mio-v1`
- source SHA-256: `394f4ab76de48457f36ea03e451fbb608b66b8660ca1374b92f6260396b110bd`
- manifest SHA-256: `58e56e7adf850d604e41933479260cce22e90da4f40ac5838fab7578d88dac44`
- sidecar: `sidecars/tpm_artifact_conditional_mio_v3.spn_payload.pkl`
- sidecar SHA-256: `2157d35ec4d18c230e8c01a074dae271c0cb161af1520582325420361bb7bc6f`
- validation target: eligible U-Bounds semantics, real fit/persist/reload, genuine learned Sum nodes,
  explicit learned denominator, raw native numerator/denominator queries, and temporary max/PWL
  pair compile/persist/reload/direct evaluation
- staging command: `uv run --offline --locked --no-sync python examples/tpm_planning/run_conditional_mio_embedding.py --stage-fixtures <fresh-directory>`
- verification command: `uv run --offline --locked --no-sync python examples/tpm_planning/run_conditional_mio_embedding.py --verify-fixtures`
- refresh policy: verify committed bytes in place; stage replacements only in a new directory for
  ordinary review

`conditional_pair_max_v1.json` and `conditional_pair_pwl_v1.json`

- status: active immutable conditional-pair fixtures
- source artifact: `tpm_artifact_conditional_mio_v3.json`, manifest SHA-256
  `58e56e7adf850d604e41933479260cce22e90da4f40ac5838fab7578d88dac44`
- retained decisions: continuous `x`, binary `activation`, and ordered categorical `service_tier`
- max pair ID: `17e45b6b387b637a0444bf021c7ea3b2d3d2703635d8fd83b4250cdc6363dea9`
- max pair SHA-256: `73a7cc0c4e6736e3f84c699ef9279fc88345b8349e92c3add630394e8811d8f7`
- PWL pair ID: `f51291a32167baa744bbc7ba0232a50d2bc5f2be941c990c40a7c39b52774a83`
- PWL pair SHA-256: `87eeaff775dfc3ec0f276cd5080d90e5d5dcce71e20e5ae1f82b5f03e19c1a3f`
- staging command: `uv run --offline --locked --no-sync python examples/tpm_planning/run_conditional_mio_embedding.py --stage-pairs <fresh-directory>`
- validation target: deterministic pair identity, explicit learned denominator, symbolic discrete
  leaves without Cartesian lookup, selected max/PWL semantics, direct representative evaluation,
  and read-only serialization verification
- refresh policy: changed semantic inputs create distinguishable pair identities; committed pair
  files are never overwritten or repaired during normal verification

`conditional_mio_evidence_v1.json`

- status: active generated validation evidence
- evidence bundle SHA-256:
  `8a80c32139b25d8c97de2d654a131031c4df59cf91a96fbbfd012c78433f533b`
- assignment coverage: lower boundary, interior, and upper boundary for both max and PWL; together
  the cases cover both binary states and all ordered categories without a Cartesian grid
- parity record IDs:
  `830d50d24483d512fdc4952306186adb8eea6b77bbcbb3e96be8405353fa16e2` and
  `547c580da250fbc593ec09e45ee97c5d017eb73dc3213a34c14235eed3ec44df`
- fidelity record IDs:
  `5792a07a8b5f6e7c1089d174cfb7c08225a3441e966e92233ed4246d95faaea9` and
  `c61869f3a8dfda6f65eb73deb898f062b0148a1e77685cca943f491fc6c86f3b`
- parity meaning: objective-free Pyomo/HiGHS roots and attachment-only violation magnitudes are
  compared with direct execution of the identical selected circuit and gated at absolute `1e-6`
- fidelity meaning: compiled-minus-native numerator, denominator, conditional-log-risk, and
  probability differences are retained without an adequacy gate
- staging command: `uv run --offline --locked --no-sync python examples/tpm_planning/run_conditional_mio_embedding.py --stage-evidence <fresh-directory>`
- verification command: `uv run --offline --locked --no-sync python examples/tpm_planning/run_conditional_mio_embedding.py --verify-fixtures`
- refresh policy: evidence changes require new record identities and an ordinary reviewed fixture
  replacement; verification never repairs source, pair, or evidence bytes

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
