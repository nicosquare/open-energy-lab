# Library Consolidation

Working tracker for turning Open Energy Lab into a readable library after
specs 001–016. This work runs outside Spec Kit, as small reviewed PRs. Each PR
checks its item off here and links itself.

## Why

Each spec was built as a self-contained slice with its own validation helpers,
error classes, fingerprint and evidence records, parity checks, and a lazy
`__init__` that lists every export three times. None of this was shared across
packages. The domain logic is sound: one battery kernel, compact controllers,
weather and demand, and a substantial TPM compile/attach pipeline. Most of the
bulk comes from this scaffolding.

## Decisions (2026-09-28)

| # | Topic | Decision |
|---|---|---|
| D1 | Julia reference parity | Keep it runnable as thesis evidence, but move it out of the core library into `validation/`. Library users don't see it. |
| D2 | Provenance | Fingerprint and version only what gets persisted (artifacts, study results), using one shared helper. In-memory objects are plain dataclasses. |
| D3 | Compatibility | Break freely (v0.1, no outside users). Rename APIs, change formats, regenerate fixtures, and re-run `artifacts/` and `tmp/` outputs as needed. |
| D4 | Workflow | Consolidate outside Spec Kit in small PRs, then rewrite `AGENTS.md` around the new architecture. Spec Kit stays for new research features. |
| D5 | TPM | Extract it as a standalone distribution in a uv workspace (`packages/tpm/`) with no `open_energy_lab` imports. OEL `planning` and `~/dev/tpm_for_sp` both depend on it. Move it to its own repo once the API settles. The name is still to be decided. |

## Baseline (main @ `3a5307e`)

| Package | Lines | Files | `__all__` exports |
|---|---|---|---|
| control | 20,983 | 16 | 109 |
| tpm | 19,116 | 21 | 140 |
| simulator | 13,289 | 23 | 111 |
| market | 12,981 | 10 | 86 |
| planning | 5,119 | 9 | 33 |
| weather | 2,491 | 7 | 8 |
| demand | 2,050 | 7 | 7 |
| visualization | 1,521 | 5 | 3 |
| core | 328 | 2 | 4 |
| **total src** | **77,900** | | |

Tests: 279 `test_*.py` files, 66,963 lines. About 15% of that is meta or
contract tests (import boundaries, export lists, doc wording).

| Smell (grep over `src/open_energy_lab`) | Count |
|---|---|
| `def _finite(` copies | 17 |
| `def _non_empty*` copies | 21 |
| `_sha256` / `_fingerprint` / `_sha` copies | 26 |
| canonical-JSON serializers | 10 |
| `_freeze` / `_deep_freeze` / `_thaw` copies | 22 |
| `fingerprint` mentions | 1,969 |
| `object.__setattr__` | 817 |
| `Feature 0NN` / `feature-0NN` strings | 93 |
| `legacy` mentions | 151 |
| `parity` mentions | 112 |
| exception classes | 78 |

Import cycles, each hidden by lazy imports:

- control ↔ simulator: plan and schedule types live in `control`.
- simulator ↔ market: `market/reference_fcr.py` golden fixture.
- tpm ↔ planning: `tpm/fit.py` and `tpm/query.py` load planning datasets.

Baseline test run (`uv run pytest tests/unit tests/integration`, 24m53s):
**2209 passed, 6 failed, 2 skipped**. Parity suite not run. All 6 failures are
in TPM and were already failing at `3a5307e`:

- `tests/unit/tpm/test_package_surface.py`, 2 tests. The root exports 16 names
  the test doesn't expect (e.g. `CategoricalMixtureConfig`).
