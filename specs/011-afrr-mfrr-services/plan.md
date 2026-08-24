# Implementation Plan: BESS aFRR and mFRR Services

**Branch**: `011-afrr-mfrr-services` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-afrr-mfrr-services/spec.md`

## Summary

Add distinct French automatic Frequency Restoration Reserve (aFRR) and manual
Frequency Restoration Reserve (mFRR) vertical slices without widening or
reinterpreting Feature 010's FCR contracts. New restoration-specific market
types will acquire RTE Balancing Energy catalog version 5.2 JSON through an
explicit OAuth operation, normalize one source acquisition into an immutable
offline artifact, and compose independently acquired RTE or ENTSO-E series only
through a fingerprint-referencing study bundle. Explicit derived-scenario
mappings may convert RTE area requests into simulated BESS inputs with a fixed
allocation fraction; public aggregates are never represented as observed
asset dispatch.

Control code will build fixed directional commitments and no-lookahead energy
baselines. Separate aFRR trajectory and mFRR event contracts feed additive
restoration replay and settlement modules that reuse the existing
charge-positive battery transition while adding directional headroom, ramp,
activation-time, event-duration, performance, activated-energy, penalty, and
throughput accounting. Routine validation and the notebook remain fully
offline. Live RTE and ENTSO-E sections are explicit, guarded consumers.

The planning feasibility check on 2026-08-23 verified both production RTE
resources without persisting raw responses. The aFRR period
`[2026-08-20T00:00:00Z, 2026-08-20T01:00:00Z)` returned exactly four PT15M
records. The mFRR reference period
`[2026-08-15T10:15:00Z, 2026-08-15T10:30:00Z)` returned separate upward and
downward rows; the downward row contains scheduled requested volume 357 MW,
satisfied need 300 MW, and clearing price 64.83 EUR/MWh. These are area-level
observations. Implementation must reacquire them through the governed staging
workflow and create canonical artifact fingerprints before they become
fixtures.

## Technical Context

**Language/Version**: Python 3.11+ under the existing package contract.

**Primary Dependencies**: Existing Open Energy Lab market, control, and
simulator modules; Python standard-library `datetime`, `zoneinfo`, `json`,
`hashlib`, `urllib`, `base64`, `pathlib`, `tempfile`, and `os`. No new
unconditional dependency. Existing `pandas` may be used by notebook consumers;
`ipykernel`, `matplotlib`, `seaborn`, `nbclient`, and `jupyterlab` remain in the
optional notebook group. `nbclient` owns automated offline cell execution;
`jupyterlab` supports the documented interactive command. Neither is imported
by core library paths or required by routine validation.

**Storage/Data**: Immutable UTF-8 JSON manifests and artifacts with canonical
JSON SHA-256 fingerprints. Raw RTE or ENTSO-E response bytes are digest-only by
default and are never embedded. A raw sidecar is allowed only when terms and
the restricted-data policy are explicitly verified. Real normalized fixtures
remain private/restricted and are excluded from built distributions and public
artifact paths.

**Testing**: Offline pytest unit and integration suites; authored synthetic RTE
JSON parser fixtures; hand-calculable aFRR and mFRR replay/settlement oracles;
restricted normalized real-data demonstrations; source-only notebook checks
plus an opt-in notebook-group execution check; an explicit `live_rte` marker;
and the unchanged Feature 010 regression and reference-result suite.

**Target Platform**: CPU-only local research workstations and ordinary CI. No
GPU, SLURM, commercial solver, experiment tracker, notebook runtime, live
network, or legacy runtime is required for core imports or routine validation.

**Project Type**: Unified Python research library under `src/open_energy_lab`;
examples and notebooks are consumers, and `legacy/*` is out of scope.

**Performance Goals**: Validation, replay, event expansion, aggregation, and
fingerprinting are linear in the number of source observations plus replay
samples or event segments, with linear result memory. No new wall-clock
acceptance threshold is introduced; the existing Feature 010 reference
benchmark remains unchanged.

**Constraints**: Offline by default; explicit fetch/refresh/offline lifecycle;
three total attempts only for transient acquisition failures; credentials and
tokens remain operation-local; one source acquisition per artifact; no source
fallback or observation merging; UTC-authoritative half-open intervals with
Europe/Paris identity; no interpolation, upsampling, filling, normalization,
or hidden clipping; one restoration product per replay; charge-positive
battery power; immutable results; default absolute tolerance `1e-6`.

**Scale/Scope**: France, one BESS, caller-bounded periods of at most the
source-supported acquisition window, PT15M RTE observations, one four-sample
aFRR real demonstration, one real mFRR scheduled-activation quarter, synthetic
high-resolution ramp/timing cases, and day-ahead plus exactly one of aFRR or
mFRR. No bidding optimization or continuous ingestion.

**Reproducibility Defaults**: Frozen typed inputs; explicit schema,
normalization, product-semantics, settlement, and simulator versions; finite
canonical numbers; sorted-key compact JSON for hashes; immutable lineage;
source and derived fingerprints; complete time grids; explicit battery,
capability, schedule, price, penalty, degradation, and tolerance inputs. Replay
contains no randomness, current-time lookup, credential lookup, or networking.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

**Pre-design status**: PASS

- **Unified library first**: All reusable restoration acquisition, artifacts,
  commitments, replay, and settlement behavior is additive under
  `src/open_energy_lab`; scripts and notebooks only consume those contracts.
- **Legacy reference boundary**: No `legacy/*` file, import, or runtime is used.
  Feature 010 is implementation evidence, not a source to copy wholesale.
- **Validation before migration**: Synthetic parser payloads, equation-level
  replay cases, exact real periods, source field meanings, and compatibility
  gates are defined before implementation.
- **Dependency isolation**: OAuth, HTTP, and notebook behavior remain behind
  explicit operations or optional groups. Package roots and offline loaders do
  not initialize them.
- **Reproducibility**: Source requests, units, time conversion, mapping formula,
  event shape, physical inputs, settlement availability, tolerances, and
  fingerprints are explicit.

**Post-design status**: PASS

- New schemas and modules preserve Feature 010's closed artifact, FCR trace,
  schedule, replay, settlement, public symbol, and fixture-byte contracts.
- RTE market observations, derived asset inputs, control schedules, physical
  replay, and settlement retain separate ownership and fingerprints.
- The study bundle references immutable artifacts; it cannot copy observations
  or weaken any source's retention or redistribution policy.
- The aFRR trajectory and mFRR event sequence are different exact types and
  cannot be substituted for FCR or each other.
- The recorded demonstrations are private, offline, deterministic, explicitly
  derived, and backed by source semantics; synthetic cases cover behavior that
  PT15M public data cannot prove.
- No constitution violation requires a complexity exception.

## Project Structure

### Documentation (this feature)

```text
specs/011-afrr-mfrr-services/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
└── contracts/
    ├── restoration-activation-contract.md
    ├── restoration-market-artifact-contract.md
    ├── restoration-replay-contract.md
    ├── restoration-settlement-contract.md
    └── rte-balancing-energy-v5.2-contract.md
```

### Existing Extension Points

```text
src/open_energy_lab/
├── market/
│   ├── time.py                     # reusable canonical UTC/local intervals
│   ├── artifact.py                 # closed Feature 010 A44/A81 artifact
│   ├── activation.py               # closed Feature 010 FCR trace
│   └── entsoe.py                   # injected transport/retry pattern
├── control/
│   └── stacked_service.py          # closed Feature 010 baselines
└── simulator/
    ├── battery.py                  # reusable charge-positive transition
    ├── stacked_service.py          # closed Feature 010 FCR replay
    └── fcr_settlement.py           # closed Feature 010 settlement
```

### Target Library Structure

```text
src/open_energy_lab/
├── market/
│   ├── restoration_artifact.py     # one-source artifacts and study bundles
│   ├── restoration_activation.py   # derived mapping, aFRR trace, mFRR events
│   └── rte.py                      # explicit OAuth and v5.2 JSON acquisition
├── control/
│   └── restoration_service.py      # commitments and no-lookahead baselines
└── simulator/
    ├── restoration_service.py      # product-discriminated physical replay
    └── restoration_settlement.py   # product-specific economics/degradation

examples/restoration_services/
├── README.md
├── fetch_rte_period.py
├── stage_private_reference_data.py
├── generate_reference_results.py
├── run_offline_replays.py
└── restoration_services_walkthrough.ipynb

docs/
├── architecture/rte-balancing-energy.md
└── migration/afrr-mfrr-services.md

tests/
├── fixtures/restoration/
│   ├── README.md
│   ├── RESTRICTED_DATA.md
│   ├── synthetic_rte/
│   ├── manual_afrr_v1.json
│   ├── manual_mfrr_v1.json
│   ├── france_2026-08-20_afrr_market_v1.json
│   ├── france_2026-08-20_afrr_scenario_v1.json
│   ├── france_2026-08-15_mfrr_market_v1.json
│   ├── france_2026-08-15_mfrr_scenario_v1.json
│   └── france_restoration_expected_results_v1.json
├── unit/market/
├── unit/control/
├── unit/simulator/
├── integration/market/
├── integration/control/
└── integration/simulator/
```

**Structure Decision**: Add restoration-specific modules instead of widening
Feature 010's closed FCR types. Reuse only general primitives such as
`CanonicalInterval`, deterministic serialization patterns, and
`apply_power_request`. Source-independent offline types may be lazy-exported
from package roots; `rte.py` and network-capable ENTSO-E adapters remain focused
module imports. Examples own dotenv parsing and explicit credential handoff.

## Phase 0: Research

Research outcomes are captured in [research.md](./research.md). They resolve:

- exact RTE v5.2 OAuth, endpoint, root, field, period, direction, resolution,
  and reference-data shapes
- additive schemas required to preserve all Feature 010 contracts
- one-source artifact, study-bundle, immutable refresh, and restricted-data
  boundaries
- null/absent/zero preservation and field-specific diagnostics
- fixed-fraction derivation, aFRR interval-average trajectory, and mFRR
  piecewise-event semantics
- directional commitment/headroom rules and reuse of battery physics
- product-specific performance, settlement availability, penalties,
  degradation, and deterministic fingerprints
- optional ENTSO-E composition without fallback or semantic substitution
- offline notebook, credential, retry, and validation strategy

No `NEEDS CLARIFICATION` items remain. Historical complementary composition
may use a separate time-compatible artifact produced by the existing Feature
010 `fr-day-ahead-symmetric-fcr-v1` lifecycle, selecting its A44
`day_ahead_price` series by fingerprint. The guarded post-transition live path
uses the additive A44-only `fr-day-ahead-quarter-hour-v2` profile, preserves
native PT15M values in a source-separated in-memory artifact, and leaves the
Feature 010 contract unchanged. Any later restoration activation series must
pass the exact document/process/product/direction/unit/resolution semantic
gate.

## Phase 1: Design

The [data model](./data-model.md), [quickstart](./quickstart.md), and
[contracts](./contracts/) define:

- token-free RTE requests, ephemeral OAuth tokens, injected transports,
  bounded responses, sanitized diagnostics, fetch/refresh/offline operations,
  and immutable lineage
- one-source restoration artifacts, explicit series availability, independent
  provenance, raw digests, and multi-source study bundles
- fixed allocation mappings and explicit derived-scenario identity
- signed-kW interval-average aFRR trajectories and typed non-overlapping mFRR
  scheduled/direct events
- restoration-specific baseline, directional capacity, battery capability,
  replay request, sample/event report, and settlement contracts
- whole-settlement availability, separately inspectable economics, and exact
  reconciliation
- the verified real-data periods, restricted fixture lifecycle, synthetic
  oracles, offline notebook, optional live check, and FCR regression matrix

## Phase 2: Implementation Strategy

1. Add restoration source-independent enums, canonical series, immutable
   artifact/bundle serializers, dual fingerprints, offline validation, and
   atomic manifest-last publication without changing Feature 010 schemas.
2. Add the RTE v5.2 adapter with keyword-only credentials, runtime OAuth,
   injected auth/data transports, response limits, sanitized diagnostics,
   transient-only bounded retries, and exact aFRR/mFRR JSON parsers.
3. Implement fetch, refresh, and offline workflows. Publish only complete
   validated artifacts; unchanged refresh publishes nothing and changed refresh
   creates one linked successor.
4. Add the fixed-fraction derived mapping, signed aFRR trajectory, mFRR event
   sequence, exact energy integration, ambiguity/overlap checks, and immutable
   fingerprints.
5. Add fixed directional commitments, restoration capability inputs, and
   deterministic baseline builders that reserve directional headroom and never
   inspect activation.
6. Implement product-discriminated replay around the existing battery
   transition, including ramp/timing enforcement, request/delivery attribution,
   deterministic saturation causes, event reports, conserved aggregation, and
   physical/result fingerprints.
7. Implement whole-settlement availability, directional capacity and activated
   energy revenue, explicit penalty, throughput degradation proxy, and exact
   total reconciliation.
8. Publish synthetic oracles. Explicitly reacquire and privately stage the
   verified RTE periods, derive labelled scenarios with allocation fraction
   `0.001`, and generate byte-stable expected results without persisting OAuth
   material or raw response bodies.
9. Add source and migration documentation, guarded examples, the offline-first
   notebook, fixture/build exclusions, secret scans, and optional live tests.
10. Run the restoration suites plus the complete Feature 010 compatibility and
    import-boundary checks before declaring the feature complete.

## Validation Strategy

Routine offline validation:

```bash
uv run pytest tests/unit/market tests/integration/market -m "not live_entsoe and not live_rte"
uv run pytest tests/unit/control tests/unit/simulator
uv run pytest tests/integration/control tests/integration/simulator -m "not reference_benchmark"
uv run pytest tests/unit/test_lazy_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py tests/unit/test_migration_policy_docs.py
uv run python -c "import open_energy_lab; import open_energy_lab.market; import open_energy_lab.control; import open_energy_lab.simulator"
rg "from legacy|import legacy" src/open_energy_lab/market src/open_energy_lab/control src/open_energy_lab/simulator tests/unit/market tests/unit/control tests/unit/simulator tests/integration/market tests/integration/control tests/integration/simulator
```

Focused unchanged Feature 010 gate:

```bash
uv run pytest tests/unit/control/test_stacked_service.py tests/unit/simulator/test_stacked_service.py tests/unit/simulator/test_fcr_settlement.py tests/unit/simulator/test_stacked_services_notebook.py tests/integration/simulator/test_stacked_service_manual.py tests/integration/simulator/test_stacked_service_compatibility.py tests/integration/simulator/test_reference_replay_generation.py tests/integration/simulator/test_stacked_service_real_replay.py -m "not reference_benchmark" -q
```

Optional live and notebook checks are documented separately and never weaken a
failed offline gate.

## Complexity Tracking

No constitution violations or justified exceptions.
