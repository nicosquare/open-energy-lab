# TPM Planning Examples

These checked-in examples exercise the TPM-planning workflow without network
services or notebook state. Generated example outputs stay under `tmp/`, while
the production TPM fixture has an explicit opt-in regeneration command.

## Generic Current-SPFlow Pipeline

`run_generic_rows_pipeline.py` is the canonical T041 fit/query/compiler
example. It:

- builds 36 deterministic mixed typed rows from a documented local formula
- derives the binary `shortfall_event` target at threshold `0.08`
- fits a real SPFlow 1.1 model with seed `13` and CPU float64 Torch settings
- persists and reloads a schema-v2 production manifest plus hashed model
  sidecar
- evaluates a native conditional-probability query
- compiles the supported graph through `spflow-v1-mio-v1` with five canonical
  breakpoints and MIO epsilon `1e-6`
- checks canonical-point native-versus-compiled probability error at `1e-6`

There is no fake backend, automatic empirical fallback, or legacy `spn.*`
runtime path in this example.

Run the example from the repository root:

```bash
uv run python examples/tpm_planning/run_generic_rows_pipeline.py
```

It writes these generated files under
`tmp/open-energy-lab-pipeline-real-backends/`:

- `generic_rows_tpm_artifact.json`
- `generic_rows_tpm_artifact.spn_payload.pkl`
- `generic_rows_pipeline_summary.json`

A successful summary records:

- `used_real_spflow_backend == true`
- `schema_version == "v2"`
- `execution_mode == "production"`
- `backend_generation == "current-spflow"`
- `backend_api_version == "1.1.0"`
- `compiler_version == "spflow-v1-mio-v1"`
- `query_result.source == "spflow_backend"`

## Production Fixture Regeneration

The same script owns the real committed production fixture:

- `tests/fixtures/tpm/tpm_artifact_spflow_v1.json`
- `tests/fixtures/tpm/sidecars/tpm_artifact_spflow_v1.spn_payload.pkl`

Regenerate both files only when the source rows, fit configuration, required
backend, compiler, or artifact contract intentionally changes:

```bash
uv run python examples/tpm_planning/run_generic_rows_pipeline.py --regenerate-fixture
```

Verify the committed sidecar hash, refit in a temporary directory, and compare
stable structure, parameters, likelihoods, query results, compiler output, and
parity evidence within `1e-9`/`1e-6` tolerances:

```bash
uv run python examples/tpm_planning/run_generic_rows_pipeline.py --verify-fixture
```

Semantic fit evidence is deterministic; pickle bytes are not used as the
repeatability oracle. Each regenerated sidecar receives its actual SHA-256 in
the manifest, and later loads verify that digest before deserialization.

## Conditional MIO Composition Walkthrough

[`conditional_mio_embedding_walkthrough.ipynb`](conditional_mio_embedding_walkthrough.ipynb)
is the required, thin Feature 016 demonstration of composable conditional risk
in a caller-owned Pyomo model. It uses only public OEL APIs and reloads the
reviewed current-SPFlow artifact, immutable max/PWL conditional pairs, and
separate parity/fidelity evidence under `tests/fixtures/tpm/`. It does not fit or
compile a model, regenerate evidence, enumerate a decision grid, or perform a
benchmark optimization.

Install the locked development and notebook groups from the OEL repository
root, then select the repository's `.venv/bin/python` as the notebook kernel:

```bash
uv sync --locked --group dev --group notebook
uv run jupyter lab examples/tpm_planning/conditional_mio_embedding_walkthrough.ipynb
```

The walkthrough explains numerator and denominator density roots, the learned
denominator, and caller-versus-OEL ownership. It demonstrates continuous affine,
binary, and ordered categorical mappings; representative objective-free max and
PWL fixed-assignment solves; embedding/solver parity separately from
native/compiler fidelity; and one caller policy with its own objective,
deterministic constraint, threshold, and chance constraint deliberately left
unsolved.

The reviewed inputs are:

- `conditional_mio_embedding_v1.json`, the human-reviewed nonuniform source;
- `tpm_artifact_conditional_mio_v3.json` and its checked sidecar;
- `conditional_pair_max_v2.json` and `conditional_pair_pwl_v2.json` (the retained
  `*_v1.json` files are rejection-only historical fixtures); and
- `conditional_mio_evidence_v1.json`.

Run the same required source and headless execution checks offline on CPU:

```bash
uv run --offline --locked --no-sync pytest \
  tests/unit/tpm/test_conditional_mio_notebook.py \
  tests/integration/tpm/test_conditional_mio_notebook_execution.py
```

The execution check blocks network access and verifies that neither the source
notebook nor reviewed fixtures change. Unlike the optional post-Feature 014
U-Bounds notebook below, this walkthrough is part of Feature 016's required
acceptance evidence.

## Post-Feature Declared Feature Domains Walkthrough

**Status**: Optional post-feature documentation extension retained after Feature 014 was completed,
following a separate reviewed request. It does not amend Feature 014's normative scope or required
acceptance surface; the canonical U-Bounds quickstart remains notebook-independent.

[`declared_feature_domains_walkthrough.ipynb`](declared_feature_domains_walkthrough.ipynb)
is the thin, offline U-Bounds walkthrough. It reloads the committed schema-v3
artifact and real SPFlow sidecar instead of fitting a second model. The notebook
demonstrates:

- the distinction between a mathematical domain, observed training support,
  normalization, and compiler validity;
- stable coordinates for datasets with different observed extrema but the same
  finite declared domain;
- explicitly unbounded support with identity normalization and a declared but
  unobserved category;
- native-query acceptance inside the declaration and rejection outside it;
- an explicitly selected compiler approximation interval, checked physical and
  model-coordinate evaluation, and rejection outside compiled validity; and
