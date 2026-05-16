# Contract: Public API Maturity

This contract defines when code in `open_energy_lab` is public, experimental,
or private.

## Stable Public API

An import path is stable public API when all conditions hold:

- It is documented as an `open_energy_lab.*` import outside
  `open_energy_lab.experimental`.
- It has focused tests under `tests/unit`, `tests/integration`, or
  `tests/parity`.
- Its dependencies are classified and do not unexpectedly import optional
  research stacks.
- Its expected behavior and compatibility expectations are documented.

Stable public APIs should preserve import paths and documented behavior across
future migrations unless a deprecation decision is recorded.

## Experimental API

An import path is experimental when it lives under:

```text
open_energy_lab.experimental.*
```

Experimental APIs may change or move while behavior is being migrated,
validated, and reviewed. They still require tests or smoke checks appropriate
to their risk.

## Private API

Private modules and objects use a leading underscore or are undocumented
implementation details. They are not user-facing contracts.

Examples:

```text
open_energy_lab.simulator._internal
open_energy_lab.core._legacy_adapter
```

## Promotion Requirements

Promotion from private or experimental to stable requires:

- Target import path and user-facing purpose.
- Validation evidence, including parity cases when migrated from `legacy/*`.
- Dependency classification.
- Documentation update.
- Explicit review in the migration or capability spec.

## Foundation Boundary

This foundation feature may define package and module boundaries, but it must
not promote migrated simulator, TPM, RL, optimization, weather, planning, or
control behavior because that behavior is not implemented here.
