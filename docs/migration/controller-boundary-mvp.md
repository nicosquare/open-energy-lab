# Controller Boundary MVP Migration Note

This note records the selected legacy evidence and intended migration boundary
for the first stable external controller surface in `open_energy_lab.core` and
the simulator-owned controller evaluation path in `open_energy_lab.simulator`.

## Target

- Target module path: `src/open_energy_lab/core/controller.py`
- Supporting simulator module path: `src/open_energy_lab/simulator/controller_runner.py`
- Supporting scenario update path: `src/open_energy_lab/simulator/scenario.py`
- Planned package-root export paths:
  - `src/open_energy_lab/core/__init__.py`
  - `src/open_energy_lab/simulator/__init__.py`
- Initial validation paths:
  - `tests/unit/core/test_controller_migration_note.py`
  - `tests/unit/core/test_controller_contract.py`
  - `tests/unit/core/test_import_boundary.py`
  - `tests/unit/simulator/test_controller_runner.py`
  - `tests/integration/simulator/test_controller_fixture_schema.py`
  - `tests/integration/simulator/test_controller_evaluation.py`
  - `tests/fixtures/simulator/controller_arbitrage_case.json`
  - `tests/fixtures/simulator/controller_battery_load_pv_case.json`

## Exact Legacy Reference Files

- `legacy/old_tpm/src_py/legacy/storage.py`
- `legacy/old_tpm/src_py/simulator/common/battery.py`
- `legacy/old_tpm/src_py/simulator/common/pricing.py`
- `legacy/old_tpm/src_py/simulator/common/time.py`
- `legacy/fed_trpo/src/custom/building.py`
- `legacy/fed_trpo/src/custom/citylearn.py`
- `legacy/fed_trpo/src/utils/cl_torchrl_helper.py`

## Behavior To Preserve

- current-step-only controller invocation with one proposal per simulator step
- positive dispatch meaning charge and negative dispatch meaning discharge
- simulator-owned battery feasibility, timestep, and discounted-settlement
  semantics already established in `open_energy_lab.simulator`
- deterministic repeated evaluation from the same scenario and controller inputs
- support for both `ArbitrageScenario` and `BatteryLoadPVScenario`
- preserved explicit-dispatch and built-in `price_threshold` simulator paths as
  separate regression baselines
- absolute numeric tolerance `1e-6` for deterministic fixture validation unless
  a stricter case is documented

## Behavior To Improve

- a stable typed controller contract under `open_energy_lab.core` rather than
  ad hoc simulator-adjacent caller logic
- explicit `ControllerContext`, `DispatchProposal`, and controller-evaluation
  result models that remain inspectable without exposing simulator internals
- stable package-root imports for `ControllerContext`,
  `ControllerEvaluationResult`, `ControllerInterface`, and
  `DispatchProposal` from `open_energy_lab.core`
- controller-facing battery and price snapshots that keep scenario internals
  out of the stable core API while preserving current-step semantics
- a named pre-evaluation rejection path for incomplete required current-step
  context instead of ambiguous downstream failures
- shared committed controller fixtures with provenance notes for both supported
  scenario families
- clear public documentation that separates preserved simulator semantics from
  rejected RL, training, and environment-wrapper abstractions
- import-light controller and simulator package roots that stay free of heavy
  research stacks at ordinary import time

## Behavior To Reject

- direct reuse of CityLearn action spaces, Gym-style wrappers, TorchRL tensor
  specs, or training-environment contracts as stable core API
- multi-agent action arrays, reward coupling, replay buffers, and rollout or
  policy-training loops in the MVP boundary
- full-horizon forecast, solver-backed optimization, or planning contracts in
  the stable controller surface
- runtime imports from `legacy/*` modules in new library code
- mandatory CityLearn, TorchRL, PyTorch, solver, W&B, notebook, GPU/SLURM, or
  Rust dependencies for default `open_energy_lab.core` or
  `open_energy_lab.simulator` imports

## Current Implementation Status

User Story 1 now establishes the stable core-side boundary:

- `src/open_energy_lab/core/controller.py` defines typed current-step controller
  inputs, one-step proposal validation, the controller protocol, and a typed
  evaluation-result surface using only Python standard-library imports
- `src/open_energy_lab/core/__init__.py` re-exports the stable public API from
  `open_energy_lab.core`
- `tests/unit/core/test_controller_contract.py` validates contract shape,
  sign semantics, and step alignment for one-step proposals
- `tests/unit/core/test_import_boundary.py` verifies that the stable core API
  remains import-light and resolves to `open_energy_lab.core.controller`

Later tasks still need to add the simulator-owned controller runner, scenario
context extraction, deterministic controller traces, named pre-evaluation
rejection handling, and simulator package-root exports.
