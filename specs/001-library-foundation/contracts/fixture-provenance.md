# Contract: Fixture and Provenance Policy

Fixtures support tests and parity cases. They must be small, reviewable, and
traceable to their origin.

## Fixture Record

Every curated generated fixture should have a nearby provenance record,
typically in `tests/fixtures/README.md` or a fixture-specific metadata file.

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
- Expected values derived from documented equations.

## Disallowed by Default

- Large generated experiment outputs.
- W&B run directories, sweep logs, or credentials.
- Solver caches and machine-specific outputs.
- Full training checkpoints.
- External datasets without clear license and access notes.
- Notebook outputs treated as source code.

## Generated Data Rules

Generated artifacts may be committed only when:

- They are small enough for routine review.
- They materially improve reproducibility.
- Regeneration instructions are documented.
- Random seeds and relevant input data are recorded.

If generation requires a commercial solver, GPU, SLURM, W&B, network API, or
other unavailable environment, document the limitation and provide a smaller
local smoke fixture when practical.

## Notebook Rules

Notebooks may be examples, references, or exploratory records. Reusable
behavior must be moved into library modules and tested before it is considered
product code.