- a CPU Pyomo/HiGHS physical-to-model-coordinate decision link.

Install the optional notebook tools and launch the source notebook from the
repository root:

```bash
uv sync --group notebook
uv run jupyter lab examples/tpm_planning/declared_feature_domains_walkthrough.ipynb
```

The notebook requires no network service, commercial solver, or generated
output directory. Its quantitative behavior comes from reviewed library APIs
and the checked-in declared-domain fixture. Fixture regeneration remains owned
by `run_declared_domains_pipeline.py`.

## Simulator-To-Planning Pipeline

`run_real_backend_pipeline.py` covers the broader simulator export and planning
path. It samples the committed weather and demand artifacts, evaluates the
simulator family, exports the planning dataset, fits and reloads a production
SPFlow 1.1 sidecar, runs a native query, compiles the model through
`spflow-v1-mio-v1`, assembles the direct battery-and-solar problem, and solves
through the default `SolverFactory("highs")` path.

Run it from the repository root:

```bash
uv run python examples/tpm_planning/run_real_backend_pipeline.py
```

Generated data stays under `tmp/open-energy-lab-pipeline-real-backends/`. A
successful `pipeline_summary.json` records production SPFlow evidence, compiler
version/five-breakpoint/`1e-6` metadata, `risk_evaluation_mode == "spn_mip"`,
an optimal HiGHS termination, seed `13`, one thread, a 30-second limit, and the
installed Pyomo/highspy versions. The example is fully offline and does not
need Gurobi, notebooks, network services, GPUs, or solver licenses.

## Discrete Solar-Storage Study

`run_discrete_study.py` executes the complete requested sequence: a 2x2
equipment sweep with shared stochastic samples, sharded Parquet persistence,
compact SPFlow fit, direct categorical MIO assembly, HiGHS optimization, and
native-SPFlow verification of the selected option IDs.

```bash
uv run python examples/tpm_planning/run_discrete_study.py
```

The resumable outputs and `summary.json` are written below
`tmp/open-energy-lab-discrete-study/`. Set `worker_count` above one for
deterministic process parallelism; batching and worker count do not change the
semantic dataset.

### Jupyter walkthrough

[`discrete_study_walkthrough.ipynb`](discrete_study_walkthrough.ipynb) presents
the configurable research-scale workflow. Its default studies a 24-hour
islanded period at Abu Dhabi city centre and enforces
`P(unmet_energy_kwh > 0.1) <= 0.05` over 80/120/160/200 kW solar and
100/200/300/400 kWh battery options. Each episode explicitly starts at 100% SOC
with a 10% floor; no simulator burn-in is used.

The notebook requests PVGIS through the versioned 5.3 endpoint and caches both
the canonical 8,760-row TMY table and fitted weather artifact. A missing cache
plus an unavailable or disabled network fails explicitly; committed fixtures
are never substituted. The default synthetic demand is labeled illustrative
small-commercial demand. A `measured_csv` mode requires at least 90 complete
hourly days with separate non-cooling electricity and cooling RT.

Independent manifests use 1,000/250/250 episodes per configuration and seeds
13/37/101 for training, candidate validation, and final testing. Default,
finer, and coarser real SPFlow candidates are compiled and ranked by validation
Brier score, with node count breaking ties. HiGHS always runs. A planning
recommendation is released only if the selected candidate passes held-out
calibration, native/MIO error is at most `1e-6`, and the selected design's
one-sided held-out 95% risk bound is at most 5%; otherwise the result is
explicitly exploratory.

The notebook prints the selected SPN's native probability for every equipment
configuration before solving, so an infeasible 5% chance constraint is visibly
different from a model-fitting failure. Its HiGHS time limit is configurable;
a time limit returns an exploratory diagnostic result without trying to load
an unproven Pyomo solution.

For this finite categorical grid, the MIO risk coefficients are evaluated
exactly from the compiled conditional SPN and linked to joint-option and
per-feature one-hot variables. They are not empirical event-rate candidates;
native SPFlow remains the independent post-solve parity check.

The default controller follows the current total site-load/PV residual, with
equipment charge/discharge power acting as a cap. Islanded simulation permits
charging only from local PV surplus and does not classify curtailed charging as
unmet site load. The notebook includes the simulator-semantics version in each
dataset directory so corrected runs do not reuse older shards.

Matplotlib and Seaborn figures cover representative TMY days and hourly
distributions, fitted/input demand, sample power/controller/SOC/unmet traces,
train/validation/test risk heatmaps, native SPN versus held-out probability
with confidence intervals, the cost-risk frontier, and final recommendation
status.

Notebook visualization dependencies are isolated from the core library. Run
`uv sync --group notebook`, then select the repository's `.venv/bin/python` as
the kernel in VS Code or another Jupyter frontend. The group provides
IPython-kernel support, Matplotlib, and Seaborn; the frontend itself is not
installed by the project. Live PVGIS access and full 24,000-episode notebook
execution are manual acceptance activities, not routine CI. The library
contracts and reduced fixture-backed split/candidate/HiGHS path remain fully
offline-tested.

## Required Environment

The locked project environment provides:

- `spflow==1.1.0`
- `pyomo==6.10.1`
- `highspy==1.15.1`

Imports remain lazy, but these are required installed dependencies. The generic
pipeline uses SPFlow and Torch only; the broader simulator-to-planning example
also exercises the required default HiGHS solve.

Inspect current SPFlow capability metadata with:

```bash
uv run python -c "from open_energy_lab.tpm import detect_spflow_backend_capabilities; import json; print(json.dumps(detect_spflow_backend_capabilities(), indent=2, sort_keys=True))"
```
