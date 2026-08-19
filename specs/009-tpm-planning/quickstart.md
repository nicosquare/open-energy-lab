# Quickstart: TPM-Backed Planning And Simulator Dataset Export

Use this quickstart to review the completed 009 implementation after the
2026-08-17 dependency clarifications. Dataset export, typed features,
production artifacts, explicit fixture replay, the current-SPFlow compiler,
and required Pyomo/HiGHS planning validation are implemented.

## Corrected Backend Policy

- SPFlow, Pyomo, and HiGHS (`highspy`) are required project dependencies.
- Required installation does not imply eager import. Package roots stay lazy.
- The initial migration pins are `spflow==1.1.0`, `pyomo==6.10.1`, and
  `highspy==1.15.1`; widen them only after compatibility-matrix evidence.
- Pyomo `SolverFactory("highs")` is the standard solver path.
- Gurobi is additionally supported but remains license- and
  environment-dependent.
- Production TPM fit/query requires a valid current-SPFlow payload.
- Empirical replay is allowed only through explicit `fixture_replay` mode and
  never activates automatically.
- Routine CI exercises real SPFlow and real Pyomo/HiGHS. Fake backends and
  committed fixtures remain supplementary deterministic evidence.

SPFlow 1.1 is a PyTorch-based rewrite. Its maintainers state that pre-1.0
models are incompatible and must be rebuilt. The migration therefore preserves
validated behavior and project artifact contracts, not old serialized model
objects.

## Preserve / Port / Reject

- **Preserve**: simulator-owned export, `shortfall` semantics, typed feature
  metadata, deterministic artifact provenance, direct battery-and-solar
  decisions, and piecewise chance-constraint semantics.
- **Port**: legacy Context/`learn_mspn` behavior to current leaf modules,
  scopes, `learn_spn`, PyTorch tensors, model likelihood/marginalization, and a
  versioned current-model sidecar.
- **Redesign**: current-SPFlow-to-piecewise-MIO traversal for SPFlow 1.1
  tensorized modules. The
  compiler must declare supported module/leaf types and demonstrate parity
  against native `model.log_likelihood(...)` results.
- **Reject**: automatic table/empirical production fallback, metadata-only
  success, optional-install semantics for SPFlow/Pyomo/HiGHS, and routine
  solver skips.

## Review The Feature And Contracts

```bash
sed -n '1,460p' specs/009-tpm-planning/spec.md
sed -n '1,360p' specs/009-tpm-planning/plan.md
sed -n '1,360p' specs/009-tpm-planning/research.md
sed -n '1,360p' specs/009-tpm-planning/data-model.md
sed -n '1,240p' specs/009-tpm-planning/contracts/tpm-artifact-contract.md
sed -n '1,240p' specs/009-tpm-planning/contracts/planning-solve-contract.md
sed -n '1,240p' specs/009-tpm-planning/contracts/validation-contract.md
```

Confirm that:

- simulator export remains independent from TPM fitting and planning solve
- ordinary library imports do not load required heavy backends
- production and fixture replay modes are explicit and mutually exclusive
- current SPFlow payloads carry backend/API/version/integrity metadata
- legacy SPFlow payloads fail with an artifact compatibility error
- omission of solver configuration selects `highs`
- only explicitly selected supplemental Gurobi checks may skip

## Environment

Synchronize and inspect the required backend versions:

```bash
uv sync --dev
uv run python -c "import spflow, pyomo, highspy; print(spflow.__version__, pyomo.__version__, highspy.Highs().version())"
```

The lock file is authoritative for routine validation. CI must cover the
project's supported Python floor and newest supported interpreter. If a
required wheel or dependency does not resolve on a claimed platform, that
platform is unsupported until compatibility is restored; the backend check is
not skipped.

### Locked-resolution evidence

T003 regenerated `uv.lock` with uv 0.12.5 on 2026-08-18, then selected the
locked environment without installing it on each initially targeted Python
version:

```bash
uv sync --locked --dry-run --python 3.11 --python-platform x86_64-unknown-linux-gnu
uv sync --locked --dry-run --python 3.12 --python-platform x86_64-unknown-linux-gnu
uv sync --locked --dry-run --python 3.13 --python-platform x86_64-unknown-linux-gnu
uv sync --locked --dry-run --python 3.14 --python-platform x86_64-unknown-linux-gnu
```

| Python | Interpreter tested | Locked selection | Required pins selected |
|---|---|---|---|
| 3.11 | CPython 3.11.16 | PASS (63 packages) | SPFlow 1.1.0, Pyomo 6.10.1, highspy 1.15.1 |
| 3.12 | CPython 3.12.14 | PASS (63 packages) | SPFlow 1.1.0, Pyomo 6.10.1, highspy 1.15.1 |
| 3.13 | CPython 3.13.15 | PASS (63 packages) | SPFlow 1.1.0, Pyomo 6.10.1, highspy 1.15.1 |
| 3.14 | CPython 3.14.6 | PASS (63 packages) | SPFlow 1.1.0, Pyomo 6.10.1, highspy 1.15.1 |

No dependency-specific incompatibility was observed for the tested Linux
x86_64 target, so the project retains `requires-python = ">=3.11"` and all
four initial Python versions. These dry runs validate locked dependency and
distribution selection; the real fit/query/compiler/solve commands below
provide runtime evidence.

## Current SPFlow Migration Mapping

The implementation validates these mappings against SPFlow 1.1:

| Legacy behavior | Current target |
|---|---|
| `Context(...)` with meta-types/domains | typed leaf modules with `Scope` |
| `learn_mspn(numpy_data, context, ...)` | `learn_spn(torch_tensor, leaf_modules=..., ...)` |
| free `log_likelihood(model, data)` | `model.log_likelihood(torch_tensor)` |
| `marginalize(model, keep_indices)` | NaN evidence or `model.marginalize(indices_to_remove)` |
| legacy pickle | versioned SPFlow 1.1 model sidecar plus JSON manifest/hash |
| scalar node topological traversal | project compiler over supported tensorized modules |

