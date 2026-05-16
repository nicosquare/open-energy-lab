# Parity Validation

This document defines the validation shape for future brownfield migrations
from `legacy/*` into `src/open_energy_lab`.

## Required Migration Record

Each migration spec should describe the following:

```text
Migration name:
Target module path:
Validation/test path:
Target API maturity:
Legacy source paths:
Behavior to preserve:
Behavior to improve:
Behavior to reject:
Dependencies and classifications:
Fixtures and provenance:
Parity or validation cases:
Known environment assumptions:
Documentation updates:
Out-of-scope work:
```

## Validation Expectations

Every migration needs at least one relevant validation evidence type:

- Fixture-based test.
- Deterministic config and seed.
- Documented equation or invariant.
- Legacy command output or snapshot.
- Focused smoke run for long-running workflows.
- Explicit limitation explaining why parity cannot be automated locally.

## Review Rules

- Cite exact legacy paths and keep them in the `legacy source paths` section.
- Keep `target module path` and `validation/test path` explicit so reviewers can
  tell where new code and tests belong.
- Classify dependencies before implementation so core imports remain isolated
  from optional, external-service-backed, hardware-bound, and legacy-only
  packages.
- Record `behavior to preserve`, `behavior to improve`, and `behavior to
  reject` separately so parity decisions stay reviewable.
- Include fixtures and provenance for any committed generated data.
- Document tolerances and environment assumptions when exact equality is not
  realistic.

## Out-of-Scope Boundary

The foundation feature does not migrate simulator, TPM, RL, optimization,
weather, planning, or control behavior. A later migration spec must handle
those changes with its own validation path. That keeps out-of-scope algorithm migration explicit and reviewable.
