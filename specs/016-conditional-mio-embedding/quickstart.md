# Quickstart: Validate Composable Conditional MIO Embedding

Run from the OEL repository root on branch `016-conditional-mio-embedding`. The validation path is
CPU-only and offline after locked dependencies are installed. It requires current SPFlow, Pyomo,
HiGHS, and the notebook group, but no commercial solver, GPU, or network service.

## Prepare the locked environment

```bash
uv sync --locked --group dev --group notebook
uv lock --check
```

All later commands avoid synchronization and dependency resolution:

```bash
uv run --offline --locked --no-sync python -c \
  "import spflow; import pyomo.environ; import highspy; import nbclient"
```

## Verify committed fixtures and evidence

```bash
uv run --offline --locked --no-sync python \
  examples/tpm_planning/run_conditional_mio_embedding.py --verify-fixtures
```

This command must verify, not rewrite, the source rows, fitted schema-v3 artifact and current-SPFlow
sidecar, max/PWL pairs, representative direct/native/HiGHS evaluations, and separate parity/fidelity
evidence.

## Run focused unit tests

```bash
uv run --offline --locked --no-sync pytest \
  tests/unit/tpm/test_conditional_pair.py \
  tests/unit/tpm/test_conditional_mio.py \
  tests/unit/tpm/test_conditional_attachment.py \
  tests/unit/tpm/test_conditional_evidence.py
```

## Run real current-SPFlow and HiGHS evidence

```bash
uv run --offline --locked --no-sync pytest \
  tests/integration/tpm/test_conditional_mio_current_spflow.py \
  tests/integration/tpm/test_conditional_mio_highs.py
```

These are required tests. Missing current SPFlow, Pyomo, or HiGHS is a failure rather than a reason
to skip. The HiGHS checks compare direct and Pyomo evaluation of the same approximate circuit; the
current-SPFlow checks retain compiler-fidelity differences separately.

## Execute the notebook contract

```bash
uv run --offline --locked --no-sync pytest \
  tests/unit/tpm/test_conditional_mio_notebook.py \
  tests/integration/tpm/test_conditional_mio_notebook_execution.py
```

The source notebook remains output-free. The headless copy executes with network access blocked and
must not alter committed notebook bytes or fixture evidence.

## Run TPM and planning regressions

```bash
uv run --offline --locked --no-sync pytest \
  tests/unit/tpm tests/unit/planning \
  tests/integration/tpm tests/integration/planning \
  --ignore=tests/integration/tpm/test_backend_adapter_workflow.py \
  --ignore=tests/integration/tpm/test_generic_rows_workflow.py \
  --ignore=tests/integration/tpm/test_mio_solver.py \
  --ignore=tests/integration/tpm/test_real_spflow_backend.py \
  --ignore=tests/integration/planning/test_fixture_schema.py \
  --ignore=tests/integration/planning/test_gurobi_solver.py \
  --ignore=tests/integration/planning/test_reproducibility_contract.py \
  --ignore=tests/integration/planning/test_spn_mio_gurobi.py \
  --ignore=tests/integration/planning/test_tpm_fit_workflow.py \
  --ignore=tests/integration/planning/test_tpm_fixture_schema.py
```

The new real current-SPFlow, pair, and HiGHS tests are not in the ignore list. Existing optional,
legacy/fake-backend, and commercial paths remain outside the routine acceptance command.

## Check import and legacy boundaries

```bash
uv run --offline --locked --no-sync pytest \
  tests/unit/test_lazy_dependency_boundaries.py \
  tests/unit/test_import_contract.py \
  tests/unit/test_no_legacy_imports.py \
  tests/unit/tpm/test_import_boundary.py \
  tests/unit/tpm/test_no_legacy_imports.py \
  tests/unit/tpm/test_package_surface.py

uv run --offline --locked --no-sync python -c \
  "import open_energy_lab; import open_energy_lab.tpm; import open_energy_lab.planning"

rg "from legacy|import legacy" \
  src/open_energy_lab/tpm src/open_energy_lab/planning \
  tests/unit/tpm tests/integration/tpm
```

The final `rg` succeeds by finding no matches.

## Review the evidence boundary

Confirm from the committed records and notebook that:

1. numerator and denominator identify one fitted source and one encoding policy;
2. the denominator was compiled explicitly despite nonuniform decision evidence;
3. direct and Pyomo values are compared under identical max or PWL semantics;
4. native/compiler differences are reported separately and have no adequacy threshold;
5. continuous validity, binary ordering, and categorical ordering survive reload;
6. caller objectives, deterministic constraints, $\alpha$, and chance constraints remain outside
   OEL's attachment block; and
7. pair and evidence files are immutable under verified reuse.

## Final repository checks

```bash
git diff --check
git status --short
```
