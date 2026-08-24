# Restoration Market Artifact and Study Bundle Contract

## Ownership and Separation

The market package owns source observation preservation, provenance,
fingerprints, publication, and offline loading. One artifact represents exactly
one RTE or ENTSO-E acquisition. It never contains an asset command, commitment,
battery configuration, replay result, or settlement result.

Feature 010 `MarketDataArtifact` remains unchanged. Feature 011 uses schema
`oel.restoration.market.v1`.

## Artifact Manifest

Every artifact contains:

- schema and normalization version
- single source, catalog/API version, profile, resource/document, owner, area
- token-free request identity and requested/covered UTC/local periods
- retrieval time and complete sanitized request-window evidence
- a manifest of every requested, required, present, null-bearing, absent, and
  not-requested series
- independent semantic identity, direction, units, currency, resolution,
  transformations, observations, and fingerprint for every series
- raw-response digest/sidecar status without raw OAuth material
- attribution, retention, repository-storage, redistribution, package, release,
  mirror, public-CI, and external-store policy
- optional predecessor fingerprint for a changed refresh
- normalized-content and full-artifact fingerprints

Series from another source, request, or refresh version are rejected.

## Missingness Contract

- Numeric `0` is a present finite observation.
- JSON/XML null is `SOURCE_NULL`.
- A missing named field is `FIELD_ABSENT`.
- A requested series absent from the response is `SOURCE_ABSENT`.
- An unselected optional series is `NOT_REQUESTED`.

Required coverage may not contain null/absent intervals unless the profile
explicitly declares the field optional for the study. Prices needed only for
settlement may remain sparse in the physical artifact, but settlement becomes
unavailable when the study declares them required.

## Time and Coverage Contract

- Observations use `CanonicalInterval` and are chronological, half-open,
  non-overlapping, and within covered bounds.
- Canonical UTC coverage is authoritative; Europe/Paris labels, offsets, and
  folds remain stored.
- Source and canonical resolutions are separate fields.
- Resolution changes, interpolation, upsampling, forward fill, averaging,
  netting, and boundary prorating require an explicitly supported transformation
  contract. Feature 011's RTE reference profile allows none of them.
- Conflicting duplicates or incomplete required coverage fail the artifact.

## Fingerprints

Canonical JSON uses UTF-8, sorted keys, compact separators, finite numbers, and
no implementation-object repr.

- `series_fingerprint` identifies one normalized semantic series.
- `content_fingerprint` identifies normalized source content and semantic
  profile, excluding retrieval timestamp and refresh lineage.
- `artifact_fingerprint` identifies the full immutable manifest, including
  retrieval provenance, policy, evidence, and predecessor.
- a study bundle has its own `bundle_fingerprint` over exact artifact
  fingerprints, selected series IDs, period, and purpose.

Credentials, tokens, filesystem output directories, temporary names, and live
transport objects are excluded from all fingerprint payloads.

## Immutability and Publication

1. Validate the complete in-memory artifact.
2. Derive a filename containing the full artifact fingerprint.
3. Serialize deterministic pretty JSON with one trailing newline.
4. Write a sibling temporary file, flush and fsync it, and atomically replace
   the final path.
5. Reuse an existing final file only when its verified bytes are identical.
6. Treat different or corrupt existing bytes as an integrity failure.

No manifest is published until all required acquisition windows and series
succeed.

## Offline Load

Offline load accepts a path, reads and verifies manifest bytes, schema,
semantics versions, fingerprints, coverage, sidecars, and policy, then returns
source-independent immutable objects. It must not:

- read any credential environment variable or `.env`
- import or instantiate RTE/ENTSO-E transports
- open a socket or authenticate
- fetch a missing artifact
- repair, fill, or refresh invalid content

## Refresh Outcomes

| Outcome | Condition | Publication |
|---|---|---|
| `UNCHANGED` | request identity compatible and content fingerprint equal | none |
| `CHANGED` | compatible request and different valid normalized content | exactly one successor |
| failure | auth, transport, parse, coverage, semantic, integrity, or policy error | none |

The prior artifact always remains byte-identical.

## Study Bundle Contract

A bundle is an immutable reference manifest, not a data file join. Each
reference includes artifact ID, full fingerprint, selected series IDs, and use
purpose. Bundle loading resolves and verifies each artifact independently.

The bundle must:

- copy no observations
- preserve source/series names and semantics
- expose source disagreement rather than choose a winner
- prohibit fallback or substitution
- adopt the strictest referenced redistribution policy
- fail when a referenced fingerprint or selected series is missing

RTE and ENTSO-E observations may coexist only as separate references.

## Restricted Reference Storage

Normalized real RTE/ENTSO-E fixtures are allowed only for authorized
collaborators in the owner-confirmed private repository and require metadata:

```text
repository_storage: permitted_private_restricted
repository_publication: prohibited
package_distribution: prohibited
release_distribution: prohibited
public_ci_artifact: prohibited
public_mirror_or_fork: prohibited
external_artifact_store: prohibited
visibility_change_action: remove_or_reassess_before_change
```

The build configuration explicitly excludes every restricted file. Tests scan
wheel/sdist contents and configured publication paths. Synthetic authored JSON
is kept in a separate redistributable directory.

## Failure Diagnostics

Failures name the phase, source, resource/series/field, requested period,
observed sanitized condition, expected contract, and relevant fingerprint.
They never include credential values, bearer/basic headers, raw response bodies,
or credential-bearing URLs.
