# Test Fixtures

Fixtures in this directory support unit, integration, and parity checks. Keep
them small, reviewable, and traceable to their origin.

## Fixture Provenance Template

Use this template in this file or a nearby fixture-specific metadata file when
adding generated, curated, or legacy-derived test fixtures.

```text
Fixture path:
Purpose:
Origin:
Source legacy path or generation script:
Generation command:
Random seed:
Input data:
Expected output or invariant:
Tolerance:
License, access, or privacy notes:
Refresh policy:
```

## Allowed

- Small synthetic datasets for unit, integration, or parity tests.
- Small legacy output snapshots with documented provenance.
- Minimal configs needed to reproduce a validation case.
- Expected values derived from documented equations or invariants.
- Small simulator fixtures under `tests/fixtures/simulator/`, including the
  battery arbitrage MVP fixture shell in
  `tests/fixtures/simulator/battery_arbitrage_case.json` and the battery load
  PV fixture shell in `tests/fixtures/simulator/battery_load_pv_case.json`.

## Disallowed by Default

- Large generated experiment outputs.
- W&B run directories, sweep logs, credentials, or service-backed state.
- Solver caches, temporary solver files, and machine-specific outputs.
- Full training checkpoints or model dumps.
- External datasets without clear license and access notes.
- Notebook outputs treated as source code.

## Generated Artifact Rules

Generated artifacts may be committed only when they materially improve
reproducibility, are small enough for routine review, and include regeneration
instructions, random seeds, relevant input data, expected outputs or invariants,
tolerances, license/access notes, and a refresh policy.

If generation requires a commercial solver, GPU, SLURM, W&B, network API, or
other unavailable environment, document the limitation and provide a smaller
local smoke fixture when practical.

## Feature 013 Robust-FCR Optimization Fixture

```text
Fixture path: tests/fixtures/fcr_bidding/robust_storage_bidding_2023-06-18_restriction_v1.json
Purpose: normalized, offline 2023-06-18 restriction input/result and source-precision evidence for native bid-selection comparison
Origin: robust-storage-bidding revision 7e44738bb30e5c8204efe40103b9be4c2203685c plus a generated untracked Experiment 2 result
Source legacy path or generation script: baselines/robust_storage_bidding/results/02/2023-06-18.json; oel_validation/scripts/normalize_robust_fcr_reference_fixture.py
Generation command: uv run python -m oel_validation.scripts.normalize_robust_fcr_reference_fixture --source-json baselines/robust_storage_bidding/results/02/2023-06-18.json --destination-dir artifacts/reference/robust_fcr_bidding
Random seed: none in source evidence; native benchmark seed 13 belongs to its separate caller-owned solve policy
Input data: exact battery, prices, terminal, 24/96/6 mappings, 0.25/2.25/2.75-hour uncertainty evidence, and restriction profile
Expected output or invariant: rounded objective/bound, 24 x0, six xr, unavailable-field ledger, joint source-precision policy, and cross-feature fixture reference
Tolerance: source decimals use closed +/-0.0005 intervals; native feasibility remains 1e-6 and native objective comparison remains a separate fingerprinted policy
License, access, or privacy notes: committed derived JSON only; original generated result is digest-only and activation data is absent/external-only
Refresh policy: normalize only an explicit 6,653-byte source with SHA-256 8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6 below ignored artifacts, inspect the ordered semantic diff, and deliberately promote reviewed bytes
```

The committed fixture fingerprint is
`d2d7d7430153d91c5c589fe8118005d01e02d70012bf5e8bbf4f419c13154ba4`.
It contains neither source JSON/baseline bytes nor activation samples, external
CSV paths, Julia/Gurobi runtime state, credentials, or a native solve policy.
The normalizer refuses direct committed-destination writes and performs no
solver, Julia, network, or credential action. `pyproject.toml` needs no Feature
013 dependency change because Pyomo 6.10.1 and highspy 1.15.1 are already
locked required dependencies.

## Feature 015 Rolling FCR Reference Fixture

```text
Fixture path: tests/fixtures/fcr_rolling_backtest/robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json
Purpose: normalized offline comparison evidence for all five non-intraday executable profiles over the bounded 2023-06-17 through 2023-06-20 Julia/Gurobi rerun
Origin: robust-storage-bidding revision 7e44738bb30e5c8204efe40103b9be4c2203685c plus caller-generated scripts 11 through 15 JSON and retained log evidence
Source legacy path or generation script: baselines/robust_storage_bidding/results/01 through 05, corresponding generated logs below baselines/robust_storage_bidding/code, and oel_validation/scripts/normalize_fcr_rolling_reference_fixture.py
Generation command: uv run python -m oel_validation.scripts.normalize_fcr_rolling_reference_fixture --source-root baselines/robust_storage_bidding --input-manifest examples/fcr_rolling_backtest/reference_inputs_v1.json --destination-dir artifacts/reference/fcr_rolling_backtest
Random seed: none declared by the source rerun; every native benchmark seed belongs to its separate caller-owned solve policy
Input data: five executable profiles, four ordinary dates, battery/uncertainty/terminal contracts, 24 hourly and six four-hour prices per delivery day, source lifecycle/carry evidence, 20 generated JSON files, 11 log segments, exact source/package references, and pinned SHA-256 identities
Expected output or invariant: canonical 5-by-4 profile/date evidence, six retained time-limit incumbents with same-solve upper bounds, source-rounded decisions/objectives/states, 08:00 initialization/finalization roles, explicit unavailable fields, and a byte-preserving semantic cross-check of Feature 013's governed fixture
Tolerance: displayed source decimals use closed +/-0.0005 intervals; compatibility requires one joint Feature 013 formulation witness plus the declared native feasibility/objective policy and never treats bilinear_violations=0 as proof
License, access, or privacy notes: only the small derived normalized JSON is committed; raw JSON, logs, workbook, activation CSV, credentials, license text, machine identities, and caller-local paths are excluded
Refresh policy: verify every entry in reference_inputs_v1.json before parsing, write only beneath ignored artifacts, inspect the ordered semantic diff, preserve the Feature 013 fixture unchanged, and promote reviewed canonical bytes as a separate action
```

The fixture is 99,635 bytes, has committed-byte SHA-256
`c075d81cb8a388c82f57c78f3f36aedf9c0da9b0dadbed636b6422e87081be4f`,
and semantic fingerprint
`d9f12af283ff0377e651d7c7aaf5e81a40f85372a6e1bf62a4f90ab928659d93`.
It supports bounded executable-profile comparison, not full-history Table A1
parity. Time-limited source records are feasible incumbents plus retained
bounds, not proven optima. Complete activation replay remains separately
selected external evidence.

## Simulator Fixture Notes

`tests/fixtures/simulator/` is reserved for deterministic simulator validation
cases. For the battery arbitrage MVP, the committed fixture should remain
synthetic and small enough for routine review, and it must record:

- exact legacy evidence files consulted
- whether the case uses explicit dispatch requests or the built-in
  `price_threshold` policy
- the discounted export settlement rule
- the default absolute numeric tolerance (`1e-6`) unless a stricter case is
  documented

For the battery load PV MVP fixture shell and its later finalized case, record
all of the above plus:

- the exact weather-to-PV evidence files consulted
- human-readable weather field names together with canonical TMY source-label
  mappings for every included weather field
- which standard TMY fields are intentionally deferred from the MVP subset
- whether expected values are placeholders, exact traces, invariant tables, or
  a mix of those forms during each implementation phase
