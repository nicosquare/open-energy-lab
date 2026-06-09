# Quickstart: Visualization And Trace Inspection MVP

Use this quickstart to review the completed visualization-traces feature and
rerun its focused validation set. The feature introduces the first reusable
inspection surface in `open_energy_lab.visualization`, with stable
inspection/reporting plus an experimental optional plotting layer for basic
single-run static plots.

## Review the Feature

```bash
sed -n '1,360p' specs/006-visualization-traces/spec.md
sed -n '1,360p' specs/006-visualization-traces/plan.md
sed -n '1,320p' specs/006-visualization-traces/research.md
sed -n '1,320p' specs/006-visualization-traces/data-model.md
```

Confirm the intended feature boundary:

- `open_energy_lab.visualization` becomes the canonical inspection layer for
  supported deterministic run outputs
- simulator and controller modules remain the sole owners of execution
- stable inspection/reporting and experimental plotting have explicit maturity
  boundaries
- same-family comparison is supported, cross-family comparison is rejected
- plotting works from existing in-memory or persisted outputs and does not
  rerun simulation
- weather reporting is limited to simulator-exposed weather variables

## Review the Contracts

```bash
sed -n '1,220p' specs/006-visualization-traces/contracts/visualization-package-contract.md
sed -n '1,220p' specs/006-visualization-traces/contracts/inspection-view-contract.md
sed -n '1,220p' specs/006-visualization-traces/contracts/comparison-contract.md
sed -n '1,220p' specs/006-visualization-traces/contracts/plotting-contract.md
sed -n '1,220p' specs/006-visualization-traces/contracts/validation-case.md
```

Confirm the contracts agree on:

- stable inspection/reporting at the package root
- optional experimental plotting
- same-family comparison only
- explicit unsupported behavior for cross-family comparison
- plotting from existing outputs only
- import-light base package behavior

## Review the Current Upstream Result Shapes

```bash
sed -n '1,260p' src/open_energy_lab/simulator/controller_runner.py
sed -n '1,340p' src/open_energy_lab/simulator/scenario.py
sed -n '1,220p' src/open_energy_lab/simulator/weather.py
sed -n '1,220p' src/open_energy_lab/simulator/pv.py
sed -n '1,120p' src/open_energy_lab/visualization/__init__.py
```

Use these files to confirm that:

- current deterministic result shapes already contain the inputs needed for
  inspection
- `BatteryLoadPVScenario` already exposes the weather-backed context that the
  visualization layer should report
- the current visualization package is still only a scaffold and this feature
  will become its first real public surface

## Review the Existing Migration Notes

```bash
sed -n '1,220p' docs/migration/api-maturity.md
sed -n '1,220p' docs/migration/dependency-policy.md
sed -n '1,220p' docs/migration/fixture-provenance.md
sed -n '1,220p' docs/migration/README.md
```

Use these files to confirm that:

- the new feature must align with the current API-maturity guidance
- optional plotting stays outside the base dependency boundary
- committed fixtures need provenance notes

## Environment

The feature uses the same minimal Python environment as the current native
library work:

```bash
uv sync --dev
```

If the environment is not prepared yet, review the foundation, controller
boundary, and controller-pack quickstarts first:

```bash
sed -n '1,220p' specs/001-library-foundation/quickstart.md
sed -n '1,260p' specs/004-controller-boundary/quickstart.md
sed -n '1,260p' specs/005-controller-pack/quickstart.md
```

## Implemented Targets

After implementation, the main touched areas should be:

```text
src/open_energy_lab/visualization/
tests/unit/visualization/
tests/integration/visualization/
tests/fixtures/visualization/
docs/migration/
```

The implemented feature stays narrow. It proves that:

- supported simulator and controller results can be inspected through one
  canonical surface
- supported weather-backed runs can report weather context alongside energy
  traces
- same-family runs can be compared deterministically
- supported persisted outputs can be loaded later for inspection or plotting
- basic static plots can be generated without rerunning simulation
- the stable package root remains free of mandatory plotting dependencies

## Stable And Experimental Surface

Stable public behavior for this feature is:

- canonical inspection/reporting over supported deterministic run outputs
- deterministic same-family comparison behavior

Experimental behavior for this feature is:

- optional plotting-layer support for basic static single-run plots

## Fixture Evidence

The completed feature may reuse existing simulator fixtures where possible and
add small visualization-specific fixtures only when existing results are not
sufficient for deterministic plotting or persisted-output coverage.

Review current fixture provenance with:

```bash
sed -n '1,260p' tests/fixtures/README.md
sed -n '1,260p' tests/fixtures/simulator/README.md
```

## Final Validation Commands

```bash
uv run pytest tests/unit/visualization tests/integration/visualization
uv run pytest tests/unit/simulator tests/integration/simulator
uv run python -c "import open_energy_lab.visualization; import open_energy_lab.simulator; import open_energy_lab.core"
rg "from legacy|import legacy" src/open_energy_lab/visualization tests/unit/visualization tests/integration/visualization docs/migration
```

Focused follow-up commands remain:

```bash
uv run pytest tests/unit/visualization
uv run pytest tests/integration/visualization
uv run pytest tests/integration/simulator/test_controller_evaluation.py
uv run pytest tests/integration/simulator/test_battery_arbitrage_trace.py tests/integration/simulator/test_battery_load_pv_trace.py
```

## Validation Outcomes

Validation should be recorded after implementation using the default uv-managed
local environment. If any plotting checks require an optional backend not yet
installed, document that explicitly and keep base import checks separate.
