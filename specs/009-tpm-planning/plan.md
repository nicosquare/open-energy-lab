# Implementation Plan: TPM-Backed Planning And Simulator Dataset Export

**Branch**: `009-tpm-planning` | **Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-tpm-planning/spec.md`

## Summary

Reconcile the technically completed TPM-planning implementation with the
clarified dependency and validation contract. The existing simulator-owned
dataset export, typed features, artifacts, current-SPFlow-to-piecewise-MIO encoding, and
battery-and-solar planning surfaces remain the implementation baseline. The
corrective pass makes current SPFlow, Pyomo, and HiGHS required
installed dependencies; retains lazy imports; makes real SPFlow fit/query and
real Pyomo/HiGHS solve coverage routine; and confines empirical replay to an
explicit fixture/test mode rather than an automatic production fallback.

## Technical Context

**Language/Version**: Python 3.11+ with an initial required CI matrix of 3.11,
3.12, 3.13, and 3.14. If the locked required backend stack does not resolve on
one interpreter, narrow `requires-python` using recorded evidence rather than
skipping that required-backend job.
**Primary Dependencies**: Existing `pandas`, `pvlib`, and `timezonefinder`;
required initial pins `spflow==1.1.0`, `pyomo==6.10.1`, and
`highspy==1.15.1`, including SPFlow's required PyTorch stack; Gurobi remains an
optional additional solver with external installation and licensing. Bounded
ranges may replace initial pins only after the real-backend matrix proves the
endpoints.
**Storage/Data**: Versioned JSON planning datasets and TPM metadata artifacts;
SPFlow payload sidecars referenced by the TPM artifact; explicit artifact
execution mode distinguishing production SPFlow payloads from fixture replay.
**Testing**: `pytest` unit and integration coverage; required offline real
SPFlow fit/reload/query and current-SPFlow-to-piecewise-MIO tests; required real Pyomo solve through
`SolverFactory("highs")` for optimal and infeasible cases; fixture-backed
determinism tests; import-laziness and no-legacy-import checks; optional Gurobi
and legacy-runtime parity checks.
**Target Platform**: CPU-only local workstations and CI across the Python
versions supported jointly by the project and required backend releases;
no GPU, SLURM, notebook runtime, network service, or commercial solver license
in the routine path. Platform support is limited to environments for which the
required `highspy` wheel and compatible SPFlow stack resolve successfully.
**Project Type**: Unified Python research library under
`src/open_energy_lab`; `legacy/*` remains reference material only.
**Performance Goals**: Preserve deterministic export of tens to low hundreds
of scenarios; complete each fixture-sized real SPFlow fit/query and HiGHS solve
within 30 seconds; and keep the combined required focused backend suite within
120 seconds per supported Python job on the reference CPU CI runner.
**Constraints**: Preserve lazy package-root imports despite required
installation; forbid silent empirical or metadata-only production fallback;
port validated legacy `spn.*` behavior to the current SPFlow API; keep `shortfall` simulator-derived;
retain battery-and-solar-only planning; make HiGHS the default solver name
(`highs`), with `appsi_highs` non-canonical and Gurobi supplemental.
**Scale/Scope**: One horizon-flattened dataset and one `shortfall` target per
artifact; direct battery and solar decisions; existing typed feature support;
one canonical current-SPFlow compiler with a general piecewise SPN-to-MILP
encoding and an exact compiled-SPN lookup encoding for finite all-categorical
decisions; corrective changes to dependency metadata, backend modes, tests,
fixtures, and documentation rather than a rewrite of completed export and
planning-domain behavior.

**Reproducibility Defaults**: Canonical seed `13` for Python, NumPy, Torch,
SPFlow, and solver randomness; robustness seeds `37` and `101`; fit/query,
repeated HiGHS solve, objective, and risk tolerances `1e-9`; MIO epsilon and
native-versus-compiled maximum absolute probability error `1e-6`; five
piecewise breakpoints; HiGHS one thread and 30-second per-fixture time limit.
The **current-SPFlow-to-piecewise-MIO compiler** produces the solver-neutral
conditional graph representation. The Pyomo MILP consumes the general
piecewise encoding for continuous or mixed decision domains and exact
compiled-graph probabilities for finite all-categorical decision domains.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: All corrective implementation remains under
  `src/open_energy_lab`, with tests under `tests`; no new reusable behavior is
  placed in `legacy/*`.
- **Legacy reference boundary**: The `legacy/old_tpm` `spn.*` sources remain
  cited behavioral evidence. Runtime legacy imports remain forbidden.
- **Validation before migration**: Existing deterministic fixtures remain, and
  the revised design adds required real-backend gates before claiming the new
  dependency contract is complete.
- **Dependency isolation**: Constitution Principle IV allows the feature spec
  to define the boundary. SPFlow, Pyomo, and HiGHS are installed by default but
  imported only at workflow boundaries; Gurobi remains isolated and optional.
- **Reproducibility**: Initial pins, Python bounds, solver name, seeds,
  tolerances, artifact modes, and required CI cases are explicit.

**Post-design status**: PASS

- Simulator export, TPM artifacts/queries, and planning solve remain separate
  contracts with explicit producer/consumer ownership.
- Required installation does not widen ordinary package imports; import tests
  assert modules are absent from `sys.modules` until workflows invoke them.
- Production query behavior requires a valid SPFlow payload, while deterministic
  empirical replay is explicitly labeled and invoked as fixture/test mode.
- Real HiGHS execution supplies license-free routine solve evidence; Gurobi and
  legacy parity checks remain documented supplements.

## Project Structure

### Documentation (this feature)

```text
specs/009-tpm-planning/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
└── contracts/
    ├── simulator-export-contract.md
    ├── planning-dataset-contract.md
    ├── tpm-artifact-contract.md
    ├── planning-solve-contract.md
    └── validation-contract.md
```

### Current Reference And Implemented Sources

```text
legacy/old_tpm/src_py/tpm/
├── data/
└── spn/
    ├── main.py
    ├── encoding.py
    └── utils_tangent.py

src/open_energy_lab/
├── simulator/planning_export.py
├── tpm/
│   ├── artifact.py
│   ├── fit.py
│   ├── query.py
│   ├── mio.py
│   └── optional_spflow.py
└── planning/
    ├── dataset.py
    ├── problem.py
    ├── piecewise.py
    └── optional_solver.py
```

### Corrective Target Structure

```text
pyproject.toml                         # required backend pins and Python bound
uv.lock                               # fully resolved required stack
src/open_energy_lab/tpm/              # explicit production vs fixture mode
src/open_energy_lab/planning/         # HiGHS default; Gurobi supplemental
tests/unit/                            # lazy-import and failure contracts
tests/integration/tpm/                 # required real SPFlow workflow
tests/integration/planning/            # required real Pyomo/HiGHS workflow
tests/fixtures/{tpm,planning}/         # explicit fixture-mode evidence
specs/009-tpm-planning/                # reconciled design and review guidance
docs/migration/tpm-planning.md         # corrected maturity/dependency claims
```

**Structure Decision**: Preserve the implemented package layout and public
ownership boundaries. Existing filenames containing `optional_` are migration
debt rather than an installation-policy statement; renaming them is optional
and should occur only if public imports and tests can be updated without
unnecessary churn. Behavior and documentation must no longer describe required
backends as optional.

## Phase 0: Research

Research outcomes are captured in [research.md](./research.md). The corrective
research resolves:

- required installation versus lazy import semantics
- the current SPFlow API mapping for validated legacy `spn.*` behavior
- initial compatibility pins, the PyTorch-backed SPFlow migration, and the
  supported Python matrix
- canonical Pyomo `SolverFactory("highs")` use with `highspy`, retaining
  `appsi_highs` only as a non-canonical compatibility option
- explicit production and fixture/test TPM query modes
- required real-backend CI versus optional Gurobi and legacy parity checks

No `NEEDS CLARIFICATION` items remain. Version pins are initial compatibility
claims that implementation validation must prove before they can be widened.

## Phase 1: Design

The reconciled [data-model.md](./data-model.md), [quickstart.md](./quickstart.md),
and [contracts](./contracts/) define:

- backend/API/version metadata and execution mode on TPM artifacts and queries
- production failure when a valid SPFlow payload is absent
- explicit empirical fixture replay that cannot activate automatically
- TPM artifact schema v2 with a project-relative sidecar locator, SHA-256
  integrity digest, atomic sibling-file replacement, backend/compiler metadata,
  and explicit rejection of schema-v1 legacy model payloads
- a first-release compiler subset limited to sum/product graphs, one output
  channel, one repetition, and Normal/Bernoulli/Categorical leaves on separate
  typed scopes; all other modules fail with type-and-scope diagnostics
- omission of solver configuration selecting the required `highs` default
- real Pyomo/HiGHS solve output and reproducibility metadata
- required real SPFlow and HiGHS validation, with fake-backend fixtures retained
  only as supplemental deterministic unit/integration evidence

## Phase 2: Corrective Implementation Strategy

The original domain implementation is complete. The remaining work is a
spec-alignment delta:

1. Declare the researched required backend pins and supported Python bounds in
   `pyproject.toml`, regenerate `uv.lock`, and document supported platforms.
2. Port the legacy fit, marginalization, likelihood, persistence, and
   current-SPFlow-to-piecewise-MIO traversal behavior to SPFlow 1.1 modules and tensors; require
   refitting because pre-1.0 serialized models are incompatible. Bound the
   compiler to sum/product composition, one channel/repetition, and
   Normal/Bernoulli/Categorical leaves for the first release.
3. Replace automatic SPFlow/table/empirical fallback with an explicit
   production-versus-fixture execution mode and validate persisted mode/payload
   compatibility.
4. Make `highs` the default solver, require real Pyomo/HiGHS execution for the
   standard solve path, and reserve skip behavior for explicitly requested
   supplemental solvers such as Gurobi. Cross-solver comparison is
   supplementary and uses a formulation-specific documented tolerance.
5. Convert backend capability checks from optional-install probes into
   compatibility diagnostics for a required installation, while preserving
   lazy imports.
6. Add required supported-Python real-backend integration coverage for SPFlow
   fit/reload/query, current-SPFlow-to-piecewise-MIO assembly, and HiGHS
   optimal/infeasible solves;
   retain fixture and fake-backend tests as supplemental deterministic checks.
7. Reconcile tasks, migration docs, examples, fixtures, and review commands;
   rerun the full 008+009 regression suites before merge.

## Phase 3: Discrete Planning Study Extension

The follow-on 009 extension adds a staged study runner without weakening the
completed backend contracts. Explicit battery and solar option catalogs form a
Cartesian configuration grid. Absolute sample identifiers generate common
weather, demand, and grid-availability realizations for every configuration,
independent of batching or worker count. Existing controllers execute each
trace through the simulator boundary. During grid-unavailable steps, battery
requests are limited to local PV surplus or residual total site load; the
simulation-semantics version participates in study fingerprints so corrected
energy-balance behavior cannot resume older shards silently.

Rows are persisted incrementally through a schema-v2 JSON manifest referencing
checksummed JSONL or Parquet shards. All simulation columns remain available,
while the default SPN fit selects categorical equipment choices, adequacy
summaries, and one active event. Pyomo optimizes categorical one-hot choices
using explicit installed option costs. For this finite categorical domain,
joint-option risk coefficients are evaluated exactly from the compiled
conditional SPN and linked to the feature one-hot variables; empirical event
rows are not optimizer candidates. The selected MIO solution is queried
against native SPFlow and fails validation above the documented tolerance.

## Phase 4: Configurable Abu Dhabi Autonomy Notebook

The notebook extension adds a versioned PVGIS 5.3 configuration and canonical
TMY cache, an already-fetched dataset fit entry point, and local-hour sampling
offsets without changing simulator initial-state semantics. Synthetic and
measured demand adapters produce the existing demand-fit payload contract.

Three independent study manifests provide training, validation, and final-test
evidence. Multiple real SPFlow structure settings must compile before Brier
score selection. Final recommendation is a separate gate over held-out
calibration, native/MIO parity, and a one-sided held-out risk bound. Live PVGIS
and full notebook execution remain manual; unit and reduced real-backend
integration validation remain offline.

The default 4×4 equipment grid produces 16,000 training, 4,000 validation, and
4,000 final-test rows. Known SPFlow degenerate-slice failures use narrow,
deterministic fallbacks and finite leaf stabilization; unrelated backend
failures still propagate. Non-optimal HiGHS terminations never load a solution
or produce a recommendation.

## Phase 5: Completion Reconciliation

The final closure pass keeps notebook execution state out of version control,
adds routine single-version offline CI for the control, simulator, weather,
and demand layers, and retains the four-version matrix for required SPFlow,
Pyomo, and HiGHS compatibility. Design records explicitly distinguish the
canonical compiler from its piecewise and exact-categorical solver encodings.

## Complexity Tracking

No constitution violation requires an exception. Installing heavyweight
workflow dependencies by default is explicitly selected by the feature spec;
lazy workflow-boundary imports satisfy the constitution's import-time
isolation requirement.
