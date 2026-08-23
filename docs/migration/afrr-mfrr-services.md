# aFRR And mFRR Service Vertical Slice

## Status And Scope

Feature 011 adds distinct French aFRR and mFRR research workflows beside the
validated Feature 010 day-ahead-plus-FCR slice. It acquires and preserves
market-area observations, constructs explicit directional commitments and
source-independent activation inputs, replays one BESS deterministically, and
reports physical performance and inspectable settlement components.

The implementation is a simulation and audit tool. It does not bid, optimize,
control a real asset, reproduce an operational AGC signal, or claim that an RTE
area price is a battery invoice.

## Single-Owner Boundaries

| Responsibility | Single owner | Boundary |
| --- | --- | --- |
| RTE OAuth, bounded transport, exact v5.2 JSON parsing, fetch, and refresh | `open_energy_lab.market.rte` | Explicit operation only; no control, mapping, replay, or settlement |
| One-source normalized market artifact, availability states, integrity, atomic IO | `open_energy_lab.market.restoration_artifact` | No networking and no source substitution |
| Multi-source provenance composition | `RestorationStudyBundle` in `market.restoration_artifact` | Fingerprint references only; never copies or joins observations |
| Derived aFRR trajectories and typed mFRR SA/DA events | `open_energy_lab.market.restoration_activation` | Source-independent contracts; area-to-asset conversion only through an explicit mapping |
| Directional commitments, capability, and no-lookahead energy baselines | `open_energy_lab.control.restoration_service` | Fixed valid schedules and deterministic heuristics; no bidding optimization or activation lookahead |
| Physical battery delivery and product performance | `open_energy_lab.simulator.restoration_service` | Restoration constraints first, then the unchanged battery transition |
| Capacity, activation, penalty, degradation, gross, and net economics | `open_energy_lab.simulator.restoration_settlement` | Whole-settlement availability; area prices require a labelled proxy mapping |
| Real reference acquisition/staging | `examples/restoration_services/fetch_rte_period.py` and `stage_private_reference_data.py` | Credentialed acquisition is explicit; staging is credential-free and network-free |
| Reference scenario/result generation and display | `generate_reference_results.py` and `run_offline_replays.py` | Offline consumers of governed fixtures only |
| Existing day-ahead/FCR behavior | Feature 010 modules | Closed and unchanged; no restoration type enters an FCR contract |

Reusable source-independent code lives under `src/open_energy_lab`. The
examples are consumers and policy gates, not second owners of market,
activation, physics, or settlement semantics.

## Source-To-Result Flow

```text
explicit RTE fetch/refresh
    -> one immutable RTE market artifact
    -> credential-free private staging
    -> explicit fixed-fraction derived scenario
    -> product-specific fixed commitment and baseline
    -> aFRR trajectory OR mFRR event sequence
    -> product-specific physical replay
    -> explicit proxy settlement
    -> offline audit tables and notebook plots
```

An optional study bundle can reference an independently acquired, compatible
Feature 010 A44 day-ahead price series. It composes artifact and series
fingerprints only. RTE and ENTSO-E rows never share one acquisition artifact,
and ENTSO-E never replaces a missing RTE observation.

## Fixed-Fraction Derivation

RTE values are French control-area aggregates, not commands addressed to the
reference battery. The real demonstrations therefore use one transparent
mapping:

```text
requested_bess_kw = requested_area_mw * 1000 * 0.001
```

The `0.001` fraction is a declared study assumption, fixed for the complete
scenario. It is not estimated from asset participation, period maxima, prices,
or activated energy. The implementation does not vary it by interval, normalize
the source curve, or clip a mapped request. A request above the compatible
commitment fails scenario construction.

In short: the allocation is fixed for the complete scenario and no request is
clipped.

For aFRR, separate upward and downward **requested need** series are the only
real-data drivers. Simultaneous nonzero directions fail as ambiguous. The four
upward French-area needs `425`, `315`, `290`, and `345 MW` map to signed BESS
interval-average requests `-425`, `-315`, `-290`, and `-345 kW`; negative is
upward/discharge under the library's charge-positive convention. Activated-for-
France and activated-in-France values remain comparison observations.

For mFRR, the selected downward **SA requested volume** of `357 MW` maps to a
`357 kW` scheduled-event magnitude. SA satisfied need and locally activated
volume remain comparison observations. The event's zero delay, zero ramp-up,
900-second hold, and zero ramp-down are explicit rectangular-shape assumptions,
not RTE fields. The selected DA values are source-null, so no DA event is
created. Synthetic cases demonstrate DA identity and nonzero timing/ramp
behavior without representing them as historical observations.

Every mapping records its source artifact and driver-series fingerprints,
direction, product, fixed fraction, MW-to-kW factor, commitment reference,
comparison-series references, creation time, assumptions, and mapping
fingerprint. Scenario, replay, narrative, and plots use the labels
`DERIVED_SIMULATION` and `derived_simulation`, never `observed_dispatch`.

## Reference Simulator Assumptions

Both real demonstrations use the same declared BESS and service capability:

