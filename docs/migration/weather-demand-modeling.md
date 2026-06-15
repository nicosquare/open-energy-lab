# Weather-Conditioned Demand Modeling Migration Note

Status: Phase 1 scaffold only

Spec `008-weather-demand-modeling` reserves the target documentation path for
the new public `open_energy_lab.demand` package and its later simulator-side
cooling-aware family integration. This file is intentionally limited to setup
scaffolding during Phase 1 and will be expanded in later tasks as the feature
ships.

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

## Phase 1 Scope

Phase 1 reserves the package, fixture, and documentation locations only.
Implementation is deferred to later tasks.

### Preserve

- no new runtime code under `legacy/*`
- offline default validation as the routine review path
- simulator-side ownership of cooling service semantics and blackout behavior

### Improve

- add a dedicated `open_energy_lab.demand` package path
- reserve deterministic fixture paths for aligned demand, artifacts, and
  cooling-aware simulator families
- reserve a migration-note path for explicit preserve/improve/reject guidance

### Reject

- merged weather-and-demand artifacts
- live-service assumptions in routine validation
- undocumented cooling accounting or mixed cooling-path configuration
