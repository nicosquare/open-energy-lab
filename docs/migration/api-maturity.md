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

### Controller Boundary MVP

The `004-controller-boundary` feature promotes the following imports to stable
public API for the MVP:

```python
from open_energy_lab.core import (
    ControllerContext,
    ControllerEvaluationResult,
    ControllerInterface,
    DispatchProposal,
)

from open_energy_lab.simulator import evaluate_with_controller
```

These imports are stable because they now have:

- focused unit and integration coverage
- deterministic committed fixtures for both supported scenario families
- import-boundary checks proving they stay clear of optional research stacks
- no-legacy-import checks for the stable core package
- documented controller-boundary behavior, validation commands, and migration
  evidence

Supporting controller-boundary types that remain in
`open_energy_lab.core.controller` are intentionally narrower in maturity for
now. They may be used by package-internal code and focused validation, but
they are not yet promoted as root-level stable imports until a later spec
explicitly broadens the public surface.

### Native Controller Pack

The `005-controller-pack` feature promotes the following imports to stable
public API for the first shipped native controller surface:

```python
from open_energy_lab.control import (
    PVSelfConsumptionConfig,
    PVSelfConsumptionController,
    PriceThresholdConfig,
    PriceThresholdController,
    SocGuardrailConfig,
    SocGuardrailController,
)
```

These imports are stable because they now have:

- package-root export coverage tied to the documented support matrix
- typed configuration validation and `ControllerInterface` conformance tests
- deterministic controller-pack fixtures plus repeated-run runner checks
- import-boundary, import-contract, and no-legacy-import coverage that names
  `open_energy_lab.control` explicitly
- preserved-path regression evidence proving the controller pack does not
  replace explicit-dispatch or built-in simulator rule flows
- migration documentation that records behavior, dependency boundaries, and
  selective parity expectations

Supporting controller modules such as `open_energy_lab.control._config`,
`open_energy_lab.control.price_threshold`,
`open_energy_lab.control.soc_guardrail`, and
`open_energy_lab.control.pv_self_consumption` remain implementation-facing
modules. They are intentionally imported lazily through the package root so
ordinary `open_energy_lab.control` imports stay import-light while the stable
package-root surface remains fixed.

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
