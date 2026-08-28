# Implementation Plan: Reference Robust FCR Bidding

**Branch**: `013-reference-robust-fcr-bidding` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-reference-robust-fcr-bidding/spec.md`

## Summary

Implement the pinned reference method's single-day, non-intraday mixed-binary
restriction and relaxation natively under `open_energy_lab.control`. Public,
immutable contracts will validate the fixed 24/96/6 time grid, battery and
price inputs, separately named recovery-window and horizon-wide uncertainty
sets, terminal rule, information cutoff, and deterministic solve policy. A
private lazy Pyomo adapter will solve both linear formulations with required
HiGHS, retain complete incumbents, and pass every extracted witness through an
independent pure-Python equation audit. Only an eligible restriction result may
emit Feature 012's existing `FixedFCRBidPlan`; replay and settlement remain
entirely in the existing Feature 012 evaluator.

The migration is validated by hand-calculable equation oracles, bounded real
HiGHS cases, restriction/relaxation bound ordering, fixed-plan extraction and
Feature 012 replay, and a new digest-pinned optimization fixture derived from
the 2023-06-18 Julia/Gurobi result. The complete historical solve is an
explicit `reference_benchmark`; joint interval-aware certification accounts
for its three-decimal outputs without inferring unrecorded optimality or
constraint evidence. Native reconstruction of that fixture additionally
requires a caller-supplied, fingerprinted `RobustFCRSolvePolicy`; the fixture
does not invent the source's unavailable tolerances. Optional Gurobi may supply
small exact-bilinear evidence, and the external activation CSV remains an
independently selected `external_reference_data` replay input.

## Technical Context

- **Language/Version**: Python 3.11 or newer, matching `pyproject.toml`
- **Primary Dependencies**: Existing required `pyomo==6.10.1` and
`highspy==1.15.1`, imported only inside the private solver boundary; existing
Feature 012 control, market-time, schedule, evaluator, and settlement
contracts; optional pinned compatible Gurobi extra for cross-backend linear and
exact small-case evidence; no new required dependency
- **Storage/Data**: Deeply immutable in-memory Python value objects and one
canonical JSON fixture under `tests/fixtures/fcr_bidding/`; solve outputs are
not persisted by the public v1 API
- **Testing**: `pytest`; pure equation and schema unit tests; real Pyomo/HiGHS
integration tests; `reference_benchmark` for the full normalized 2023-06-18
solve; `external_reference_data` only for the separately selected Feature 012
activation replay
- **Target Platform**: Offline CPU-only Linux/macOS research workstation or CI;
one deterministic solver thread; no GPU, SLURM, Julia runtime, commercial
license, network, or credential requirement for routine use
- **Project Type**: Unified Python research library with source examples and
explicit benchmark commands; `baselines/*` and `legacy/*` are reference inputs
only
- **Performance Goals**: Routine equation and bounded HiGHS cases finish within
the existing required-backend CI budget; model assembly preserves the
reference `O(K^2)` triangular structure and the full 96-step historical solve
is never a routine-CI gate; full benchmark resource limits are explicit and
reported rather than hidden
- **Constraints**: Exact public v1 ordinary-day 24/96/6 grid; no activation or
evaluation leakage into bidding; charge-positive public schedules; absolute
`1e-6` deployability threshold kept separate from solver and source-precision
tolerances; native objective comparisons use configurable, fingerprinted
absolute/relative allowances with public defaults `1e-6 EUR` and `1e-9`;
public decisions use fixed
`solver-output-kw-1e-9-half-even-v1` canonicalization followed by an unrepaired
independent re-audit; deterministic semantic fingerprints exclude runtime,
logs, and paths; no changes under `baselines/*` or `legacy/*`
- **Scale/Scope**: One battery, one 24-hour delivery day, 96 quarter-hour robust
intervals, 24 hourly energy decisions, six four-hour FCR decisions, restriction
and relaxation MILPs, optional exact small cases, and one pinned historical
optimization comparison

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1 design.*

- **Unified library first — PASS**: Reusable bidding contracts and behavior are
  placed in `src/open_energy_lab/control`; tests and examples use the public
  library surface. No new standalone research implementation is introduced.
- **Legacy reference boundary — PASS**: `legacy/*` is untouched. The pinned
  `baselines/robust_storage_bidding` files are cited and inspected only for
  migration research and fixture normalization; production and routine tests
  cannot read or import them.
- **Validation before migration — PASS**: Equation oracles, deterministic
  solver cases, independent residual audits, a digest-pinned normalized
  fixture, bound-order checks, and Feature 012 replay are defined before task
  generation.
- **Dependency isolation — PASS**: Pyomo and HiGHS remain required installed
  backends but are lazy at package and pure-contract import boundaries.
  Gurobi is optional and Julia is never a runtime dependency.
- **Reproducibility — PASS**: Fixed time mappings, units, signs, reference
  revision/digests, solver versions, one thread, random seed, limits,
  tolerances, rounding intervals, fingerprints, and benchmark selection are
  explicit in the design and quickstart.

The post-design review reaches the same result. The Python API contract keeps
all solver objects private, the fixture schema carries source provenance and
rounding limitations, and the quickstart separates routine, benchmark,
optional exact, and external-replay evidence. No constitution exception is
required.

## Project Structure

### Documentation (this feature)

```text
specs/013-reference-robust-fcr-bidding/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── python-api.md
│   └── robust-fcr-reference-fixture-v1.schema.json
└── tasks.md                                      # generated by /speckit-tasks
```

### Current Reference Sources

```text
baselines/robust_storage_bidding/
├── code/
│   ├── 01_datastruct.jl    # source parameter meanings, units, signs
│   ├── 02_model.jl         # restriction, relaxation, exact equations
│   └── 12.jl               # Experiment 2 fixed profile and input assembly
└── results/02/
    └── 2023-06-18.json     # generated, digest-pinned result evidence

src/open_energy_lab/
├── control/fcr_bid_plan.py                 # Feature 012 plan envelope
├── market/reference_fcr.py                 # Feature 012 replay fixture only
└── simulator/fcr_bid_evaluation.py         # common ex-post evaluator
```

### Target Library Structure

```text
src/open_energy_lab/control/
├── __init__.py                         # new exports remain lazily resolved
├── robust_fcr_bidding.py               # immutable public contracts, pure
│                                        # equations/audit, orchestration,
│                                        # result and fixed-plan extraction
├── _robust_fcr_formulation.py          # private Pyomo restriction,
│                                        # relaxation, certification, exact
├── _robust_fcr_solver.py               # private lazy backend/status adapter
└── robust_fcr_reference.py             # explicit fixture loader/comparison

tests/
├── robust_fcr_case_utils.py
├── unit/control/
│   ├── test_robust_fcr_problem.py
│   ├── test_robust_fcr_equations.py
│   ├── test_robust_fcr_solver.py
│   ├── test_robust_fcr_reference.py
│   ├── test_robust_fcr_import_boundary.py
│   ├── test_robust_fcr_source_documentation.py
│   └── test_robust_fcr_backend_compatibility.py
├── integration/control/
│   ├── test_robust_fcr_highs.py
│   ├── test_robust_fcr_reference_normalization.py
│   └── test_robust_fcr_optional_gurobi.py
├── integration/simulator/
│   ├── robust_fcr_replay_utils.py
│   ├── test_robust_fcr_feature_012_replay.py
│   └── test_robust_fcr_external_reference_replay.py
├── parity/
│   └── test_robust_fcr_reference_benchmark.py
└── fixtures/fcr_bidding/
    ├── README.md
    └── robust_storage_bidding_2023-06-18_restriction_v1.json

examples/robust_fcr_bidding/
├── README.md
├── normalize_reference_fixture.py
├── run_small_case.py
└── run_reference_benchmark.py

docs/
├── architecture/README.md
└── migration/
    ├── README.md
    ├── api-maturity.md
    ├── dependency-policy.md
    ├── reference-robust-fcr-bidding.md
    ├── fixture-provenance.md
    ├── parity-validation.md
    └── environment-assumptions.md

README.md
tests/fixtures/README.md
.github/workflows/ci.yml
```

**Structure Decision**: Keep the bidder in `open_energy_lab.control`, which
already owns Feature 012's plan-production and producer-lineage contract.
`open_energy_lab.planning` remains the Feature 009 capacity-design/TPM planning
surface and its solver deliberately discards non-optimal incumbents, so it is
not reused. `simulator` continues to own physical replay and settlement, while
the reference optimizer fixture gets a new strict loader instead of changing
Feature 012's exact aggregate-fixture schema.

## Phase 0: Research

Research decisions and source-level findings are recorded in
[research.md](./research.md). The phase resolves:

- exact non-intraday indexing, uncertainty-budget derivation, objective units,
  terminal/slack behavior, and the shared/restriction/relaxation equations;
- control-package placement and why the Feature 009 solve adapter is not a
  compatible abstraction;
- lazy Pyomo/HiGHS and optional Gurobi execution policy;
- independent witness auditing and deployability status mapping;
- separate optimization-fixture provenance and joint interval-aware Julia
  certification; and
- routine versus full-reference versus external-replay validation gates.

No `NEEDS CLARIFICATION` item remains.

## Phase 1: Design

The implementation-facing design is split across:

- [data-model.md](./data-model.md) for immutable entities, validation,
  relationships, result states, deployability transitions, and fingerprint
  boundaries;
- [contracts/python-api.md](./contracts/python-api.md) for the public library
  surface, solver isolation, plan extraction, comparison semantics, and Feature
  012 replay handoff;
- [contracts/robust-fcr-reference-fixture-v1.schema.json](./contracts/robust-fcr-reference-fixture-v1.schema.json)
  for the normalized optimization evidence envelope; and
- [quickstart.md](./quickstart.md) for exact offline validation, benchmark,
  optional exact, and external-replay commands.

Implementation will preserve the public 24/96/6 restriction while allowing a
private formulation kernel to assemble bounded reduced-horizon equation cases
for solver validation. Public validation always rejects any nonconforming time
grid. The private solver extracts the complete witness, and a separate
pure-Python evaluator recomputes objective terms, integrality, every named
constraint-family residual, and every modeled slack before plan eligibility is
decided.

The solve policy stores configurable objective-comparison tolerances separately
from solver feasibility and MIP-gap options. Pairwise ordering uses
`max(configured_absolute_eur, configured_relative * max(abs(a), abs(b),
1 EUR))`; public defaults are `1e-6 EUR` and `1e-9`, and compared problems must
carry identical values. Public market decisions are decimal round-half-even
quantized to `1e-9 kW`; the canonical audit substitutes only those values into
the unchanged raw auxiliary witness, so canonicalization cannot repair
feasibility. Maximization relative gaps use `max(abs(incumbent),
abs(best_upper_bound), 1 EUR)` as the denominator.

The normalized source fixture never owns a native solve policy.
`build_robust_fcr_reference_problem(fixture, solve_policy=...)` requires one
explicitly and fingerprints it separately from Julia provenance. The
researcher command constructs the documented
`native-reference-benchmark-highs-v1` profile and prints its full mapping and
fingerprint. In one pinned backend environment, objectives, bounds, gaps, and
all other fingerprint-bearing numeric values must repeat exactly; comparison
tolerances do not normalize semantic identity.

## Complexity Tracking

No constitution violations require justification.
