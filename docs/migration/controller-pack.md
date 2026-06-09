# Native Controller Pack Migration Note

Status: complete

Spec `005-controller-pack` introduces the first reusable native controller
package under `src/open_energy_lab/control`. The completed feature ships the
full first controller pack, commits exact deterministic fixture evidence for
all three shipped controllers, and keeps simulator-owned feasibility
enforcement, settlement behavior, and preserved-path regression coverage
separate from the native controller evidence.

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
- `tests/unit/control/test_soc_guardrail.py`
- `tests/unit/control/test_pv_self_consumption.py`
- `tests/integration/control/controller_fixture_utils.py`
- `tests/integration/control/test_price_threshold_controller.py`
- `tests/integration/control/test_scenario_support.py`
- `tests/integration/simulator/test_controller_fixture_schema.py`
- `tests/integration/simulator/test_controller_evaluation.py`
- `tests/integration/simulator/test_battery_arbitrage_trace.py`
- `tests/integration/simulator/test_battery_load_pv_trace.py`
- `tests/unit/test_optional_dependency_boundaries.py`
- `tests/unit/test_no_legacy_imports.py`
- `tests/unit/test_import_contract.py`

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
- Ship active controller-pack fixtures with exact requested-power,
  realized-power, SOC, PV, net-grid, and settlement outputs verified against
  the simulator runner.

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

- `tests/fixtures/simulator/price_threshold_controller_case.json` is an active
  deterministic fixture with exact trace expectations for
  `PriceThresholdController`
- `tests/fixtures/simulator/soc_guardrail_arbitrage_case.json` is an active
  deterministic fixture with exact low-SOC correction outputs for
  `SocGuardrailController`
- `tests/fixtures/simulator/pv_self_consumption_case.json` is an active
  deterministic fixture with exact PV, net-grid, clamp-event, and settlement
  outputs for `PVSelfConsumptionController`
- provenance, planned config fields, exact traces, and legacy evidence remain
  committed for all three fixture paths

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

## Shipped US2 Behaviors

`SocGuardrailController` and `PVSelfConsumptionController` now complete the
first shipped controller pack.

`SocGuardrailController` applies deterministic SOC-band correction rules:

- charge when `soc_fraction < target_min_soc`
- discharge when `soc_fraction > target_max_soc`
- idle when the current SOC is inside the configured band or exactly on a
  satisfied boundary
- support both `ArbitrageScenario` and `BatteryLoadPVScenario`

The committed deterministic arbitrage guardrail fixture uses:

- config: `target_min_soc=0.3`, `target_max_soc=0.7`,
  `charge_request_kw=5.0`, `discharge_request_kw=5.0`
- initial SOC: `0.2`
- verified trace:
  - requested power: `[5.0, 0.0, 0.0]`
  - realized power: `[5.0, 0.0, 0.0]`
  - SOC trace: `[0.675, 0.675, 0.675]`
  - step settlement: `[-0.5, -0.0, -0.0]`
  - total settlement: `-0.5`

`PVSelfConsumptionController` applies deterministic current-step PV-balancing
rules:

- charge when `pv_generation_kw > load_kw` and SOC is below `reserve_max_soc`
- discharge when `load_kw > pv_generation_kw` and SOC is above `reserve_min_soc`
- idle when load equals PV generation or the battery is already at the
  relevant reserve boundary
- support only `BatteryLoadPVScenario`

The committed deterministic PV self-consumption fixture uses:

- config: `reserve_min_soc=0.2`, `reserve_max_soc=0.8`,
  `charge_request_kw=5.0`, `discharge_request_kw=5.0`
- initial SOC: `0.5`
- verified trace:
  - requested power: `[-5.0, 5.0, 5.0]`
  - realized power: `[-4.75, 5.0, 5.0]`
  - SOC trace: `[0.0, 0.475, 0.95]`
  - PV generation: `[0.0, 1.992, 3.968]`
  - net-grid power: `[-2.75, 4.508, 1.532]`
  - direction: `["export", "import", "import"]`
  - step settlement: `[0.22000000000000003, -0.9016000000000001, -0.4596]`
  - total settlement: `-1.1412`
  - constraint events: `["step 0: requested -5.0 kW, realized -4.75 kW"]`

This PV fixture is intentionally important for boundary clarity: the native
controller requests current-step discharge at step 0, while the simulator
retains ownership of feasibility clamping and records the realized deviation
explicitly.

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

## Final Validation Summary

The completed Phase 6 validation run records:

- `96 passed` from
  `uv run pytest tests/unit/control tests/integration/control tests/integration/simulator`
- `65 passed` from `uv run pytest tests/unit/core tests/unit/simulator`
- successful import smoke coverage for
  `open_energy_lab.control`, `open_energy_lab.core`, and
  `open_energy_lab.simulator`
- no `legacy/*` runtime import matches under `src/open_energy_lab/control`,
  the controller-pack test directories, or `docs/migration`
