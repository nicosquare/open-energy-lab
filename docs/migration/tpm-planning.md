# TPM-Backed Planning Migration

Status: the `009-tpm-planning` library path is implemented with required
current SPFlow, Pyomo, and HiGHS validation. Simulator export, TPM artifacts,
queries, current-SPFlow-to-piecewise-MIO compilation, planning assembly, and a
license-free solve are reusable library workflows under
`src/open_energy_lab`.

## Ownership Boundaries

- `open_energy_lab.simulator` exports aligned planning rows and derives the
  canonical `shortfall` metric from simulator outputs.
- `open_energy_lab.tpm` owns typed feature metadata, model fitting, artifact
  persistence, current-SPFlow queries, and solver-neutral MIO compilation.
- `open_energy_lab.planning` validates battery/solar decisions, assembles the
  chance constraint, and solves through Pyomo.
- Outage and blackout semantics remain simulator-owned. They are not inferred
  by TPM fitting or planning assembly.
- Empirical fixture replay remains explicit test evidence and is not a
  production fallback.

## Required Backends And Lazy Imports

The locked first-release backend versions are:

- `spflow==1.1.0`
- `pyomo==6.10.1`
- `highspy==1.15.1`

They are required installation dependencies, but package imports remain lazy.
Importing `open_energy_lab`, `open_energy_lab.tpm`, or
`open_energy_lab.planning` does not import SPFlow, Torch, Pyomo, or highspy.
Those modules load only when a fit, production query/compiler, or solve begins.

Missing or incompatible required versions are installation failures. They may
not be converted into successful skips. Gurobi remains a separately managed,
supplemental solver and may skip only when explicitly selected and its binary
or license is unavailable.

Verify the installed versions with:

```bash
uv run python -c "import spflow, pyomo, highspy; print(spflow.__version__, pyomo.__version__, highspy.Highs().version())"
```

## Artifact And Execution-Mode Migration

Production artifacts use schema v2 JSON manifests plus hashed
`spflow-model-sidecar` payloads. The manifest records current backend/API
versions, feature schema, target semantics, deterministic fit configuration,
compiler metadata, payload locator, and SHA-256 digest. Loading rejects a
missing, corrupt, legacy, or incompatible sidecar before deserialization.

Production queries require a valid current-SPFlow payload and report
`source="spflow_backend"`. Empirical rows are available only when the caller
and artifact explicitly select `fixture_replay`; production never silently
downgrades to table, empirical, or metadata-only results.

Pre-1.0 SPFlow objects are incompatible with SPFlow 1.1 and must be refitted
from source rows. The migration preserves validated equations, typed domains,
fit/query behavior, and provenance rather than serialized legacy objects.

## Current-SPFlow Compiler

`compile_spflow_model_to_mio(...)` accepts the declared first-release subset:

- exact native Sum and Product modules
- Normal, Bernoulli, and Categorical typed leaves
- one output channel and one repetition
- five canonical normalized breakpoints
- MIO epsilon `1e-6`

It emits versioned `spflow-v1-mio-v1` solver-neutral data. Planning validates
the schema, compiler/backend versions, graph shape, breakpoint count, epsilon,
feature scopes, and binary shortfall-event ordering before consuming it.
Unsupported modules, custom subclasses, shared graphs, extra channels or
repetitions, and incompatible compiler metadata fail explicitly.

Canonical native-likelihood versus compiled probability error is at most
`1e-6`; repeated compiler/query results use `1e-9` tolerance.

## Required Planning Solve

Omitting solver configuration selects Pyomo `SolverFactory("highs")` with:

- random seed `13`
- one thread
- a 30-second per-fixture time limit
- numeric and repeated-solve tolerance `1e-9`

The first release optimizes battery and solar decisions only and enforces:

`P(shortfall > threshold) <= epsilon`

The target threshold and chance limit remain distinct inputs. The planning
summary records the selected design, objective, estimated risk, feasibility
diagnostics, Pyomo/highspy versions, solver interface, exact options,
termination condition, and whether a solution was loaded. Infeasible runs are
classified before solution loading; optimal runs load explicitly.

Assembly-only inspection remains supported, but it does not replace the
required real HiGHS review path.

## Reproducibility Contract

- canonical Python, NumPy, Torch, SPFlow, and solver seed: `13`
- robustness seeds: `37` and `101`
- fit/query/repeated-HiGHS/objective/risk tolerance: `1e-9`
- native-versus-compiled probability tolerance and MIO epsilon: `1e-6`
- canonical piecewise breakpoint count: `5`
- HiGHS execution: one thread and 30 seconds

The committed production SPFlow fixture is:

- `tests/fixtures/tpm/tpm_artifact_spflow_v1.json`
- `tests/fixtures/tpm/sidecars/tpm_artifact_spflow_v1.spn_payload.pkl`

The planning fixture records required HiGHS optimal/infeasible outcomes and
supplemental HiGHS-versus-Gurobi objective/risk tolerances in
`tests/fixtures/planning/planning_problem_case.json`.

## Runnable Examples

Fit, reload, query, compile, and verify the canonical production fixture:

```bash
uv run python examples/tpm_planning/run_generic_rows_pipeline.py --verify-fixture
```

Run the complete offline simulator-to-production-SPFlow-to-default-HiGHS path:

```bash
uv run python examples/tpm_planning/run_real_backend_pipeline.py
```

Generated example artifacts remain under
`tmp/open-energy-lab-pipeline-real-backends/`.

## Required Review Commands

```bash
uv run pytest tests/integration/tpm/test_spflow_v1_fit.py tests/integration/tpm/test_spflow_v1_persistence.py tests/integration/tpm/test_spflow_v1_query.py tests/integration/tpm/test_spflow_v1_mio_parity.py
uv run pytest tests/integration/planning/test_highs_solver.py tests/integration/planning/test_spflow_v1_highs_pipeline.py
uv run pytest tests/unit/planning tests/unit/tpm tests/integration/planning tests/integration/tpm
uv run pytest tests/unit/test_lazy_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.weather; import open_energy_lab.demand; import open_energy_lab.simulator; import open_energy_lab.tpm; import open_energy_lab.planning"
rg "from legacy|import legacy" src/open_energy_lab/tpm src/open_energy_lab/planning tests/unit/tpm tests/unit/planning tests/integration/tpm tests/integration/planning
```

These required checks are offline and need no notebooks, network services,
commercial solver license, GPU, SLURM, or W&B access.

## Supplemental Validation

When Gurobi is installed and licensed, compare it with HiGHS using the
fixture-defined `reference_solver`, `candidate_solver`, `objective_tolerance`,
and `risk_tolerance`. Record both values and measured absolute differences. An
availability skip is acceptable for Gurobi only and does not weaken required
HiGHS validation.

Legacy runtime comparisons are also supplemental. If the legacy environment
cannot be reproduced, document that outcome rather than changing base
dependencies or treating it as required validation.

## Legacy Evidence

The migrated behavior is grounded in these reference paths without runtime
imports from `legacy/*`:

- `legacy/old_tpm/src_py/tpm/data/datahandler.py`
- `legacy/old_tpm/src_py/tpm/data/features/feature.py`
- `legacy/old_tpm/src_py/tpm/spn/main.py`
- `legacy/old_tpm/src_py/tpm/spn/encoding.py`
- `legacy/old_tpm/src_py/tpm/spn/utils_tangent.py`
- `legacy/old_tpm/src_py/utils/densities.py`

The current library rejects legacy package and pickle compatibility as a
runtime requirement; only tested behavior and documented equations migrate.
