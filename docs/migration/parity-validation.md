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

## Controller Boundary Governance

The `004-controller-boundary` migration adds a controller-specific validation
shape that later migrations should preserve when they extend this boundary:

- Keep `src/open_energy_lab/core` import-light and free of runtime `legacy/*`
  imports.
- Keep `src/open_energy_lab/simulator` import-light, with controller execution
  owned by `evaluate_with_controller`.
- Treat `tests/fixtures/simulator/controller_arbitrage_case.json` and
  `tests/fixtures/simulator/controller_battery_load_pv_case.json` as active
  deterministic evidence, not placeholder scaffolds.
- Preserve exact fixture provenance, numeric tolerance, and refresh-policy
  notes when those controller fixtures change.
- Validate both supported scenario families through the same controller runner
  API before expanding the stable surface.
- Keep named incomplete-context rejection behavior explicit so failures remain
  distinguishable from simulator-side clamping.

Minimum controller-boundary validation now includes:

- `tests/integration/simulator/test_controller_fixture_schema.py`
- `tests/integration/simulator/test_controller_evaluation.py`
- `tests/integration/simulator/test_battery_arbitrage_trace.py`
- `tests/integration/simulator/test_battery_load_pv_trace.py`
- `tests/unit/test_optional_dependency_boundaries.py`
- `tests/unit/core/test_no_legacy_imports.py`
- `tests/unit/simulator/test_import_boundary.py`
- `tests/unit/test_import_contract.py`

If future controller-boundary work cannot run one of these checks locally, the
skip reason must be recorded in the relevant spec plan or quickstart, alongside
any environment assumptions and the intended follow-up validation path.

## Out-of-Scope Boundary

The foundation feature does not migrate simulator, TPM, RL, optimization,
weather, planning, or control behavior. A later migration spec must handle
those changes with its own validation path. That keeps out-of-scope algorithm migration explicit and reviewable.
