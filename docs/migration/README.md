# Migration Documentation

Migration notes define how behavior may move from `legacy/*` into the unified
library, including API maturity, dependency classification, fixture provenance,
parity validation, and environment assumptions.

## Current Native Package References

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
  `open_energy_lab.control`, `open_energy_lab.weather`,
  `open_energy_lab.demand`, and `open_energy_lab.simulator` stochastic and
  cooling-aware package-root exports plus the visualization
  stable-versus-experimental boundary
- `dependency-policy.md`: import-light dependency classification and rejected
  runtime stacks for the controller pack, visualization feature,
  stochastic-weather workflow, and weather-conditioned demand workflow
- `parity-validation.md`: controller-pack validation minimums,
  stochastic-weather validation minimums, weather-conditioned demand validation
  minimums, and preserved-path regression rules
- `environment-assumptions.md`: default local validation environment, weather
  and demand offline-validation assumptions, and skip rules for non-core
  capabilities
- `fixture-provenance.md`: fixture record requirements, including weather,
  demand, and simulator-family provenance rules for recorded responses and
  deterministic baselines

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
