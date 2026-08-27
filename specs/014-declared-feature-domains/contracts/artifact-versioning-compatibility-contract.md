# Contract: Artifact Versioning and Compatibility

## Version policy

New fits produced after U-Bounds write TPM artifact schema v3. The new reader accepts valid v2 and
v3 artifacts. V1 remains incompatible with existing refit guidance. Readers predating U-Bounds are
not required to accept v3.

The version boundary is mandatory because pre-feature v2 readers can ignore unknown feature keys;
therefore new declared meaning must never be emitted as a v2 extension that appears safely readable
while losing semantics.

## V3 requirements

A v3 artifact preserves:

- feature identity, kind, role, and ordering;
- mathematical-domain purpose, shape, content, and origin;
- physical training support and its observation provenance;
- normalization kind, parameters, and origin;
- fit configuration, seed, backend/version information, and feature order;
- existing query/model metadata required by OEL; and
- the SPFlow sidecar location and integrity digest.

Manifest and embedded sidecar feature metadata are interpreted in the same schema context and must
agree. Non-finite numeric metadata is rejected; unboundedness is represented semantically.

## V2 compatibility interpretation

When a valid v2 artifact is loaded:

- its mathematical domain is unknown;
- a bare continuous range becomes training-support and legacy-inferred normalization evidence;
- bare discrete values/order remain legacy-inferred observed encoding information;
- current normalization and native-query restrictions remain operationally compatible;
- none of those values becomes a decision domain, distribution support, or compiler interval; and
- loading does not rewrite the manifest or sidecar.

A loaded v2 object serializes only its schema-aware v2 representation and retains `schema_version`
`v2`; it never emits v3-only semantic records. New fits write v3. Obtaining v3 semantics from a v2
artifact requires refitting from the original evidence rather than an in-place upgrade.

## Compiled-artifact boundary

Fitted TPM artifact version and compiled-MIO payload version are independent. New compiled payloads
use their own v2 contract with per-feature validity, but producing one requires a v3 fitted artifact
with finite declared mathematical domains for retained continuous decision approximations. A loaded
v2 fitted artifact remains loadable and queryable through compatibility behavior but fails new
compiled-v2 compilation; refitting original evidence with declarations is the migration path.
Legacy compiled-v1 payloads retain their normalized-only meaning and remain evaluable without being
promoted to physical validity by inference.

## Fixture policy

- Existing `tpm_artifact_v2.json`, `tpm_artifact_spflow_v1.json`, and sidecars remain byte-stable
  compatibility anchors.
- Existing v1 rejection fixtures remain unchanged.
- A new reviewable domain-input fixture and production v3 manifest/sidecar provide new behavior.
- Fixture documentation records generation command, declared inputs, exact physical rows, seed,
  fit/compiler versions, digest, expected coordinate probes, validity intervals, and assertion
  tolerances.

## Failure behavior

Loading fails clearly for malformed semantic combinations, manifest/sidecar disagreement, integrity
failure, unsupported future versions, non-finite stored endpoints, or absent mandatory provenance.
Failure never causes an in-place rewrite or best-effort strengthening of meaning.
