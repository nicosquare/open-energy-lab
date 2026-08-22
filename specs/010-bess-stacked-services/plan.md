# Implementation Plan: French BESS Stacked Services

**Branch**: `010-bess-stacked-services` | **Date**: 2026-08-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-bess-stacked-services/spec.md`

## Summary

Add the first end-to-end French battery simulation that stacks a fixed
day-ahead energy baseline with fixed symmetric Frequency Containment Reserve
(FCR). A new `open_energy_lab.market` package will explicitly retrieve France
day-ahead prices (`A44`) and the R3 combined contracted-reserve response
(`A81`) containing both symmetric-FCR volume and capacity price, validate
source and delivery semantics,
and atomically publish an immutable source-independent JSON artifact without
retaining or exposing the caller's token. A separate activation-artifact
boundary will ingest a source-explicit 10-second trace. The simulator will
align hourly energy, 15-minute checkpoints, four-hour reserve blocks, and
10-second activation; reuse the existing charge-positive battery transition;
report requested versus delivered response and saturation; and settle energy,
capacity, explicit penalties, throughput, and total profit.

The hand-calculable four-hour case is the equation-level oracle. The selected
real demonstration is the Europe/Paris delivery day **2022-08-19**, represented
in UTC as `[2022-08-18T22:00:00Z, 2022-08-19T22:00:00Z)`. It was pre-screened
against the cited robust-storage-bidding data for 24 hourly prices, six FCR
blocks, and 8,640 gap-free RTE frequency observations. Fixture publication is
conditional on a credentialed ENTSO-E completeness check proving compatible
`A44` and combined `A81` coverage for that exact period. Failure of that gate
blocks the fixture; it does not authorize interpolation, synthetic patching,
or an RTE price fallback.

## Technical Context

**Language/Version**: Python 3.11+ under the repository's existing supported
interpreter contract.
**Primary Dependencies**: Existing Open Energy Lab battery and deterministic
controller modules; Python standard-library `datetime`, `zoneinfo`, `json`,
`hashlib`, `urllib`, and XML parsing. No new core or solver dependency is
required. Retrieval code remains isolated from package-root imports and from
all offline simulation paths.
**Storage/Data**: Human-inspectable, versioned JSON market, activation, and
expected-result artifacts; SHA-256 fingerprints; optional separately managed
raw XML or ZIP sidecars only when recorded source terms permit them. Canonical
artifacts never embed raw source responses.
**Testing**: Offline `pytest` unit and integration suites; synthetic ENTSO-E XML
for parser, acknowledgement, retry, token-redaction, revision, DST, and atomic
publication tests; the manual four-hour fixture; validation of the committed
normalized one-day French activation artifact without reopening its external
raw input; zero-FCR and zero-energy compatibility tests; an explicitly selected
credentialed ENTSO-E smoke check and raw-activation regeneration workflow
outside the routine path.
**Target Platform**: CPU-only local research workstation and ordinary CI; no
GPU, SLURM, notebook runtime, commercial solver license, legacy runtime, or
network service for default validation.
**Project Type**: Unified Python research library under
`src/open_energy_lab`; examples are consumers; `legacy/*` and the external
robust-storage-bidding repository remain reference evidence only.
**Performance Goals**: Validate and replay one 24-hour reference day containing
8,640 activation samples in under 10 seconds under the Reference Benchmark
Protocol below; preserve exact energy aggregation to `1e-6 kWh`; avoid
algorithmic work above linear complexity in the number of normalized intervals.
**Reference Benchmark Protocol**: The initial acceptance host is Linux x86_64
on an Intel Xeon Gold 5218R CPU at 2.10 GHz, using one CPython 3.14.6 process
with no deliberate parallelism and at least 4 GiB available memory. Record the
actual CPU model, process/core allocation, available memory, operating system,
Python version, and repository revision with the acceptance result. Use
`time.perf_counter` around committed-artifact load and validation, fixed-schedule
load, replay, settlement, fingerprinting, and expected-result comparison;
exclude interpreter startup, environment setup, and console formatting. Run
one unmeasured warm-up followed by five measured runs, each of which must
complete in under 10 seconds. A result from a different environment is
informative until its relationship to this reference is documented.
**Constraints**: Explicit fetch/refresh only; offline by default; no token in
artifacts, paths, cache identities, output, logs, or exceptions; immutable and
atomic artifact publication; half-open UTC computation intervals with
Europe/Paris delivery metadata; no gap filling; source revision regression
rejection; complete replay product blocks; charge-positive battery power;
deterministic behavior and default absolute tolerance `1e-6`.
**Scale/Scope**: France, one BESS, one selected or caller-bounded historical
period, three required market series produced from two source requests, one separate activation trace, hourly
energy, 15-minute checkpoints, four-hour symmetric FCR, and 10-second replay.
Fixed schedules and deterministic heuristics only; no optimization.

**Reproducibility Defaults**: JSON schema and normalization versions are
explicit; canonical JSON fingerprints use sorted keys and deterministic number
serialization; the simulation-semantics version, artifact fingerprints, grids,
battery, schedules, penalty rule, and tolerance identify a replay. There is no
randomness or implicit current-time input during offline execution. Live
retrieval time is provenance, not simulator state.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: Reusable producer, artifact, activation, replay,
  and settlement behavior belongs under `src/open_energy_lab`; examples and
  tests consume those public contracts.
- **Legacy reference boundary**: No `legacy/*` edits or imports are planned.
  The external robust-storage-bidding code and data are cited by exact commit
  and path but are not runtime dependencies.
- **Validation before migration**: The exact four-hour oracle, source parser
  fixtures, selected real period, compatibility cases, and tolerance are
  defined before implementation.
- **Dependency isolation**: Standard-library networking/XML support is reached
  only by explicit ENTSO-E operations. Package roots and offline replay do not
  load a network client, solver, notebook, or research backend.
- **Reproducibility**: Periods, sign and unit conversions, fingerprints,
  source revisions, activation normalization, expected fixtures, settlement
  equations, tolerances, and the hardware-specific benchmark protocol are
  explicit.

**Post-design status**: PASS

- Market-data production owns credentials, source parsing, temporal validity,
  and artifact publication. The simulator consumes only canonical artifacts
  and owns physical delivery and settlement.
- The activation trace is a separately fingerprinted artifact. A83/A84 data
  cannot satisfy that contract without an explicit resolution-and-semantics
  proof.
- Fixed schedules and heuristics remain inputs; no robust, rolling, intraday,
  learned, or solver-backed bidding behavior enters Feature 010.
- Routine validation is offline and fixture-backed. Live ENTSO-E access is an
  explicit optional compatibility check whose absence cannot weaken the
  committed artifact and replay gates.

## Project Structure

### Documentation (this feature)

```text
specs/010-bess-stacked-services/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
└── contracts/
    ├── activation-trace-contract.md
    ├── entsoe-market-data-contract.md
    ├── market-artifact-contract.md
    ├── settlement-validation-contract.md
    └── stacked-service-replay-contract.md
```

### Current Reference Sources

```text
src/open_energy_lab/
├── control/price_threshold.py       # current-step deterministic arbitrage request
├── simulator/battery.py             # charge-positive power and efficiency-aware SOC
├── simulator/objective.py           # existing arbitrage compatibility surface
└── simulator/scenario.py            # BatteryComponent configuration

notes/
└── 2026-08-20-bess-arbitrage-frequency-regulation-roadmap.md

external: lauinger/robust-storage-bidding @ 7e44738bb30e5c8204efe40103b9be4c2203685c
├── code/01_datastruct.jl
├── code/02_model.jl
├── data_processing/day_ahead_prices.ipynb
├── data_processing/FCR_prices.ipynb
├── data_processing/RTE_frequencies.ipynb
├── data_processing/freq_data/RTE_Frequence_2022_08.txt
├── data/day_ahead_FR.csv
└── data/FCR_RTE.csv
```

### Target Library Structure

```text
src/open_energy_lab/
├── market/
│   ├── __init__.py                  # import-light public surface
│   ├── artifact.py                  # canonical market artifact and atomic IO
│   ├── activation.py                # activation artifact and source-independent import
│   ├── entsoe.py                    # explicit France retrieval and XML normalization
│   └── time.py                      # UTC/local interval and multi-rate validation
├── control/
│   └── stacked_service.py           # deterministic regulation/stacked schedules
└── simulator/
    ├── stacked_service.py           # validation, alignment, and physical replay
    └── fcr_settlement.py            # schedule and capacity settlement/penalties

examples/bess_stacked_services/
├── README.md
├── fetch_french_period.py           # explicit credentialed fetch/refresh consumer
├── import_reference_activation.py   # explicit local-raw fixture regeneration
└── run_offline_replay.py            # default recorded demonstration

tests/
├── fixtures/market/
│   ├── README.md
│   ├── synthetic_entsoe/            # redistributable parser/sidecar fixtures
│   ├── manual_stacked_service_v1.json
│   ├── france_2022-08-19_market_v1.json
│   ├── france_2022-08-19_activation_v1.json
│   └── france_2022-08-19_expected_replay_v1.json
├── unit/market/
├── unit/control/test_stacked_service.py
├── unit/simulator/
│   ├── test_fcr_settlement.py
│   └── test_stacked_service.py
├── integration/market/
│   ├── test_entsoe_fixture_workflow.py
│   ├── test_reference_activation_import.py
│   └── test_entsoe_live.py           # explicitly selected, credentialed only
└── integration/simulator/
    ├── test_stacked_service_manual.py
    ├── test_stacked_service_real_replay.py
    └── test_stacked_service_compatibility.py

docs/migration/
└── bess-stacked-services.md          # exact reference provenance and boundaries

docs/architecture/
└── entsoe-transparency-platform.md   # R3 endpoint, requests, parsing, and reuse policy
```

**Structure Decision**: Add one source-independent `market` package rather
than putting ENTSO-E response types in `simulator`. Keep physical replay and
FCR settlement under `simulator`, and deterministic schedule construction
under `control`. The new package root and public exports remain import-light.
Examples provide explicit acquisition and replay workflows without creating a
new mandatory CLI framework.

## Phase 0: Research

Research outcomes are captured in [research.md](./research.md). They resolve:

- the France ENTSO-E request profile and strict `A44`/combined-`A81` R3 semantics
- one-day local-delivery source windows, bounded retries, sanitized errors,
  raw digests, atomic publication, and revision-aware refresh
- source-independent JSON structure, dual content/integrity fingerprints, and
  DST-aware interval representation
- safe XML/HTTP implementation using the standard library behind an injected
  transport boundary
- separate activation ingestion from RTE 10-second frequency measurements,
  with explicit droop normalization and left-hold interval-average conversion
- reuse of charge-positive `apply_power_request`, exact unit/sign conversion,
  FCR performance attribution, settlement, and throughput semantics
- deterministic regulation-only and headroom-clipped stacked baselines
- selection of 2022-08-19 and the credentialed completeness/licensing gates
  required before committing the real ENTSO-E fixture

No `NEEDS CLARIFICATION` items remain. The selected real period is deliberately
an acceptance gate: if ENTSO-E does not provide complete compatible required
series, implementation must report the failed gate and amend the selected
period through the specification workflow rather than substitute data.

## Phase 1: Design

The [data model](./data-model.md), [quickstart](./quickstart.md), and
[contracts](./contracts/) define:

- a token-free `EntsoeMarketDataRequest`, explicit fetch/refresh results,
  sanitized diagnostics, source query windows, and immutable lineage
- market intervals carrying both UTC boundaries and unambiguous Europe/Paris
  delivery labels, offsets, and fold information
- `MarketDataArtifact` schema v1 with required series, document evidence,
  response digests, license/retention metadata, canonical content fingerprint,
  full artifact integrity fingerprint, and optional verified raw sidecars
- `RegulationActivationTrace` schema v1 with dimensionless interval-average
  values, source sign/normalization provenance, and strict coverage validation
- fixed `EnergyBaselineSchedule` and `FCRCapacitySchedule` inputs in kW,
  explicit MW/MWh conversion at market settlement and volume checks, and exact
  multi-rate index maps
- per-substep requested/delivered combined and FCR power, SOC, energy,
  saturation cause, tracking error, non-delivery, aggregate events, and
  terminal-target reporting
- schedule-based day-ahead revenue, eligible FCR capacity revenue, one explicit
  absolute-undelivered-energy penalty profile, battery-terminal throughput,
  and exact total-profit reconciliation
- manual and real fixtures, zero-FCR parity, regulation-only behavior, DST and
  source-failure matrices, and explicit live-check boundaries

## Phase 2: Implementation Strategy

1. Create the import-light `open_energy_lab.market` surface, canonical interval
   types, artifact validators, deterministic serializers, dual fingerprints,
   sidecar checks, and atomic manifest-last publication.
2. Implement an injected ENTSO-E transport that accepts the token separately
   from the persistable request, builds HTTPS requests only inside the
   retrieval call, sanitizes all failures, enforces source-window response
   bounds, and applies the fixed three-attempt retry policy.
3. Parse and normalize A44 XML and combined A81 XML/ZIP by validated root/schema and
   semantic fields; expand supported curve types; select current document
   revisions; reject acknowledgements, gaps, conflicts, wrong products,
   resolutions, units, areas, and DST coverage; then implement fetch and
   revision-aware refresh.
4. Implement activation import modes for already interval-averaged input and
   explicitly declared left-hold point samples. Regenerate the 2022-08-19 RTE
   activation fixture only through the explicitly selected
   `examples/bess_stacked_services/import_reference_activation.py` consumer,
   which accepts a caller-supplied local raw file, verifies and records its
   digest, and reads validated gap-free observations directly rather than the
   reference notebook's gap-filled aggregate output. Routine tests validate the
   committed normalized artifact and never require that external raw file.
5. Implement fixed schedules, exact grid alignment, market-volume and symmetric
   power-headroom validation, and 10-second replay by reusing the existing
   battery transition. Derive ordered saturation causes without changing the
   library-wide charge-positive convention.
6. Implement settlement, explicit penalty, throughput, and the report-only
   terminal-target result.
7. Publish the manual fixture and expected equations. After the credentialed
   completeness and legal-reuse gates pass, publish the normalized 2022-08-19
   market artifact, activation artifact, and expected replay result. The fixed
   demonstration configuration records the 475/540 EUR/MWh price thresholds,
   5 kW controller request, each unmodified threshold request, each admissible
   FCR-headroom interval, the resulting fixed hourly baseline, and expected
   replay fingerprints/totals. Add the zero-network offline example against
   those recorded inputs.
8. Implement deterministic regulation-only and price-threshold-derived stacked
   schedule builders. Prove zero-FCR parity against the existing arbitrage path
   and prove that the stacked builder reproduces the exact fixed schedule
   recorded by the demonstration without activation lookahead.
9. Add optional live compatibility selection, package/import
   tests, no-legacy-import checks, fixture provenance, and the exact external
   source migration note. Run focused market/control/simulator tests plus the
   existing import-boundary and arbitrage regression suite.

## Complexity Tracking

No constitution violation requires an exception. The new source adapter is
isolated behind explicit operations, while the canonical artifact, activation,
simulation, and settlement paths remain lightweight and offline-capable.
