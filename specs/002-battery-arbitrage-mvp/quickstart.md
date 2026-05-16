# Quickstart: Battery Arbitrage Simulator MVP

Use this quickstart to review the plan and to guide the later simulator MVP
implementation. This feature migrates a narrow simulator slice only.

## Review the Feature

```bash
sed -n '1,260p' specs/002-battery-arbitrage-mvp/spec.md
sed -n '1,260p' specs/002-battery-arbitrage-mvp/plan.md
sed -n '1,240p' specs/002-battery-arbitrage-mvp/research.md
sed -n '1,240p' specs/002-battery-arbitrage-mvp/data-model.md
```

Confirm the intended boundary:

- target code stays under `src/open_energy_lab/simulator`
- the first case is deterministic battery arbitrage only
- battery, time-grid, tariff, dispatch, and settlement behavior are in scope
- planning, control, RL, solver, CityLearn-runtime, notebook, W&B, GPU/SLURM,
  and Rust-bound behavior are out of scope

## Review the Contracts

```bash
sed -n '1,220p' specs/002-battery-arbitrage-mvp/contracts/scenario-contract.md
sed -n '1,220p' specs/002-battery-arbitrage-mvp/contracts/battery-component.md
sed -n '1,220p' specs/002-battery-arbitrage-mvp/contracts/validation-case.md
```

Before implementation, make sure the contracts agree on:

- energy in `kWh`
- power in `kW`
- SOC as fraction in `[0.0, 1.0]`
- positive dispatch request meaning charge
- timestep duration expressed in hours
- discounted export settlement relative to import price
- default absolute tolerance `1e-6`
- the only built-in rule policy being `price_threshold`

## Review the Legacy Evidence

```bash
sed -n '1,260p' legacy/old_tpm/src_py/legacy/storage.py
sed -n '1,260p' legacy/old_tpm/src_py/simulator/common/battery.py
sed -n '1,220p' legacy/old_tpm/src_py/simulator/common/pricing.py
sed -n '1,120p' legacy/old_tpm/src_py/simulator/common/time.py
sed -n '1,220p' legacy/old_tpm/scripts/test_battery_consistency.py
```

Use these sources to validate the chosen battery, tariff, and tolerance
semantics. Do not copy broad legacy structure into the new package.

## Environment

The simulator MVP uses the same base environment as the foundation:

```bash
conda activate open-energy-lab
uv sync --dev
```

If the environment is not present yet, follow the foundation quickstart first:

```bash
sed -n '1,200p' specs/001-library-foundation/quickstart.md
```

## Expected Implementation Targets

After implementation, the main touched areas should be:

```text
src/open_energy_lab/simulator/
tests/unit/simulator/
tests/integration/simulator/
tests/fixtures/simulator/
docs/migration/
```

The implementation should stay narrow. A single deterministic scenario is
enough if it proves the contracts. That scenario may use explicit dispatch
requests or the built-in `price_threshold` policy, but the validation path must
state which mode it is using.

## Expected Checks After Tasks Exist

```bash
uv run pytest tests/unit/simulator tests/integration/simulator
uv run python -c "import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/simulator tests/unit tests/integration
```

Expected result for the legacy-import scan: no matches in new library modules
or their default tests.

Optional reference check when the legacy environment is locally runnable:

```bash
cd legacy/old_tpm && python scripts/test_battery_consistency.py
```

## Checks Intentionally Out of Scope

This feature should not require or run:

- solver-backed optimization
- TorchRL or PyTorch adapter flows
- CityLearn environment execution
- W&B or notebook workflows
- GPU or SLURM execution
- real-data tariff ingestion
- Rust builds or Rust parity checks

## Task Planning Reminder

When `/speckit-tasks` is generated, make sure it includes:

- simulator module creation
- battery invariant tests
- timestep/tariff alignment tests
- discounted-export settlement tests
- optional built-in `price_threshold` policy tests
- one deterministic arbitrage integration case with `1e-6` tolerance-backed
  assertions
- fixture provenance updates when fixtures are committed
- docs covering preserved, improved, and rejected legacy behavior
