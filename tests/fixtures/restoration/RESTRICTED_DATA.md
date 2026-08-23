# Restricted Restoration-Service Data

The following Feature 011 files are restricted to authorized collaborators in
this private repository:

- `france_2026-08-20_afrr_market_v1.json`
- `france_2026-08-20_afrr_scenario_v1.json`
- `france_2026-08-15_mfrr_market_v1.json`
- `france_2026-08-15_mfrr_scenario_v1.json`
- `france_restoration_expected_results_v1.json`

The files are not offered under the repository's Apache-2.0 license. They must
not enter a wheel, source distribution, release, public CI artifact, public
fork or mirror, or external artifact store. Remove them or complete a new
rights and policy assessment before changing repository visibility.

## Permitted Repository State

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

The market files preserve normalized RTE Balancing Energy v5.2 observations.
The scenario and expected-result files remain restricted because they are
deterministically derived from those values. No production raw market body,
OAuth response, credential, or access token is committed.

This restriction does not apply to project-authored files under
`synthetic_rte/` or to the hand-calculable `manual_afrr_v1.json` and
`manual_mfrr_v1.json` oracles. Those inputs must be visibly labelled synthetic
and must not claim to be observed asset dispatch.

## Attribution And Exact Identities

Source attribution for the normalized market files is **RTE Balancing Energy
API v5.2; normalized by Open Energy Lab**. RTE Réseau de Transport
d'Électricité is the source owner. The derivative files preserve the same
restriction because their requests, plots, and results can reproduce the
normalized observations.

| File | Semantic identity | File SHA-256 |
| --- | --- | --- |
| `france_2026-08-20_afrr_market_v1.json` | artifact `83f0c88e5c8d9c0f781305a9552596c3a03956588a75871e9f78e97415811516`; content `9f44272301f164562d7552723054438253704c3f65618d2acf8e70755ffd1506` | `5042f7d7d21ec839670b80b22eaa1abcbed2eacb0bc2d1d55367bbd543723799` |
| `france_2026-08-15_mfrr_market_v1.json` | artifact `d2d4007fafe5138f0bfdc8d91ba232c435f9b4f7097a0cc519064011c624ca10`; content `57bff8041d4691e7cda82da53790b92228130007c2d2ba5986fc280e5f14c1a4` | `76c5ad31f677a83b7a70d7bb629a4bfa9636b66d2a065302750fdfb8039cec91` |
| `france_2026-08-20_afrr_scenario_v1.json` | scenario `fea97fb2e9596e907a7204df9466c355d0ce2493c8c846e85a69093eadcfd9cb`; mapping `d1fc944a2f45e1032f7c9c6cafc76b212fd6d4b54576ae1eb58adbe0853a5178` | `b21a9bd4f56fe6fe324ce0e4c93b566b525102f404925301b877f12a8ef9a62c` |
| `france_2026-08-15_mfrr_scenario_v1.json` | scenario `028b0067c9173c4998d47616d138e395f682f676e1a9d012a1e32769cee6a172`; mapping `24275dcf84e098521315995a2c2cda63cf46257ff46c91325ac5cfaadba52f0b` | `8881bb013e8649c8dc86c5c73848dea8611cbce2146c12ced5b6940163169489` |
| `france_restoration_expected_results_v1.json` | result set `92f043191f161bce49ef71425ca02055d721a81ad3a6fd0d8084fee7bd65730e` | `7cee2a58ddb3075ca50e44c62431bbafc281cefd686a02c0f25c32e69755fe34` |

Raw RTE response bytes are not committed. The aFRR artifact retains digest
`d2496d713c7f217ff76487db2aba0b7a49479861118bea61ca3c001fbbfe2eb3`
and the mFRR artifact retains
`ce9d3c3d694a78776e5bdb188239f9b2ed4b711e3c389d0e89c8a47e5391d1a1`
as `DIGEST_ONLY` evidence. Neither has a raw sidecar. OAuth responses and
credential material are never source evidence and are never retained.

## Governed Production And Refresh

Acquisition is a caller-triggered operation under ignored `artifacts/` and is
the only step permitted to read RTE credentials. Staging reads no environment
or network, validates the exact periods/profile/fields/digests/policy, scans for
secret and raw-body markers, requires an explicit private-repository
acknowledgement, and writes only the two fixed normalized destinations.

```bash
uv run python examples/restoration_services/stage_private_reference_data.py \
  --afrr-artifact artifacts/restoration/reference-acquisition/afrr/ARTIFACT.json \
  --mfrr-artifact artifacts/restoration/reference-acquisition/mfrr/ARTIFACT.json \
  --acknowledge-private-restricted-repository

uv run python examples/restoration_services/generate_reference_results.py \
  --acknowledge-private-restricted-repository
```

The first command refuses package, release, public, mirror, CI-artifact, and
external-store targets. The second command loads only the fixed normalized
fixtures and deterministically regenerates the two scenarios and expected
results. Both commands are idempotent for identical bytes and fail closed on a
conflicting existing file.

A refresh must be explicit and use the same token-free request identity.
Unchanged normalized content writes nothing; changed content creates an
immutable predecessor-linked acquisition artifact. A changed raw digest is
reported for semantic review and does not alone authorize replacement of a
committed reference. Re-staging requires exact semantic invariants:

- four consecutive aFRR PT15M rows with upward requested needs
  `425, 315, 290, 345 MW` and zero downward requested need;
- one mFRR quarter retaining both directional rows, with downward SA requested
  `357 MW`, satisfied `300 MW`, clearing price `64.83 EUR/MWh`, and source-null
  DA rather than a fabricated event; and
- deterministic derivatives labelled `derived_simulation`, a fixed `0.001`
  allocation, no raw body, and byte-stable physical/proxy-settlement results at
  absolute tolerance `1e-6`.

## Visibility Change And Incident Response

Before making the repository, a fork, or a mirror public, remove all five files
from the branch and proposed public history, then verify wheels, source
distributions, releases, CI upload manifests, and external stores contain none
of their paths or hashes. A future public fixture requires a new documented
source-rights decision; renaming, aggregating, plotting, or deriving the values
does not satisfy that review.

If a restricted file is published accidentally, stop further distribution,
remove it from every destination and proposed public history, invalidate any
artifact/release containing it, notify the repository owner, and record a new
rights/security review before restoring any replacement evidence.

The field-level provenance record is in [README.md](README.md). The project-
wide policy is in
[`docs/migration/restricted-reference-fixtures.md`](../../../docs/migration/restricted-reference-fixtures.md),
and the API/source contract is in
[`docs/architecture/rte-balancing-energy.md`](../../../docs/architecture/rte-balancing-energy.md).
