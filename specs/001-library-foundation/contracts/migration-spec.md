# Contract: Brownfield Migration Spec

Use this contract before moving selected behavior from `legacy/*` into
`src/open_energy_lab`.

## Required Sections

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

## Legacy Reference Rules

- Cite exact files, directories, notebooks, configs, or scripts used as
  evidence.
- Treat legacy code as reference material, not target architecture.
- Do not copy whole files without explaining the selected behavior and the
  improvements being made.
- Do not edit `legacy/*` unless the migration spec explicitly authorizes a
  reference fix or submodule-maintenance change.

## Validation Evidence

Each migration must provide at least one relevant evidence type:

- Fixture-based test.
- Deterministic config and seed.
- Documented equation or invariant.
- Legacy command output or snapshot.
- Focused smoke run for long-running workflows.
- Explicit limitation explaining why parity cannot be automated locally.

Focused parity is optional. Use it when a migration explicitly preserves a
trusted legacy behavior. Do not require broad simulator-level replay when
cleaner new logic and invariant-based validation are the better standard.

## Acceptance Rules

A migration is not ready for implementation until reviewers can identify:

- Where new code belongs under `src/open_energy_lab`.
- Where tests belong under `tests`.
- Which legacy behavior is preserved, improved, or rejected.
- Which dependencies are core, optional, service-backed, hardware-bound, or
  legacy-only.
- Which fixtures or generated artifacts are committed and how to regenerate
  them.

## Foundation Boundary

This foundation feature satisfies the governance portion of the migration
contract only. Simulator, TPM, RL, optimization, weather, planning, and control
migrations must each get their own later spec.
