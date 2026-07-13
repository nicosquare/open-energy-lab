# Parity Validation

This document defines the validation shape for future brownfield migrations
from `legacy/*` into `src/open_energy_lab`.

## Core Principle

Legacy code is guidance and evidence, not a target architecture to replay
mechanically.

- Preserve parity only for explicitly named behavior that the migration says
  must remain the same.
- Prefer clean, typed, reviewable simulator logic when legacy structure,
  control flow, or incidental behavior does not deserve preservation.
- Use parity checks as one validation tool, not as the default success
  criterion for the whole simulator surface.

## Required Migration Record

Each migration spec should describe the following:

```text
Migration name:
Target module path:
Validation/test path:
Target API maturity:
Legacy source paths:
Behavior to preserve:
Behavior to improve:
Behavior to reject:
Dependencies and classifications:
Fixtures and provenance:
Parity or validation cases:
Known environment assumptions:
Documentation updates:
Out-of-scope work:
```

## Validation Expectations

Every migration needs at least one relevant validation evidence type:

- Fixture-based test.
- Deterministic config and seed.
- Documented equation or invariant.
- Legacy command output or snapshot.
- Focused smoke run for long-running workflows.
- Explicit limitation explaining why parity cannot be automated locally.

Parity is therefore optional and selective. A migration may rely primarily on
fixtures, invariants, deterministic configs, or smoke checks when those better
capture the intended clean behavior.

## Review Rules

- Cite exact legacy paths and keep them in the `legacy source paths` section.
- Keep `target module path` and `validation/test path` explicit so reviewers can
  tell where new code and tests belong.
- Classify dependencies before implementation so core imports remain isolated
  from optional, external-service-backed, hardware-bound, and legacy-only
  packages.
- Record `behavior to preserve`, `behavior to improve`, and `behavior to
  reject` separately so validation and selective-preservation decisions stay
  reviewable.
- Include fixtures and provenance for any committed generated data.
- Document tolerances and environment assumptions when exact equality is not
  realistic.
- For simulator-level migrations, do not require broad end-to-end legacy
  parity. Use focused reference checks only for named preserved physics,
  settlement, or trace semantics, and allow cleaner implementation choices
  everywhere else.

## TPM-Backed Planning Validation Governance

The `009-tpm-planning` migration adds a TPM/planning-specific validation shape
that later work should preserve when it extends the shipped workflow:

- Keep `src/open_energy_lab/simulator` as the owner of simulator-family export
  semantics, flattened-series selection, and `shortfall` derivation inputs.
- Keep `src/open_energy_lab/tpm` import-light at the package root, with typed
  feature handling, persisted artifact reload, and empirical query replay
  clear of runtime `legacy/*` imports.
- Keep `src/open_energy_lab/planning` import-light at the package root, with
  persisted dataset reload and offline planning assembly clear of runtime
  solver requirements.
- Treat the committed planning fixtures under `tests/fixtures/planning` as
  active workflow evidence for deterministic export replay, planning-problem
  scope, solver metadata, and fake-backend optional-solve expectations.
- Treat the committed TPM fixtures under `tests/fixtures/tpm` as active
  contract evidence for persisted dataset reload, supported and unsupported
  TPM artifact behavior, typed feature ordering, piecewise metadata, and
  deterministic query replay.
- Preserve the simulator-versus-artifact-versus-planning boundary: simulator
  export owns flattened dataset construction, TPM artifacts own feature and
  query metadata, and planning owns decision-scope validation and optional
  solve behavior.
- Keep parity selective: use the cited legacy feature-engineering, typed
  feature, SPN, and piecewise files as reference evidence, but validate the
  shipped feature primarily through deterministic fixtures, reload contracts,
  query semantics, and assembly invariants rather than broad legacy runtime
  parity.

Minimum TPM-planning validation now includes:

- `tests/unit/simulator/test_planning_export.py`
- `tests/unit/tpm/test_import_boundary.py`
- `tests/unit/tpm/test_no_legacy_imports.py`
- `tests/unit/tpm/test_package_surface.py`
- `tests/unit/tpm/test_features.py`
- `tests/unit/tpm/test_data_handler.py`
- `tests/unit/tpm/test_artifact_schema.py`
- `tests/unit/tpm/test_query.py`
- `tests/unit/planning/test_import_boundary.py`
- `tests/unit/planning/test_no_legacy_imports.py`
- `tests/unit/planning/test_package_surface.py`
- `tests/unit/planning/test_dataset_schema.py`
- `tests/unit/planning/test_problem.py`
- `tests/unit/planning/test_piecewise.py`
- `tests/unit/planning/test_optional_solver.py`
- `tests/unit/test_optional_dependency_boundaries.py`
- `tests/unit/test_import_contract.py`
- `tests/unit/test_no_legacy_imports.py`
- `tests/integration/planning/test_fixture_schema.py`
- `tests/integration/planning/test_tpm_fixture_schema.py`
- `tests/integration/planning/test_reproducibility_contract.py`
- `tests/integration/planning/test_dataset_export.py`
- `tests/integration/planning/test_tpm_fit_workflow.py`
- `tests/integration/planning/test_problem_assembly.py`
- `tests/integration/planning/test_optional_solve.py`

