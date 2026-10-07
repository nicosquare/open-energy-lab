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

## FCR Bid-Evaluation Reference Validation

Feature `012-fcr-bid-evaluation-parity` uses the pinned code under
`baselines/robust_storage_bidding/` as the reference implementation and the OEL
fixed-plan evaluator as the common environment. Bid generation and optimizer
translation are out of scope: manual, heuristic, robust, and future TPM bidders
all supply the existing energy and FCR schedules to the same replay, settlement,
reporting, and comparison path.

Routine checks use the hand oracle and committed Golden Reference Fixture with
no Julia, no Gurobi, no network, no submodule initialization, and no external
CSV. The complete test is marked `external_reference_data` and requires an
explicit digest-matched user path. It may produce `exact`,
`source_precision_compatible`, `mismatch`, or `unavailable` per field; a blanket
tolerance is forbidden.

The initial artifact supports aggregate decisions, economics, stored energy,
charge/discharge, and mapped power extrema. It does not support complete ten-second
trace parity, tracking, saturation, directional FCR energy,
throughput, or separate observed capacity/activation subrevenue. Those remain
OEL-invariant evidence or `unavailable`, never inferred parity. Dynamic
saturation is valid OEL behavior but outside the initial no-curtailment parity
domain.

## Reference Robust-FCR Bid-Selection Validation

Feature `013-reference-robust-fcr-bidding` compares bid selection directly,
before Feature 012 receives realized activation. The committed normalized
optimization fixture reconstructs identical declared battery, prices, 24/96/6
mapping, terminal rule, uncertainty sets, and restriction profile. Routine
validation never reads the runtime reference tree or activation CSV and never
invokes Julia or Gurobi.

Every comparison field receives exactly one category:

- `exact`: native and recorded exact evidence are equal;
- `source_precision_compatible`: the native value or one jointly feasible
  latent source schedule is within the declared rounded-source envelope;
- `alternative_optimum_compatible`: decisions differ, but both native and one
  joint source schedule pass common feasibility and objective-equivalence
  evidence;
- `mismatch`: required common feasibility, objective equivalence, or field
  compatibility fails; or
- `unavailable`: the source record or selected environment does not contain the
  evidence, without inferring a substitute.

Alternative-optimum acceptance requires one simultaneous 30-decision box,
common restriction feasibility, all modeled slacks at or below `1e-6`, and the
intersection of the source objective interval with the separately declared
native objective-equivalence band. Thirty independent rounded comparisons or a
matching three-decimal objective are insufficient.

The complete solve is a selected `reference_benchmark`, not routine CI. Its
caller supplies every field of `native-reference-benchmark-highs-v1`; the
fixture's absent source tolerances remain unavailable and are never populated
from native policy. Feature 012 replay is a later ex-post validation using the
same emitted plan and evaluator. It neither proves robust feasibility nor
changes the bid-selection parity category.

## Rolling FCR Backtest Reference Validation

Feature `015-fcr-rolling-backtest-parity` compares the pinned executable
behavior of scripts 11–15 over 2023-06-17 through 2023-06-20. Routine tests
load only the committed normalized fixture. They do not read `baselines`, raw
source JSON/logs, the workbook, Julia, Gurobi, a credential, the network, or
the external activation CSV.

Every field has one explicit outcome:

- `exact_displayed_decision_parity` when all displayed decisions match exactly;
- `source_precision_compatible` when one common audited native/source witness
  satisfies the closed three-decimal envelopes;
- `alternative_optimum_compatible` only when both plans have sufficient
  optimality and common-feasibility evidence plus objective equivalence;
- `source_incumbent_equivalent` when an audited native plan is
  objective-equivalent to a time-limited source incumbent under the declared
  precision policy;
- `improved_feasible_incumbent_compatible_with_source_bound` when the audited
  native incumbent improves on the displayed source incumbent without
  violating its same-solve upper bound;
- `bound_incompatible` when the claimed native objective relationship cannot
  fit the retained source bound;
- `mismatch` for proven decision, formulation, objective, state, overlap, or
  lifecycle incompatibility;
- `unavailable` when the source or selected environment lacks the evidence;
  or
- `incomplete_or_unfinalized` for an initialization edge, unclosed delivery,
  blocked/failed date, or incomplete study record.

Thirty independent interval checks are insufficient. Source-precision
compatibility uses one simultaneous witness over the decisions, objective,
state, and accepted overlap and requires Feature 013's modeled-slack and
independent residual audit. The source JSON's `bilinear_violations=0` value is
never feasibility proof. Source rounding is a closed interval; it is not the
hidden full-precision solver solution.

