# Restricted French Reference Fixtures

## Scope And Decision

The repository owner confirmed on 2026-08-22 that this repository is private
and its contents are limited to authorized collaborators. That decision permits
restricted private-repository storage of the governed Feature 010 references
and, after explicit Feature 011 staging on 2026-08-23, the governed restoration
references listed below.

This is permission for restricted private-repository storage only. It does not
claim a public-data license from EPEX SPOT, RTE, or ENTSO-E. It does not claim public redistribution rights.
Private/internal access does not convert the fixture data into public data.
The fixture data is not offered under the repository's Apache-2.0 license.

### Feature 010 day-ahead and FCR

Feature 010 stores these three real-data reference fixtures:

- `tests/fixtures/market/france_2022-08-19_market_v1.json`
- `tests/fixtures/market/france_2022-08-19_activation_v1.json`
- `tests/fixtures/market/france_2022-08-19_expected_replay_v1.json`


### Feature 011 aFRR and mFRR

Feature 011 stores these five normalized or deterministically derived files:

- `tests/fixtures/restoration/france_2026-08-20_afrr_market_v1.json`
- `tests/fixtures/restoration/france_2026-08-20_afrr_scenario_v1.json`
- `tests/fixtures/restoration/france_2026-08-15_mfrr_market_v1.json`
- `tests/fixtures/restoration/france_2026-08-15_mfrr_scenario_v1.json`
- `tests/fixtures/restoration/france_restoration_expected_results_v1.json`

The normalized market artifacts preserve RTE Balancing Energy 5.2 area
observations. The scenarios and results remain restricted because their
deterministic values and plots can reproduce those observations.

## Mandatory Boundary

Access is limited to authorized repository collaborators. All eight governed
fixtures MUST NOT be:

- copied to a public repository, fork, or mirror;
- included in a source or wheel package, release attachment, public CI
  artifact, website, publication supplement, or external artifact store; or
- supplied to a downstream party as a redistributable dataset.

If repository visibility might become public, remove all eight fixtures from
the branch and its proposed public history before changing visibility. A future
public fixture requires a separate reviewed source-rights decision; the
private-repository decision documented here does not satisfy that requirement.
For the unchanged Feature 010 policy specifically, remove all three fixtures
listed in its subsection; Feature 011 additionally requires removal of its five.

Raw ENTSO-E and RTE market responses remain digest-only. ENTSO-E tokens, RTE
client credentials, and RTE OAuth responses remain outside Git and must never
enter an artifact, cache identity, log, notebook output, or documentation
example.

## Feature 010 Staging Workflow

The explicit staging consumer performs no network access and reads no token.
It accepts only the exact, technically validated France period, requires a
positive private-repository acknowledgement, preserves the normalized content
fingerprint, and creates a new artifact fingerprint carrying the restricted
storage policy:

```bash
uv run python examples/bess_stacked_services/stage_private_reference_market.py \
  --market artifacts/market/reference-gate/MARKET_ARTIFACT.json \
  --destination tests/fixtures/market \
  --acknowledge-private-restricted-repository
```

The staged market artifact records `repository_storage` as
`permitted_private_restricted` and `repository_publication` as `prohibited`.
Its policy also prohibits package distribution, release attachment, public
forks and mirrors, and external artifact upload.

Generate the derived replay only from the staged market fixture:

```bash
uv run python examples/bess_stacked_services/generate_reference_replay.py \
  --market tests/fixtures/market/france_2022-08-19_market_v1.json \
  --destination tests/fixtures/market
```

The expected replay repeats the restricted-data policy and fingerprints the
staged source market artifact. Both operations are deterministic and
fail-closed. Unstaged A44 material can be written only beneath ignored
`artifacts/`.

## Feature 011 Staging And Generation Workflow

Feature 011 acquisition is an explicit operation that writes immutable
artifacts below ignored `artifacts/`. The credential-free staging consumer
then accepts only the two pinned RTE profiles and periods, validates every
requested series and the selected study invariants, compares fresh response
digests to planning evidence, scans for secret/raw-body markers, and requires
the private-repository acknowledgement:

```bash
uv run python examples/restoration_services/stage_private_reference_data.py \
  --afrr-artifact artifacts/restoration/reference-acquisition/afrr/ARTIFACT.json \
  --mfrr-artifact artifacts/restoration/reference-acquisition/mfrr/ARTIFACT.json \
  --acknowledge-private-restricted-repository

uv run python examples/restoration_services/generate_reference_results.py \
  --acknowledge-private-restricted-repository
```

