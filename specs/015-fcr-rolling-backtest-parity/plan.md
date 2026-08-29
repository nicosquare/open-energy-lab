# Implementation Plan: FCR Rolling Backtest Parity

**Branch**: `015-fcr-rolling-backtest-parity` | **Date**: 2026-08-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/015-fcr-rolling-backtest-parity/spec.md`

## Summary

Implement an immutable, deterministic rolling-study layer under
`open_energy_lab.control` for the pinned reference's five non-intraday
executable profiles. Feature 013 remains the owner of robust bid optimization
and its existing public 24/96/6 contract remains unchanged. Additive rolling
optimization contracts cover the source's exact-zero-FCR model and its 08:00
40-hour horizon with accepted predecessor decisions fixed in place. Feature
012 remains the sole owner of battery replay and settlement; new public
segmentation helpers will evaluate accepted plan prefixes and tails without
duplicating physical equations.

Each requested delivery date remains visible in one immutable envelope whose
append-only revisions distinguish original optimization evidence, provisional
replay, successor-finalized replay, failure, blocking, exclusion, and an
unfinalized edge. Midnight and 08:00 state links carry either the explicitly
source-rounded state or native full precision according to the profile.
Resume and aggregation fail closed on semantic identity and never hide missing
days. A digest-pinned normalized fixture captures the bounded 2023-06-17
through 2023-06-20 Julia/Gurobi rerun, including log-derived status and bounds,
but distinguishes source-incumbent compatibility from optimal parity and
records the script/paper/workbook profile crosswalk.

## Technical Context

- **Language/Version**: Python 3.11 or newer, matching `pyproject.toml`
- **Primary Dependencies**: Existing Feature 012 control/market/simulator
  contracts, Feature 013 robust bidder, and required lazy `pyomo==6.10.1` and
  `highspy==1.15.1`; optional pinned `gurobipy==13.0.2` remains research-only;
  no new required dependency
- **Storage/Data**: Frozen Python value objects; one canonical normalized JSON
  fixture; canonical resumable study-result JSON; explicitly supplied CSV
  descriptors and optional activation samples; raw Julia results, logs,
  workbook, and activation CSV remain outside the fixture tree
- **Testing**: `pytest` unit, bounded Pyomo/HiGHS integration, Feature 012
  replay/settlement integration, normalized-fixture contract tests, explicit
  `reference_benchmark`, and optional `external_reference_data` replay
- **Target Platform**: Offline CPU-only Linux/macOS workstation and CI; one
  deterministic HiGHS thread for routine solver cases; no Julia, Gurobi
  license, network, credentials, GPU, or SLURM required
- **Project Type**: Unified Python research library with source examples and
  explicit fixture-normalization/benchmark commands; `baselines/*` and
  `legacy/*` are reference inputs only
- **Performance Goals**: Routine validation uses operation/cardinality bounds,
  bounded solver cases, and a short authored multi-day study within the
  existing 120-second focused-test command limits and 15-minute CI job limits;
  the full four-date native reference solve and 1,453-date study are never
  routine gates; the rolling 08:00 formulation preserves the reference's
  `O(K^2)` robust structure for 160 quarter-hour indices
- **Constraints**: No activation visible to bid selection; charge-positive
  public schedules; explicit EUR/kWh-to-EUR/MWh conversion at the evaluator
  boundary; separate ex-ante objective, same-solve upper bound, realized
  settlement, and realized profit; immutable revision history; semantic
  fingerprints exclude volatile runtime duration, execution-host/process
  metadata, and caller-local paths while retaining solver/version, content,
  cutoff, interval, and provenance evidence; explicit half-open cutoff
  semantics; production and routine-validation code never read baselines,
  invoke Julia, inspect credentials, or introduce another replay/settlement
  model; only the explicit maintainer normalizer may read caller-listed,
  digest-pinned baseline artifacts
- **Scale/Scope**: Five separate one-profile manifests; ordinary 24-hour
  delivery dates; 24/96/6 daily decisions for ordinary profiles; a 40-hour
  40/160/10 optimization frame with 16 hourly and four FCR predecessor
  fixings for 08:00; bounded source evidence for five profiles and four dates

## Constitution Check

*GATE: Passed before Phase 0 and re-checked after Phase 1 design.*

- **Unified library first — PASS**: Rolling bidding and orchestration belong
  under `src/open_energy_lab/control`; partial/full replay and settlement stay
  under the existing simulator owner. Examples call public library APIs.
- **Legacy reference boundary — PASS**: The pinned
  `baselines/robust_storage_bidding` sources and generated reruns are read only
  by an explicit maintainer normalizer. Production and routine tests consume
  the committed normalized fixture and never import or open the baseline.
- **Validation before migration — PASS**: The plan defines hand-calculable
  orchestration oracles, bounded solver cases, causal replay tests, immutable
  lifecycle/resume checks, and digest-pinned comparison evidence before tasks
  are generated.
- **Dependency isolation — PASS**: Existing Pyomo/HiGHS imports remain lazy and
  solver work stays behind private adapters. Gurobi and Julia are optional
  source/research evidence and cannot affect routine imports or validation.
- **Reproducibility — PASS**: Ordered dates, data fingerprints, cutoffs,
  acceptance assumptions, solver/numeric policy, rounding mode, state links,
  source digests, comparison rules, and semantic fingerprint exclusions are
  explicit.

The post-design review reaches the same result. The public contracts preserve
Feature 013 compatibility, the simulator contract keeps replay physics in one
owner, the schemas retain every failure and edge day, and the quickstart
separates routine, reference, external-data, and full-history workflows. No
constitution exception is required.

## Project Structure

### Documentation (this feature)

```text
specs/015-fcr-rolling-backtest-parity/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── python-api.md
│   ├── fcr-rolling-reference-fixture-v1.schema.json
│   └── fcr-rolling-study-result-v1.schema.json
└── tasks.md                                      # generated by /speckit-tasks
```

### Current Reference and Reused Sources

```text
baselines/robust_storage_bidding/
├── code/
│   ├── 01_datastruct.jl
│   ├── 02_model.jl
│   ├── 03_backtest_save.jl
│   ├── 04_parse_results.jl
│   ├── 05_dates.txt
│   └── 11.jl ... 15.jl
└── results/
    ├── 01/ ... 05/                         # generated bounded JSON evidence
    └── result_overview.xlsx                # aggregate/profile audit only

src/open_energy_lab/
├── control/
│   ├── robust_fcr_bidding.py               # Feature 013 public daily contract
│   ├── _robust_fcr_formulation.py          # Feature 013 equation owner
│   ├── _robust_fcr_solver.py               # Feature 013 backend owner
│   └── fcr_bid_plan.py                     # Feature 012 accepted plan contract
├── market/activation.py                    # realized activation contract
└── simulator/
    ├── fcr_bid_evaluation.py               # sole FCR physical evaluator
    └── fcr_settlement.py                   # sole FCR settlement owner
```

### Target Library Structure

```text
src/open_energy_lab/
├── control/
│   ├── __init__.py                         # deliberate lazy public exports
│   ├── robust_fcr_bidding.py               # compatible private-helper refactor only
│   ├── _robust_fcr_formulation.py          # shared normalized equation kernel
│   ├── _robust_fcr_solver.py               # shared lazy solver/status adapter
│   ├── robust_fcr_rolling.py               # additive rolling/fixed-decision solve API
│   ├── fcr_rolling_backtest.py             # immutable public study contracts/API
│   ├── _fcr_rolling_orchestrator.py        # deterministic private state machine
│   └── fcr_rolling_reference.py            # normalized fixture/comparison
├── market/
│   └── activation.py                       # public half-open trace slicing
└── simulator/
    └── fcr_rolling_evaluation.py           # segmented Feature 012 composition

tests/
├── fcr_rolling_case_utils.py
├── unit/
│   ├── control/
│   │   ├── test_fcr_rolling_manifest.py
│   │   ├── test_fcr_rolling_orchestration.py
│   │   ├── test_fcr_rolling_results.py
│   │   ├── test_fcr_rolling_reference.py
│   │   ├── test_fcr_rolling_import_boundary.py
│   │   └── test_fcr_rolling_source_documentation.py
│   ├── market/
│   │   └── test_activation.py
│   ├── simulator/
│   │   └── test_fcr_rolling_evaluation.py
│   └── test_ci_workflow.py
├── integration/control/
│   ├── test_fcr_rolling_highs.py
│   ├── test_fcr_rolling_resume.py
│   └── test_fcr_rolling_reference_normalization.py
├── integration/simulator/
│   ├── test_fcr_rolling_feature_012_replay.py
│   └── test_fcr_rolling_external_reference_replay.py
├── parity/
│   └── test_fcr_rolling_reference_benchmark.py
└── fixtures/fcr_rolling_backtest/
    ├── README.md
    └── robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json

examples/fcr_rolling_backtest/
├── README.md
├── run_authored_study.py
├── normalize_reference_fixture.py
├── reference_inputs_v1.json
└── run_reference_benchmark.py

docs/
├── architecture/README.md
└── migration/
    ├── README.md
    ├── api-maturity.md
    ├── dependency-policy.md
    ├── fcr-rolling-backtest-parity.md
    ├── fixture-provenance.md
    ├── parity-validation.md
    └── environment-assumptions.md

README.md
tests/fixtures/README.md
.github/workflows/ci.yml
```

**Structure Decision**: `control` owns market decisions, rolling state, and
orchestration; `simulator` owns physical replay and settlement; `market` owns
activation data slicing. Feature 013's public ordinary-day model is not
generalized. A new rolling solve envelope uses the same private equation and
solver machinery for the 40-hour fixed-overlap case and the exact-zero-FCR
case. A separate Feature 015 fixture/comparator avoids changing Feature 013's
governed single-day fixture or comparison vocabulary.

## Phase 0: Research

Research decisions and source findings are recorded in
[research.md](./research.md). This phase resolves:

- the script, results-directory, workbook, and paper experiment crosswalk;
- reset, midnight carry-over, 08:00 bootstrap/overlap/finalization, and
  list-predecessor date semantics;
- the 40-hour source indexing, fixed accepted decisions, fixed-tail objective
  constant, and exact-zero-FCR formulation boundary;
- immutable revision, continuity, resume, aggregation, and acceptance policy;
- Feature 012-only cutoff replay and state handoff;
- solver/incumbent/deployability and source-precision comparison rules; and
- normalized fixture provenance, log redaction, benchmark isolation, and
  deterministic validation.

No `NEEDS CLARIFICATION` item remains.

## Phase 1: Design

The implementation-facing design is split across:

- [data-model.md](./data-model.md) for immutable entities, relationships,
  validation, state transitions, continuity segments, aggregation, resume, and
  fingerprint boundaries;
- [contracts/python-api.md](./contracts/python-api.md) for public control,
  rolling optimization, simulator, and reference-comparison behavior;
- [contracts/fcr-rolling-reference-fixture-v1.schema.json](./contracts/fcr-rolling-reference-fixture-v1.schema.json)
  for digest-pinned normalized Julia/Gurobi evidence;
- [contracts/fcr-rolling-study-result-v1.schema.json](./contracts/fcr-rolling-study-result-v1.schema.json)
  for resumable deterministic study evidence; and
- [quickstart.md](./quickstart.md) for routine, fixture-maintenance, reference,
  external-activation, and full-history commands.

Implementation proceeds in six dependency-ordered increments:

1. Protect Feature 012/013 behavior, refactor Feature 013's private formulation
   and solver helpers, and add public activation slicing plus simulator-owned
   segmented evaluation.
2. Add frozen manifest/profile/date/input/state/result and rolling-solve
   contracts, exact semantic fingerprint rules, exact-zero-FCR and 40-hour
   fixed-overlap formulations, and profile-level orchestration.
3. Complete causal 08:00 behavior, midnight carry-over, immutable lifecycle
   revisions, failure propagation, resume validation, and partial/complete
   aggregates.
4. Normalize the bounded source evidence through an explicit digest manifest
   and implement joint interval-aware, status-aware comparison without reading
   raw source files at runtime.
5. Complete multi-day Feature 012 replay and settlement integration plus the
   optional explicit-path external activation replay.
6. Add authored examples, routine/offline CI gates, the explicit reference
   benchmark, optional Gurobi and full-history research operation, migration
   documentation, and final compatibility checks.

The 08:00 implementation preserves one original accepted full-day plan. The
successor fixes that plan's unchanged 08:00–24:00 tail; it does not revise the
predecessor decision. Provisional and finalized *evaluation* revisions remain
separate. Because source JSON stores only three-decimal decisions while its
successor fixed live full-precision values, exact chain reconstruction from
JSON is unavailable. Source compatibility therefore requires one joint latent
interval certificate linking predecessor and successor overlap, or reports
the field unavailable; it never substitutes displayed values as exact
fixings.

## Complexity Tracking

No constitution violations require justification.