A time-limited incumbent plus bound is not an optimum. Two time-limited
incumbents are never called alternative optima merely because their displayed
objectives are close. A different native plan may be compatible only when its
common feasibility and objective/bound relationship are positively justified.
Optimization objective, best bound, Feature 012 settlement, and realized
profit remain separate quantities.

For script 14, 2023-06-17 is initialization evidence, 2023-06-18 and
2023-06-19 are primary finalized comparisons, and 2023-06-20 is an explicit
unfinalized edge until another 08:00 solve closes it. Exact full-precision
restart parity remains unavailable because the source did not persist every
in-memory fixing. Such dates remain in the result and are excluded from parity
aggregates with an explicit reason rather than silently dropped.

The complete native 5-by-4 run is an explicit `reference_benchmark`; governed
ten-second replay is `external_reference_data`; optional Gurobi is licensed
research evidence. Routine Pyomo/HiGHS oracles and bounded cases remain
complete without them. The bounded fixture cannot establish full-history or
Table A1 parity because source/profile metric reconciliation and complete
1,453-date evidence remain outside its scope.

## TPM-Backed Planning Validation Governance

The `009-tpm-planning` migration validates current library behavior rather
than attempting broad equality with the pre-1.0 runtime:

- Simulator export owns flattened planning rows and derives `shortfall` from
  simulator outputs. TPM owns typed metadata, current-SPFlow fitting,
  persistence, query, and solver-neutral compilation. Planning owns
  battery/solar decision validation and the Pyomo/HiGHS solve.
- The migrated behavior cites exact legacy paths in
  `docs/migration/tpm-planning.md`; no production module imports or
  deserializes `legacy/*`.
- Schema-v1 and pre-1.0 SPFlow artifacts are rejection/refit evidence only.
  They must be refitted from source rows through current SPFlow 1.1 and cannot
  serve production queries or planning.
- The canonical production evidence is
  `tests/fixtures/tpm/tpm_artifact_spflow_v1.json` plus its SHA-256-verified
  model sidecar. The `fixture_replay` mode and its replay fixtures were
  removed; there is no empirical query path.
- Required validation includes real SPFlow 1.1 fit/reload/query, native versus
  compiled probability checks, and real Pyomo 6.10.1/HiGHS 1.15.1 optimal and
  infeasible solves. Missing required backends fail validation; only explicitly
  selected, unavailable Gurobi may skip.

The `spflow-v1-mio-v1` compiler accepts exact native Sum, Product, Normal,
Bernoulli, and Categorical modules with one output channel and repetition.
SPFlow `Cat` adapters are unwrapped. Normal leaves use recorded normalized
breakpoints; discrete leaves and graph composition retain their probability
semantics. Custom/unsupported leaves, legacy histogram payloads, shared
subgraphs, custom subclasses, and extra dimensions fail with type/scope
diagnostics.

Compiler parity is deliberately bounded. The native and solver-neutral
evaluators are compared at five canonical evidence rows with maximum absolute
error `1e-6`; repeat compilation/evaluation tolerance is `1e-9`.
`tests/integration/tpm/test_spflow_v1_mio_parity.py` covers a native
Sum-of-Products graph, while the committed learned fixture covers Product plus
Normal/Bernoulli/Categorical leaves. These checks do not claim:

- accuracy across the whole continuous evidence domain
- support for rejected modules or graph shapes
- pickle-byte, pre-1.0 runtime, or broad legacy result equality
- cross-solver equality or production-scale performance
- a general inference compiler beyond planning's explicit event conditioning,
  decision-scope retention, and other-scope marginalization

Minimum focused evidence includes:

- `tests/integration/tpm/test_spflow_v1_fit.py`
- `tests/integration/tpm/test_spflow_v1_persistence.py`
- `tests/integration/tpm/test_spflow_v1_query.py`
- `tests/integration/tpm/test_spflow_v1_mio_parity.py`
- `tests/integration/planning/test_highs_solver.py`
- `tests/integration/planning/test_spflow_v1_highs_pipeline.py`
- the TPM/planning unit, lazy-import, import-contract, and no-legacy-import
  suites listed in `AGENTS.md`

If required SPFlow, Pyomo, or HiGHS validation cannot run, record it as a
failure rather than a successful skip. Record unavailable supplemental Gurobi
or legacy-runtime checks separately in the feature quickstart.

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
migration spec must handle any further out-of-scope algorithm migration or
dependency expansion with
its own validation path. That keeps out-of-scope migration work explicit and
reviewable.
