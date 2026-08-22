# Restricted French Reference Fixtures

## Scope And Decision

The repository owner confirmed on 2026-08-22 that this repository is private
and its contents are limited to authorized collaborators. Under that explicit
boundary, Feature 010 may store its three real-data reference fixtures in Git:

- `tests/fixtures/market/france_2022-08-19_market_v1.json`
- `tests/fixtures/market/france_2022-08-19_activation_v1.json`
- `tests/fixtures/market/france_2022-08-19_expected_replay_v1.json`

This is permission for restricted private-repository storage only. It does not
claim a public-data license from EPEX SPOT, RTE, or ENTSO-E.
It does not claim public redistribution rights. Private/internal access does
not convert the fixture data into public data. The
fixture data is not offered under the repository's Apache-2.0 license.

## Mandatory Boundary

Access is limited to authorized repository collaborators. The three fixtures
MUST NOT be:

- copied to a public repository, fork, or mirror;
- included in a source or wheel package, release attachment, public CI
  artifact, website, publication supplement, or external artifact store; or
- supplied to a downstream party as a redistributable dataset.

If repository visibility might become public, remove all three fixtures from
the branch and its proposed public history before changing visibility. A
future public fixture requires a separate reviewed source-rights decision; the
private-repository decision documented here does not satisfy that requirement.

Raw ENTSO-E responses remain digest-only. The API token remains in the ignored
`.env` file and must never enter Git, an artifact, logs, or documentation.

## Staging Workflow

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

## API And Provenance Context

The technical source contract remains the ENTSO-E Transparency Platform R3
integration: exact A44 and combined A81 `B95/A52/A01` requests, XML/ZIP
handling, dynamic ISP price conversion, digest-only raw evidence, and the
dotenv credential boundary are documented in
[`docs/architecture/entsoe-transparency-platform.md`](../architecture/entsoe-transparency-platform.md).
The exact source, normalization, ownership, and replay responsibility matrix
is documented in [`bess-stacked-services.md`](bess-stacked-services.md).
