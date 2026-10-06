# Fixture Provenance

This document describes the provenance expectations for curated fixtures used
by tests, parity cases, and small reproducibility checks.

## Fixture Record

Each curated fixture should have a nearby record with these fields:

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

## Allowed Fixture Content

- Small synthetic datasets for unit, integration, or parity tests.
- Small legacy output snapshots when provenance is documented.
- Minimal configs needed to reproduce a validation case.
- Expected values derived from documented equations or invariants.

## Disallowed by Default

- Large generated experiment outputs.
- W&B run directories, sweep logs, or credentials.
- Solver caches and machine-specific outputs.
- Full training checkpoints.
- External datasets without clear license and access notes.
- Notebook outputs treated as source code.

## Generation Rules

Generated artifacts may be committed only when they are small enough for
routine review, materially improve reproducibility, and include regeneration
instructions, random seeds, relevant input data, expected output or invariant,
tolerance, license/access notes, and a refresh policy.

If generation requires a commercial solver, GPU, SLURM, W&B, network API, or
other unavailable environment, document the limitation and provide a smaller
local smoke fixture when practical.

## Relationship to `tests/fixtures/README.md`

The fixture README mirrors these requirements and is the default place for the
provenance template when a dedicated fixture-specific metadata file is not
needed.

## French BESS Stacked-Services Fixture Guidance

Feature `010-bess-stacked-services` is an **experimental-v1** public workflow
whose stable module locations are `open_energy_lab.market.artifact`,
`open_energy_lab.market.activation`, `open_energy_lab.market.entsoe`,
`open_energy_lab.control.stacked_service`,
`open_energy_lab.simulator.stacked_service`, and
`open_energy_lab.simulator.fcr_settlement`. Its routine fixture contract is
offline and never turns a missing fixture into a network fetch.

The committed activation record is:

- fixture path: `tests/fixtures/market/france_2022-08-19_activation_v1.json`
- purpose: exact PT10S regulation input for the selected Europe/Paris delivery
  day, validated without reopening the raw source
- origin: RTE France public grid-frequency data preserved at
  `lauinger/robust-storage-bidding@7e44738bb30e5c8204efe40103b9be4c2203685c:data_processing/freq_data/RTE_Frequence_2022_08.txt`
- generation script: `examples/bess_stacked_services/import_reference_activation.py`
- complete raw SHA-256:
  `314a84556383161e9a9628b31eaa885e471f04db213a971c4f25efaef1053a8a`
- input and invariant: exactly 8,640 unique naive Europe/Paris timestamps on a
  10-second grid, frequency range 49.9234--50.0547 Hz, no gap filling or
  duplicate removal
- transformation: explicit left hold and
  `clip((50.0 - frequency_hz) / 0.2, -1, 1)`
- tolerance: exact timestamps and fingerprints; replay numeric tolerance
  `1e-6`
- license/access: source attribution to RTE under the RTE Services Portal
  public-data reuse terms; pinned reference software/documentation is MIT; the
  raw file is not committed
- refresh policy: regenerate only for an intentional pinned source, activation
  schema, normalization, selected period, or provenance-policy change

Reproduction uses the documented command in
`specs/010-bess-stacked-services/quickstart.md`, including the exact digest and
an explicit `--created-at` when byte-stable artifact identity is required.

The market and expected-replay fixtures are deliberately absent as of the
2026-08-21 gate record because no caller-provided ENTSO-E credential was
available to prove exact A44/combined-A81 completeness and normalized-fixture reuse
terms. Do not create a small smoke substitute for these identity-bearing real
fixtures: the manual oracle already supplies synthetic arithmetic coverage,
while the real replay and benchmark must skip with the documented blocker until
the hard gate passes.

## Feature 012 Golden Reference Fixture

Feature `012-fcr-bid-evaluation-parity` uses the small committed fixture path
`tests/fixtures/fcr_bid_evaluation/robust_storage_bidding_2023-06-18_aggregate_v1.json`.
Its purpose is bounded aggregate evidence for the fixed-plan common environment,
not a copy of the reference implementation or its activation dataset.

- origin and source legacy path or generation script: pinned reference
  implementation commit `7e44738bb30e5c8204efe40103b9be4c2203685c`, especially
  `baselines/robust_storage_bidding/code/01_datastruct.jl`, `02_model.jl`,
  `03_backtest_save.jl`, and `04_parse_results.jl`;
