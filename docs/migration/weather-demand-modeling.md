# Weather-Conditioned Demand Modeling Migration Note

Status: User Story 3 fit, reload, offline paired-family sampling, and cooling-aware simulator evaluation implemented

Spec `008-weather-demand-modeling` adds a public `open_energy_lab.demand`
package that now supports aligned-history fitting, offline artifact reload,
and offline paired-family sampling without widening the import boundary or
coupling cooling-service behavior into the producer-side workflow. The
simulator now consumes those sampled families through a cooling-aware
evaluation surface that preserves deterministic `BatteryLoadPVScenario`
behavior while adding explicit local-electric versus district-cooling
accounting.

## Target Module Paths

- `src/open_energy_lab/demand/__init__.py`
- `src/open_energy_lab/demand/_aligned_history.py`
- `src/open_energy_lab/demand/_weather_response.py`
- `src/open_energy_lab/demand/fit.py`
- `src/open_energy_lab/demand/artifact.py`
- `src/open_energy_lab/demand/sampling.py`
- `src/open_energy_lab/simulator/__init__.py`
- `src/open_energy_lab/simulator/demand.py`
- `src/open_energy_lab/simulator/pricing.py`
- `src/open_energy_lab/simulator/objective.py`
- `src/open_energy_lab/simulator/stochastic_demand.py`

## Planned Validation Paths

- `tests/unit/demand/`
- `tests/integration/demand/`
- `tests/integration/simulator/`
- `tests/fixtures/demand/`
- `tests/fixtures/simulator/demand_local_electric_family_case.json`
- `tests/fixtures/simulator/demand_district_cooling_family_case.json`
- `tests/fixtures/simulator/demand_invalid_mixed_cooling_case.json`

## Reserved Legacy Evidence Paths

- `legacy/old_tpm/src_py/simulator/common/pricing.py`
- `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb`
- `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb`
- `legacy/fed_trpo/src/notebooks/citylearn_ccai_tutorial.ipynb`
- `legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb`

## Implemented Producer Surface

The implemented producer-side surface is:

- `open_energy_lab.demand.fit_demand_model`
- `open_energy_lab.demand.load_demand_artifact`
- `open_energy_lab.demand.DemandSamplingRequest`
- `open_energy_lab.demand.sample_demand_family`

The package root now mirrors the lazy export pattern used by
`open_energy_lab.weather`, so `import open_energy_lab.demand` stays
import-light while still exposing the stable US1 and US2 entry points.

## Implemented Simulator Surface

The simulator root now exports the cooling-aware paired-family surface:

- `open_energy_lab.simulator.evaluate_demand_family`
- `open_energy_lab.simulator.DemandFamilyEvaluationRequest`
- `open_energy_lab.simulator.DemandFamilyEvaluationResult`
- `open_energy_lab.simulator.DemandScenarioEvaluationResult`
- `open_energy_lab.simulator.DEMAND_SUPPORTED_SUMMARY_OUTPUT_FIELDS`

This keeps the stable package root import-light while making the simulator-side
consumer API discoverable without forcing callers to import
`open_energy_lab.simulator.stochastic_demand` directly.

## Committed Offline Fixtures

US1 and US2 now ship committed, active fixtures for:

- positive aligned training history
- missing-cooling fail-fast input
- missing-non-thermal fail-fast input
- supported demand artifact reload
- unsupported-version artifact rejection
- deterministic demand sampling request replay
- deterministic sampled demand-family replay aligned to one committed weather
  family fixture

These fixtures live under `tests/fixtures/demand/` and support the offline
review path described in the quickstart and integration tests.

## Committed Cooling-Aware Simulator Fixtures

US3 now ships committed active fixtures for:

- local-electric paired-family evaluation
- district-cooling paired-family evaluation
- invalid mixed-path rejection

These fixtures live under `tests/fixtures/simulator/` and point back to the
committed sampled weather and sampled demand family fixtures so a reviewer can
inspect the exact deterministic scenario ordering, settlement values, and
cooling-service accounting without generating new artifacts.

## Preserve / Improve / Reject

### Preserve

