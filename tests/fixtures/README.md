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
