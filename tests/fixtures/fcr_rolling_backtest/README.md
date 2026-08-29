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

## Governed fixture

The committed fixture is
[`robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json`](./robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json).
It has semantic fingerprint
`d9f12af283ff0377e651d7c7aaf5e81a40f85372a6e1bf62a4f90ab928659d93`
and committed-byte SHA-256
`c075d81cb8a388c82f57c78f3f36aedf9c0da9b0dadbed636b6422e87081be4f`.

The normalized evidence covers exactly five profiles by four dates in canonical
profile/date order. It pins 20 generated JSON files and 11 retained logs. Log
segments establish six `TIME_LIMIT` incumbents: scripts 14 and 15 for
2023-06-17, 2023-06-18, and 2023-06-19. All preserve feasible incumbents and
same-solve upper bounds; none is relabelled optimal. The 08:00 lifecycle is
`initialization_only`, `finalized`, `finalized`, `unfinalized`, with
2023-06-18 and 2023-06-19 as the primary paired comparison dates.

The fixture separately records:

- runtime evidence from Julia 1.10.1 and Gurobi 11.0.3;
- committed Julia environment versions JuMP 1.23.3, Gurobi.jl 1.3.1, and
  Gurobi runtime 11.0.3;
- README claims JuMP 1.22.2 and Gurobi 11.0.2 without merging those claims into
  runtime evidence;
- every cited source, price/activation descriptor, environment file, workbook,
  generated result, and log by logical path and SHA-256;
- closed three-decimal source-precision policy and the requirement for one
  joint Feature 013 formulation witness; and
- explicit absence of source unrounded decisions, independent restriction
  residuals, exact 08:00 restart fixings, Feature 012 schedule fingerprints,
  and redistributed activation samples.

The Feature 013 cross-check preserves its governed fixture byte-for-byte. Its
original raw result digest is
`8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6`;
the separate Feature 015 Experiment 2 rerun digest is
`6aee0bbc3353e0b08d1471b2e5c7c3b79aeffd220e2d9c1b69e8c4d711d8f37b`.
Their displayed objective, bound, 24 hourly decisions, and six FCR decisions
match semantically even though the raw bytes do not.

## Refresh procedure

The explicit input manifest is
[`reference_inputs_v1.json`](../../../examples/fcr_rolling_backtest/reference_inputs_v1.json).
From the repository root, a maintainer with the selected local evidence runs:

```bash
uv run python examples/fcr_rolling_backtest/normalize_reference_fixture.py \
  --source-root baselines/robust_storage_bidding \
  --input-manifest examples/fcr_rolling_backtest/reference_inputs_v1.json \
  --destination-dir artifacts/reference/fcr_rolling_backtest
```

The command resolves no unlisted file, verifies all 49 artifact digests before
parsing, segments consolidated logs by their exact four date markers,
reconciles log and JSON evidence, and writes the candidate and ordered semantic
diff atomically below ignored `artifacts/`. It never invokes Julia or a solver,
accesses the network, or overwrites this directory. Promotion requires review
of a zero or deliberately understood semantic diff and a separate file change.

The strict schema is
[`fcr-rolling-reference-fixture-v1.schema.json`](../../../specs/015-fcr-rolling-backtest-parity/contracts/fcr-rolling-reference-fixture-v1.schema.json).
