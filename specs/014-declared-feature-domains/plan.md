# Implementation Plan: Declared TPM Feature Domains

**Branch**: `014-declared-feature-domains` | **Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/014-declared-feature-domains/spec.md`

## Summary

Extend the existing OEL TPM library so callers can declare role-appropriate mathematical feature
domains without conflating them with observed training support or compiler validity. The
implementation will add import-light domain, training-support, and normalization semantics; make
fitting validate physical rows before normalization and SPFlow invocation; write a new TPM artifact
schema v3 while explicitly adapting v2 artifacts; and require physical approximation intervals for
continuous compiler treatments that need them. New compiled-v2 output requires a v3 fitted artifact
with finite declared domains for retained continuous decisions; loaded v2 fitted artifacts must be
refit with declarations rather than having their legacy ranges strengthened. Existing
declaration-free callers retain their
sample-inferred behavior, visibly classified as legacy-inferred rather than mathematical truth.
Generic-row requests and the planning/study fit entry points expose one `feature_domains` concept,
and all mathematical-domain comparisons are exact and closed.

The compiler will record both authoritative physical and derived model-coordinate validity and will
link physical Pyomo decisions to their TPM coordinates. Continuous features removed by existing
marginalization, and exact discrete treatments, will not acquire artificial approximation domains.
All reusable behavior and validation remain inside OEL; no parent-repository or legacy source is
modified.

## Technical Context

**Language/Version**: Python `>=3.11`, validated across the repository's Python 3.11–3.14 matrix

**Primary Dependencies**: Existing `spflow==1.1.0`, `pyomo==6.10.1`, and `highspy==1.15.1` at their lazy workflow boundaries; standard-library dataclasses and JSON-compatible mappings for metadata; no new dependency

**Storage/Data**: Versioned JSON TPM manifests with integrity-checked SPFlow pickle sidecars; JSON-compatible compiled-MIO payloads; frozen v2 fixtures plus one small v3 fixture

**Testing**: `pytest` unit and integration tests; real offline SPFlow fit/query/persistence checks; one small Pyomo/HiGHS feasibility smoke check; package import and legacy-boundary checks

**Target Platform**: Local and CI CPU execution through the locked `uv` environment, offline after dependency installation; no GPU, network service, notebook, or commercial solver

**Project Type**: Unified research library with existing TPM and minimal planning adapters

**Performance Goals**: Domain validation and support derivation remain linear in rows times features; no new paper-scale throughput target or performance framework

**Constraints**: Preserve lazy imports; preserve valid v2 behavior without strengthening its claims; write loaded v2 artifacts as v2 and new fits as v3; require v3 fitted semantics for new compiled-v2 output while retaining normalized-only compiled-v1 evaluation; use exact closed domain membership; do not serialize floating-point infinity; never clamp, widen, or extrapolate; reject invalid data before SPFlow; deterministic fixture generation; no parent gitlink update in this feature

**Scale/Scope**: Continuous finite, fixed, one-sided, unbounded, and unknown domains; declared binary and categorical domains; mixed artifacts load compatibly but receive no new mixed-domain design; focused scalar-sized fixtures and compiler checks

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

- **Unified library first — PASS**: All reusable semantics are implemented in
  `src/open_energy_lab/tpm`. Planning changes are limited to carrying the new compiler contract and
  marginalizing before compilation; no paper-specific workflow or parent-repository change is
  introduced.
- **Legacy reference boundary — PASS**: No `legacy/*` source is used or edited. Existing OEL TPM v2
  artifacts and tests are the compatibility evidence.
- **Validation before migration — PASS**: The design freezes v2 fixtures, adds reviewable declared
  inputs and v3 expectations, and requires real SPFlow and HiGHS checks before the new representation
  replaces current write behavior.
- **Dependency isolation — PASS**: No dependency is added. SPFlow, Pyomo, and HiGHS remain lazy at
  their established workflow boundaries, with import-boundary tests retained.
- **Reproducibility — PASS**: The v3 fixture records physical rows, declarations, fit seed/config,
  backend and schema versions, sidecar digest, expected transforms, validity intervals, and the
  tolerance used by each numerical assertion.

## Project Structure

### Documentation (this feature)

```text
specs/014-declared-feature-domains/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── artifact-versioning-compatibility-contract.md
│   ├── compiler-validity-contract.md
│   ├── feature-domain-contract.md
│   ├── training-normalization-query-contract.md
│   └── validation-contract.md
└── tasks.md                                      # generated by /speckit-tasks
```

### Current OEL Sources

```text
src/open_energy_lab/tpm/
├── artifact.py                 # v2 manifest/sidecar persistence and integrity checks
├── data.py                     # row canonicalization, type/support inference, normalization
├── features.py                 # overloaded bounds, validation, and transforms
├── fit.py                      # public fit requests and SPFlow artifact construction
├── mio.py                      # current normalized [0,1] compiler and Pyomo linking
├── optional_spflow.py          # lazy SPFlow fit/serialize/load adapter
├── piecewise.py                # shared approximation metadata
└── query.py                    # physical assignment validation and native evaluation

src/open_energy_lab/planning/
├── piecewise.py                # compiled-payload consumer
├── problem.py                  # solver-facing TPM assembly
└── workflow.py                 # planning TPM compilation workflow

tests/
├── fixtures/tpm/               # frozen v1/v2 manifests and SPFlow sidecars
├── unit/tpm/
├── integration/tpm/
└── integration/planning/
```

### Target Library Structure

```text
src/open_energy_lab/tpm/
├── domains.py                  # new import-light semantic declarations and transforms
├── features.py                 # resolved per-feature envelope and compatibility projections
├── data.py                     # physical support derivation before declaration-aware normalization
├── fit.py                      # optional declaration propagation and v3 artifact construction
├── artifact.py                 # schema-aware v3 write and explicit v2 read adapter
├── optional_spflow.py          # sidecar schema context without eager backend imports
├── query.py                    # semantic validation and source-aware diagnostics
├── mio.py                      # physical compiler validity and physical/model-coordinate linking
└── piecewise.py                # changed only where shared validity metadata belongs here

src/open_energy_lab/planning/
├── piecewise.py                # consume compiled v2 while retaining legacy v1 evaluation
├── problem.py                  # pass explicit compiler domains; no objective redesign
└── workflow.py                 # marginalize first, then compile the retained graph

tests/fixtures/tpm/
├── declared_feature_domains_v1.json
├── tpm_artifact_domains_v3.json
└── sidecars/tpm_artifact_domains_v3.spn_payload.pkl

tests/unit/tpm/
├── test_domains.py
├── test_features.py
├── test_data_handler.py
├── test_fit.py
├── test_artifact_schema.py
├── test_query.py
└── test_spflow_v1_mio.py

tests/integration/tpm/
├── test_declared_domains_fit_query.py
├── test_declared_domains_mio.py
├── test_declared_domains_highs_link.py
└── test_spflow_v1_persistence.py

examples/tpm_planning/
└── run_declared_domains_pipeline.py  # regenerate/verify only the v3 evidence fixture

docs/migration/
└── declared-feature-domains.md       # public declaration and compatibility guidance
```

**Structure Decision**: Add one focused `tpm.domains` module because domain purpose, training
support, normalization meaning, and compiler validity are shared across fit, query, persistence, and
MIO boundaries. Keep `TPMFeatureSpec` as the stable feature envelope and keep old convenience fields
as compatibility projections, while new code consumes the explicit semantic records. Touch planning
only where it must pass or enforce the new compiler contract.

## Phase 0: Research

Research is complete in [research.md](research.md). It resolves:

- the separation of mathematical domain, training support, normalization meaning, and approximation
  validity;
- declaration-aware feature typing and validation before normalization;
- one `feature_domains` carrier across generic, planning-dataset, and study-manifest fit paths;
- omission versus explicit unknown behavior;
- artifact schema v3 and the non-mutating v2 compatibility adapter;
- schema-aware v2 reserialization and exact mathematical-domain membership;
- rejection of loaded v2 fitted artifacts by new compiled-v2 compilation, with refitting as the
  explicit migration path;
- physical approximation intervals and versioned compiled results;
- marginalization-before-compilation and physical-to-model Pyomo linking;
- treatment of declared but unobserved discrete values without invented evidence; and
- fixture, dependency, and offline validation strategy.

All planning questions are resolved.

## Phase 1: Design

Design is complete in the following artifacts:

- [data-model.md](data-model.md) defines semantic entities, invariants, derived compatibility views,
  artifact states, and fit/compile transitions.
- [feature-domain-contract.md](contracts/feature-domain-contract.md) defines caller declarations,
  domain shapes, role compatibility, and discrete ordering.
- [training-normalization-query-contract.md](contracts/training-normalization-query-contract.md)
  defines the physical-row pipeline, normalization table, query behavior, and diagnostics.
- [artifact-versioning-compatibility-contract.md](contracts/artifact-versioning-compatibility-contract.md)
  defines v3 persistence, v2 adaptation, sidecar integrity, and backward-only compatibility.
- [compiler-validity-contract.md](contracts/compiler-validity-contract.md) defines explicit physical
  approximation intervals, compiled v2 records, evaluation guards, and decision linking.
- [validation-contract.md](contracts/validation-contract.md) defines fixtures and required evidence.
- [quickstart.md](quickstart.md) defines the locked, offline CPU validation sequence.

The post-design constitution re-check passes with no exception or complexity waiver.

## Implementation Sequence

1. Introduce import-light semantic value objects and exhaustive validation/serialization tests.
2. Refactor row preparation into physical support derivation, declaration resolution, validation,
   and normalization; preserve declaration-free legacy inference as an explicit mode.
3. Propagate `TPMArtifactBuildRequest.feature_domains` through generic-row fitting and the optional
   `feature_domains` keyword through planning-dataset and study-manifest fitting; construct resolved
   v3 feature metadata without synthesizing domain or training evidence.
4. Add schema-aware v3 persistence and the v2 compatibility adapter while freezing existing fixture
   bytes and behavior. Loaded v2 artifacts write only v2; new fits write v3; refitting is the only
   route from v2 evidence to v3 semantics.
5. Move native query validation and transforms onto resolved semantics with source-aware failures.
6. Version the compiler payload, require a v3 fitted artifact plus physical approximation intervals
   for retained continuous decision approximations, reject loaded v2 or unknown/legacy-only fitted
   semantics, and persist physical/model-coordinate validity. Keep existing compiled-v1 payloads on
   their separate normalized-only evaluation path.
7. Link physical Pyomo variables to model coordinates and update only the necessary planning
   consumers to marginalize first and forward compiler declarations.
8. Add real SPFlow, persistence, compiled-evaluation, and HiGHS smoke evidence; then run the focused
   and regression suites in the quickstart.

## Complexity Tracking

No constitution violations require justification.
