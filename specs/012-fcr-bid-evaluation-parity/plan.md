# Implementation Plan: FCR Bid-Evaluation Parity

**Branch**: `012-fcr-bid-evaluation-parity` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-fcr-bid-evaluation-parity/spec.md`

## Summary

Add one bidder-neutral evaluation boundary around Feature 010's existing hourly
`EnergyBaselineSchedule`, four-hour `FCRCapacitySchedule`, charge-positive
battery physics, activation replay, and deterministic fingerprints. A fixed plan
records who produced those schedules and any available solve metadata; the
evaluator binds the plan to one market, battery, activation, time, and settlement
context only after the information cutoff, then returns either a fully settled
daily report or a deterministic validation-failure report with no profit.

The first reference adapter maps the pinned
`baselines/robust_storage_bidding/` Experiment 2 result for 2023-06-18 into that
same environment. The repository retains only a small provenance-rich Golden
Reference Fixture containing aggregate evidence. The 528,805,941-byte
regulation CSV remains external: users download it from the pinned reference
README's release URL, place it under ignored
`artifacts/reference/robust_storage_bidding/`, and select the full parity run
explicitly. No production or routine-test path reads `baselines/`, starts Julia,
loads Gurobi, or performs a download.

The generated reference JSON rounds both decisions and results to three decimals.
Research proved that replaying its published `x0`/`xr` can produce adjacent
three-decimal values for several aggregates. Initial parity therefore reports
field-specific `source_precision_compatible` evidence derived analytically from
decision and output rounding; it does not claim unsupported exact equality.

## Technical Context

**Language/Version**: Python 3.11+ under the existing package contract.

**Primary Dependencies**: Existing `open_energy_lab.market`,
`open_energy_lab.control`, and `open_energy_lab.simulator` types plus the Python
standard library (`csv`, `datetime`, `zoneinfo`, `json`, `hashlib`, `pathlib`,
and `math`). No new unconditional dependency. Julia, JuMP, and Gurobi are
fixture-generation-only tools and never library imports.

**Storage/Data**: Small immutable UTF-8 JSON fixtures with canonical SHA-256
fingerprints; one user-managed external CSV referenced by URL, byte count,
SHA-256, schema, date, and cadence; no pickle, solver artifact, raw Julia object,
or copied baseline file in a package or routine fixture.

**Testing**: Offline `pytest` unit and integration suites; a complete
hand-calculable oracle; synthetic malformed external-CSV cases; Golden Reference
Fixture schema/provenance checks; exact Feature 010 regression/fingerprint
checks; and an explicit `external_reference_data` integration test for the
complete 2023-06-18 case.

**Target Platform**: CPU-only local research workstations and ordinary CI. No
GPU, SLURM, notebook runtime, network service, Julia runtime, or commercial
solver license is required for core use or routine validation.

**Project Type**: Unified Python research library under `src/open_energy_lab`;
examples are explicit consumers, while `baselines/*` and `legacy/*` remain
read-only evidence.

**Performance Goals**: Validation, replay, aggregation, comparison, and
fingerprinting remain linear in interval count. For the required 8,640-interval
ordinary-day evaluation, each stage performs at most two complete iterations
over its primary interval collection and retains no superlinear collection,
verified with instrumented operation counts rather than wall-clock thresholds.
The replay must not regress Feature 010's existing reference benchmark; no
threshold is imposed on the one-time scan and SHA-256 verification of the 529 MB
external source file.

**Constraints**: Offline by default; no activation look-ahead in plan
construction; no implicit data acquisition; no sign, unit, price, timezone, or
index inference; 24/6/96/8,640 exact ordinary-day grids; charge-positive library
power; immutable ordered diagnostics; internal absolute tolerance `1e-6`;
reference precision handled separately; existing Feature 010 public behavior,
fixture bytes, default settlement, trace fingerprints, and result fingerprints
unchanged.

**Scale/Scope**: The common evaluator accepts batteries compatible with the
existing Feature 010 contracts. The initial reference-parity evidence covers one
French BESS, one ordinary 24-hour delivery day, 24 hourly energy decisions, six
four-hour symmetric-FCR commitments, 96 quarter-hour checkpoints, 8,640
ten-second activation samples, one hand oracle, and one pinned aggregate
reference result. No bid optimization, uncertainty-set construction, intraday
recourse, multi-day state carry-over, TPM fitting, or restoration-product change.

**Reproducibility Defaults**: Frozen typed values; explicit schema, plan,
mapping, replay, settlement, and comparison versions; Europe/Paris delivery-day
metadata with UTC-authoritative intervals; compact sorted-key canonical JSON;
finite numbers; complete input fingerprints; stable diagnostic ordering; no
randomness, current-time lookup, environment lookup, network call, or solver in
evaluation.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: The plan, reference mapping, external-input adapter,
  evaluator, settlement profile, and report belong under `src/open_energy_lab`;
  scripts only consume those contracts.
- **Legacy/reference boundary**: `legacy/*` is unused. Exact pinned baseline paths
  are citations and fixture-generation evidence only; no target code is added
  there and no production code imports it.
- **Validation before migration**: The hand oracle, aggregate evidence domain,
  analytic precision policy, external-data integrity gate, failure contract, and
  Feature 010 regression suite are defined before implementation.
- **Dependency isolation**: The feature adds no core dependency. The external CSV
  is caller-supplied, and Julia/JuMP/Gurobi remain optional fixture-refresh tools.
- **Reproducibility**: Commit, command, result digest, data digest, mappings,
  grids, timezone, settlement formulas, comparison bounds, and deterministic
  fingerprints are explicit.

**Post-design status**: PASS

- The fixed plan references existing schedules and keeps producer-visible inputs
  separate from evaluation-only activation lineage, preventing look-ahead.
- The evaluator uses the existing physical replay kernel. The Feature 010 wrapper
  and settlement remain byte-compatible, while the reference profile is an
  explicit additive path.
- A source-independent reference input view is used instead of fabricating A44 or
  A81 provenance that the pinned artifact does not contain.
- Routine evidence remains committed, small, offline, and deterministic; the
  complete external data path is explicit and fail-closed.
- Reference claims are restricted to fields the JSON supports, with separate
  `exact`, `source_precision_compatible`, `mismatch`, and `unavailable` outcomes.
- No constitution violation requires a complexity exception.

## Project Structure

### Documentation (this feature)

```text
specs/012-fcr-bid-evaluation-parity/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
└── contracts/
    ├── fixed-bid-evaluation-contract.md
    ├── reference-fixture-contract.md
    ├── reference-mapping-contract.md
    └── reference-settlement-report-contract.md
```

### Current Extension And Reference Sources

```text
src/open_energy_lab/
├── control/stacked_service.py       # existing schedule constructors
├── market/activation.py             # existing RegulationActivationTrace
├── market/artifact.py               # Feature 010 source-specific market artifact
└── simulator/
    ├── battery.py                    # existing charge-positive transition
    ├── stacked_service.py            # existing schedules, request, replay, fingerprints
    └── fcr_settlement.py             # existing default FCR settlement

baselines/robust_storage_bidding/ @ 7e44738bb30e5c8204efe40103b9be4c2203685c
├── README.md                         # authoritative manual data-download instruction
├── code/01_datastruct.jl             # units, signs, battery and resolution
├── code/02_model.jl                  # decisions, prices, indexing, objective
├── code/03_backtest_save.jl          # realized replay and JSON fields
├── code/04_parse_results.jl          # aggregate reporting context
└── results/02/2023-06-18.json        # generated aggregate evidence
```

### Target Library Structure

```text
src/open_energy_lab/
├── control/
│   └── fcr_bid_plan.py               # plan envelope and x0/xr schedule mapping
├── market/
│   └── reference_fcr.py              # explicit external CSV validation and case inputs
└── simulator/
    ├── stacked_service.py            # shared private replay kernel; public v1 unchanged
    ├── fcr_settlement.py             # additive reference profile; default v1 unchanged
    └── fcr_bid_evaluation.py          # preflight, reports, comparison, fingerprints

examples/fcr_bid_evaluation/
├── README.md
├── run_reference_parity.py           # explicit caller-supplied CSV consumer
└── normalize_reference_result.py     # reviewed fixture-generation helper

tests/
├── fixtures/fcr_bid_evaluation/
│   ├── README.md
│   ├── manual_fcr_bid_evaluation_v1.json
│   └── robust_storage_bidding_2023-06-18_aggregate_v1.json
├── unit/control/test_fcr_bid_plan.py
├── unit/market/test_reference_fcr.py
├── unit/simulator/
│   ├── test_fcr_bid_evaluation.py
│   ├── test_fcr_bid_evaluation_scaling.py
│   └── test_fcr_reference_settlement.py
└── integration/simulator/
    ├── fcr_bid_evaluation_fixture_utils.py
    ├── test_fcr_bid_evaluation_manual.py
    ├── test_fcr_bid_evaluation_compatibility.py
    ├── test_fcr_bid_evaluation_product_separation.py
    ├── test_fcr_bid_evaluation_public_compatibility.py
    ├── test_fcr_reference_fixture.py
    ├── test_fcr_reference_aggregate_parity.py
    └── test_fcr_reference_normalization.py

artifacts/reference/robust_storage_bidding/  # ignored, user-managed
└── regulation_signal.csv

docs/migration/
└── fcr-bid-evaluation-parity.md
```

**Structure Decision**: Plan production and reference decision mapping belong in
`control`; explicit local activation-data validation belongs in `market`; physical
evaluation, profile settlement, daily reporting, and parity comparison belong in
`simulator`. The existing replay implementation is factored only enough to expose
one private physical kernel to both the unchanged Feature 010 wrapper and the new
evaluation wrapper. The reference path uses an explicit source-independent price
and accepted-bid context because the pinned result has no contracted-volume A81
evidence; it must not manufacture an ENTSO-E artifact merely to satisfy the old
source-specific request. This is one physical simulator with two versioned input
adapters, not a second replay implementation.

## Phase 0: Research

Research outcomes are captured in [research.md](./research.md). They resolve:

- exact reference discharge-positive to library charge-positive mapping
- hourly, quarter-hour, four-hour, and ten-second index transformations
- EUR/MWh, EUR/kWh, EUR/MW/4h, EUR/kW/block conversions
- Europe/Paris interpretation of naive reference delivery timestamps
- shared no-curtailment parity domain and the deliberate delivered-energy rule
- bidder-plan versus evaluation-context lineage needed to prevent look-ahead
- source-independent replay adaptation without false A44/A81 evidence
- deterministic valid, invalid, and diagnostic evaluation states
- directional requested/delivered FCR energy and stored-energy reporting
- authoritative regulation download URL, digest, size, schema, and local path
- Golden Reference Fixture domain and field-specific propagation of rounded
  decisions
- exact Feature 010 compatibility and dependency/import boundaries

No `NEEDS CLARIFICATION` items remain.

## Phase 1: Design

The [data model](./data-model.md), [quickstart](./quickstart.md), and
[contracts](./contracts/) define:

- immutable plan, producer, optimization-metadata, information-cutoff, and
  schedule-reference contracts
- evaluation-time binding of market, activation, battery, time, settlement, and
  reference expectations without exposing activation to the bidder
- one shared physical replay path, deterministic preflight, settled success,
  failed report, and explicitly separate diagnostic replay
- versioned reference decision, unit, price, index, and timezone mappings
- opt-in delivered-activation settlement and exact component reconciliation
- daily stored-energy, power, directional FCR energy, tracking, saturation,
  settlement, lineage, and fingerprint reports
- immutable aggregate evidence, external data descriptors, supported parity
  fields, analytic source-precision bounds, and unavailable-evidence outcomes
- routine offline validation, explicit external-reference selection, and
  fixture-refresh boundaries

## Phase 2: Implementation Strategy

1. Add frozen plan/producer/metric/diagnostic entities and builders that retain
   exact schedule objects, validate information cutoffs, and compute a plan
   fingerprint without evaluation-only activation data.
2. Add reference mapping declarations and construct existing schedules from the
   published `x0`/`xr` with explicit sign, unit, index, and interval references.
3. Add the small Golden Reference Fixture loader with strict schema, commit,
   source-path, command, digest, precision, evidence-domain, and redistribution
   validation.
4. Add the explicit external regulation CSV loader. Hash and validate the whole
   caller-supplied file, select exactly 2023-06-18 `xi_EU`, assign declared
   Europe/Paris intervals, and build the existing activation trace without
   downloading or consulting `baselines/`.
5. Refactor Feature 010 replay internals into one private source-independent
   physical kernel. Prove the existing public request, output payload,
   settlement, ordering, fixture bytes, trace fingerprint, and result fingerprint
   remain unchanged before adding the new adapter.
6. Add evaluation preflight and immutable success/failure results. Only a valid
   plan enters normal replay and settlement; diagnostic replay is a separate
   labelled operation and cannot be compared as bidder performance.
7. Add the explicit reference settlement profile using delivered FCR energy,
   component availability states, directional energy, and `1e-6` reconciliation,
   without changing `settle_stacked_services()`.
8. Add daily aggregation, field-level comparison, analytic decision-rounding
   propagation, canonical report serialization, and deterministic input/trace/
   settlement/result fingerprints.
9. Implement the hand oracle, Golden Reference Fixture validation, external
   full-day test,
   malformed-data cases, no-look-ahead checks, zero-FCR/zero-energy cases, and
   the complete Feature 010/import/lazy-dependency regression matrix.
10. Add examples and migration/provenance/environment/parity documentation;
    register and exclude the `external_reference_data` marker from routine CI;
    document an explicit reviewed fixture-refresh path for future unrounded
    decision evidence.

## Complexity Tracking

No constitution violations or exceptions are required.
