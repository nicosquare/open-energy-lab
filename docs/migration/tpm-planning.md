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
| row and feature preparation | `legacy/old_tpm/src_py/tpm/data/datahandler.py`, `legacy/old_tpm/src_py/tpm/data/features/feature.py` | `packages/sp-tpm/src/tpm/fit.py`, `packages/sp-tpm/src/tpm/features.py` |
| SPN fit, persistence, and query | `legacy/old_tpm/src_py/tpm/spn/main.py` | `packages/sp-tpm/src/tpm/spflow_backend.py`, `packages/sp-tpm/src/tpm/artifact.py`, `packages/sp-tpm/src/tpm/query.py` |
| SPN-to-MIO equations and density handling | `legacy/old_tpm/src_py/tpm/spn/encoding.py`, `legacy/old_tpm/src_py/tpm/spn/utils_tangent.py`, `legacy/old_tpm/src_py/utils/densities.py` | `packages/sp-tpm/src/tpm/mio/`, `src/open_energy_lab/planning/piecewise.py`, `src/open_energy_lab/planning/problem.py` |

The current code does not import or deserialize the legacy package. The
canonical source rows and reproducible production-fixture workflow live in
`examples/tpm_planning/run_generic_rows_pipeline.py`; the fixture can be
regenerated with `--regenerate-fixture` and independently refitted and checked
with `--verify-fixture`.

New production fits use schema v3 JSON manifests plus hashed
`spflow-model-sidecar` payloads. Existing schema v2 manifests remain loadable
through the labelled legacy-inferred compatibility path and are never silently
promoted to v3. The manifest records current backend/API
versions, feature schema, target semantics, deterministic fit configuration,
compiler metadata, payload locator, and SHA-256 digest. Loading rejects a
missing, corrupt, legacy, or incompatible sidecar before deserialization.

Production queries require a valid current-SPFlow payload and report
`source="spflow_backend"`. There is no empirical or table query mode:
artifacts are fitted and queried with SPFlow only, and a `fixture_replay`
manifest fails to load.

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

The normalized-only compatibility call emits versioned `spflow-v1-mio-v1`
solver-neutral data. A declared-domain v3 fitted artifact plus explicit
physical approximation intervals emits compiled payload v2 with
`spflow-v1-mio-v2` provenance. Planning validates the schema,
compiler/backend versions, graph shape, breakpoint count, epsilon, feature
scopes, physical/model validity, and binary shortfall-event ordering before
consuming it.
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
classified before solution loading; optimal runs load explicitly. A solver
time limit is returned as a diagnostic `time_limit` summary and is never loaded
as an optimal solution, so recommendation validation remains blocked.

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

## Discrete Study Workflow

The scalable study API now covers the full solar-storage design loop without
brute-force selection. `PlanningStudyRequest` defines explicit equipment
options, repeated horizons, an existing named battery controller, and the grid
availability policy. The simulator reuses each absolute stochastic sample
across the full Cartesian equipment grid and writes bounded, resumable Parquet
or JSONL shards.

The default PV self-consumption controller follows the current total
site-load/PV residual and treats each option's charge/discharge rating as an
upper bound. The simulator separately enforces grid feasibility: during an
islanded or outage step it permits charging only from local PV surplus and
discharging only into residual site load. This keeps curtailed charging out of
the unmet-load metric. Manifests record
`simulation_semantics_version="grid-balanced-dispatch-v2"`, and that version
participates in the input fingerprint so older shards cannot be resumed under
the corrected behavior.

Those shards retain the simulator traces needed to inspect policy behavior: PV
generation, site load, controller-requested and physically realized battery
power, post-step state of charge, grid availability, and unmet load. Battery
power follows the simulator convention: positive is charging and negative is
discharging.

`fit_planning_study_tpm` selects the compact SPN columns after checking the
dense tensor memory requirement. `compile_planning_study_tpm` validates the
supported SPFlow graph. `solve_planning_study` then places categorical option
IDs and their installed costs directly in the MIO; the optimizer is not
choosing from enumerated simulation rows. When all decisions are categorical,
the MIO evaluates the compiled conditional graph exactly over the finite joint
option domain and links those risk coefficients to the feature one-hot
variables. Finally, the selected option IDs are queried against native SPFlow.
Encoded/native error above `1e-6` or native risk above the chance limit is a
validation failure.

Use `run_planning_study` for the same stages as one resumable convenience call,
or run `examples/tpm_planning/run_discrete_study.py` for an offline 2x2 case.

## Abu Dhabi Autonomy Notebook

The expanded `examples/tpm_planning/discrete_study_walkthrough.ipynb` is a
configuration and presentation layer over the library-owned workflow. It does
not redefine simulator unmet-energy semantics, TPM metadata, or planning solve
behavior. `local_start_step` is propagated through weather, demand, and study
requests so a local-hour window stays aligned while every episode still resets
to its explicitly configured initial SOC.

The live-input boundary is explicit: PVGIS 5.3 configuration and cache
provenance belong to the weather producer, the canonical hourly cache remains
separate from the fitted artifact, and `fit_weather_dataset` avoids a second
request. Synthetic and measured demand inputs both terminate at the existing
`fit_demand_model` boundary. Simulator-owned manifests remain separate for
training, validation, and final test.

SPN selection uses only validation Brier score among candidates that genuinely
compile. Final-test calibration, native/MIO parity, and the selected design's
one-sided confidence bound gate the user-facing recommendation. HiGHS output is
still retained when a gate fails, but is labeled exploratory. Full live PVGIS
and 24,000-row notebook execution are manual checks; routine validation stays
offline and fixture-backed.

## Required Review Commands

```bash
uv run pytest tests/integration/tpm/test_spflow_v1_fit.py tests/integration/tpm/test_spflow_v1_persistence.py tests/integration/tpm/test_spflow_v1_query.py tests/integration/tpm/test_spflow_v1_mio_parity.py
uv run pytest tests/integration/planning/test_highs_solver.py tests/integration/planning/test_spflow_v1_highs_pipeline.py
uv run pytest tests/unit/planning tests/unit/tpm tests/integration/planning tests/integration/tpm
uv run pytest tests/unit/test_lazy_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py
uv run python -c "import open_energy_lab; import open_energy_lab.weather; import open_energy_lab.demand; import open_energy_lab.simulator; import open_energy_lab.tpm; import open_energy_lab.planning"
rg "from legacy|import legacy" packages/sp-tpm/src/tpm src/open_energy_lab/planning tests/unit/tpm tests/unit/planning tests/integration/tpm tests/integration/planning
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
