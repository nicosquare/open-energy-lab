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
- Scalable study datasets additionally require `pyarrow==25.0.0`; Parquet is
  the default shard format and JSONL is the reviewable alternative. PyArrow is
  imported only when a Parquet read/write boundary is invoked.
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

## Discrete Solar-Storage Study

The public staged workflow is:

1. `generate_planning_study_dataset(...)` sweeps the explicit battery/solar
   grid and reuses each absolute weather/demand/grid sample across all designs.
2. `fit_planning_study_tpm(...)` materializes only selected SPN columns after
   a tensor-memory preflight.
3. `compile_planning_study_tpm(...)` compiles the supported current-SPFlow
   graph.
4. `solve_planning_study(...)` minimizes per-option installed costs in the
   direct categorical MIO and verifies the selected design with native SPFlow.

`run_planning_study(...)` executes the same stages and resumes compatible
dataset shards. The default controller is PV self-consumption; supplied,
islanded, and two-state Markov grid traces are supported. Active adequacy events
may use shortfall ratio, unmet energy, or unmet-timestep fraction thresholds.

### Configurable Abu Dhabi autonomy notebook

`examples/tpm_planning/discrete_study_walkthrough.ipynb` is the full manual
acceptance workflow. Defaults are Abu Dhabi city centre (`24.4539, 54.3773`,
`Asia/Dubai`), a 24-hour local-midnight islanded horizon, explicitly reset
100% initial SOC, a 10% SOC floor, 95% efficiencies, 0.5C storage, and the
chance rule `P(unmet_energy_kwh > 0.1) <= 0.05`.

The notebook uses the versioned PVGIS 5.3 TMY endpoint. It caches a canonical
8,760-row table separately from the fitted weather artifact and fits from that
already fetched dataset, so a fresh run makes one request. It fails if neither
a compatible cache nor the configured network fetch is available; no fixture
fallback is allowed. Live PVGIS remains outside routine CI.

Demand is either explicitly labeled synthetic small-commercial demand or a
measured CSV containing at least 90 complete hourly days and separate
non-cooling electric demand plus cooling RT. Both modes use
`fit_demand_model`; total electricity without separate cooling remains invalid.

Default study evidence is split into independent manifests:

- training: 1,000 episodes/configuration, seed 13, 9,000 rows;
- validation: 250/configuration, seed 37, 2,250 rows;
- final test: 250/configuration, seed 101, 2,250 rows.

Real default/finer/coarser SPFlow candidates must compile before selection.
Validation Brier score selects the candidate, with smaller node count breaking
ties. HiGHS always executes. Recommendation requires mean final-test
configuration error at most 5 points, maximum error at most 10 points, both
labels, selected native probability within its held-out confidence interval,
native/MIO error at most `1e-6`, and a one-sided held-out 95% risk upper bound
at most 5%. A failure produces an exploratory result rather than a reliability
recommendation.

Install the isolated notebook environment before opening the walkthrough:

```bash
uv sync --group notebook
```

Select `.venv/bin/python` as the kernel. Matplotlib and Seaborn are confined to
that dependency group and are not imported by the core library.

### Recorded notebook-extension validation — 2026-08-20

- Focused weather cache/offset, demand-input, planning-validation, and notebook
  structure checks: `37 passed in 8.22s`.
- Reduced fixture-backed autonomy study using separate train, validation, and
  test manifests, two real SPFlow candidates, MIO compilation, HiGHS solving,
  and deliberate recommendation blocking: `1 passed in 5.94s`.
- Notebook/public-package checks: `20 passed in 0.27s`.
- Complete relevant weather, demand, simulator, TPM, planning, backend, and
  import-boundary regression: `457 passed, 6 skipped in 25.92s`. All six skips
  were supplemental unavailable-Gurobi checks; required SPFlow, Pyomo, and
  HiGHS validation passed.
- Python compilation, all-package lazy-import smoke testing, strict Python
  legacy-import scanning, and `git diff --check` passed.

The live PVGIS request and full 8,760-hour/13,500-episode notebook acceptance
run remain manual by repository policy. They were not run as part of this
offline validation and are not replaced by fixtures or synthetic provenance.

Run the offline example:

```bash
uv run python examples/tpm_planning/run_discrete_study.py
```

### Recorded extension validation — 2026-08-19

- Focused compact-fit, MIO, staged workflow, real 2x2 SPFlow/HiGHS, and package
  surface checks: `61 passed in 6.66s`.
- Full required 008+009 demand, weather, simulator, TPM, planning, and import
  boundary regression: `429 passed, 6 skipped in 21.09s`. All six skips were
  supplemental unavailable-Gurobi checks; required HiGHS checks passed.
- Spawn-based process parity after deliberate import-boundary module reloads:
  `54 passed in 10.63s`, with no sequential fallback or process warning.
- Offline discrete example: `32` rows, selected `battery-5` + `solar-3`, total
  installed cost `8000.0`, encoded/native risk `0.96875`, discrepancy `0.0`.
- Root import smoke test passed. The legacy-import scan found only the checked
  command text in documentation/reproducibility assertions, and no source or
  test import of `legacy`.
- Ruff was not installed in the locked environment, so the attempted Ruff
  command could not execute; `git diff --check` and Python compilation passed.

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

### Recorded focused validation — 2026-08-19

The required focused suite passed on Linux x86_64 with uv 0.12.5, CPython
3.14.6, SPFlow 1.1.0, Pyomo 6.10.1, and highspy 1.15.1. Each phase was run in
a separate warmed process and measured with `/usr/bin/time -f '%e'`; the
pytest duration and full command wall time are both retained so interpreter
and uv startup overhead remains visible.