If future TPM-planning work cannot run one of these checks locally, the skip
reason must be recorded in the relevant spec plan or quickstart, including
whether the blocked check depended on optional SPFlow, Pyomo, or solver
availability outside the default offline validation subset.

## Controller Boundary Governance

The `004-controller-boundary` migration adds a controller-specific validation
shape that later migrations should preserve when they extend this boundary:

- Keep `src/open_energy_lab/core` import-light and free of runtime `legacy/*`
  imports.
- Keep `src/open_energy_lab/simulator` import-light, with controller execution
  owned by `evaluate_with_controller`.
- Treat `tests/fixtures/simulator/controller_arbitrage_case.json` and
  `tests/fixtures/simulator/controller_battery_load_pv_case.json` as active
  deterministic evidence, not placeholder scaffolds.
- Preserve exact fixture provenance, numeric tolerance, and refresh-policy
  notes when those controller fixtures change.
- Validate both supported scenario families through the same controller runner
  API before expanding the stable surface.
- Keep named incomplete-context rejection behavior explicit so failures remain
  distinguishable from simulator-side clamping.

Minimum controller-boundary validation now includes:

- `tests/integration/simulator/test_controller_fixture_schema.py`
- `tests/integration/simulator/test_controller_evaluation.py`
- `tests/integration/simulator/test_battery_arbitrage_trace.py`
- `tests/integration/simulator/test_battery_load_pv_trace.py`
- `tests/unit/test_optional_dependency_boundaries.py`
- `tests/unit/core/test_no_legacy_imports.py`
- `tests/unit/simulator/test_import_boundary.py`
- `tests/unit/test_import_contract.py`

If future controller-boundary work cannot run one of these checks locally, the
skip reason must be recorded in the relevant spec plan or quickstart, alongside
any environment assumptions and the intended follow-up validation path.

## Native Controller Pack Governance

The `005-controller-pack` migration extends the controller boundary with a
stable native controller surface while keeping parity selective:

- Keep `src/open_energy_lab/control` import-light, free of runtime `legacy/*`
  imports, and layered on top of `open_energy_lab.core` and
  `open_energy_lab.simulator`.
- Treat `tests/fixtures/simulator/price_threshold_controller_case.json`,
  `tests/fixtures/simulator/soc_guardrail_arbitrage_case.json`, and
  `tests/fixtures/simulator/pv_self_consumption_case.json` as controller-pack
  validation evidence, not as preserved-path parity baselines.
- Keep `tests/integration/simulator/test_battery_arbitrage_trace.py` and
  `tests/integration/simulator/test_battery_load_pv_trace.py` focused on the
  preserved explicit-dispatch and built-in-rule simulator paths that must stay
  available alongside the new control package.
- Preserve exact fixture provenance, numeric tolerance, and refresh-policy
  notes when controller-pack fixtures change.
- Keep unsupported-scenario failures explicit so boundary errors remain
  distinguishable from simulator feasibility clamping and settlement behavior.
- Use focused invariants and deterministic traces instead of broad legacy
  controller parity claims.

Minimum controller-pack validation now includes:

- `tests/unit/control/test_import_boundary.py`
- `tests/unit/control/test_controller_interface.py`
- `tests/unit/control/test_support_matrix.py`
- `tests/unit/test_optional_dependency_boundaries.py`
- `tests/unit/test_no_legacy_imports.py`
- `tests/unit/test_import_contract.py`
- `tests/integration/control/test_price_threshold_controller.py`
- `tests/integration/control/test_scenario_support.py`
- `tests/integration/simulator/test_controller_fixture_schema.py`
- `tests/integration/simulator/test_controller_evaluation.py`
- `tests/integration/simulator/test_battery_arbitrage_trace.py`
- `tests/integration/simulator/test_battery_load_pv_trace.py`

If future controller-pack work cannot run one of these checks locally, the
skip reason must be recorded in the relevant spec plan or quickstart,
alongside any environment assumptions and the intended follow-up validation
path.

## Stochastic Weather Validation Governance

The `007-stochastic-weather` migration adds a weather-specific validation shape
that later work should preserve when it extends the shipped workflow:

- Keep `src/open_energy_lab/weather` import-light at the package root, with
  live-fetch dependencies isolated from offline artifact loading and sampling.
- Keep `src/open_energy_lab/simulator` as the owner of scenario-family
  execution semantics, blackout interpretation, and summary generation.
- Treat the committed weather fixtures under `tests/fixtures/weather` as active
  contract evidence for canonical normalization, artifact schema and reload
  behavior, deterministic seed replay, and unsupported-version failures.