- generation command: `julia --project=. 12.jl 2023-06-18` from the reference
  `code/` directory;
- original result SHA-256:
  `8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6`;
- random seed: no random seed; this is deterministic fixed-result evidence;
- input data: 24 `x0`, six `xr`, prices, battery/time configuration, and an
  external activation descriptor;
- expected output or invariant: supported aggregate economics/physics,
  declared mappings, field-specific precision bounds, and explicit unavailable
  fields;
- tolerance: internal equations use `1e-6`; rounded source evidence uses
  analytic, field-specific intervals and may be `source_precision_compatible`;
- license, access, or privacy notes: derived fixture values are committed, but
  `regulation_signal.csv` remains `external_only`; and
- refresh policy: the explicit normalizer writes below ignored `artifacts/`,
  emits semantic differences, and never modifies a committed fixture.

The external file is 528805941 bytes, has SHA-256
`0c2bf5203410f193c555460ec5593b546af42556f29afac821584e403c407d13`,
and exact header `DateTime,Frequency (Hz),xi,xi_EU`. The pinned README release
URL is authoritative; the older MV locator is superseded. The file is excluded
from Git, wheels, sdists, releases, mirrors, and public CI artifacts.

## Feature 013 Robust-Bidding Optimization Fixture

Feature `013-reference-robust-fcr-bidding` owns the distinct small normalized
optimization fixture:

- path:
  `tests/fixtures/fcr_bidding/robust_storage_bidding_2023-06-18_restriction_v1.json`;
- schema: `oel.robust-fcr-reference-restriction.v1`;
- fixture fingerprint:
  `4677ff94aee7f6e836d2429fe8aead10a4147fcb7c14231e87ee23253f0a6a9e`;
- pinned reference revision:
  `7e44738bb30e5c8204efe40103b9be4c2203685c`;
- generated source result path:
  `baselines/robust_storage_bidding/results/02/2023-06-18.json`, which is not
  tracked at that revision;
- generated source result digest and size:
  `8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6`
  and 6,653 bytes;
- content: exact battery, price, 24/96/6 mapping, terminal, uncertainty, and
  restriction-profile inputs plus the rounded objective, bound, 24 `x0`, six
  `xr`, unavailable-field ledger, source-precision policy, and a fingerprinted
  cross-reference to the Feature 012 fixture; and
- exclusions: no original source JSON bytes, baseline code, Julia environment,
  activation sample, external CSV locator, credential, or native solve policy.

The normalizer is
`oel_validation/scripts/normalize_robust_fcr_reference_fixture.py`. It accepts only
an explicit digest-matched source path, writes canonical JSON only beneath the
ignored `artifacts/reference/robust_fcr_bidding/` staging area, runs no Julia or
solver, reports an ordered semantic diff, and refuses to overwrite the
committed destination. Promotion into `tests/fixtures/` is a deliberate review
action after byte and semantic inspection.

Redistribution is intentionally split: the normalized problem/result evidence
is committed derived evidence; the generated original result is represented by
digest only; and activation data is absent and remains external evaluation-only
evidence. Fixture loading never supplies a native execution policy. A selected
native benchmark must separately declare and fingerprint every HiGHS tolerance,
limit, thread, seed, incumbent, canonicalization, and comparison option.

## Feature 015 Rolling Backtest Reference Fixture

Feature `015-fcr-rolling-backtest-parity` owns a separate normalized fixture
for the bounded five-profile/four-date source rerun:

- fixture path:
  `tests/fixtures/fcr_rolling_backtest/robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json`;
- fixture size and committed-byte SHA-256: 99,635 bytes and
  `c075d81cb8a388c82f57c78f3f36aedf9c0da9b0dadbed636b6422e87081be4f`;
- semantic fingerprint:
  `d9f12af283ff0377e651d7c7aaf5e81a40f85372a6e1bf62a4f90ab928659d93`;
- pinned reference revision:
  `7e44738bb30e5c8204efe40103b9be4c2203685c`;
- input manifest and SHA-256:
  `examples/fcr_rolling_backtest/reference_inputs_v1.json` and
  `b84aef1734df9cb366696b9183b47610e540f5ecd47515ac012bf33e67875edc`;