| Input | Value |
| --- | ---: |
| Battery energy capacity | 2,000 kWh |
| Maximum charge / discharge power | 500 / 500 kW |
| Charge / discharge efficiency | 0.95 / 0.95 |
| Initial SOC | 0.50 |
| Minimum / maximum SOC | 0.10 / 0.90 |
| Maximum service ramp up / down | 500 / 500 kW/s |
| Maximum activation delay | 1 second for aFRR and mFRR |
| Supported duration | 1 through 3,600 seconds |
| aFRR upward / downward commitment | 450 / 450 kW |
| mFRR upward / downward commitment | 400 / 400 kW |
| Energy baseline | Fixed zero, built without activation lookahead |
| Absolute numeric tolerance | `1e-6` |

Positive battery power means charging and negative means discharging. Replay
validates commitment, reserved headroom, ramp, activation time, duration,
battery power, SOC, and efficiency deterministically. It reports requested,
capability-accepted, and physically delivered response separately rather than
silently resizing a commitment.

The real reference settlement declares zero day-ahead and capacity-price study
assumptions, maps the matching RTE area activation price only as
`scenario_proxy`, leaves the non-performance penalty unconfigured, and applies
an explicit `0.02 EUR/kWh` battery-terminal-throughput comparison proxy. That
proxy is a first-order study cost, not an electrochemical-aging model. An
unconfigured penalty is inspectably zero; a required missing/incompatible price
makes the entire financial settlement unavailable rather than producing a
partial total.

## Synthetic And Real Evidence

| Evidence | What it proves | What it does not prove |
| --- | --- | --- |
| `synthetic_rte/*.json` | Exact parser shapes, source null/absent/zero, malformed data, time, unit, direction, auth, and retry failures | Availability or dispatch of a real BESS |
| `manual_afrr_v1.json` | Hand-calculable upward/downward/zero tracking, ramp/power/SOC/headroom limits and conserved energy | High-frequency historical aFRR tracking |
| `manual_mfrr_v1.json` | Hand-calculable SA/DA event shape, delay, ramps, energy, zero activation, and overlap rejection | A historical DA call or national activation-time certification |
| Real aFRR market artifact | Four exact RTE PT15M area observations and their provenance | The AGC trajectory or command sent to a battery |
| Derived aFRR scenario/replay | Deterministic `0.001` interval-average simulation and BESS response | Observed asset dispatch or real settlement |
| Real mFRR market artifact | One quarter with downward SA requested/satisfied values and sparse DA state | An asset-level event shape or DA occurrence |
| Derived mFRR scenario/replay | Deterministic rectangular SA simulation and BESS response | The actual RTE activation order sent to an asset |
| Expected-results fixture | Byte-stable physical and explicit proxy economics from the pinned inputs | A commercial invoice, forecast, or optimal strategy |

The real-data integration tests block network and credential access, verify the
exact source and mapping fields, physical bounds, settlement reconciliation,
sparse DA reporting, and repeated-result equality. Routine correctness remains
fully offline; the live producer is only an optional source-compatibility check.

## Feature 010 Preservation

Feature 011 is additive. It does not widen or rewrite:

- `MarketDataArtifact`, `RegulationActivationTrace`, or the closed
  `fr-day-ahead-symmetric-fcr-v1` A44/A81 schema;
- `FCRCapacitySchedule`, Feature 010 baseline configuration, or its controller
  behavior;
- `StackedServiceReplayRequest`, FCR replay samples/results, or
  `SettlementBreakdown`; or
- the three restricted Feature 010 fixture files or any recorded Feature 010
  fingerprint.

Feature 011 reuses only product-neutral primitives such as
`CanonicalInterval`, `BatteryComponent`, `build_initial_state`, and
`apply_power_request`. New source-independent restoration symbols use lazy
package exports. The live RTE adapter remains a focused-module API, so importing
the library cannot read credentials or initialize networking. Exact type and
product gates reject FCR, aFRR, and mFRR cross-substitution before dispatch.

## Explicit Exclusions

Feature 011 does not implement or imply:

- joint FCR/aFRR/mFRR replay or bidding optimization;
- bid selection, forecast-aware MPC, stochastic bidding, reinforcement
  learning, or market-strategy profitability claims;
- inference of a per-BESS command from price, requested need, satisfied need,
  activated energy, or any other area aggregate;
- interpolation or upsampling of RTE PT15M aFRR data into operational AGC;
- fabricated mFRR DA events, hidden event precedence, or overlapping events;
- partial settlement totals, implicit prices, penalties, or degradation costs;
- continuous production ingestion, cache-miss fetching, or automatic refresh;
- cross-border PICASSO/MARI platform simulation;
- detailed French prequalification, certification, telemetry, or performance-
  monitoring compliance; or
- notebook, legacy runtime, solver, GPU/SLURM, experiment-tracker, or network
  dependencies in core offline imports.

## Restricted Evidence And Reproduction

Normalized real observations and every deterministic derivative remain
restricted because derived files can reproduce source values. They are stored
only for authorized collaborators in the owner-confirmed private repository,
excluded from packages/releases/public artifacts, and removed or reassessed
before visibility changes. Raw market bodies remain digest-only and credentials
remain outside Git.

The exact governed paths, hashes, generation commands, retention rules, and
refresh process are recorded in [Restricted French reference fixtures](restricted-reference-fixtures.md).
The source API contract is documented in [RTE Balancing Energy 5.2](../architecture/rte-balancing-energy.md).
