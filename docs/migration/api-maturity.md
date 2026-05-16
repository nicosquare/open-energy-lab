# API Maturity Policy

This policy defines how `open_energy_lab` import paths become stable, remain
experimental, or stay private while the project migrates selected behavior from
legacy references.

## Stable Public API

An import path is stable public API when all conditions hold:

- It is documented as an `open_energy_lab.*` import outside
  `open_energy_lab.experimental`.
- It has focused tests under `tests/unit`, `tests/integration`, or
  `tests/parity`.
- Its dependencies are classified and do not unexpectedly import optional
  research stacks.
- Its expected behavior and compatibility expectations are documented.
- A migration or capability spec explicitly reviews the promotion.

Stable public APIs should preserve import paths and documented behavior across
future migrations unless a deprecation decision is recorded.

## Experimental API

`open_energy_lab.experimental.*` is for immature migrations and incubating APIs.
Experimental APIs may change or move while behavior is being migrated,
validated, and reviewed.

Experimental placement does not remove quality requirements. Experimental code
still needs appropriate tests or smoke checks, dependency classification, and
clear documentation before users rely on it.

## Private API

Private modules and objects use a leading underscore or are undocumented
implementation details. They are not user-facing contracts and may change
without deprecation.

Examples:

```text
open_energy_lab.simulator._internal
open_energy_lab.core._legacy_adapter
```

## Promotion Rules

Promotion from private or experimental to stable requires:

- Target import path and user-facing purpose.
- Validation evidence, including parity cases when migrated from `legacy/*`.
- Dependency classification.
- Documentation update.
- Explicit review in the migration or capability spec.

Promotion must not make solver licenses, W&B accounts, GPU/SLURM tooling,
notebooks, Rust builds, or external data APIs required for ordinary package
imports unless a later spec explicitly accepts that tradeoff.

## Deprecation Rules

Deprecating stable public API requires:

- A recorded reason in the relevant spec, changelog, or migration note.
- A replacement path or explicit statement that no replacement exists.
- A compatibility expectation for how long the old path remains available.
- Tests or documentation updates that make the transition visible.

Experimental and private APIs may change faster, but changes should still be
documented when users or future migration specs are expected to notice them.