- content: exact canonical ordering for scripts 11–15 and dates 2023-06-17
  through 2023-06-20, source inputs/decisions/objectives/bounds, log-derived
  termination, lifecycle roles, source precision, version evidence,
  crosswalk discrepancies, unavailable fields, and every raw input digest;
  and
- exclusions: raw generated JSON, raw logs, workbook bytes, complete
  activation data, baseline code, credentials, license text, machine/user
  identities, caller-local paths, and native solver policy.

The no-glob normalizer at
`oel_validation/scripts/normalize_fcr_rolling_reference_fixture.py` accepts only
the 49 entries explicitly listed in the input manifest, verifies every byte
digest before parsing, and writes canonical candidates plus semantic diffs
only beneath ignored `artifacts/reference/fcr_rolling_backtest/`. It neither
invokes Julia or a solver nor accesses the network or credentials. Promotion
to the committed fixture is a separate reviewed action.

The fixture records six source `TIME_LIMIT` incumbents—scripts 14 and 15 for
2023-06-17, 2023-06-18, and 2023-06-19—with their same-solve upper bounds.
They are not relabelled optimal. The source JSON's three-decimal fields define
closed half-unit-last-place intervals and its hard-coded
`bilinear_violations=0` field is not independent feasibility evidence. Native
compatibility instead requires one common decision/objective/state/overlap
witness that passes Feature 013's independent formulation audit.

The Feature 013 fixture is preserved byte-for-byte. Its governed original
Experiment 2 digest is
`8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6`;
the separate Feature 015 rerun digest is
`6aee0bbc3353e0b08d1471b2e5c7c3b79aeffd220e2d9c1b69e8c4d711d8f37b`.
Their displayed objective, bound, 24 hourly decisions, and six FCR decisions
match semantically, while their raw bytes remain distinct evidence.

No random seed is claimed for source output. A native benchmark must supply
and fingerprint its own solver policy. The fixture supports only the bounded
executable-profile comparison; the external activation replay and 1,453-date
full-history study remain optional caller-owned research evidence and cannot
be inferred from these normalized bytes.

### Feature 010 Single-Owner Matrix

| Responsibility ID | Responsibility | Single owner |
| --- | --- | --- |
| `OEL-F010-OWNER-RETRIEVAL` | ENTSO-E retrieval and market normalization | `open_energy_lab.market.entsoe` |
| `OEL-F010-OWNER-MARKET-ARTIFACT` | Market-artifact validity | `open_energy_lab.market.artifact` |
| `OEL-F010-OWNER-ACTIVATION` | Activation-artifact validity | `open_energy_lab.market.activation` |
| `OEL-F010-OWNER-SCHEDULES` | Deterministic fixed schedules | `open_energy_lab.control.stacked_service` |
| `OEL-F010-OWNER-PHYSICAL` | Battery-constrained physical delivery | `open_energy_lab.simulator.stacked_service` |
| `OEL-F010-OWNER-SETTLEMENT` | Day-ahead and FCR settlement | `open_energy_lab.simulator.fcr_settlement` |
| `OEL-F010-OWNER-ROBUST` | Robust bidding and optimization | later robust-bidding feature |

## TPM-Backed Planning Fixture Guidance

The `009-tpm-planning` feature has simulator-export and planning fixtures under
`tests/fixtures/planning` and dataset, TPM, sidecar, and query fixtures under
`tests/fixtures/tpm`. Keep the simulator/dataset, TPM artifact/query, and
planning decision/solve ownership boundaries explicit.

The canonical production TPM record is:

- fixture path: `tests/fixtures/tpm/tpm_artifact_spflow_v1.json`
- sidecar path:
  `tests/fixtures/tpm/sidecars/tpm_artifact_spflow_v1.spn_payload.pkl`
- purpose: required real SPFlow 1.1 fit, reload, production query, compiler,
  and sidecar-integrity evidence
- origin and input data: 36 deterministic generic rows from
  `examples/tpm_planning/run_generic_rows_pipeline.py::_training_rows`
- random seed: `13`; semantic repeatability tolerance: `1e-9`; native versus
  compiled maximum absolute probability error: `1e-6`
- compiler scope: version `spflow-v1-mio-v1`, exact Sum/Product and
  Normal/Bernoulli/Categorical modules, one channel/repetition, five canonical
  breakpoints, and MIO epsilon `1e-6`