| Phase | Focused files | Exact outcome | Pytest duration | Wall duration |
|---|---|---:|---:|---:|
| fit/persistence | `test_spflow_v1_fit.py`, `test_spflow_v1_persistence.py` | 6 passed, 0 skipped | 5.26 s | 8.13 s |
| production query | `test_spflow_v1_query.py` | 6 passed, 0 skipped | 4.10 s | 5.97 s |
| compiler parity | `test_spflow_v1_mio_parity.py` | 2 passed, 0 skipped | 2.76 s | 4.42 s |
| required solve | `test_highs_solver.py`, `test_spflow_v1_highs_pipeline.py` | 3 passed, 0 skipped | 3.45 s | 5.00 s |
| total | 6 focused files | 17 passed, 0 skipped | 15.57 s | 23.52 s |

Pytest 9.0.3's console entrypoint on the active Python 3.14 environment did
not initially expose the repository root to imports from shared
`tests.integration` support modules. T061 adds `.` beside `src` in the
configured pytest `pythonpath`; the table records successful warmed runs after
that collection-path fix and excludes the one-time editable-package rebuild.

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

### Recorded complete regression — 2026-08-19

The required regression commands passed on the same Linux x86_64, uv 0.12.5,
CPython 3.14.6 environment used for the focused evidence. Pytest and wall
durations are retained separately.

| Command group | Exact outcome | Pytest duration | Wall duration |
|---|---:|---:|---:|
| demand plus integration simulator | 91 passed, 0 skipped | 0.52 s | 0.99 s |
| TPM plus planning | 202 passed, 5 skipped | 6.77 s | 9.46 s |
| lazy dependency, import contract, and no-legacy unit checks | 59 passed, 0 skipped | 4.43 s | 4.81 s |
| all-package import smoke | PASS | n/a | 0.08 s |
| total pytest results | 352 passed, 5 skipped | 11.72 s | 15.26 s |

All five skips reported `gurobi solver unavailable` and came from the older
supplemental Gurobi integration files
`test_spn_mio_gurobi.py`, `test_backend_adapter_workflow.py`,
`test_generic_rows_workflow.py`, `test_mio_solver.py`, and
`test_real_spflow_backend.py`. No required SPFlow, Pyomo, or HiGHS check
skipped.

The broad documented legacy-import scan returned two self-referential strings:
the command in `docs/migration/tpm-planning.md` and the reproducibility test
that asserts the command remains documented. A stricter scan anchored to
Python import statements returned 0 matches. The shared fixture-schema helper
also passed 26 focused weather/visualization tests and requires cited legacy
files only when the corresponding reference submodule is populated.

The regression pass additionally repaired in-memory planning-dataset handoff
across deliberate module reloads, updated the replay fixture expectation to
the canonical five-breakpoint policy, and made test-only sidecar mutations
update their manifest SHA-256 digest before reload.

Import-boundary tests now assert laziness, not absence from the installation:

- importing package roots must not add `spflow`, `torch`, `pyomo`, or
  `highspy` modules to `sys.modules`
- invoking the corresponding real workflow must load its required backend
- dependency incompatibility is reported as a failed installation/workflow,
  not a successful skip

## Supplementary Validation

These checks may remain optional and must be reported accurately when skipped:

```bash
uv run pytest tests/integration/planning/test_gurobi_solver.py -ra
cd legacy/old_tpm && cargo test
cd legacy/old_tpm && python scripts/test_battery_consistency.py
cd legacy/old_tpm && pytest src_py/tpm/spn/test_tangent_lower_bound.py
cd legacy/old_tpm && ./scripts/test_data_validation.sh --test-type automatic
```

- Gurobi-backed solve parity when its package, binary, and license are present
- legacy runtime comparisons when the legacy environment is reproducible

They supplement but do not replace the required current-SPFlow and HiGHS
checks.

### Recorded supplemental validation — 2026-08-19

The licensed-solver integration always runs the required HiGHS reference solve
before attempting Gurobi. It records the following fixture-defined comparison
payload through the pytest result:

| Field | Recorded value |
|---|---:|
| comparison status | `availability-skip` |
| HiGHS status | `optimal` |
| HiGHS objective | 13400.0 |
| HiGHS estimated risk | 0.0 |
| Gurobi status | `availability-skip` |
| Gurobi objective | unavailable (`null`) |
| Gurobi estimated risk | unavailable (`null`) |
| measured objective difference | unavailable (`null`) |
| measured risk difference | unavailable (`null`) |
| fixture objective tolerance | `1e-9` |
| fixture risk tolerance | `1e-9` |
| availability reason | `solver 'gurobi' is unavailable` |

The exact pytest outcome was `1 skipped in 0.62s`. Because Gurobi did not
execute, no objective/risk difference is presented as measured and the result
is not mislabeled as a comparison pass. Required HiGHS remained optimal; the
availability skip does not weaken the required results recorded above.

The four optional legacy commands were also attempted. Both legacy submodules
were unpopulated in this checkout, so the results are availability skips:

| Legacy check | Exit | Exact availability result |
|---|---:|---|
| `cargo test` | 101 | no `Cargo.toml` in `legacy/old_tpm` or a parent |
| battery consistency script | 2 | `scripts/test_battery_consistency.py` missing |
| tangent lower-bound pytest | 4 | requested test file missing; 0 tests collected |
| automatic data validation | 127 | `scripts/test_data_validation.sh` missing |

These are missing-reference-checkout results, not behavioral parity failures.
No package dependency, required test, or solver policy was relaxed to make
the optional checks appear successful.

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