- `tests/integration/tpm/test_backend_adapter_workflow.py`,
  `test_generic_rows_workflow.py`, `test_real_spflow_backend.py`. These fail in
  the v1 serialized `spn_mip` payload path used for direct chance-model solves
  ("requires a valid current-SPFlow model payload", "does not expose a
  serialized SPN MIO payload"). This path is retired in B3.
- `tests/integration/tpm/test_mio_solver.py::test_solve_spn_chance_model_from_artifact_solves_with_gurobi`.
  It loads a `schema_version 'v1'` fixture, which is now rejected as
  `LegacyTPMArtifactVersionError`.

## Track A — energy library

- [ ] **A1 core foundation.** Add `core/validation.py`, `core/serialization.py`
  (canonical JSON, fingerprint, atomic write-once), `core/time.py`, and
  `core/errors.py`. Move `market` onto them first, then the other packages.
  Behavior-preserving.
- [ ] **A2 shared schedule types.** Move `FixedFCRBidPlan`, the energy and
  capacity schedules, and `RestorationCapability` to `core/schedules.py`.
  Breaks control ↔ simulator.
- [ ] **A3 `validation/` package.** Move `control/robust_fcr_reference.py`,
  `control/fcr_rolling_reference.py`, `market/reference_fcr.py`, the parity
  functions in `simulator/fcr_bid_evaluation.py`, and the TPM parity/fidelity
  evidence. Breaks simulator ↔ market.
- [ ] **A4 package surface.** Replace lazy `__init__` files with plain imports
  and 25–40 curated names each. Strip feature numbers from code. Point pytest at
  `tests/` and gate runs with markers instead of CI file lists. Collapse the
  meta-tests into one parametrized module.
- [ ] **A5 provenance trim** (D2). Keep fingerprints on persisted artifacts and
  results only. Add one versioned JSON artifact base shared by weather, demand,
  market, and the planning dataset.
- [ ] **A6 merge variants**, one PR per package:
  - [ ] market: one `MarketArtifact`, one activation sign convention, a shared
    HTTP layer for ENTSO-E and RTE.
  - [ ] simulator: one replay driver for stacked FCR, aFRR, and mFRR; one step
    loop; one FCR settlement path.
  - [ ] control: aFRR and mFRR combined with a product parameter; one rolling
    orchestrator with a cutoff strategy; the rolling problem folded into the
    base robust problem.
- [ ] **A7 docs and rules.** Write concept docs, archive `docs/migration/` and
  `specs/` as history, and rewrite `AGENTS.md`.

## Track B — standalone TPM library

Can run in parallel with Track A once the TPM part of A3 lands.

- [ ] **B1 workspace package.** Create `packages/tpm/` with its own
  `pyproject.toml` and tests. `open_energy_lab.tpm` temporarily re-exports it.
- [ ] **B2 invert planning.** Move planning-dataset loading
  (`fit.py:607,1179`, `query.py:673`) and `build_spn_chance_model` / `solve_*`
  (`mio.py:1712-2340`) into `planning`. Add a test that the TPM package never
  imports `open_energy_lab`.
- [ ] **B3 retire old paths.** Remove the v1 `spn_mip` payload, the
  `planning-v1` mode, legacy feature semantics, `fixture_replay`, and
  `FEATURE_NAME`.
- [ ] **B4 internal consolidation.** One circuit representation, one DAG
  traversal and evaluator. Split `mio.py` into compile, condition, encode, and
  solve. One checkpoint helper. Merge `product_mixture` into `native`.
- [ ] **B5 public API and style.** Lay out `schema/`, `learn/`, `compile/`,
  `embed/` (pyomo, gurobi), and `evaluate/`. Make public the private names
  `tpm_for_sp` relies on (`_stabilize_leaf_parameters`,
  `_materialize_native_categorical_leaves`, `_spflow_operation_children`).
  Type, format, and document the research-kernel modules. Make SPFlow, Pyomo,
  and Gurobi optional extras.
- [ ] **B6 switch `tpm_for_sp`.** Make it depend on the workspace package
  instead of the whole `references/oel` submodule, then drop the re-export.

## Rules for every PR

- Unit, integration, and parity suites stay green against the baseline, or the
  PR states why a test changed.
- Update the metrics above when an item lands.
- Don't add new per-module copies of helpers that exist in `core/` (or in the
  TPM package's internal helpers).
