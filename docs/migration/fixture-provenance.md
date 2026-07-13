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

The `009-tpm-planning` feature adds two active fixture families that should
stay small, deterministic, and reviewable:

- simulator-export and planning-problem workflow fixtures under
  `tests/fixtures/planning`
- persisted planning-dataset, TPM artifact, and query fixtures under
  `tests/fixtures/tpm`

For this feature, fixture provenance must also make these points explicit:

- which exact legacy simulator, typed-feature, SPN, or piecewise paths were
  consulted as reference-only evidence
- whether the fixture is synthetic, manually curated, or regenerated from the
  current library implementation
- the paired family seed, training seed, scenario ordering, timestep, and
  numeric tolerance used for replayable export, query, or planning validation
- the referenced planning-dataset or TPM artifact fixture identities when one
  fixture derives from another committed payload
- whether the fixture uses fake-backend SPFlow summaries or fake-backend
  optional-solve expectations to preserve the default offline review path
- the refresh trigger for planning-dataset schema changes, TPM artifact schema
  changes, typed-feature ordering changes, piecewise contract changes, or
  planning decision-scope and solver-metadata changes

Default TPM-planning validation should prefer the committed planning and TPM
fixtures over notebook execution, live services, solver-backed parity runs, or
legacy runtime checks. If a future refresh needs optional SPFlow, Pyomo, or
solver access, document that requirement in the fixture README and in the
feature quickstart rather than broadening the default validation path.

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
