# Feature 015 normalized rolling-reference fixtures

This directory is reserved for the small, immutable, provenance-rich fixture
that normalizes the bounded 2023-06-17 through 2023-06-20 Julia/Gurobi rerun
for executable scripts 11 through 15.

Committed fixture content may include only:

- normalized profile, date-role, input, decision, objective, bound,
  termination, lifecycle, and source-precision evidence;
- the pinned reference revision and SHA-256 identities of every selected raw
  input;
- separately identified runtime and committed-package version evidence;
- the script/result/paper/workbook crosswalk and known discrepancies; and
- explicit unavailable fields and redistribution classifications.

It must not include raw logs, complete source result JSON files, the complete
activation CSV, the source workbook, credentials, license text, machine or
user identities, caller-local paths, or other non-redistributable payloads.
Routine code and tests consume only the committed normalized fixture and must
never resolve the raw artifacts from `baselines/robust_storage_bidding`.

Regeneration is a two-step governance action. A maintainer runs the explicit
no-glob normalizer against a manifest that pins every input digest and writes
only below ignored `artifacts/`; promotion into this directory is then a
separate reviewed change. Feature 013's governed single-day fixture under
`tests/fixtures/fcr_bidding/` is immutable input to the cross-check and must
not be modified by Feature 015 normalization.

The fixture and refresh command will be added in the source-evidence phase.
Until then, the schema contract is
[`fcr-rolling-reference-fixture-v1.schema.json`](../../../specs/015-fcr-rolling-backtest-parity/contracts/fcr-rolling-reference-fixture-v1.schema.json).