- no new runtime code under `legacy/*`
- offline default validation as the routine review path
- simulator-side ownership of cooling service semantics and blackout behavior
- import-light package roots with stable file locations for later exports
- explicit separation between non-thermal electric demand and cooling demand
- separate weather and demand artifacts rather than a merged producer payload

### Improve

- add a dedicated `open_energy_lab.demand` package path with stable root
  exports for fitting and artifact loading
- convert US1 demand fixtures from scaffolds into active aligned-history and
  artifact contract payloads with explicit provenance
- keep artifact reload fully offline through committed JSON fixtures and
  `load_demand_artifact`
- document the exact first-release weather-driver subset required by the
  committed fit workflow
- preserve deterministic fail-fast behavior for missing aligned inputs and
  unsupported artifact versions
- add a stable offline demand-family sampling workflow that reuses one shared
  paired-family seed and preserves exact weather-family ordering on replay
- commit deterministic request and sampled-family fixtures that let reviewers
  inspect explicit non-thermal electric and cooling outputs without refitting
- add a stable simulator root export surface for cooling-aware paired-family
  evaluation
- move district-cooling tariff settlement into shared simulator pricing and
  objective helpers so served `RT-hour` accounting is documented and reusable
- commit deterministic local-electric, district-cooling, and invalid mixed-path
  simulator fixtures with explicit expected outputs

### Reject

- merged weather-and-demand artifacts
- live-service assumptions in routine validation
- undocumented cooling accounting or mixed cooling-path configuration
- training inputs that provide total electric load without explicit
  non-thermal and cooling separation
- partial artifact creation when aligned training validation fails

## Legacy Evidence Used

US1 uses the following legacy notebook paths as conceptual-only evidence for
weather-sensitive demand separation:

- `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb`
- `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb`
- `legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb`

No legacy runtime imports or copied notebook code were introduced into the
stable package.

US3 uses `legacy/old_tpm/src_py/simulator/common/pricing.py` as exact legacy
evidence for step-aligned deterministic tariff treatment. The new
district-cooling settlement is an inference from that preserved settlement
direction: the simulator applies the same step-start tariff discipline to
served `RT-hour` accounting instead of copying a district-cooling runtime path
from the reference repositories, where no stable reusable district-cooling
module exists.

## Shared Paired-Family Seed Semantics

The committed US2 workflow now fixes one shared paired-family seed across both
producers:

1. `sample_weather_family(...)` owns the weather family seed and scenario
   ordering.
2. `DemandSamplingRequest.paired_family_seed` must match that weather family
   seed exactly.
3. `sample_demand_family(...)` derives demand-side scenario randomness from
   the shared seed plus scenario index, preserving one-to-one ordering with
   the weather traces.
4. Replaying the same weather family and demand request reproduces the same
   per-step demand outputs without refitting or live services.

This keeps weather and demand as separate persisted artifacts while still
giving the simulator one deterministic paired-family contract to consume.

## Offline Artifact And Sampling Usage

The intended offline usage path is:

1. Load or construct one aligned training payload that satisfies the canonical
   weather-plus-demand contract.
2. Call `fit_demand_model(...)` to produce a supported JSON artifact.
3. Persist that artifact to disk for later replay or review.
4. Call `load_demand_artifact(...)` on the persisted JSON with the expected
   timestep lock.
5. Prepare or load one sampled weather family with the same fixed timestep as
   the demand artifact.
6. Build `DemandSamplingRequest(...)` with the shared paired-family seed,
   positive horizon, and exact scenario count from that weather family.
7. Call `sample_demand_family(...)` to produce explicit non-thermal electric
   and cooling traces aligned to the referenced weather traces.
8. Build `DemandFamilyEvaluationRequest(...)` with one base deterministic
   `BatteryLoadPVScenario`, the sampled weather family, the sampled demand
   family, and exactly one cooling-service configuration.
9. Call `evaluate_demand_family(...)` to compare local-electric versus
   district-cooling outcomes without mutating the persisted producer-side
   artifacts.

The committed fixtures in `tests/fixtures/demand/` exercise both the positive
path and the documented fail-fast negative paths without any live data fetch,
CityLearn dependency, or simulator-side coupling.

The committed fixtures in `tests/fixtures/simulator/` exercise the cooling-
aware positive and negative simulator paths without introducing new runtime
dependencies, live services, or runtime `legacy/*` imports.
