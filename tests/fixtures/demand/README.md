# Demand Fixtures

This directory now holds the committed User Story 1 validation fixtures for
the `open_energy_lab.demand` aligned-history fit and offline artifact-load
workflow. They are synthetic, deterministic, and explicit about provenance so
default validation can stay offline and reviewable.

## Active US1 Fixture Set

- `aligned_training_case.json`
- `aligned_training_case_missing_cooling.json`
- `aligned_training_case_missing_non_thermal.json`
- `fitted_demand_artifact_v1.json`
- `fitted_demand_artifact_unsupported_version.json`

## Reserved Later-Story Paths

- `sampling_request_case.json`
- `sampled_demand_family_case.json`

The sampling files remain scaffolds until the US2 offline paired-family
workflow is implemented.

## Provenance Fields

Every committed demand fixture keeps these top-level metadata fields:

```text
fixture_name
fixture_status
purpose
spec_feature
provenance
```

The `provenance` mapping always records:

- `author`
- `origin`
- `legacy_evidence_paths`
- `generation_command`
- `random_seed`
- `refresh_policy`

Training fixtures keep the aligned history payload needed by
`fit_demand_model`. Artifact fixtures keep the full persisted payload needed
by `load_demand_artifact`, with fixture metadata left in place so integration
schema checks can validate provenance at the same time.

## Fixture Records

`aligned_training_case.json`

- purpose: supported aligned weather-plus-demand training fixture
- status: active
- origin: synthetic current-library fixture
- exact legacy reference paths consulted:
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb`
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb`
  - `legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb`
- generation command: committed manually from the current-library fit contract
- random seed: none
- expected validation target: offline fit, JSON persistence, and reload
  coverage
- weather-field coverage: full canonical order expected by the aligned-history
  contract
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: only three daily records are
  retained
- access, license, or network notes: entirely offline
- refresh policy: update only when the documented aligned-history contract or
  supported fitted-artifact schema intentionally changes

`aligned_training_case_missing_cooling.json`

- purpose: fail-fast missing-cooling training fixture
- status: active
- origin: derived from the supported aligned training fixture
- exact legacy reference paths consulted:
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb`
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb`
  - `legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb`
- generation command: committed manually from the current-library fit contract
- random seed: none
- expected validation target: explicit `cooling_demand_rt` fail-fast coverage
- weather-field coverage: full canonical order retained
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: reuses the three-record positive
  case
- access, license, or network notes: entirely offline
- refresh policy: update only when the explicit cooling-history requirement
  intentionally changes

`aligned_training_case_missing_non_thermal.json`

- purpose: fail-fast missing non-thermal training fixture
- status: active
- origin: derived from the supported aligned training fixture
- exact legacy reference paths consulted:
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb`
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb`
  - `legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb`
- generation command: committed manually from the current-library fit contract
- random seed: none
- expected validation target: explicit
  `non_thermal_electric_demand_kw` fail-fast coverage
- weather-field coverage: full canonical order retained
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: reuses the three-record positive
  case
- access, license, or network notes: entirely offline
- refresh policy: update only when the explicit non-thermal-history
  requirement intentionally changes

`fitted_demand_artifact_v1.json`

- purpose: supported offline load artifact fixture
- status: active
- origin: synthetic current-library artifact fixture derived from the
  committed aligned training case
- exact legacy reference paths consulted:
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb`
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb`
  - `legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb`
- generation command: committed manually from the current-library fit contract
- random seed: none
- expected validation target: supported artifact schema and offline load
  coverage
- weather-driver coverage: the required first-release subset used by the
  committed fit implementation
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: uses one interval per day so the
  artifact stays readable
- access, license, or network notes: entirely offline
- refresh policy: update only when the documented artifact schema,
  demand-driver set, or preserved fit workflow semantics intentionally change

`fitted_demand_artifact_unsupported_version.json`

- purpose: unsupported-version artifact fixture
- status: active
- origin: copy of the supported artifact with only the schema version changed
- exact legacy reference paths consulted:
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb`
  - `legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb`
  - `legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb`
- generation command: committed manually from the current-library fit contract
- random seed: none
- expected validation target: unsupported-version fail-fast coverage
- weather-driver coverage: same required first-release subset as the supported
  artifact
- numeric tolerance: exact fixture values
- why the fixture is small enough to commit: reuses the supported daily
  artifact shape
- access, license, or network notes: entirely offline
- refresh policy: update only when the explicit schema compatibility contract
  intentionally changes

## Working Rule

Keep committed demand fixtures synthetic or tightly trimmed, explicit about
review assumptions, and loadable offline without notebooks, live services, or
legacy runtime imports.
