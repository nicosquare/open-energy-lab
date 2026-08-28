# Migration Documentation

Migration notes define how behavior may move from `legacy/*` into the unified
library, including API maturity, dependency classification, fixture provenance,
parity validation, and environment assumptions.

## Current Native Package References

- `tpm-planning.md`: shipped simulator planning export, persisted dataset and
  TPM artifact workflows, current-SPFlow compiler, required HiGHS solve, and exact
  legacy evidence for `open_energy_lab.simulator`, `open_energy_lab.tpm`, and
  `open_energy_lab.planning`
- `controller-pack.md`: preserve/improve/reject decisions, shipped controller
  behavior, fixture evidence, and exact legacy references for
  `open_energy_lab.control`
- `stochastic-weather.md`: shipped weather workflow behavior, simulator-family
  semantics, blackout rules, stable versus deferred controls, and exact legacy
  evidence for `open_energy_lab.weather` and stochastic simulator evaluation
- `weather-demand-modeling.md`: shipped demand fit/load/sample behavior,
  cooling-aware simulator-family semantics, explicit electric-versus-cooling
  separation, and exact legacy evidence for `open_energy_lab.demand` plus the
  paired demand-family simulator surface
- `visualization-traces.md`: shipped inspection/reporting behavior, focused
  same-family comparison scope, experimental plotting split, and validation
  outcomes for `open_energy_lab.visualization`
- `api-maturity.md`: stable public API promotion for
  `open_energy_lab.tpm`, `open_energy_lab.planning`, simulator planning export,
  `open_energy_lab.control`, `open_energy_lab.weather`,
  `open_energy_lab.demand`, and `open_energy_lab.simulator` stochastic and
  cooling-aware package-root exports plus the visualization
  stable-versus-experimental boundary
- `dependency-policy.md`: import-light dependency classification and rejected
  runtime stacks for TPM/planning, the controller pack, the visualization
  feature, the stochastic-weather workflow, and the weather-conditioned demand
  workflow
- `parity-validation.md`: TPM/planning validation minimums, controller-pack
  validation minimums, stochastic-weather validation minimums,
  weather-conditioned demand validation minimums, and preserved-path
  regression rules
- `environment-assumptions.md`: default local validation environment,
  TPM-planning, weather, and demand offline-validation assumptions, and skip
  rules for non-core capabilities
- `fixture-provenance.md`: fixture record requirements, including planning,
  TPM, weather, demand, and simulator-family provenance rules for recorded
  responses and deterministic baselines
- `restricted-reference-fixtures.md`: private-repository storage boundary,
  distribution prohibitions, package exclusions, and explicit staging workflow
  for the three Feature 010 real-data fixtures
- `afrr-mfrr-services.md`: Feature 011 source, artifact, derived-scenario,
  control, replay, settlement, restricted-data, and Feature 010 compatibility
  ownership boundaries
- `fcr-bid-evaluation-parity.md`: Feature 012 fixed-plan common environment,
  pinned reference implementation mappings, bounded aggregate evidence,
  external-data governance, and no-bid-generation boundary
- `reference-robust-fcr-bidding.md`: Feature 013 preserved equations,
  restriction/relaxation roles, native solve/audit evidence, normalized Julia
  bid-selection comparison, and Feature 012 handoff boundary

## Reference Robust-FCR Bidding Review Path

For `013-reference-robust-fcr-bidding`, review these artifacts in order:

1. [Feature 013 plan](../../specs/013-reference-robust-fcr-bidding/plan.md) and
   [Python API contract](../../specs/013-reference-robust-fcr-bidding/contracts/python-api.md)
   for the single-day restriction/relaxation scope and stable lazy surface.
2. [Migration/equation ledger](./reference-robust-fcr-bidding.md) for exact
   pinned source paths, sign/unit mappings, audit semantics, and evidence limits.
3. `fixture-provenance.md` and `tests/fixtures/fcr_bidding/README.md` for the
   digest-pinned normalized optimization fixture and no-runtime-baseline rule.
4. `api-maturity.md`, `dependency-policy.md`, and `parity-validation.md` for
   stable API, required HiGHS/optional Gurobi, and the five comparison statuses.
5. [Feature 013 quickstart](../../specs/013-reference-robust-fcr-bidding/quickstart.md)
   for routine checks, the separately owned native benchmark policy, and
   optional post-acceptance Feature 012 replay.

Feature 013 reuses Feature 009's dependency stack without using its planning or
TPM APIs. It emits Feature 012's existing plan contract and never owns replay,
activation, or realized settlement.

## FCR Bid-Evaluation Parity Review Path

For `012-fcr-bid-evaluation-parity`, review these artifacts in order:

1. `fcr-bid-evaluation-parity.md` for preserve/improve/reject decisions, exact
   reference paths, common-environment ownership, and bid generation exclusions.
2. `fixture-provenance.md` and
   `tests/fixtures/fcr_bid_evaluation/README.md` for the Golden Reference
   Fixture, authoritative download, digest, external-only rule, supported and
   unavailable evidence, and refresh policy.
3. `parity-validation.md` for field-specific `source_precision_compatible`
   comparison and the absence of complete ten-second reference parity.
