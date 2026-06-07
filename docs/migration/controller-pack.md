# Native Controller Pack Migration Note

Status: phase-2-foundation

Spec `005-controller-pack` introduces the first reusable native controller
package under `src/open_energy_lab/control`. This phase establishes the shared
configuration types, support declarations, package-root exports, fixture-schema
requirements, and migration rationale that later controller behavior tasks will
build on.

## Target Module Paths

- `src/open_energy_lab/control/__init__.py`
- `src/open_energy_lab/control/_config.py`
- `src/open_energy_lab/control/price_threshold.py`
- `src/open_energy_lab/control/soc_guardrail.py`
- `src/open_energy_lab/control/pv_self_consumption.py`

## Validation Paths

- `tests/unit/control/test_import_boundary.py`
- `tests/unit/control/test_configs.py`
- `tests/unit/control/test_support_matrix.py`
- `tests/unit/control/test_controller_interface.py`
- `tests/integration/control/controller_fixture_utils.py`
- `tests/integration/simulator/test_controller_fixture_schema.py`

## Legacy Source Paths

Preserved battery, timestep, and settlement evidence:

- `legacy/old_tpm/src_py/legacy/storage.py`
- `legacy/old_tpm/src_py/simulator/common/battery.py`
- `legacy/old_tpm/src_py/simulator/common/pricing.py`
- `legacy/old_tpm/src_py/simulator/common/time.py`

Current-step PV context evidence:

- `legacy/old_tpm/src_py/simulator/common/specs.py`
- `legacy/fed_trpo/src/custom/building.py`

Rejected integration-direction evidence:

- `legacy/fed_trpo/src/custom/citylearn.py`
- `legacy/fed_trpo/src/utils/cl_torchrl_helper.py`

## Preserve / Improve / Reject

### Preserve

- `open_energy_lab.core.ControllerInterface` remains the only controller
  contract; `open_energy_lab.control` layers on top of it rather than replacing
  it.
- `open_energy_lab.simulator.evaluate_with_controller` remains the execution
  path for controller-driven episodes, preserving simulator ownership of
  feasibility enforcement, state transitions, and settlement.
- Deterministic fixture provenance stays explicit and tied to small committed
  JSON artifacts under `tests/fixtures/simulator`.
- Legacy references remain evidence only; no new runtime behavior is imported
  from `legacy/*`.

### Improve

- Promote package-root imports from `open_energy_lab.control` as the stable
  public entry point for shipped controller types and their configs.
- Add typed per-controller configuration surfaces with validation for threshold
  bands, SOC bounds, and positive request magnitudes.
- Publish explicit support declarations for shipped controllers so unsupported
  scenario use fails immediately and deterministically.
- Extend fixture-schema validation to cover controller-pack scaffold artifacts,
  provenance metadata, and exact legacy-reference expectations.

### Reject

- Runtime coupling to CityLearn, TorchRL, PyTorch, solver stacks, W&B,
  notebook tooling, or other heavy research dependencies for ordinary
  `open_energy_lab.control` imports.
- Broad legacy controller parity claims without focused fixtures and
  deterministic validation evidence.
- Compatibility shims that silently accept unsupported scenario families.
- Training loops, policy networks, replay buffers, MPC, federated control, or
  multi-agent abstractions inside the stable controller package.

## Fixture Record

The controller-pack feature reserves these committed fixture paths:

- `tests/fixtures/simulator/price_threshold_controller_case.json`
- `tests/fixtures/simulator/soc_guardrail_arbitrage_case.json`
- `tests/fixtures/simulator/pv_self_consumption_case.json`

Current status:

- all three fixtures remain scaffold artifacts with `status: "scaffold"`
- provenance, planned config fields, and legacy evidence are already committed
- exact expected traces remain intentionally empty until implementation tasks
  `T019` and `T030` verify controller behavior through the simulator runner

## Shared Public Surface

This phase promotes the following stable import surface:

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

The controllers are scaffolded to conform to the stable interface now, while
their final decision rules are intentionally deferred to the user-story
implementation tasks.

## Follow-Up Work

- `T016` to `T018` will complete the price-threshold controller behavior and
  align the config and package-root export with the documented arbitrage rules.
- `T025` to `T029` will complete the guardrail and PV controller behavior and
  align their scaffolds with the documented support matrix.
- `T019` and `T030` will populate controller-pack fixtures with verified
  expected traces.
- Later migration docs will promote API maturity and dependency-boundary notes
  once the shipped behaviors are complete.
