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