4. `environment-assumptions.md` and
   `specs/012-fcr-bid-evaluation-parity/quickstart.md` for routine no Julia/no
   Gurobi validation and the explicitly selected `external_reference_data` run.

The resulting evaluator is the common environment for fixed schedules. It does
not perform bid generation, reference optimizer translation, or TPM selection.

## aFRR/mFRR Restoration-Services Review Path

For `011-afrr-mfrr-services`, review these linked artifacts in order:

1. [Feature 011 design](../../specs/011-afrr-mfrr-services/plan.md) for scope,
   product separation, source semantics, and offline acceptance gates.
2. [RTE Balancing Energy architecture](../architecture/rte-balancing-energy.md)
   and [migration ownership note](./afrr-mfrr-services.md) for the source and
   library boundaries implemented under
   [`src/open_energy_lab`](../../src/open_energy_lab/).
3. [Offline example guide](../../examples/restoration_services/README.md) for
   deterministic aFRR/mFRR replay, settlement, and notebook use.

The migrated slice is an offline research workflow. RTE observations are
control-area aggregates and become BESS inputs only through an explicit,
labelled derivation; the feature is neither production dispatch nor bidding
optimization.

## TPM-Planning Review Path

For the `009-tpm-planning` feature, read the migration docs in this order:

1. `tpm-planning.md` for the shipped simulator export, persisted dataset and
   TPM artifact workflows, current-SPFlow compiler, and required HiGHS solve,
   preserve/improve/reject decisions, and exact legacy evidence.
2. `api-maturity.md` for the stable package-root simulator export, planning,
   and TPM imports versus narrower focused-module helpers.
3. `dependency-policy.md` for the import-light TPM/planning dependency
   boundary: SPFlow 1.1.0, Pyomo 6.10.1, and highspy 1.15.1 are required
   installations, while Gurobi is supplemental and optional.
4. `fixture-provenance.md` together with `tests/fixtures/planning/README.md`
   and `tests/fixtures/tpm/README.md` for export replay, persisted artifact,
   deterministic query, and planning-problem provenance rules.
5. `environment-assumptions.md` and
   `specs/009-tpm-planning/quickstart.md` for the default offline validation
   suite and any optional licensed-Gurobi or legacy-runtime follow-up checks.

This review path keeps the TPM-planning feature anchored to the shipped
library workflow and offline contract rather than the earlier scaffolding
milestone.

## Visualization Review Path

For the `006-visualization-traces` feature, read the migration docs in this
order:

1. `visualization-traces.md` for the shipped inspection/reporting surface,
   same-family comparison scope, experimental plotting split, fixture set, and
   recorded validation outcomes.
2. `api-maturity.md` for the stable package-root visualization imports versus
   focused comparison and experimental plotting module imports.
3. `dependency-policy.md` for the import-light visualization dependency
   boundary and optional plotting guidance.
4. `fixture-provenance.md` together with
   `tests/fixtures/visualization/README.md` for the committed fixture record
   requirements and refresh expectations.

This review path keeps the visualization feature anchored to shipped library
behavior, not to the earlier scaffolding state.

## Stochastic Weather Review Path

For the `007-stochastic-weather` feature, read the migration docs in this
order:

1. `stochastic-weather.md` for the shipped fit/load/sample workflow,
   simulator-family semantics, blackout behavior, and preserve/improve/reject
   decisions.
2. `api-maturity.md` for the stable package-root weather and stochastic
   simulator exports versus narrower focused-module helpers.
3. `dependency-policy.md` for the offline-first import boundary and the
   promoted live-fit dependency stance.
4. `fixture-provenance.md` together with `tests/fixtures/weather/README.md`
   and `tests/fixtures/simulator/README.md` for recorded-response,
   artifact-schema, sampled-family, and blackout-baseline provenance rules.
5. `environment-assumptions.md` and
   `specs/007-stochastic-weather/quickstart.md` for the default offline
   validation subset and live-fetch follow-up checks.

This review path keeps the weather feature anchored to the shipped offline
workflow and simulator-family contract rather than the earlier scaffolding
milestone.

## Weather-Conditioned Demand Review Path

For the `008-weather-demand-modeling` feature, read the migration docs in this
order:

1. `weather-demand-modeling.md` for the shipped aligned-history fit/load/sample
   workflow, cooling-aware simulator-family semantics, preserve/improve/reject
   decisions, and exact legacy evidence.
2. `api-maturity.md` for the stable package-root demand imports and
   cooling-aware simulator exports versus narrower focused-module helpers.
3. `dependency-policy.md` for the offline-first import boundary and the
   promoted demand-workflow plus simulator-family dependency stance.
4. `fixture-provenance.md` together with `tests/fixtures/demand/README.md`
   and `tests/fixtures/simulator/README.md` for aligned-history, artifact,
   paired-family, and cooling-accounting provenance rules.
5. `environment-assumptions.md` and
   `specs/008-weather-demand-modeling/quickstart.md` for the default offline
   validation subset and any optional follow-up checks.

This review path keeps the demand feature anchored to the shipped producer
workflow and simulator-family contract rather than the earlier scaffolding
milestone.

## Working Rule

Future migration specs must identify target library paths, validation paths,
legacy source paths, preserved or rejected behavior, and dependency boundaries
before implementation begins.
