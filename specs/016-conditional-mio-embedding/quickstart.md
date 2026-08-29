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

## Executed acceptance record — 2026-08-29

The Feature 016 implementation was validated from the OEL repository root with the locked offline
environment. No acceptance step required a commercial solver, GPU, network service, fixture rewrite,
or dependency change.

- `uv --cache-dir /tmp/oel-uv-cache lock --check` completed successfully and reported the existing
  149-package lock resolution.
- `uv --cache-dir /tmp/oel-uv-cache run --offline --locked --no-sync python
  examples/tpm_planning/run_conditional_mio_embedding.py --verify-fixtures` verified the semantic
  refit, exact source/artifact/sidecar/pair/evidence digests and identities, create-only reuse,
  corruption/mismatch non-repair, and unchanged committed bytes.
- The focused conditional unit command passed 91 tests.
- The real current-SPFlow and Pyomo/HiGHS command passed 10 tests.
- The blocked-network headless notebook command passed 5 tests and left source/fixture bytes
  unchanged.
- The complete bounded TPM/planning regression command passed 490 tests.
- The package-wide lazy dependency, public import, no-legacy, focused TPM import-boundary, and TPM
  package-surface command passed 113 tests.
- `uv --cache-dir /tmp/oel-uv-cache run --offline --locked --no-sync python -c "import
  open_energy_lab; import open_energy_lab.tpm; import open_energy_lab.planning"` succeeded.
- The documented `rg "from legacy|import legacy" ...` command produced no matches (its expected
  no-match exit status is 1).
- `git diff --check` succeeded. Before this acceptance record was appended, OEL `git status
  --short --branch` contained only the branch header.

The fixture audit recomputed these committed SHA-256 values:

- source: `394f4ab76de48457f36ea03e451fbb608b66b8660ca1374b92f6260396b110bd`;
- artifact manifest: `58e56e7adf850d604e41933479260cce22e90da4f40ac5838fab7578d88dac44`;
- current-SPFlow sidecar: `2157d35ec4d18c230e8c01a074dae271c0cb161af1520582325420361bb7bc6f`;
- max pair: `73a7cc0c4e6736e3f84c699ef9279fc88345b8349e92c3add630394e8811d8f7`;
- PWL pair: `87eeaff775dfc3ec0f276cd5080d90e5d5dcce71e20e5ae1f82b5f03e19c1a3f`;
  and
- evidence bundle: `8a80c32139b25d8c97de2d654a131031c4df59cf91a96fbbfd012c78433f533b`.

`tests/fixtures/tpm/README.md` records the origin, fit/compiler inputs, backend versions, digests,
pair/evidence identities, staging commands, verification command, and create-only refresh policy for
every conditional source/artifact/pair/evidence file. A diff from OEL `main` confirmed no
`pyproject.toml` or `uv.lock` change and no generalized artifact framework. The parent repository
contained only the expected uncommitted `references/oel` gitlink movement; Feature 016 created no
parent file or parent commit. There was no genuine environmental limitation to record.
