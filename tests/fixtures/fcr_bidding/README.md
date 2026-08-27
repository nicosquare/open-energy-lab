# Robust FCR Bidding Fixtures

This directory owns the small optimization evidence used by Feature 013.
Fixtures here reconstruct and compare the ex-ante bid-selection problem; they
do not own realized activation, battery replay, or settlement evidence. Those
remain under the separate Feature 012 fixture boundary.

## Ownership and provenance

The planned
`robust_storage_bidding_2023-06-18_restriction_v1.json` fixture is a normalized
derived manifest, not a copy of the source result. It is governed by:

- reference repository revision
  `7e44738bb30e5c8204efe40103b9be4c2203685c`;
- generated result path
  `baselines/robust_storage_bidding/results/02/2023-06-18.json`;
- generated result SHA-256
  `8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6`;
- exact source files and equation ranges recorded in
  `docs/migration/reference-robust-fcr-bidding.md`; and
- schema
  `specs/013-reference-robust-fcr-bidding/contracts/robust-fcr-reference-fixture-v1.schema.json`.

The pinned submodule revision does not track the generated JSON. The digest is
therefore mandatory provenance. Routine production and validation must consume
only the reviewed normalized fixture and must not read the source tree.

## Redistribution boundary

The repository may commit the small normalized problem and rounded result
evidence as `committed_derived_evidence`. It does not redistribute the original
generated JSON (`digest_only`) or regulation signal
(`absent_external_evaluation_only`). No baseline, Julia environment, solver
log, machine path, credential, or external activation byte belongs in this
directory.

The source record contains three-decimal objective, bound, and market
decisions. It does not prove formal termination, optimality, exact gap,
unrounded feasibility, constraint residuals, actual solver versions, or solver
tolerances. These fields remain explicitly unavailable and must not be inferred
from equal displayed objective and bound values.

## Refresh policy

Maintainers normalize only an explicitly selected local JSON whose bytes match
the pinned digest. The normalizer never starts Julia, Gurobi, HiGHS, or a
network client. It writes candidate output and an ordered semantic diff only
below ignored `artifacts/`; it refuses committed destinations.

After inspecting provenance, schema validation, source-precision intervals,
all semantic differences, and byte stability, a maintainer may deliberately
promote the candidate in a separate reviewed change. Production code and
routine tests never refresh fixtures, and no refresh operation may modify
`baselines/robust_storage_bidding` or `legacy/*`.
