# Quickstart: External Controller Boundary MVP

Use this quickstart to review the plan and guide the later implementation.
This feature introduces a stable controller contract in `open_energy_lab.core`
and a simulator-owned controller evaluation path in
`open_energy_lab.simulator`.

## Review the Feature

```bash
sed -n '1,340p' specs/004-controller-boundary/spec.md
sed -n '1,320p' specs/004-controller-boundary/plan.md
sed -n '1,260p' specs/004-controller-boundary/research.md
sed -n '1,260p' specs/004-controller-boundary/data-model.md
```

Confirm the intended boundary:

- stable controller contracts live under `src/open_energy_lab/core`
- the simulator owns the controller episode loop under
  `src/open_energy_lab/simulator`
- the controller interface is single-step and current-step only
- both `ArbitrageScenario` and `BatteryLoadPVScenario` are required release
  targets
- explicit-dispatch and built-in rule simulator behavior remain preserved
- RL, CityLearn, training, reward, solver, notebook, W&B, GPU/SLURM, and Rust
  behavior remain out of scope

## Review the Contracts

```bash
sed -n '1,220p' specs/004-controller-boundary/contracts/controller-contract.md
sed -n '1,220p' specs/004-controller-boundary/contracts/simulator-evaluation-contract.md
sed -n '1,220p' specs/004-controller-boundary/contracts/scenario-compatibility-contract.md
sed -n '1,220p' specs/004-controller-boundary/contracts/validation-case.md
```

Before implementation, make sure the contracts agree on:

- power in `kW`
- timestep duration in hours
- positive dispatch meaning charge
- one controller proposal per simulator step
- incomplete required current-step context causing a named pre-evaluation
  rejection
- simulator-owned proposal validation and feasibility enforcement
- stable imports from `open_energy_lab.core` and `open_energy_lab.simulator`
- support for both migrated scenario families
- preserved explicit-dispatch and built-in `price_threshold` regression
  coverage
- default absolute tolerance `1e-6`

## Review the Legacy Evidence

```bash
sed -n '1,260p' legacy/old_tpm/src_py/legacy/storage.py
sed -n '1,260p' legacy/old_tpm/src_py/simulator/common/battery.py
sed -n '1,220p' legacy/old_tpm/src_py/simulator/common/pricing.py
sed -n '1,120p' legacy/old_tpm/src_py/simulator/common/time.py
sed -n '350,470p' legacy/fed_trpo/src/custom/citylearn.py
sed -n '855,972p' legacy/fed_trpo/src/custom/citylearn.py
sed -n '287,360p' legacy/fed_trpo/src/utils/cl_torchrl_helper.py
```

Use these sources to verify preserved dispatch and timestep semantics, and to
confirm which action-space and training-environment patterns are intentionally
rejected from the stable library boundary.

## Environment

The feature uses the same base environment as the existing simulator
migrations:

```bash
conda activate open-energy-lab
uv sync --dev
```

If the environment is not present yet, review the foundation quickstart first:

```bash
sed -n '1,220p' specs/001-library-foundation/quickstart.md
```

## Expected Implementation Targets

After implementation, the main touched areas should be:

```text
src/open_energy_lab/core/
src/open_energy_lab/simulator/
tests/unit/core/
tests/unit/simulator/
tests/integration/simulator/
tests/fixtures/simulator/
tests/parity/
docs/migration/
```

The implementation should stay narrow. One or two deterministic controller
fixtures are enough if they prove:

- the controller contract is import-light and stable
- the simulator builds current-step context without exposing scenario internals
- both supported scenarios evaluate through the same runner API
- proposal validation catches wrong-step or wrong-sign semantics
- incomplete current-step context is rejected as a named pre-evaluation failure
  mode
- simulator-side clamping remains visible in the result when requests are
  infeasible
- preserved explicit-dispatch and built-in `price_threshold` paths still pass
  dedicated regression validation
- repeated evaluation is deterministic

## Planned Stable Surface

Planned stable imports for the MVP are:

```python
from open_energy_lab.core import (
    ControllerContext,
    ControllerEvaluationResult,
    ControllerInterface,
    DispatchProposal,
)

from open_energy_lab.simulator import (
    ArbitrageScenario,
    BatteryLoadPVScenario,
    evaluate_with_controller,
)
```

The exact exported names may be finalized during implementation, but the plan
assumes:

- controller contracts are stable public API in `open_energy_lab.core`
- the simulator evaluation entry point is stable public API in
  `open_energy_lab.simulator`
- `open_energy_lab.control` remains deferred for broader future control work

## Controller Fixture Notes

The controller-driven fixtures are committed as active deterministic evidence:

- `tests/fixtures/simulator/controller_arbitrage_case.json`
- `tests/fixtures/simulator/controller_battery_load_pv_case.json`

Use them to review the expected three-step `sequence-controller` proposals and
realized traces without re-reading simulator internals. Refresh them only when
the documented controller boundary, controller sequence, battery semantics,
weather-to-PV derivation, timestep semantics, or settlement rules
intentionally change.

Review the provenance and refresh notes with:

```bash
sed -n '1,260p' tests/fixtures/simulator/README.md
sed -n '1,220p' tests/fixtures/simulator/controller_arbitrage_case.json
sed -n '1,260p' tests/fixtures/simulator/controller_battery_load_pv_case.json
```

## Expected Checks After Tasks Exist

```bash
uv run pytest tests/unit/core tests/unit/simulator tests/integration/simulator
uv run python -c "import open_energy_lab.core; import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/core src/open_energy_lab/simulator tests/unit/core tests/unit/simulator tests/integration/simulator
```

Focused validation commands should include:

```bash
uv run pytest tests/integration/simulator/test_controller_fixture_schema.py
uv run pytest tests/unit/core/test_controller_contract.py
uv run pytest tests/unit/simulator/test_controller_runner.py
uv run pytest tests/integration/simulator/test_controller_evaluation.py
uv run pytest tests/integration/simulator/test_battery_arbitrage_trace.py tests/integration/simulator/test_battery_load_pv_trace.py
```

For the controller-driven path plus the preserved regression baselines, run:

```bash
uv run pytest \
  tests/integration/simulator/test_controller_fixture_schema.py \
  tests/integration/simulator/test_controller_evaluation.py \
  tests/integration/simulator/test_battery_arbitrage_trace.py \
  tests/integration/simulator/test_battery_load_pv_trace.py
```

Expected result for the legacy-import scan: no matches in new library modules
or their runtime tests.

## Checks Intentionally Out of Scope

This feature should not require or run:

- CityLearn environment execution
- RL training loops
- MPC or solver-backed planning
- reward-function evaluation as a feature gate
- notebook or W&B workflows
- GPU or SLURM execution
- external data downloads
- Rust builds or Rust parity checks

## Task Planning Reminder

When `/speckit-tasks` is generated, make sure it includes:

- tests first for the stable controller contract and simulator runner
- fixture-first validation for both supported scenario families
- import-boundary tests for `open_energy_lab.core` and
  `open_energy_lab.simulator`
- migration note updates that explain preserved, improved, and rejected
  controller-boundary semantics