Important semantic checks:

- current structural marginalization names variables to remove, unlike the
  legacy keep-index convention
- current likelihood results are tensors and require an explicit scalar
  root/channel/repetition reduction contract
- mixed feature types need explicit per-scope leaf modules and dtype/domain
  validation
- canonical seed `13` covers Python, NumPy, Torch, SPFlow, and solver settings;
  robustness coverage uses seeds `37` and `101`
- repeated fit/query/solve outputs must agree within `1e-9`; compiled
  probabilities must be within `1e-6` absolute error of native likelihood
- pre-1.0 model files are rejected and rebuilt from source planning datasets

## Explicit TPM Execution Modes

Production mode is the default:

```python
request = TPMQueryRequest(
    decision_assignments={...},
    marginalized_features=(...),
    target_name="shortfall",
    output_mode="conditional_probability",
    execution_mode="production",
)
```

It requires a valid current-SPFlow payload. Missing, corrupt, legacy, or
unsupported payloads fail explicitly.

Fixture replay must be requested deliberately:

```python
request = TPMQueryRequest(
    decision_assignments={...},
    marginalized_features=(...),
    target_name="shortfall",
    output_mode="conditional_probability",
    execution_mode="fixture_replay",
)
```

Fixture replay is for deterministic contract tests and artifact inspection. A
fixture result must identify `source="empirical_fixture"` and must never be
reported as real-backend evidence.

## Required HiGHS Solve

The standard planning workflow is:

1. Load a production current-SPFlow TPM artifact.
2. Validate direct battery and solar decision variables.
3. Compile sum/product structure with one output channel and repetition and
   Normal, Bernoulli, or Categorical typed leaves to the canonical piecewise
   Pyomo formulation; reject unsupported modules or graph shapes explicitly.
4. Enforce `P(shortfall > threshold) <= epsilon`.
5. Solve through `SolverFactory("highs")` with seed `13`, one thread, and a
   30-second fixture time limit.
6. Record Pyomo, `highspy`, solver-interface, options, termination, tolerance,
   and objective/risk metadata.

Assembly-only inspection remains supported, but routine CI must also solve.
Missing Pyomo or HiGHS is an installation failure. Gurobi may be selected
explicitly for supplemental validation and may skip only when its environment
or license is unavailable.

Run the complete offline simulator-to-production-SPFlow-to-default-HiGHS
example:

```bash
uv run python examples/tpm_planning/run_real_backend_pipeline.py
```

## Required Validation

Run the focused real-backend tests:

```bash
uv run pytest tests/integration/tpm/test_spflow_v1_fit.py tests/integration/tpm/test_spflow_v1_persistence.py tests/integration/tpm/test_spflow_v1_query.py tests/integration/tpm/test_spflow_v1_mio_parity.py
uv run pytest tests/integration/planning/test_highs_solver.py
uv run pytest tests/integration/planning/test_spflow_v1_highs_pipeline.py
```

Coverage must include:

- real SPFlow fit, save, load, marginalization, and conditional query
- mixed supported feature scopes and deterministic seed behavior
- rejection of legacy/incompatible payloads
- production failure without a valid payload
- explicit empirical fixture replay
- compiler rejection of unsupported SPFlow module types
- compiled probability parity against native SPFlow likelihood
- real HiGHS optimal and infeasible termination paths
- integrality, time-limit/options, solution loading, and repeatability

Run the complete relevant regression set after those focused checks:

```bash
uv run pytest tests/unit/demand tests/integration/demand tests/integration/simulator
uv run pytest tests/unit/planning tests/unit/tpm tests/integration/planning tests/integration/tpm
uv run pytest tests/unit/test_lazy_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.simulator; import open_energy_lab.tpm; import open_energy_lab.planning"
uv run python -c "import open_energy_lab; import open_energy_lab.weather; import open_energy_lab.demand; import open_energy_lab.simulator; import open_energy_lab.tpm; import open_energy_lab.planning"
rg "from legacy|import legacy" src/open_energy_lab/tpm src/open_energy_lab/planning src/open_energy_lab/simulator tests/unit/planning tests/unit/tpm tests/integration/planning tests/integration/tpm docs/migration
```

Import-boundary tests now assert laziness, not absence from the installation:

- importing package roots must not add `spflow`, `torch`, `pyomo`, or
  `highspy` modules to `sys.modules`
- invoking the corresponding real workflow must load its required backend
- dependency incompatibility is reported as a failed installation/workflow,
  not a successful skip

## Supplementary Validation

These checks may remain optional and must be reported accurately when skipped:

```bash
cd legacy/old_tpm && pytest src_py/tpm/spn/test_tangent_lower_bound.py
```

- Gurobi-backed solve parity when its package, binary, and license are present
- legacy runtime comparisons when the legacy environment is reproducible

They supplement but do not replace the required current-SPFlow and HiGHS
checks.

## Review Gate

Confirm all of the following before accepting the implementation:

- required dependencies and supported Python policy are declared and locked
- current SPFlow fit/query artifacts replace legacy model assumptions
- automatic empirical/metadata fallback is removed
- the supported SPFlow 1.1 module subset compiles to the planning formulation
- native likelihood and compiled probability agree within documented tolerance
- real Pyomo/HiGHS optimal and infeasible tests pass offline
- the 008 demand/simulator regression suites remain green
- migration and API-maturity documentation no longer calls required backends
  optional

The previous fake-backend and Gurobi replay results remain historical evidence;
they are not validation outcomes for this corrected contract.
