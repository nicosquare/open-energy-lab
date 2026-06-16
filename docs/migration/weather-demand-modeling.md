# Weather-Conditioned Demand Modeling Migration Note

Status: User Story 1 fit and reload workflow implemented

Spec `008-weather-demand-modeling` adds a public `open_energy_lab.demand`
package that now supports aligned-history fitting and offline artifact reload
without widening the import boundary or coupling cooling-service behavior into
the producer-side workflow. Later user stories will add offline paired-family
sampling and simulator-side cooling-path evaluation on top of this US1 base.

## Target Module Paths

- `src/open_energy_lab/demand/__init__.py`
- `src/open_energy_lab/demand/_aligned_history.py`
- `src/open_energy_lab/demand/_weather_response.py`
- `src/open_energy_lab/demand/fit.py`
- `src/open_energy_lab/demand/artifact.py`
- `src/open_energy_lab/demand/sampling.py`
- `src/open_energy_lab/simulator/demand.py`
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

## Implemented US1 Surface

The current implemented producer-side surface is:

- `open_energy_lab.demand.fit_demand_model`
- `open_energy_lab.demand.load_demand_artifact`

The package root now mirrors the lazy export pattern used by
`open_energy_lab.weather`, so `import open_energy_lab.demand` stays
import-light while still exposing the stable US1 entry points.

## Committed Offline Fixtures

US1 now ships committed, active fixtures for:

- positive aligned training history
- missing-cooling fail-fast input
- missing-non-thermal fail-fast input
- supported demand artifact reload
- unsupported-version artifact rejection

These fixtures live under `tests/fixtures/demand/` and support the offline
review path described in the quickstart and integration tests.

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

## Offline Artifact Usage

The intended offline usage path is:

1. Load or construct one aligned training payload that satisfies the canonical
   weather-plus-demand contract.
2. Call `fit_demand_model(...)` to produce a supported JSON artifact.
3. Persist that artifact to disk for later replay or review.
4. Call `load_demand_artifact(...)` on the persisted JSON with the expected
   timestep lock.

The committed fixtures in `tests/fixtures/demand/` exercise both the positive
path and the documented fail-fast negative paths without any live data fetch,
CityLearn dependency, or simulator-side coupling.
