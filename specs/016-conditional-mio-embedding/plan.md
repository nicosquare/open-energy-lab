# Implementation Plan: Composable Conditional MIO Embedding

**Branch**: `016-conditional-mio-embedding` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/016-conditional-mio-embedding/spec.md`

## Summary

Extend the existing OEL TPM compiler with an additive composable path that turns one persisted,
declared-domain current-SPFlow artifact into an immutable solver-neutral conditional pair. The pair
contains a numerator for $\log p_{X,Y}(x,y)$ and an explicit denominator for $\log p_X(x)$, both
derived from one verified compiled graph and one fully resolved max or PWL policy. A new direct
evaluator will execute the selected approximation semantics exactly, and a lazy Pyomo adapter will
attach the unchanged pair as one namespaced `Block` to caller-owned continuous, binary, and ordered
categorical decisions without adding an objective, threshold, chance constraint, or solver call.

The implementation will factor the existing graph-conditioning and circuit-encoding mathematics
into TPM-owned helpers while leaving the current fitted-artifact v2/v3 loaders, compiled-v1/v2
payloads, and whole-model planning APIs compatible. Pair and evaluation-evidence records receive
separate schemas and create-only canonical JSON persistence. One small deliberately nonuniform,
mixed-type current-SPFlow fixture will exercise genuine learned Sum nodes under max and PWL, direct
evaluation, caller-owned Pyomo/HiGHS parity, native/compiler fidelity, persistence, and the required
offline notebook.

## Technical Context

**Language/Version**: Python `>=3.11`, validated across the existing Python 3.11-3.14 CI matrix

**Primary Dependencies**: Existing `spflow==1.1.0`, `pyomo==6.10.1`, and `highspy==1.15.1` at lazy
workflow boundaries; existing standard-library dataclasses, hashing, JSON, and filesystem
primitives; existing notebook dependency group; no new dependency

**Storage/Data**: Existing versioned JSON fitted-artifact manifests with integrity-checked pickle
sidecars; new canonical JSON conditional-pair and separate parity/fidelity evidence records;
reviewable JSON source rows and small committed current-SPFlow/pair fixtures

**Testing**: `pytest` unit, contract, and integration tests; one real fit/persist/reload/native
current-SPFlow path; fixed-assignment Pyomo/HiGHS parity; headless `nbclient` notebook execution;
existing TPM/planning and lazy-import regressions

**Target Platform**: Local and CI CPU execution through the locked `uv` environment, offline after
dependency installation; no GPU, distributed runtime, network service, commercial solver, or
license service

**Project Type**: Unified research library with an import-light TPM package, lazy SPFlow/Pyomo
workflow adapters, existing planning consumers, and thin reviewed examples

**Performance Goals**: Compilation, direct evaluation, and attachment remain linear in compiled
nodes plus mapping size; representative evidence uses six fixed-assignment HiGHS solves across max
and PWL; no Cartesian decision enumeration, query grid, adaptive fitting, or paper-scale runtime
target

**Constraints**: Require a persisted production schema-v3 artifact with verified current-SPFlow
sidecar and no legacy-inferred feature semantics; retain one explicit learned denominator; preserve
exact closed U-Bounds membership; use one selected encoding consistently; keep pair records
immutable; validate all mappings before one final model mutation; preserve raw log-risk without
clamping; use absolute `1e-6` parity/residual and positive-log-risk policies; keep existing
whole-model APIs unchanged; do not modify the parent repository

**Scale/Scope**: Exactly one binary event value; any joint mixture of continuous, binary, and
ordered categorical retained decisions; one small mixed fixture with genuine Sum nodes; two
published pair variants (max and PWL); three representative assignments per encoding; focused
conditional-pair and evidence schemas rather than generalized artifact infrastructure

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

- **Unified library first - PASS**: All reusable records, compilation, evaluation, persistence, and
  model-composition behavior belongs under `src/open_energy_lab/tpm`. The example and notebook call
  public OEL behavior and contain no duplicate compiler implementation.
- **Legacy reference boundary - PASS**: No `legacy/*` runtime or source edit is required. Existing
  current OEL compiler, fitted-artifact, planning, and U-Bounds behavior is the compatibility
  baseline; older planning conditioning code is refactored into TPM-owned shared behavior rather
  than copied from legacy material.
- **Validation before migration - PASS**: The design defines reviewable nonuniform physical inputs,
  explicit max/PWL settings, source/pair/evidence identities, real current-SPFlow and HiGHS checks,
  and separate solver-parity versus compiler-fidelity records before implementation changes the
  reusable compiler boundary.
- **Dependency isolation - PASS**: No dependency changes are needed. SPFlow, Torch, Pyomo, HiGHS,
  and notebook tools remain lazy or group-scoped; root imports and record loading remain usable
  without importing those stacks.
- **Reproducibility - PASS**: The source rows, domain declarations, fit seed/configuration, selected
  encoding, approximation domains, compiler constants, backend versions, assignment cases,
  tolerances, solver, fixture commands, pair identities, and evidence identities are all persisted
  or declared in the validation contract.

## Project Structure

### Documentation (this feature)

```text
specs/016-conditional-mio-embedding/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── conditional-pair-contract.md
│   ├── direct-evaluation-contract.md
│   ├── pyomo-attachment-contract.md
│   ├── parity-fidelity-evidence-contract.md
│   └── validation-contract.md
└── tasks.md                                      # generated by /speckit-tasks
```

### Current OEL Sources

```text
src/open_energy_lab/tpm/
├── __init__.py                  # lazy public exports
├── artifact.py                  # fitted-artifact v2/v3 persistence and sidecar integrity
├── domains.py                   # declared domains, normalization, compiled validity
├── features.py                  # resolved feature schema
├── fit.py                       # current-SPFlow fitting and schema-v3 sidecars
├── mio.py                       # compiled-v1/v2 graph compiler and whole-model Pyomo encoding
├── optional_spflow.py           # lazy current-SPFlow sidecar loading
├── piecewise.py                 # max/PWL metadata and interpolation helpers
└── query.py                     # native conditional query and structural marginalization

src/open_energy_lab/planning/
├── piecewise.py                 # current private serialized-graph conditioner
└── problem.py                   # current whole-model planning compilation path

tests/
├── fixtures/tpm/
├── unit/tpm/
└── integration/tpm/

examples/tpm_planning/
├── declared_feature_domains_walkthrough.ipynb
└── run_declared_domains_pipeline.py
```

### Target Library Structure

```text
src/open_energy_lab/tpm/
├── conditional.py              # import-light pair/evidence records, canonical identity, persistence
├── conditional_mio.py          # lazy compile, exact selected-semantics evaluation, attachment
├── mio.py                       # shared conditioned-circuit evaluator/encoder primitives
├── query.py                     # explicit-event raw native numerator/denominator evaluator
├── optional_spflow.py           # verified current-model loading only if a focused helper is needed
└── __init__.py                  # new public symbols remain lazily resolved

src/open_energy_lab/planning/
└── piecewise.py                 # delegates shared conditioning primitive; public behavior unchanged

tests/fixtures/tpm/
├── conditional_mio_embedding_v1.json
├── tpm_artifact_conditional_mio_v3.json
├── conditional_pair_max_v1.json
├── conditional_pair_pwl_v1.json
├── conditional_mio_evidence_v1.json
└── sidecars/tpm_artifact_conditional_mio_v3.spn_payload.pkl

tests/unit/tpm/
├── test_conditional_pair.py
├── test_conditional_mio.py
├── test_conditional_attachment.py
├── test_conditional_evidence.py
└── test_conditional_mio_notebook.py

tests/integration/tpm/
├── conditional_mio_test_support.py
├── test_conditional_mio_current_spflow.py
├── test_conditional_mio_highs.py
└── test_conditional_mio_notebook_execution.py

examples/tpm_planning/
├── run_conditional_mio_embedding.py
└── conditional_mio_embedding_walkthrough.ipynb

docs/migration/
└── conditional-mio-embedding.md
```

**Structure Decision**: Keep immutable, backend-free records and persistence in `tpm.conditional`.
Place operations that need SPFlow, Torch, Pyomo, or compiled-circuit execution in
`tpm.conditional_mio`, with those imports inside workflow calls. Factor only the low-level graph
conditioning and circuit encoding/evaluation primitives needed by both the new path and existing
planning into `tpm.mio`; do not route existing whole-model public APIs through the new composable
contract. This keeps the TPM root lazy, prevents a TPM-to-planning dependency, and avoids enlarging
the already broad fitted-artifact schema.

## Phase 0: Research

Research is complete in [research.md](research.md). It resolves:

- dedicated conditional-pair and evidence schemas instead of fitted-artifact v4 or compiled-v3;
- strict current schema-v3 artifact eligibility and source/model digest provenance;
- compile-once, condition-twice numerator/denominator construction from one verified graph;
- exact simplification of fully marginalized subcircuits before max/PWL approximation;
- explicit event-value indexing instead of the existing hard-coded positive event;
- one resolved leaf and Sum-encoding policy shared by both circuits;
- direct raw-log evaluation that mirrors selected max or PWL Pyomo semantics;
- create-only canonical JSON identity and recursive immutability;
- typed continuous, binary, and categorical caller mapping records;
- structural affine validation that remains sound for fixed Pyomo variables;
- detached-block construction and one final atomic namespace attachment;
- attachment-only residual extraction after caller-owned solver execution;
- separate immutable embedding-parity and native-fidelity evidence;
- a dedicated nonuniform mixed fixture with genuine learned Sum nodes; and
- required single-version notebook CI alongside the existing backend matrix.

All planning questions are resolved; no `NEEDS CLARIFICATION` markers remain.

## Phase 1: Design

Design is complete in the following artifacts:

- [data-model.md](data-model.md) defines pair, compilation request, circuits, mappings,
  attachment, evaluation, evidence, identity, and lifecycle invariants.
- [conditional-pair-contract.md](contracts/conditional-pair-contract.md) defines eligibility,
  compilation, marginalization, event, encoding, identity, persistence, and compatibility.
- [direct-evaluation-contract.md](contracts/direct-evaluation-contract.md) defines assignment modes,
  exact max/PWL execution, raw numerical policy, and native raw-log comparison.
- [pyomo-attachment-contract.md](contracts/pyomo-attachment-contract.md) defines typed caller
  mappings, full preflight, detached construction, namespace ownership, and returned expressions.
- [parity-fidelity-evidence-contract.md](contracts/parity-fidelity-evidence-contract.md) keeps
  embedding/solver parity and native/compiler fidelity separate and immutable.
- [validation-contract.md](contracts/validation-contract.md) defines the reviewed mixed fixture,
  representative assignments, real backend path, regressions, notebook, and CI evidence.
- [quickstart.md](quickstart.md) defines the locked, offline CPU validation sequence.

The post-design constitution re-check passes with no exception or complexity waiver.

## Implementation Sequence

1. Add recursively immutable conditional-pair, compile-request, evaluation, mapping, attachment,
   and evidence value objects with strict schema validation, finite canonical JSON, SHA-256
   identities, and create-only/verified-reuse persistence.
2. Extract one TPM-owned graph conditioner from the planning implementation. Parameterize the
   declared event value, introduce an exact log-one constant node, and simplify fully marginalized
   products and Sums before approximation. Update planning to call the shared primitive without
   changing its public payload or whole-model behavior.
3. Add the pair compiler: require a persisted production v3 artifact, verify its current-SPFlow
   sidecar, reject omitted/legacy-inferred semantics, validate the binary event and ordered retained
   decisions, structurally marginalize every other feature, compile the retained graph once, derive
   both circuits, resolve one explicit max/PWL policy, and compute source-model and pair identities.
4. Add a raw conditioned-circuit evaluator that accepts exactly one complete declared-domain or
   model-coordinate assignment mode and evaluates continuous leaves, discrete leaves, products,
   constants, max Sums, and PWL Sums exactly as the attachment does. Retain raw roots/difference,
   apply the `1e-6` validity classification without clamping, and reject nonfinite values.
5. Add an explicit-event native current-SPFlow evaluator that returns raw numerator and denominator
   logs, validates the pair/source-artifact identity, and leaves compiler discrepancies outside the
   solver-parity gate.
6. Add typed caller mapping preflight and detached Pyomo attachment. Validate complete mappings,
   structural affine expressions, domains, ordered labels, variable domains, ownership, and
   namespace before building one detached block with shared links, numerator/denominator subblocks,
   and a conditional-log-risk expression; attach it once and add no caller policy or solve action.
7. Add post-solve attachment inspection and immutable evidence builders. Compute attachment-local
   constraint-violation magnitudes, direct/Pyomo deltas, solver metadata, and native/compiler
   differences while proving that the published pair bytes never change.
8. Add the reviewed nonuniform mixed input, deterministic real fit, max/PWL pair and evidence
   fixtures, explicit regeneration/verification script, and unit/integration tests. Assert the
   learned and conditioned graphs contain genuine Sum nodes so both encodings are exercised.
9. Add the output-free public-API notebook, source contract, blocked-network headless execution
   test, example README, migration note, package exports, import-boundary checks, and one required
   Python-3.11 notebook CI job. Keep library/solver coverage in the existing Python 3.11-3.14 job.
10. Run the focused fixture, unit, current-SPFlow, HiGHS, notebook, import, TPM/planning regression,
    lock, and repository-integrity commands from [quickstart.md](quickstart.md).

## Complexity Tracking

No constitution violations require justification.