- Treat the simulator family fixtures under `tests/fixtures/simulator` as
  active deterministic baselines for no-blackout and explicit blackout paths.
- Preserve the documented artifact-versus-simulator-consumed field boundary:
  the artifact keeps the full canonical field set, while the current simulator
  PV path consumes only the fields it documents.
- Keep blackouts distinct from weather attenuation and validate them through
  simulator-side outage traces rather than weather-model parity claims.

Minimum stochastic-weather validation now includes:

- `tests/unit/weather/test_canonical_schema.py`
- `tests/unit/weather/test_artifact_schema.py`
- `tests/unit/weather/test_sampling.py`
- `tests/unit/weather/test_events.py`
- `tests/unit/simulator/test_stochastic_weather.py`
- `tests/unit/test_optional_dependency_boundaries.py`
- `tests/unit/test_import_contract.py`
- `tests/unit/test_no_legacy_imports.py`
- `tests/integration/weather/test_fit_workflow.py`
- `tests/integration/weather/test_fixture_schema.py`
- `tests/integration/weather/test_offline_sampling.py`
- `tests/integration/weather/test_sampling_statistics.py`
- `tests/integration/simulator/test_stochastic_weather_family.py`
- `tests/integration/simulator/test_blackout_semantics.py`
- `tests/integration/simulator/test_weather_family_fixture_schema.py`
- `tests/integration/simulator/test_battery_load_pv_trace.py`

If future stochastic-weather work cannot run one of these checks locally, the
skip reason must be recorded in the relevant spec plan or quickstart,
including whether the blocked check was live-fetch behavior or part of the
default offline validation subset.

## Weather-Conditioned Demand Validation Governance

The `008-weather-demand-modeling` migration adds a demand-specific validation
shape that later work should preserve when it extends the shipped workflow:

- Keep `src/open_energy_lab/demand` import-light at the package root, with
  aligned-history fitting, offline artifact loading, and offline paired-family
  sampling clear of runtime `legacy/*` imports and live-service assumptions.
- Keep `src/open_energy_lab/simulator` as the owner of cooling-service
  semantics, demand-family evaluation, blackout interpretation, and settlement
  reporting.
- Treat the committed demand fixtures under `tests/fixtures/demand` as active
  contract evidence for aligned-history validation, artifact schema and
  reload behavior, unsupported-version rejection, and paired-seed replay.
- Treat the committed demand-family simulator fixtures under
  `tests/fixtures/simulator` as active deterministic evidence for
  local-electric conversion, district-cooling settlement, one-path validation,
  and explicit unserved-cooling reporting.
- Preserve the producer-versus-simulator boundary: demand artifacts and
  sampled demand traces keep explicit non-thermal electric and cooling outputs,
  while cooling service choice and district settlement remain simulator-side
  configuration.
- Keep parity selective: use the cited pricing module and demand-related
  notebooks as reference evidence for preserved semantics, but validate the
  shipped feature primarily through deterministic fixtures, replay contracts,
  and accounting invariants rather than broad CityLearn or notebook parity.

Minimum weather-conditioned-demand validation now includes:

- `tests/unit/demand/test_import_boundary.py`
- `tests/unit/demand/test_no_legacy_imports.py`
- `tests/unit/demand/test_package_surface.py`
- `tests/unit/demand/test_aligned_history.py`
- `tests/unit/demand/test_artifact_schema.py`
- `tests/unit/demand/test_sampling_request.py`
- `tests/unit/demand/test_sampling_family.py`
- `tests/unit/simulator/test_demand.py`
- `tests/unit/simulator/test_stochastic_demand.py`
- `tests/unit/test_optional_dependency_boundaries.py`
- `tests/unit/test_import_contract.py`
- `tests/unit/test_no_legacy_imports.py`
- `tests/integration/demand/test_fixture_schema.py`
- `tests/integration/demand/test_sampling_fixture_schema.py`
- `tests/integration/demand/test_fit_workflow.py`
- `tests/integration/demand/test_offline_sampling.py`
- `tests/integration/demand/test_paired_replay.py`
- `tests/integration/simulator/test_demand_family_fixture_schema.py`
- `tests/integration/simulator/test_stochastic_demand_family.py`
- `tests/integration/simulator/test_cooling_service_validation.py`
- `tests/integration/simulator/test_battery_load_pv_trace.py`

If future weather-conditioned-demand work cannot run one of these checks
locally, the skip reason must be recorded in the relevant spec plan or
quickstart, including whether the blocked check fell outside the default
offline validation subset.

## Out-of-Scope Boundary

The foundation feature does not migrate TPM, RL, optimization, or planning
behavior beyond the explicitly shipped features. A later
migration spec must handle any further algorithm or dependency expansion with
its own validation path. That keeps out-of-scope migration work explicit and
reviewable.
