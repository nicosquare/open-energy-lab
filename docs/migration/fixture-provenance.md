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
