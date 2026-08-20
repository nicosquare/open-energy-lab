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

- `tpm_artifact_v2.json` and its JSON sidecar are explicit empirical
  `fixture_replay` evidence. They are not production-model or compiler-parity
  evidence and cannot activate as a fallback.
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
