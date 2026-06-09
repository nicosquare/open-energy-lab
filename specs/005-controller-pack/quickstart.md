# Quickstart: Native Controller Pack

Use this quickstart to review the completed controller-pack feature and rerun
its focused validation set. The feature introduces the first reusable native
controllers in `open_energy_lab.control` while preserving the stable
controller contract in `open_energy_lab.core` and the simulator-owned runner
in `open_energy_lab.simulator`.

## Review the Feature

```bash
sed -n '1,320p' specs/005-controller-pack/spec.md
sed -n '1,320p' specs/005-controller-pack/plan.md
sed -n '1,320p' specs/005-controller-pack/research.md
sed -n '1,320p' specs/005-controller-pack/data-model.md
```

Confirm the intended feature boundary:

- `open_energy_lab.control` becomes the first shipped control package
- `open_energy_lab.core` keeps the stable controller contract
- `open_energy_lab.simulator.evaluate_with_controller` remains the only
  controller execution path
- the shipped controller set is price-threshold, SOC guardrail, and PV
  self-consumption
- explicit-dispatch and built-in simulator rule baselines remain preserved
- CityLearn, RL, solver-backed planning, and runtime legacy imports remain out
  of scope

## Review the Final Migration Notes

```bash
sed -n '1,260p' docs/migration/controller-pack.md
sed -n '1,220p' docs/migration/api-maturity.md
sed -n '1,260p' docs/migration/dependency-policy.md
sed -n '1,260p' docs/migration/parity-validation.md
sed -n '1,220p' docs/migration/README.md
```

Use these files to confirm that:

- the stable `open_energy_lab.control` package-root exports are documented
- the native control package remains import-light and free of runtime
  `legacy/*` imports
- controller-pack evidence stays fixture-backed and separate from broad legacy
  parity claims
- migration overview references point reviewers to the current controller-pack
  guidance

## Review the Contracts

```bash
sed -n '1,220p' specs/005-controller-pack/contracts/control-package-contract.md
sed -n '1,220p' specs/005-controller-pack/contracts/controller-support-contract.md
sed -n '1,220p' specs/005-controller-pack/contracts/configuration-contract.md
sed -n '1,220p' specs/005-controller-pack/contracts/validation-case.md
```

Confirm the contracts agree on:

- stable package-root exports from `open_energy_lab.control`
- explicit per-controller scenario support
- positive dispatch meaning charge
- deterministic threshold and boundary tie behavior
- typed config validation before evaluation
- simulator-owned feasibility enforcement and settlement
- import-light package behavior
- preserved explicit-dispatch and built-in-rule regression coverage

## Review the Current Boundary and Simulator Evidence

```bash
sed -n '1,220p' src/open_energy_lab/control/__init__.py
sed -n '1,260p' src/open_energy_lab/core/controller.py
sed -n '1,240p' src/open_energy_lab/simulator/controller_runner.py
sed -n '1,180p' src/open_energy_lab/simulator/scenario.py
```

Use these files to confirm that:

- the controller contract is already stable and current-step only
- `BatteryLoadPVScenario` context already exposes `load_kw` and
  `pv_generation_kw`
- the new control package should layer on top of the existing runner rather
  than extending simulator ownership

## Review the Legacy Evidence

```bash
sed -n '1,260p' legacy/old_tpm/src_py/legacy/storage.py
sed -n '1,260p' legacy/old_tpm/src_py/simulator/common/battery.py
sed -n '1,220p' legacy/old_tpm/src_py/simulator/common/pricing.py
sed -n '1,120p' legacy/old_tpm/src_py/simulator/common/time.py
sed -n '1,220p' legacy/fed_trpo/src/custom/building.py
sed -n '350,470p' legacy/fed_trpo/src/custom/citylearn.py
sed -n '287,360p' legacy/fed_trpo/src/utils/cl_torchrl_helper.py
```

Use these sources to review preserved battery and settlement semantics, the
current-step battery-plus-PV context direction, and the training-oriented
abstractions that remain explicitly rejected from the native control package.

## Environment

The feature uses the same minimal Python environment as the current native
library work:

```bash
uv sync --dev
```

If the environment is not prepared yet, review the foundation and controller
boundary quickstarts first:

```bash
sed -n '1,220p' specs/001-library-foundation/quickstart.md
sed -n '1,260p' specs/004-controller-boundary/quickstart.md
```

## Implemented Targets

After implementation, the main touched areas should be:

```text
src/open_energy_lab/control/
tests/unit/control/
tests/integration/control/
tests/integration/simulator/
tests/fixtures/simulator/
docs/migration/
```

The implemented feature stays narrow. It proves that:

- shipped controllers can be imported and configured from the package root
- each shipped controller satisfies the stable controller contract
- each shipped controller runs through `evaluate_with_controller`
- invalid configurations and unsupported scenarios fail deterministically
- repeated execution remains deterministic
- preserved explicit-dispatch and built-in simulator rule paths still pass
- the control package remains free of heavy runtime dependencies

## Stable Surface

Stable imports for this feature are:

```python
from open_energy_lab.control import (
    PVSelfConsumptionConfig,
    PVSelfConsumptionController,
    PriceThresholdConfig,
    PriceThresholdController,
    SocGuardrailConfig,
    SocGuardrailController,
)

from open_energy_lab.core import ControllerInterface
from open_energy_lab.simulator import evaluate_with_controller
```

## Fixture Evidence

The completed feature ships small committed controller-pack fixtures under
`tests/fixtures/simulator` for shipped controller behavior:

- one arbitrage case for `PriceThresholdController`
- one guardrail case showing low-SOC or high-SOC correction
- one battery-load-PV case for `PVSelfConsumptionController`

Existing boundary fixtures remain runner evidence. The controller-pack fixtures
prove native shipped controller behavior directly.

Review current fixture provenance with:

```bash
sed -n '1,260p' tests/fixtures/simulator/README.md
sed -n '1,220p' tests/fixtures/simulator/controller_arbitrage_case.json
sed -n '1,260p' tests/fixtures/simulator/controller_battery_load_pv_case.json
```

## Final Validation Commands

```bash
uv run pytest tests/unit/control tests/integration/control tests/integration/simulator
uv run pytest tests/unit/core tests/unit/simulator
uv run python -c "import open_energy_lab.control; import open_energy_lab.core; import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/control tests/unit/control tests/integration/control tests/integration/simulator docs/migration
```

Focused follow-up commands remain:

```bash
uv run pytest tests/unit/control
uv run pytest tests/integration/control
uv run pytest tests/integration/simulator/test_controller_evaluation.py
uv run pytest tests/integration/simulator/test_battery_arbitrage_trace.py tests/integration/simulator/test_battery_load_pv_trace.py
```

## Validation Outcomes

Validation was rerun on `2026-06-08` with the default uv-managed local
environment.

- `uv run pytest tests/unit/control tests/integration/control tests/integration/simulator`
  passed with `96 passed`
- `uv run pytest tests/unit/core tests/unit/simulator` passed with
  `65 passed`
- `uv run python -c "import open_energy_lab.control; import open_energy_lab.core; import open_energy_lab.simulator"`
  passed
- `rg "from legacy|import legacy" src/open_energy_lab/control tests/unit/control tests/integration/control tests/integration/simulator docs/migration`
  returned no matches
- No Phase 6 validation commands were skipped

Checks intentionally out of scope for this feature:

- CityLearn runtime execution
- RL training loops
- solver-backed planning or MPC
- W&B or notebook workflows
- GPU or SLURM execution
- external data downloads
- Rust builds or Rust parity checks
