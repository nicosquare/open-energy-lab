# Native Controller Pack Migration Note

Status: phase-3-us1

Spec `005-controller-pack` introduces the first reusable native controller
package under `src/open_energy_lab/control`. The current phase ships the first
native arbitrage controller, commits exact deterministic fixture evidence for
that behavior, and keeps the remaining controller-pack surface staged for the
later guardrail and PV tasks.

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
- `tests/unit/control/test_price_threshold.py`
- `tests/integration/control/controller_fixture_utils.py`
- `tests/integration/control/test_price_threshold_controller.py`
- `tests/integration/simulator/test_controller_fixture_schema.py`
- `tests/integration/simulator/test_controller_evaluation.py`

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
- Extend fixture-schema validation to cover controller-pack artifacts,
  provenance metadata, and exact legacy-reference expectations.
- Ship the first active controller-pack fixture with exact requested-power,
  realized-power, SOC, and settlement outputs verified against the simulator
  runner.

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

- `tests/fixtures/simulator/price_threshold_controller_case.json` is now an
  active deterministic fixture with exact trace expectations for
  `PriceThresholdController`
- `tests/fixtures/simulator/soc_guardrail_arbitrage_case.json` and
  `tests/fixtures/simulator/pv_self_consumption_case.json` remain scaffold
  artifacts until the later US2 implementation tasks populate them
- provenance, planned config fields, and legacy evidence remain committed for
  all three fixture paths

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

## Shipped Arbitrage Behavior

`PriceThresholdController` is the first shipped native controller in the pack.
Its current-step rules are intentionally narrow and deterministic:

- charge when `import_price < charge_below_import_price`
- discharge when `import_price > discharge_above_import_price`
- idle when the current import price falls inside the neutral band or exactly
  equals either threshold
- reject unsupported scenario kinds immediately through the shared support
  declarations in `src/open_energy_lab/control/_config.py`

This controller remains simulator-owned at execution time: it proposes one
dispatch request per step and relies on
`open_energy_lab.simulator.evaluate_with_controller` for clamping, state
transitions, and settlement.

## Arbitrage Usage

```python
from open_energy_lab.control import PriceThresholdConfig, PriceThresholdController
from open_energy_lab.simulator import evaluate_with_controller

controller = PriceThresholdController(
    PriceThresholdConfig(
        charge_below_import_price=0.15,
        discharge_above_import_price=0.25,
        charge_request_kw=5.0,
        discharge_request_kw=5.0,
    )
)

result = evaluate_with_controller(arbitrage_scenario, controller)
```

The committed deterministic arbitrage fixture uses this exact configuration on
a three-step `ArbitrageScenario` with import prices `[0.10, 0.20, 0.30]` and
records the verified native-controller trace:

- requested power: `[5.0, 0.0, -5.0]`
- realized power: `[5.0, 0.0, -5.0]`
- SOC trace: `[0.975, 0.975, 0.44868421052631574]`
- step settlement: `[-0.5, -0.0, 1.2]`
- total settlement: `0.7`

## Follow-Up Work

- `T025` to `T029` will complete the guardrail and PV controller behavior and
  align their scaffolds with the documented support matrix.
- `T030` will populate the remaining controller-pack fixtures with verified
  expected traces.
- Later migration docs will promote API maturity and dependency-boundary notes
  once the shipped behaviors are complete.