- generation command:
  `uv run python examples/tpm_planning/run_generic_rows_pipeline.py --regenerate-fixture`
- verification command:
  `uv run python examples/tpm_planning/run_generic_rows_pipeline.py --verify-fixture`
- license, access, or privacy notes: synthetic local rows; no network,
  notebooks, commercial license, external data, or legacy runtime

The manifest records the source-row configuration, fit settings, backend/API
versions, compiler metadata, project-relative sidecar locator, and SHA-256
digest. Verification compares deterministic structure, parameters,
likelihoods, query results, compiler output, and canonical-point probabilities,
not pickle bytes. A regenerated sidecar may have a new digest; the manifest
must record that digest and reload must verify it before deserialization.

Regenerate the production fixture only when its source rows, fit
configuration, required SPFlow API, compiler contract, or schema-v2 artifact
contract intentionally changes. Do not edit a digest to bypass integrity
validation.

The remaining fixtures have narrower roles:

- `tpm_artifact_v1.json` preserves an old inline payload only to verify an
  explicit incompatibility/refit error. Pre-1.0 artifacts must be refitted
  from source rows rather than migrated or deserialized in place.
- `planning_problem_case.json` records required Pyomo 6.10.1/HiGHS 1.15.1
  optimal and infeasible outcomes, canonical solver options, and `1e-9`
  repeatability. Its HiGHS check may not skip; its Gurobi comparison is
  supplemental and may skip only for unavailable binary/license.

Parity provenance must name what was tested and what was not. The dedicated
integration graph covers Sum/Product and all three supported leaf families;
the learned production fixture currently covers Product plus those leaves.
Neither fixture establishes whole-domain interpolation accuracy, rejected
graph support, legacy-runtime or pickle equality, cross-solver equality, or
production-scale performance. Record such extensions as new evidence rather
than silently widening the existing claim.

## Stochastic Weather Fixture Guidance

The `007-stochastic-weather` feature adds a fixture family that should remain
small, deterministic, and reviewable:

- recorded provider responses under `tests/fixtures/weather`
- fitted weather artifacts and unsupported-version artifacts under
  `tests/fixtures/weather`
- deterministic sampling requests and sampled weather-family results under
  `tests/fixtures/weather`
- simulator family and blackout baselines under `tests/fixtures/simulator`

For this feature, fixture provenance must also make these points explicit:

- whether the fixture replaces a live PVGIS fetch in the default review path
- which exact legacy weather or simulator files were consulted as
  reference-only evidence
- whether the fixture is synthetic, manually curated, or regenerated from the
  current library implementation
- the family seed, scenario ordering, timestep, and numeric tolerance used for
  replayable weather or simulator-family validation
- the refresh trigger for artifact-schema changes, sampling-contract changes,
  blackout semantics changes, or summary-surface changes

Default weather validation should prefer the committed fixtures over live
network fetches. If a future refresh needs live PVGIS access or optional
weather dependencies, document that requirement in the fixture README and in
the feature quickstart rather than broadening the default validation path.

## Weather-Conditioned Demand Fixture Guidance

The `008-weather-demand-modeling` feature adds two active fixture families
that should stay small, deterministic, and reviewable:

- aligned training, artifact, sampling-request, and sampled-demand fixtures
  under `tests/fixtures/demand`
- cooling-aware simulator-family fixtures under `tests/fixtures/simulator`

For this feature, fixture provenance must also make these points explicit:

- which exact legacy notebook or simulator pricing paths were consulted as
  reference-only evidence
- whether the fixture is synthetic, manually curated, or regenerated from the
  current library implementation
- the paired-family seed, scenario ordering, timestep, and referenced weather
  or demand fixture identities used for replayable paired-family validation
- the cooling service path, local-electric conversion factor, or
  district-cooling tariff assumptions when simulator settlement is part of the
  fixture
- the numeric tolerance and refresh trigger for aligned-history validation,
  artifact-schema changes, paired-seed replay changes, cooling-accounting
  semantics, or supported summary-surface changes

Default demand validation should prefer the committed demand and simulator
fixtures over notebook execution, live services, or ad hoc parity snapshots.
If a future refresh needs optional weather fetch checks or environment-sensitive
tooling, document that requirement in the fixture README and in the feature
quickstart rather than broadening the default validation path.
