# Golden Reference Fixture And External Data Contract

## Committed Fixture Boundary

The committed Golden Reference Fixture is:

```text
tests/fixtures/fcr_bid_evaluation/
└── robust_storage_bidding_2023-06-18_aggregate_v1.json
```

It is a normalized evidence manifest, not a copy of the baseline result or
activation dataset. Routine loading uses only its committed bytes and never
resolves baseline paths or the external CSV.

Required top-level sections are:

```text
schema_version
fixture_id
reference_provenance
runtime_provenance
reference_configuration
fixed_decisions
price_inputs
mapping
external_activation
precision_policy
expected_fields
unsupported_fields
redistribution_status
fixture_fingerprint
```

Unknown schema versions, missing fields, non-finite values, duplicate field IDs,
wrong counts, invalid fingerprints, or digest mismatch fail.

## Required Provenance

The fixture records exactly:

- reference commit
  `7e44738bb30e5c8204efe40103b9be4c2203685c`;
- generation working directory `baselines/robust_storage_bidding/code/`;
- generation command `julia --project=. 12.jl 2023-06-18`;
- original result path
  `baselines/robust_storage_bidding/results/02/2023-06-18.json`;
- original result SHA-256
  `8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6`;
- exact cited reference source paths;
- model `restrict`, `xi_EU`, energy payment enabled, intraday disabled,
  efficiencies 0.92, K=96, Δt=0.25 h, dt=1/360 h, six PT4H commitments,
  and three-decimal saved precision;
- documented runtime versions and separately recorded locked manifest versions;
- per-input redistribution status.

The fixture retains 24 published `x0`, six published `xr`, 24 `p0`, six `pr`,
battery/time configuration, objective/bound metadata, supported expected
aggregates, source JSON pointers, and mapping/precision versions.

## External Activation Descriptor

The fixture references but does not embed:

```text
URL:
https://github.com/lauinger/robust-storage-bidding/releases/download/v0.1/regulation_signal.csv

OEL local default:
artifacts/reference/robust_storage_bidding/regulation_signal.csv

byte count:
528805941

SHA-256:
0c2bf5203410f193c555460ec5593b546af42556f29afac821584e403c407d13

header:
DateTime,Frequency (Hz),xi,xi_EU
```

The pinned README URL is authoritative. The older
`lauinger/MV/releases/download/v1.0-publication/` locator in
`data/regulation_signal_info.txt` is recorded as superseded provenance, not an
automatic fallback.

## External Loader Contract

The explicit loader receives a caller-supplied path. It performs, in order:

1. regular-file and safe-path checks;
2. exact byte-count and full SHA-256 validation;
3. UTF-8 CSV and exact-header validation;
4. strict timestamp and finite numeric parsing;
5. selection of date `2023-06-18` and column `xi_EU`;
6. exactly 8,640 unique chronological timestamps from local `00:00:00` through
   `23:59:50` at PT10S cadence;
7. explicit Europe/Paris local-to-UTC interval assignment; and
8. construction of the existing immutable `RegulationActivationTrace` with
   source/digest lineage.

It does not:

- open a URL;
- consult an environment variable unless an example explicitly turns it into a
  path argument;
- search `baselines/`;
- accept the first same-named file found;
- accept a partial day or alternate activation column;
- interpolate, fill, deduplicate, clip, or reorder values; or
- persist a normalized raw/reference slice implicitly.

A public loader raises an actionable domain error on absent or invalid input.
Only the explicitly selected pytest wrapper may skip when the file is absent.

## Precision Policy

The initial JSON rounds both fixed decisions and expected aggregates to three
decimal places. The fixture therefore stores:

- decision half-unit `0.0005 kW`;
- aggregate half-unit `0.0005` in each expected field's unit;
- analytic formula and evaluated bound for every source-precision field;
- exact rounded-match outcome as a separate observation; and
- `source_precision_compatible` as the strongest claim when equality relies on
  overlapping rounding intervals.

Field-specific decision-only bounds for this fixture are:

```text
charge_energy_kwh or discharge_energy_kwh: 0.012970
stored_energy_kwh extrema/terminal:         0.014097
power extrema kW:                           0.0007345
day_ahead_revenue_eur:                      0.0010736
fcr_capacity_revenue_eur:                   0.0003798
activation_revenue_eur:                     0.0000867
combined_fcr_revenue_eur:                   0.0004665
total_revenue_eur:                          0.0015401
```

Implementation must recompute these from fixture inputs and formulas; it cannot
trust only stored bound values. Add the output half-unit when constructing the
expected interval.

If a future reviewed reference export provides full-precision decisions, it must
use a new fixture/precision schema version. Existing bounded evidence is not
silently upgraded.

## Supported And Unsupported Evidence

Supported aggregate evidence:

- fixed published `x0` and `xr` decisions;
- objective value and bound as optimization metadata;
- total, day-ahead, and combined FCR profit;
- charge and discharge energy;
- stored-energy initial/minimum/maximum/terminal; and
- realized reference power minimum/maximum.

Provenance only:

- solve time;
- reference intraday-disabled zero; and
- reported zero bilinear violations for the restriction run.

Unsupported reference parity:

- complete ten-second stored-energy trajectory;
- per-step requested/delivered tracking;
- non-delivery and saturation causes;
- directional FCR energy;
- separate reference-observed capacity/activation revenue; and
- OEL throughput.

The fixture lists every unsupported field explicitly. A comparison request for
one returns `unavailable` and cannot broaden the claim.

## Redistribution Rules

The full regulation CSV has `external_only` status. It must never enter Git,
source/wheel distributions, releases, mirrors, external artifact uploads, or CI
artifacts. The ignored `artifacts/` location is user-managed.

The normalized Golden Reference Fixture contains permitted small derived values
and provenance only. Its per-section redistribution statuses must be reviewed before
promotion. Uncertain fields stay out of the committed fixture; they are not
replaced with synthetic values under a reference-generated label.

## Fixture Generation And Refresh

Normal evaluation never writes fixtures. Refresh is an explicit reviewed
operation:

1. an authorized researcher runs the pinned reference implementation separately;
2. the researcher supplies the generated JSON path and expected result digest to
   the normalization example;
3. the example validates schema/configuration/provenance and writes byte-stable
   output below ignored `artifacts/` by default;
4. comparison against the committed fixture identifies every semantic change;
5. promotion into `tests/fixtures/` is a reviewed repository change; and
6. routine tests continue to require neither Julia nor the baseline tree.

The helper may optionally consume a future full-precision decision export, but it
does not execute Julia or Gurobi itself and does not modify the baseline.

## Routine And Explicit Tests

Routine validation uses:

- a small authored hand oracle;
- Golden Reference Fixture schema/provenance/mapping/precision tests;
- tiny synthetic external-CSV parser failures; and
- Feature 010 compatibility and deterministic evaluation tests.

The full-day test is marked `external_reference_data`, excluded from routine CI,
and selected explicitly after user setup. It requires the external CSV but not
Julia, Gurobi, network access, or the reference submodule.
