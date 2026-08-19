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

## Migration Provenance And Refit Policy

The migration translates behavior from these reference-only paths:

| Preserved concern | Legacy evidence | Current implementation |
| --- | --- | --- |
| row and feature preparation | `legacy/old_tpm/src_py/tpm/data/datahandler.py`, `legacy/old_tpm/src_py/tpm/data/features/feature.py` | `src/open_energy_lab/tpm/fit.py`, `src/open_energy_lab/tpm/features.py` |
| SPN fit, persistence, and query | `legacy/old_tpm/src_py/tpm/spn/main.py` | `src/open_energy_lab/tpm/optional_spflow.py`, `src/open_energy_lab/tpm/artifact.py`, `src/open_energy_lab/tpm/query.py` |
| SPN-to-MIO equations and density handling | `legacy/old_tpm/src_py/tpm/spn/encoding.py`, `legacy/old_tpm/src_py/tpm/spn/utils_tangent.py`, `legacy/old_tpm/src_py/utils/densities.py` | `src/open_energy_lab/tpm/mio.py`, `src/open_energy_lab/planning/piecewise.py`, `src/open_energy_lab/planning/problem.py` |

The current code does not import or deserialize the legacy package. The
canonical source rows and reproducible production-fixture workflow live in
`examples/tpm_planning/run_generic_rows_pipeline.py`; the fixture can be
regenerated with `--regenerate-fixture` and independently refitted and checked
with `--verify-fixture`.

Production artifacts use schema v2 JSON manifests plus hashed
`spflow-model-sidecar` payloads. The manifest records current backend/API
versions, feature schema, target semantics, deterministic fit configuration,
compiler metadata, payload locator, and SHA-256 digest. Loading rejects a
missing, corrupt, legacy, or incompatible sidecar before deserialization.

Production queries require a valid current-SPFlow payload and report
`source="spflow_backend"`. Empirical rows are available only when the caller
and artifact explicitly select `fixture_replay`; production never silently
downgrades to table, empirical, or metadata-only results.

Pre-1.0 SPFlow objects and schema-v1 artifacts are incompatible with SPFlow
1.1. They are accepted only far enough to produce explicit refit guidance and
must be rebuilt from their source planning rows. The retained
`tests/fixtures/tpm/tpm_artifact_v1.json` is negative-case evidence, never a
production or query input.

Refit verification compares stable structure, parameters, likelihoods,
queries, compiler output, and canonical-point probabilities. Pickle bytes and
sidecar digests may change across a legitimate refit, so byte equality is not
a repeatability promise; the newly persisted SHA-256 digest is authoritative
for subsequent reload integrity. Regenerate the canonical fixture only when
its source rows, fit configuration, required SPFlow API, compiler contract, or
schema-v2 artifact contract intentionally changes.

## Current-SPFlow Compiler

`compile_spflow_model_to_mio(...)` accepts the declared first-release subset:

- exact native Sum and Product modules; internal SPFlow `Cat` adapters are
  unwrapped as edges rather than emitted as nodes
- exact native Normal, Bernoulli, and Categorical typed leaves on separate
  scopes
- one output channel and one repetition
- five canonical normalized breakpoints `(0, 0.25, 0.5, 0.75, 1)` by default,
  with any global or continuous-feature override recorded explicitly
- MIO epsilon `1e-6`

It emits versioned `spflow-v1-mio-v1` solver-neutral data. Planning validates
the schema, compiler/backend versions, graph shape, breakpoint count, epsilon,
feature scopes, and binary shortfall-event ordering before consuming it.
Normal log densities use the piecewise approximation; Bernoulli and
Categorical probabilities and Sum/Product composition retain their declared
probability semantics. Unsupported or custom leaves, legacy histogram
payloads, custom subclasses, shared subgraphs, extra dimensions, channels or
repetitions, and incompatible compiler metadata fail explicitly.

Canonical native-likelihood versus compiled probability error is at most
`1e-6`; repeated compiler/query results use `1e-9` tolerance.

## Parity Scope And Limitations

Current-backend parity means comparing native SPFlow likelihood with the
solver-neutral compiler evaluator at the five canonical normalized evidence
rows. `tests/integration/tpm/test_spflow_v1_mio_parity.py` exercises a native
Sum-of-Products graph containing Normal, Bernoulli, and Categorical leaves;
the committed production fixture independently covers its learned Product and
typed-leaf graph. The allowed maximum absolute probability error is `1e-6`,
and repeated compilation/evaluation must agree within `1e-9`.

This evidence does not prove accuracy over every point in the continuous
evidence domain, support for rejected graph/module shapes, serialized-pickle
or legacy-runtime equality, HiGHS/Gurobi equality, or production-scale
performance. Planning additionally conditions the compiled graph by fixing
the binary shortfall event, retaining battery/solar decision scopes, and
marginalizing other scopes; that adapter is validated by planning tests and is
not a general SPFlow inference compiler. Robustness seeds `37` and `101` are
supplemental checks and do not replace seed `13` canonical baselines.

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