The staging command performs no network or credential lookup, has fixed output
paths, and refuses destinations associated with packages, releases, public
repositories, mirrors, CI artifacts, or external stores. The generator uses
only the staged normalized manifests. It creates the two fixed-fraction
`derived_simulation` scenarios and one expected-results fixture atomically and
byte-stably. Neither command persists raw source or OAuth response bytes.

The governed Feature 011 identities are:

| File | Primary semantic fingerprint | File SHA-256 |
| --- | --- | --- |
| aFRR market | `83f0c88e5c8d9c0f781305a9552596c3a03956588a75871e9f78e97415811516` | `5042f7d7d21ec839670b80b22eaa1abcbed2eacb0bc2d1d55367bbd543723799` |
| mFRR market | `d2d4007fafe5138f0bfdc8d91ba232c435f9b4f7097a0cc519064011c624ca10` | `76c5ad31f677a83b7a70d7bb629a4bfa9636b66d2a065302750fdfb8039cec91` |
| aFRR scenario | `fea97fb2e9596e907a7204df9466c355d0ce2493c8c846e85a69093eadcfd9cb` | `b21a9bd4f56fe6fe324ce0e4c93b566b525102f404925301b877f12a8ef9a62c` |
| mFRR scenario | `028b0067c9173c4998d47616d138e395f682f676e1a9d012a1e32769cee6a172` | `8881bb013e8649c8dc86c5c73848dea8611cbce2146c12ced5b6940163169489` |
| Expected results | result set `abe68d7130db368245ca41d972dd41ec5a544ba4ef25d208c93377b3e440586f`; notebook display `88ab88e3859e4fe81555651468bcc9e4c474db43feee11ecd1eef6b18568e976` | `277a3d7c429bc108e42a5ed659d7d954ccc67c30c7d7e67e90083e381044e135` |

Source response SHA-256 values are
`d2496d713c7f217ff76487db2aba0b7a49479861118bea61ca3c001fbbfe2eb3`
for the aFRR hour and
`ce9d3c3d694a78776e5bdb188239f9b2ed4b711e3c389d0e89c8a47e5391d1a1`
for the mFRR quarter. Both are digest-only and have no raw sidecar.

Refreshing source data is never implicit. A matching explicit refresh writes
nothing when normalized content is unchanged and creates a predecessor-linked
artifact when it changes. Any digest or content change requires semantic and
rights review before a new committed reference version is staged; existing
immutable bytes are never overwritten.

The expected staging invariants are four consecutive aFRR PT15M rows with
upward requested need `425, 315, 290, 345 MW` and zero downward requested need,
plus one mFRR quarter retaining both directions with downward SA requested
`357 MW`, satisfied `300 MW`, clearing price `64.83 EUR/MWh`, and source-null DA.
The derivatives use a fixed `0.001` mapping, report DA as sparse rather than
fabricating it, and reproduce deterministic physical/proxy-settlement results
within absolute tolerance `1e-6`.

## API And Provenance Context

The technical source contract remains the ENTSO-E Transparency Platform R3
integration: exact A44 and combined A81 `B95/A52/A01` requests, XML/ZIP
handling, dynamic ISP price conversion, digest-only raw evidence, and the
dotenv credential boundary are documented in
[`docs/architecture/entsoe-transparency-platform.md`](../architecture/entsoe-transparency-platform.md).
The exact source, normalization, ownership, and replay responsibility matrix
is documented in [`bess-stacked-services.md`](bess-stacked-services.md).

Feature 011 uses RTE Balancing Energy catalog version 5.2 with production path
version `v5`, one-source immutable restoration artifacts, exact availability
states, and explicit fixed-fraction derived scenarios. Its OAuth, endpoint,
field, unit, time, error, attribution, and area-versus-asset rules are
documented in
[`rte-balancing-energy.md`](../architecture/rte-balancing-energy.md). Its
ownership and simulation boundaries are documented in
[`afrr-mfrr-services.md`](afrr-mfrr-services.md). Per-file purpose, origin,
generation command, transformation history, fingerprint, invariant, and refresh
record are maintained in
[`tests/fixtures/restoration/README.md`](../../tests/fixtures/restoration/README.md).

Before any public visibility change, verify package contents, release and CI
upload manifests, mirrors, and external stores contain none of the eight paths
or hashes. Renaming, aggregating, plotting, or deriving a restricted value does
not remove the restriction.
