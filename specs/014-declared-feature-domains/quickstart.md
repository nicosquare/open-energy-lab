# Quickstart: Validate Declared TPM Feature Domains

Run from the OEL repository root on branch `014-declared-feature-domains`. The routine path is
offline and CPU-only after the locked environment is installed. It requires current SPFlow, Pyomo,
and HiGHS but no Gurobi license, notebook, GPU, network service, or legacy checkout.

## Prepare the locked environment

```bash
uv sync --locked --group dev
uv lock --check
```

## Run the focused semantic suite

The following files are the planned focused acceptance surface and become runnable as their
implementation tasks land:

```bash
uv run --locked --no-sync pytest \
  tests/unit/tpm/test_domains.py \
  tests/unit/tpm/test_features.py \
  tests/unit/tpm/test_data_handler.py \
  tests/unit/tpm/test_fit.py \
  tests/unit/tpm/test_artifact_schema.py \
  tests/unit/tpm/test_query.py \
  tests/unit/tpm/test_spflow_v1_mio.py
```

## Run real backend evidence

```bash
uv run --locked --no-sync pytest \
  tests/integration/tpm/test_declared_domains_fit_query.py \
  tests/integration/tpm/test_declared_domains_mio.py \
  tests/integration/tpm/test_declared_domains_highs_link.py \
  tests/integration/tpm/test_spflow_v1_persistence.py
```

These checks must exercise real current SPFlow and one real Pyomo/HiGHS feasibility solve. A missing
required backend is a validation failure rather than a reason to skip the test.

Verify that the committed v3 manifest and sidecar reproduce the same semantic evidence:

```bash
uv run --locked --no-sync python \
  examples/tpm_planning/run_declared_domains_pipeline.py --verify-fixture
```

## Run TPM and planning regressions

```bash
uv run --locked --no-sync pytest \
  tests/unit/planning tests/unit/tpm \
  tests/integration/planning tests/integration/tpm \
  --ignore=tests/integration/tpm/test_mio_solver.py \
  --ignore=tests/integration/tpm/test_real_spflow_backend.py \
  --ignore=tests/integration/planning/test_gurobi_solver.py \
  --ignore=tests/integration/planning/test_spn_mio_gurobi.py
```

The ignored files are existing optional/commercial or separately invoked checks; the new declared-
domain SPFlow and HiGHS evidence must live in the required paths above and must not depend on these
ignores.

## Check import and legacy boundaries

```bash
uv run --locked --no-sync pytest \
  tests/unit/test_lazy_dependency_boundaries.py \
  tests/unit/test_import_contract.py \
  tests/unit/test_no_legacy_imports.py

uv run --locked --no-sync python -c \
  "import open_energy_lab; import open_energy_lab.tpm; import open_energy_lab.planning"

rg "from legacy|import legacy" \
  src/open_energy_lab/tpm src/open_energy_lab/planning \
  tests/unit/tpm tests/integration/tpm
```

The final `rg` command succeeds by returning no matches.

## Review the persisted evidence

Confirm that the v3 fixture and compiled v2 result visibly keep these apart:

1. mathematical decision domain or distribution support;
2. observed physical training support;
3. normalization meaning and origin; and
4. compiler physical/model-coordinate validity.

Also confirm that existing v2 fixture files are unchanged, load through the labelled compatibility
path, and acquire no mathematical or compiler-domain claim. A new compiled-v2 request against a
loaded v2 fitted artifact must fail even if the caller supplies an interval; the successful
compiled-v2 evidence must originate from a v3 fit with finite declared decision domains. Existing
compiled-v1 payloads remain normalized-only compatibility evidence.

## Final repository checks

```bash
git diff --check
git status --short
```
