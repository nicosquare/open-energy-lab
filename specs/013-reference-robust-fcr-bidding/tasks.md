# Tasks: Reference Robust FCR Bidding

**Input**: Design documents from `/specs/013-reference-robust-fcr-bidding/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/python-api.md`,
`contracts/robust-fcr-reference-fixture-v1.schema.json`, `quickstart.md`

**Tests**: Feature 013 is a reference-method migration with explicit
equation-oracle, real-solver, fixture, replay, and parity requirements. Test
tasks precede their implementation tasks wherever practical.

**Organization**: Tasks are grouped by user story so that the deployable
restriction, bound evidence, equation audit, Julia comparison, common replay,
and offline diagnostics can each be reviewed as a distinct increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Safe to execute in parallel because it targets different files and
  has no dependency on an unfinished task in the same group.
- **[Story]**: User-story mapping from `spec.md` (`US1` through `US6`).
- Every checklist item names the exact file or directory it changes or the
  exact file-scoped command it runs.

## Phase 1: Setup

**Purpose**: Establish the Feature 013 source, evidence, example, and test
locations without editing `baselines/*` or `legacy/*`.

- [X] T001 Create the Feature 013 example scaffold and scope statement in `examples/robust_fcr_bidding/README.md`
- [X] T002 [P] Create the optimization-fixture ownership, provenance, redistribution, and refresh-policy scaffold in `tests/fixtures/fcr_bidding/README.md`
- [X] T003 [P] Record the pinned source inventory and behavior-preserve/improve/drop boundary for `baselines/robust_storage_bidding/code/01_datastruct.jl`, `code/02_model.jl`, `code/12.jl`, and `results/02/2023-06-18.json` in `docs/migration/reference-robust-fcr-bidding.md`
- [X] T004 [P] Add fixture-independent authored battery, time, price, uncertainty, terminal, and solver-policy mappings with deferred library imports, including configurable objective-comparison fields and the complete `native-reference-benchmark-highs-v1` mapping, in `tests/robust_fcr_case_utils.py`

---

## Phase 2: Foundational Contracts and Lazy Boundaries

**Purpose**: Build the shared serialization, solver-loading, and private-model
boundaries required by every user story.

**Critical**: User-story implementation must not begin until public validation
can run without importing a mathematical-programming backend and the private
adapter can identify the required backend versions actionably.

- [X] T005 [P] Add failing import-boundary and source-contract tests proving Feature 013 pure imports do not load Pyomo, HiGHS, Gurobi, Julia, pandas, `baselines`, `legacy`, network clients, or credentials in `tests/unit/control/test_robust_fcr_import_boundary.py`
- [X] T006 Implement Feature 013 semantic-version constants, validation exceptions, finite/deep-freeze helpers, canonical JSON, UTC normalization, and SHA-256 primitives in `src/open_energy_lab/control/robust_fcr_bidding.py`
- [X] T007 [P] Define private normalized index sets, immutable model-input/handoff records, source-equation identifiers, and model-cardinality helpers without importing Pyomo in `src/open_energy_lab/control/_robust_fcr_formulation.py`
- [X] T008 [P] Implement lazy Pyomo/HiGHS version detection, required-versus-optional backend errors, and backend-neutral raw solve-result records without importing a solver at module import time in `src/open_energy_lab/control/_robust_fcr_solver.py`
- [X] T009 Extend repository no-reference-import coverage to the new control modules and tests, including runtime-read guards for `baselines/*`, `legacy/*`, and the regulation CSV, in `tests/unit/test_no_legacy_imports.py`
- [X] T010 Run the foundational boundary checks with `uv run pytest tests/unit/control/test_robust_fcr_import_boundary.py tests/unit/test_no_legacy_imports.py -q` and resolve failures only in `src/open_energy_lab/control/robust_fcr_bidding.py`, `src/open_energy_lab/control/_robust_fcr_formulation.py`, and `src/open_energy_lab/control/_robust_fcr_solver.py`

**Checkpoint**: Feature 013 modules exist, pure imports are lightweight, and
required/optional solver boundaries are explicit before domain behavior is
migrated.

---

## Phase 3: User Story 1 - Produce a Deployable Robust Daily Plan (Priority: P1)

**Goal**: Solve a valid ordinary-day restriction without realized activation,
retain complete solver evidence, independently audit it, and emit exactly one
eligible robust-labelled Feature 012 fixed plan.

**Independent Test**: Build one presolve-simple but complete 24/96/6 problem,
solve it twice with HiGHS, inspect 24 charge-positive energy and six FCR
decisions, confirm all slacks/residuals are at most `1e-6`, and verify identical
objectives, bounds, schedules, diagnostics, and semantic fingerprints. Invalid,
infeasible, nonzero-slack, no-incumbent, and default non-optimal-incumbent cases
must emit no plan.

### Tests for User Story 1

- [X] T011 [P] [US1] Add failing public-contract tests for battery limits, exact ordinary-day 24/96/6 mapping, DST rejection, prices including negatives/ties, terminal rule, information cutoff, uncertainty lineage, no-activation leakage, default and non-default finite non-negative objective-comparison policies, fixed canonicalization ID rejection, and deterministic problem fingerprints in `tests/unit/control/test_robust_fcr_problem.py`
- [X] T012 [P] [US1] Add failing controlled-backend tests for optimal, feasible-incumbent opt-in/default rejection, no-incumbent, infeasible, positive-terminal-slack, residual-above-`1e-6`, objective/bound, non-negative and tolerance-normalized gaps, zero/negative-objective denominators, inconsistent bounds, and plan eligibility in `tests/unit/control/test_robust_fcr_solver.py`
- [X] T013 [P] [US1] Add failing real Pyomo/HiGHS integration tests for one presolve-simple public 96-step restriction, one infeasible case, one non-deployable terminal-slack case, and two-run exact equality of every fingerprint-bearing objective, bound, gap, schedule, diagnostic, and semantic fingerprint in one pinned backend environment in `tests/integration/control/test_robust_fcr_highs.py`

### Implementation for User Story 1

- [X] T014 [US1] Implement immutable battery, time-contract, price, recovery-window budget, horizon-wide budget, uncertainty-profile, terminal-rule, solve-policy, and problem contracts with strict validation; accept and fingerprint finite non-negative objective-comparison values with `1e-6 EUR`/`1e-9` defaults; require exact `solver-output-kw-1e-9-half-even-v1`; and reject only invalid values or unsupported canonicalization IDs in `src/open_energy_lab/control/robust_fcr_bidding.py`
- [X] T015 [US1] Implement solver-neutral formulation, decision, objective-breakdown, residual, feasibility-audit, solver-evidence, diagnostic, and solve-result contracts with explicit unavailable fields and runtime-excluded identities in `src/open_energy_lab/control/robust_fcr_bidding.py`
- [X] T016 [US1] Translate the non-intraday restriction variables, hard headroom, efficiency epigraphs, lower/upper robust SOC counterparts, common binary disjunctions, restriction-only `v_res` bounds, exact terminal target/slack, and ex-ante objective from `baselines/robust_storage_bidding/code/02_model.jl:86-135,170-230,252-263` into `src/open_energy_lab/control/_robust_fcr_formulation.py`
- [X] T017 [US1] Implement deterministic HiGHS options, `load_solutions=False` execution, solver-confirmed incumbent detection/loading, complete finite witness extraction, maximization upper-bound normalization, absolute-gap normalization within the declared objective allowance, relative-gap denominator `max(abs(incumbent), abs(bound), 1 EUR)`, inconsistent-bound diagnostics, termination mapping, and actionable failures in `src/open_energy_lab/control/_robust_fcr_solver.py`
- [X] T018 [US1] Implement pure-Python raw and canonical witness auditing for variable bounds, binary integrality, every restriction constraint family, source-declared inert slacks, terminal slack, and objective reconciliation using the absolute `1e-6` deployability rule; canonical audit must replace only the 30 market decisions and retain all raw auxiliaries, binaries, and slacks in `src/open_energy_lab/control/robust_fcr_bidding.py`
- [X] T019 [US1] Map private discharge-positive `x0` to public charge-positive energy, retain non-negative `xr`, implement `solver-output-kw-1e-9-half-even-v1` from shortest round-trip decimal text with `Decimal("0.000000001")`, `ROUND_HALF_EVEN`, and signed-zero normalization, map canonical energy back to private `x0` for the unrepaired witness audit, and complete solve orchestration plus optimal/explicit-feasible-incumbent policy gates in `src/open_energy_lab/control/robust_fcr_bidding.py`
- [X] T020 [US1] Map private discharge-positive `x0` to charge-positive `EnergyBaselineSchedule`, preserve non-negative `xr` in `FCRCapacitySchedule`, and construct deterministic robust `FixedFCRBidPlan` lineage/objective/bound/diagnostics without circular fingerprints in `src/open_energy_lab/control/robust_fcr_bidding.py`
- [X] T021 [US1] Add the US1 bidding contracts, exceptions, time/budget/problem builders, and `solve_robust_fcr_bid` through the existing lazy `_EXPORT_MAP`, `TYPE_CHECKING`, `__all__`, and resolver pattern in `src/open_energy_lab/control/__init__.py`; the reference-problem builder is added later by T051
- [X] T022 [US1] Implement the authored restriction workflow and print solver evidence, objective reconciliation, residual/slack summaries, 24/6 schedules, and plan fingerprints in `examples/robust_fcr_bidding/run_small_case.py`
- [X] T023 [US1] Run `uv run pytest tests/unit/control/test_robust_fcr_problem.py tests/unit/control/test_robust_fcr_solver.py tests/integration/control/test_robust_fcr_highs.py -q` and make User Story 1 pass using only `src/open_energy_lab/control/robust_fcr_bidding.py`, `src/open_energy_lab/control/_robust_fcr_formulation.py`, `src/open_energy_lab/control/_robust_fcr_solver.py`, and `src/open_energy_lab/control/__init__.py`

**Checkpoint**: A complete offline restriction produces a deployable Feature
012 plan only under the declared solve-status and independent-audit policy.

---

## Phase 4: User Story 2 - Distinguish a Feasible Plan From an Optimistic Bound (Priority: P1)

**Goal**: Solve and report the mixed-binary relaxation separately, verify the
maximization bound order, and keep relaxation and optional exact decisions out
of the deployable-plan surface.

**Independent Test**: Solve one paired bounded case with identical inputs and
policy, verify `z_restriction <= z_relaxation`, confirm only restriction can
emit a plan, and report exact evidence as unavailable without Gurobi. When an
optional licensed exact solve is available, verify
`z_restriction <= z_exact <= z_relaxation`.

### Tests for User Story 2

- [X] T024 [P] [US2] Add failing unit tests for formulation identity, common-problem and identical-comparison-policy compatibility, default and non-default pairwise `max(configured_absolute_eur, configured_relative * max(abs(a), abs(b), 1 EUR))` ordering at/below/above the boundary, rejection of mismatched comparison policies, unavailable exact evidence, and refusal to expose relaxation/exact plans in `tests/unit/control/test_robust_fcr_solver.py`
- [X] T025 [P] [US2] Add failing real HiGHS paired restriction/relaxation tests with identical problem/policy fingerprints, exact repeated objective/bound/gap payloads, and repeatable configured objective ordering in `tests/integration/control/test_robust_fcr_highs.py`
- [X] T026 [P] [US2] Add explicitly selected optional-Gurobi tests for nonconvex exact configuration, structured unavailable evidence, and three-way bound ordering in `tests/integration/control/test_robust_fcr_optional_gurobi.py`

### Implementation for User Story 2

- [X] T027 [US2] Implement restriction, relaxation, and exact formulation profiles plus `RobustFCRBoundComparison` and `compare_robust_fcr_bounds` compatibility/order evidence using the fingerprinted pairwise absolute/relative objective allowance in `src/open_energy_lab/control/robust_fcr_bidding.py`
- [X] T028 [US2] Implement the mixed-binary relaxation by retaining all common constraints and omitting only the exact bilinear and restriction-only tightening from `baselines/robust_storage_bidding/code/02_model.jl:205-230` in `src/open_energy_lab/control/_robust_fcr_formulation.py`
- [X] T029 [US2] Implement the optional exact bilinear formulation from `baselines/robust_storage_bidding/code/02_model.jl:220-224` without exposing its decisions as a plan in `src/open_energy_lab/control/_robust_fcr_formulation.py`
- [X] T030 [US2] Add explicit compatible-Gurobi selection, `NonConvex=2`, optional binary/license/version handling, and no-HiGHS-fallback behavior for exact solves in `src/open_energy_lab/control/_robust_fcr_solver.py`
- [X] T031 [US2] Enforce `candidate_plan`, `upper_bound_only`, and `exact_evidence_only` roles during result construction and add bound-comparison exports lazily in `src/open_energy_lab/control/robust_fcr_bidding.py` and `src/open_energy_lab/control/__init__.py`
- [X] T032 [US2] Extend the authored example with paired restriction/relaxation values, inequality evidence, and explicit missing/available exact interpretation in `examples/robust_fcr_bidding/run_small_case.py`
- [X] T033 [US2] Run `uv run pytest tests/unit/control/test_robust_fcr_solver.py tests/integration/control/test_robust_fcr_highs.py -q` and separately run `uv run pytest tests/integration/control/test_robust_fcr_optional_gurobi.py -q -s`, preserving an actionable optional skip in `tests/integration/control/test_robust_fcr_optional_gurobi.py` when licensed evidence is absent

**Checkpoint**: Restriction, relaxation, and exact evidence have distinct
meanings, and no optimistic-bound formulation can masquerade as a plan.

---

## Phase 5: User Story 3 - Audit the Robustness Equations and Time Mapping (Priority: P1)

**Goal**: Make every preserved equation, mapping, unit, source reference,
objective component, slack interpretation, and model-size characteristic
independently inspectable.

**Independent Test**: Hand calculations reproduce the 2.75-hour horizon
budget, 4/16 repeated mappings, power headroom, asymmetric-efficiency branches,
prefix SOC bounds, terminal rule, and objective components; model metadata shows
the expected triangular index counts and quadratic—not cubic—growth.

### Tests for User Story 3

- [X] T034 [P] [US3] Add equation-oracle tests for the 2.75-hour derivation, invalid budget combinations, 24/96/6 mapping, headroom, charge/discharge efficiency branches, lower/upper robust SOC, terminal shortfall, inert source slacks, and objective assembly in `tests/unit/control/test_robust_fcr_equations.py`
- [X] T035 [US3] After T034, add private K=8/16/32 index/cardinality growth tests and public K=96 assembly-without-solve checks for triangular and strict off-diagonal families in `tests/unit/control/test_robust_fcr_equations.py`
- [X] T036 [P] [US3] Add documentation/source-contract tests requiring the exact pinned equation paths, line ranges, sign conversion, FCR price unit correction, and `lambdaHigh[l]` versus `lambdaHigh[k]` restriction detail in `tests/unit/control/test_robust_fcr_source_documentation.py`

### Implementation for User Story 3

- [X] T037 [US3] Complete deterministic `to_dict` evidence for recovery-window/horizon-wide lineage, explicit planning-to-energy/FCR maps, formulation profiles, objective components, units, and source references in `src/open_energy_lab/control/robust_fcr_bidding.py`
- [X] T038 [US3] Enrich every pure audit family with canonical unit, relation, checked count, maximum positive violation, witness indices, and exact `code/02_model.jl` references while preserving independence from Pyomo expressions in `src/open_energy_lab/control/robust_fcr_bidding.py`
- [X] T039 [US3] Record semantic index counts, total variables/binaries/active constraints, and formulation-specific quadratic cardinality metadata during assembly in `src/open_energy_lab/control/_robust_fcr_formulation.py`
- [X] T040 [US3] Reconcile displayed day-ahead value, FCR capacity value, slack penalty, and total objective separately from runtime and Feature 012 settlement fields in `src/open_energy_lab/control/robust_fcr_bidding.py`
- [X] T041 [US3] Add human-readable mapping, uncertainty derivation, equation-family residual, objective-component, and model-cardinality tables to `examples/robust_fcr_bidding/run_small_case.py`
- [X] T042 [US3] Document the exact preserved equations, corrected units, terminal/slack semantics, sign adapter, reference quirks, and intentionally excluded LP/intraday variants in `docs/migration/reference-robust-fcr-bidding.md`
- [X] T043 [US3] Run `uv run pytest tests/unit/control/test_robust_fcr_equations.py tests/unit/control/test_robust_fcr_source_documentation.py -q` and verify public K=96 is assembled but not solved in `tests/unit/control/test_robust_fcr_equations.py`

**Checkpoint**: A reviewer can reproduce the robust model from named evidence
without treating a successful solver status as the equation audit.

---

## Phase 6: User Story 4 - Compare Native and Julia Restriction Results (Priority: P1)

**Goal**: Reconstruct the exact normalized 2023-06-18 restriction input,
compare the native result with all rounded Julia decisions and solver metadata,
and certify rounding compatibility jointly without runtime baseline access.

**Independent Test**: Explicitly run the offline `reference_benchmark`, obtain
a status for objective, bound, all 24 `x0`, all six `xr`, decision-content and
producer schedule fingerprints, native feasibility, and the joint Julia
certificate; accept an alternative optimum only with common feasibility and
objective-equivalence evidence.

### Tests for User Story 4

- [X] T044 [P] [US4] Add failing strict fixture-loader tests for schema version, exact section set, source revision/digest, exact terminal target, counts, units, signs, mappings, 0.25/2.25/2.75 budgets, unavailable evidence, redistribution, source-precision separation from native policy, rejection of any invented native/source tolerance fields, fingerprint, tampering, and zero runtime reference access in `tests/unit/control/test_robust_fcr_reference.py`
- [X] T045 [P] [US4] Add failing normalization tests for explicit digest-pinned input, byte stability, ordered semantic diff, ignored-artifact-only output, committed-destination refusal, and zero Julia/solver/network execution in `tests/integration/control/test_robust_fcr_reference_normalization.py`
- [X] T046 [US4] After T044, add failing field-comparison tests for exact, source-precision-compatible, alternative-optimum-compatible, mismatch, unavailable, visible deltas, source-bound limitations, the fingerprinted native objective allowance, and status precedence in `tests/unit/control/test_robust_fcr_reference.py`
- [X] T047 [US4] After T046, add failing joint-certificate tests for all 30 closed decision intervals, reserve non-negativity, the fixed native equivalence band scaled by native objective and both source interval endpoints, objective-band intersection, `1e-6` slack limits, infeasible boxes, and objective-equivalence failure in `tests/unit/control/test_robust_fcr_reference.py`

### Implementation for User Story 4

- [X] T048 [US4] Implement immutable reference-fixture, recorded-result, source-precision-policy, unavailable-field, certificate, field-result, and comparison contracts plus a strict explicit-path loader matching `specs/013-reference-robust-fcr-bidding/contracts/robust-fcr-reference-fixture-v1.schema.json`; the loader must expose no native solve policy in `src/open_energy_lab/control/robust_fcr_reference.py`
- [X] T049 [US4] Implement the digest-pinned fixture normalizer with canonical JSON, ordered semantic diff, explicit source/destination, ignored-artifact-only writes, and no Julia/Gurobi execution in `examples/robust_fcr_bidding/normalize_reference_fixture.py`
- [X] T050 [US4] Generate, independently inspect, and deliberately promote the normalized restriction evidence to `tests/fixtures/fcr_bidding/robust_storage_bidding_2023-06-18_restriction_v1.json`, then finalize regeneration and evidence-limit instructions in `tests/fixtures/fcr_bidding/README.md` without changing `baselines/robust_storage_bidding`
- [X] T051 [US4] Implement and lazily export `build_robust_fcr_reference_problem(fixture, *, solve_policy)` to reconstruct `RobustFCRBiddingProblem` from exact normalized battery, time, price, uncertainty, terminal, information-cutoff, and formulation evidence plus the separately supplied, complete, fingerprinted native policy; retain source unavailable-tolerance evidence and reject any attempt to infer native values from it in `src/open_energy_lab/control/robust_fcr_reference.py` and `src/open_energy_lab/control/__init__.py`
- [X] T052 [US4] Build the auxiliary restriction certification model with one simultaneous 30-decision box, common feasibility equations, the source objective interval intersected with a fixed native equivalence band using the declared absolute/relative scale, and bounded deployability slacks in `src/open_energy_lab/control/_robust_fcr_formulation.py`
- [X] T053 [US4] Implement native/source feasibility, objective equivalence with the fingerprinted native allowance kept separate from source rounding, source-bound metadata, retained decision deltas, and exact/source-precision/alternative-optimum/mismatch/unavailable classification in `src/open_energy_lab/control/robust_fcr_reference.py`
- [X] T054 [US4] Implement canonical positive-discharge comparison-frame fingerprints for energy, FCR, and combined decision content while reporting—but not numerically equating—producer-specific Feature 012 schedule/plan fingerprints in `src/open_energy_lab/control/robust_fcr_reference.py`
- [X] T055 [US4] Add the explicitly marked full normalized 2023-06-18 HiGHS solve and field-complete comparison gate using the complete `native-reference-benchmark-highs-v1` policy mapping separately from the fixture, with policy fingerprint assertions, exact same-environment repeatability where the benchmark is repeated, actionable resource-limit evidence, and no activation CSV dependency, in `tests/parity/test_robust_fcr_reference_benchmark.py`
- [X] T056 [US4] Implement the explicit-fixture, explicit-time-limit researcher report that constructs and prints every `native-reference-benchmark-highs-v1` field and its separate fingerprint before the full optimization comparison in `examples/robust_fcr_bidding/run_reference_benchmark.py`
- [X] T057 [US4] Run routine comparison checks with `uv run pytest tests/unit/control/test_robust_fcr_reference.py tests/integration/control/test_robust_fcr_reference_normalization.py -m "not reference_benchmark and not external_reference_data" -q` and keep `tests/parity/test_robust_fcr_reference_benchmark.py` excluded until the explicit benchmark gate

**Checkpoint**: Bid-selection parity is evaluated directly and honestly within
the rounded source artifact's evidence, without Julia, Gurobi, activation data,
or runtime reads from the reference tree.

---

## Phase 7: User Story 5 - Replay the Selected Plan Through One Environment (Priority: P2)

**Goal**: Pass a successful restriction plan unchanged into Feature 012 after
acceptance, keeping ex-ante objective and ex-post physical/settlement evidence
separate and implementing no bidder-owned replay.

**Independent Test**: Bind one authored restriction plan to an ordinary Feature
012 request and obtain its normal settled report. With the optional governed
CSV explicitly present, evaluate native and recorded reference schedules
through the same existing external path; without it, routine checks pass and
the selected test skips actionably.

### Tests for User Story 5

- [X] T058 [P] [US5] Add an authored post-acceptance integration test that passes `RobustFCRSolveResult.deployable_plan` unchanged to the existing Feature 012 evaluator and asserts ordinary physical, settlement, and lineage behavior in `tests/integration/simulator/test_robust_fcr_feature_012_replay.py`
- [X] T059 [P] [US5] Add an explicitly marked external-data test that evaluates native and recorded schedules through Feature 012, injects only `artifacts/reference/robust_storage_bidding/regulation_signal.csv` after bid selection, and skips actionably when absent in `tests/integration/simulator/test_robust_fcr_external_reference_replay.py`

### Implementation for User Story 5

- [X] T060 [US5] Add shared post-acceptance market, accepted-volume, battery, and activation binding helpers that consume an existing plan without optimizer-specific replay logic in `tests/integration/simulator/robust_fcr_replay_utils.py`
- [X] T061 [US5] Ensure solve-result serialization and example labels keep `optimization_objective_eur`, `best_upper_bound_eur`, and Feature 012 realized settlement/profit fields distinct in `src/open_energy_lab/control/robust_fcr_bidding.py` and `examples/robust_fcr_bidding/run_small_case.py`
- [X] T062 [US5] Document the solve-then-accept-then-evaluate flow, the absence of a replay wrapper, and the optional explicit external-data command in `examples/robust_fcr_bidding/README.md` and `specs/013-reference-robust-fcr-bidding/quickstart.md`
- [X] T063 [US5] Run the routine replay gate with `uv run pytest tests/integration/simulator/test_robust_fcr_feature_012_replay.py -m "not external_reference_data" -q` and verify no Feature 013 production file under `src/open_energy_lab/control/` imports `RegulationActivationTrace`
- [X] T064 [US5] Run `uv run pytest tests/integration/simulator/test_robust_fcr_external_reference_replay.py -m external_reference_data -q -s` and record either passing fingerprints or the actionable missing-file skip in `docs/migration/reference-robust-fcr-bidding.md`

**Checkpoint**: Robust, manual, heuristic, and future TPM plans share Feature
012 physics and accounting; activation remains evaluation-only information.

---

## Phase 8: User Story 6 - Reproduce and Diagnose Solves Offline (Priority: P2)

**Goal**: Make every routine result, dependency failure, diagnostic,
fingerprint, and CI gate deterministic, offline, and actionable across the
supported Python/backend matrix.

**Independent Test**: In isolated processes, import all public Feature 013
contracts without loading backends; run guarded routine tests with network,
credentials, subprocesses, baseline/artifact reads, Gurobi, and the external
CSV blocked; repeat identical solves and prove semantic equality despite
different runtime metadata.

### Tests for User Story 6

- [X] T065 [P] [US6] Extend exact control-package export and lazy dependency expectations for all Feature 013 public symbols in `tests/unit/test_import_contract.py` and `tests/unit/test_lazy_dependency_boundaries.py`
- [X] T066 [P] [US6] Add guarded offline tests that fail on socket creation, credential/environment inspection, subprocess execution, `baselines/*`, `legacy/*`, `artifacts/*`, regulation CSV, and Gurobi access during routine problem/fixture/comparison paths in `tests/unit/control/test_robust_fcr_reference.py`
- [X] T067 [P] [US6] Complete controlled result-matrix tests for optimal, feasible, no-solution, infeasible, unbounded, interrupted, time-limited, failed, incompatible required backend, and unavailable optional exact outcomes in `tests/unit/control/test_robust_fcr_solver.py`
- [X] T068 [US6] After T066, add repeatability tests proving canonical input order, exact `1e-9 kW` half-even boundary behavior, signed-zero normalization, unchanged auxiliary-witness re-audit, exact same-environment objective/bound/gap payloads, ordered diagnostics, and runtime/path/log exclusion yield stable problem, decision, result, certificate, and comparison fingerprints; also prove that a distinct non-decision numeric value changes semantic identity even when comparison tolerance accepts it in `tests/unit/control/test_robust_fcr_problem.py` and `tests/unit/control/test_robust_fcr_reference.py`

### Implementation for User Story 6

- [X] T069 [US6] Complete backend-neutral termination/status normalization, structured missing/incompatible dependency errors, solver versions/options/cardinality metadata, incumbent provenance, and non-semantic runtime capture in `src/open_energy_lab/control/_robust_fcr_solver.py`
- [X] T070 [US6] Complete deterministic diagnostic ordering, explicit unavailable reasons, separate semantic/runtime payloads, and stable result/certificate/comparison fingerprints in `src/open_energy_lab/control/robust_fcr_bidding.py` and `src/open_energy_lab/control/robust_fcr_reference.py`
- [X] T071 [US6] Add required Pyomo/HiGHS compatibility tests and optional Gurobi isolation checks for Feature 013 in `tests/unit/control/test_robust_fcr_backend_compatibility.py`
- [X] T072 [US6] Add Feature 013 unit and bounded real-HiGHS integration paths to required-backend and offline jobs, explicitly exclude `reference_benchmark`, `external_reference_data`, and optional Gurobi, and protect those selections in `.github/workflows/ci.yml` and `tests/unit/test_ci_workflow.py`
- [X] T073 [US6] Document required/lazy Pyomo and HiGHS, optional exact Gurobi, offline CPU assumptions, no new dependency, benchmark separation, complete native benchmark policy ownership, fixture policy non-ownership, fixture availability, and blocked external services in `docs/migration/environment-assumptions.md`, `docs/migration/dependency-policy.md`, and `docs/migration/fixture-provenance.md`
- [X] T074 [US6] Run `uv run pytest tests/unit/control tests/integration/control tests/unit/test_ci_workflow.py tests/unit/test_lazy_dependency_boundaries.py tests/unit/test_import_contract.py tests/unit/test_no_legacy_imports.py -m "not reference_benchmark and not external_reference_data" --ignore=tests/integration/control/test_robust_fcr_optional_gurobi.py --strict-markers -ra` and resolve all routine failures in the named Feature 013 source/test/docs paths

**Checkpoint**: Required open-source behavior is deterministic and offline;
missing optional evidence is explicit and cannot weaken routine validation.

---

## Phase 9: Polish and Cross-Cutting Validation

**Purpose**: Complete public navigation, governance, compatibility, explicit
benchmark records, and final repository checks across all user stories.

- [ ] T075 [P] Link Feature 013's robust-bidding boundary, examples, plan, and evidence limitations from `README.md` and `docs/architecture/README.md`
- [ ] T076 [P] Add the Feature 013 API maturity, parity categories, benchmark policy, and relationship to Feature 012/Feature 009 to `docs/migration/api-maturity.md`, `docs/migration/parity-validation.md`, and `docs/migration/README.md`
- [ ] T077 [P] Register the new optimization fixture, source digest, regeneration boundary, redistribution status, and absence of baseline/external bytes in `tests/fixtures/README.md` and `docs/migration/fixture-provenance.md`, then confirm `pyproject.toml` needs no dependency change
- [ ] T078 Run `rg "from baselines|import baselines|from legacy|import legacy" src/open_energy_lab/control tests/unit/control tests/integration/control tests/parity` and remove any runtime imports from the named Feature 013 paths
- [ ] T079 Run `uv run python -m compileall -q src/open_energy_lab/control tests/unit/control tests/integration/control tests/parity examples/robust_fcr_bidding` and correct syntax failures in those paths
- [ ] T080 Run the exact routine Feature 013 command from `specs/013-reference-robust-fcr-bidding/quickstart.md` and record the final pass count plus exact same-environment semantic fingerprints and fingerprint-bearing numeric payloads in `docs/migration/reference-robust-fcr-bidding.md`
- [ ] T081 Run Feature 012 compatibility regressions in `tests/unit/control/test_fcr_bid_plan.py`, `tests/unit/simulator/test_fcr_bid_evaluation.py`, `tests/unit/simulator/test_fcr_reference_settlement.py`, `tests/integration/simulator/test_fcr_bid_evaluation_compatibility.py`, and `tests/integration/simulator/test_fcr_bid_evaluation_public_compatibility.py`
- [ ] T082 Run `uv run pytest tests/parity/test_robust_fcr_reference_benchmark.py -m reference_benchmark -q -s` and record the complete native policy mapping/fingerprint separately from source evidence, objective/bound, all comparison-status counts, fingerprints, solver/resource outcome, and evidence limitations in `docs/migration/reference-robust-fcr-bidding.md`
- [ ] T083 Run optional `tests/integration/control/test_robust_fcr_optional_gurobi.py` and `tests/integration/simulator/test_robust_fcr_external_reference_replay.py`, then record passing evidence or actionable unavailable reasons in `docs/migration/reference-robust-fcr-bidding.md` without weakening routine acceptance
- [ ] T084 Run documentation, fixture-governance, CI-contract, import-boundary, and no-legacy checks in `tests/unit/test_dependency_policy_docs.py`, `tests/unit/test_environment_policy_docs.py`, `tests/unit/test_fixture_provenance_docs.py`, `tests/unit/test_migration_policy_docs.py`, `tests/unit/test_ci_workflow.py`, `tests/unit/test_lazy_dependency_boundaries.py`, `tests/unit/test_import_contract.py`, and `tests/unit/test_no_legacy_imports.py`
- [ ] T085 Run `git diff --check`, inspect `git status --short`, and verify no task changed `baselines/robust_storage_bidding` or any `legacy/*` path before marking `specs/013-reference-robust-fcr-bidding/tasks.md` complete

---

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependency; T001-T004 may be split by file as marked.
- **Phase 2 (Foundational)**: Depends on Phase 1 and blocks every user story.
- **US1 (Phase 3)**: Depends on Phase 2 and is the first functional increment.
- **US2 (Phase 4)**: Depends on US1's common formulation, solver adapter, and
  result/plan policy.
- **US3 (Phase 5)**: Depends on US1's restriction and audit. Its equation-oracle
  and source-documentation tests may begin while US2 is in progress, but shared
  implementation files T037-T041 follow US2's T027-T032 to avoid conflicting
  edits to the public contracts, formulation kernel, and authored example.
- **US4 (Phase 6)**: Depends on US1, US2, and US3 because joint certification
  reuses the restriction, status/bound semantics, and independent equation
  audit.
- **US5 (Phase 7)**: Authored replay depends only on US1; its optional
  native-versus-recorded external replay depends on US4. Treat the full phase as
  complete only after US4.
- **US6 (Phase 8)**: Foundational isolation work can begin after Phase 2, but
  final status/fingerprint/CI matrices depend on US1-US5 surfaces.
- **Phase 9 (Polish)**: Depends on every selected user story.

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 Deployable restriction -> US2 Bound separation
                              |                              |
                              |                              v
                              |                       US3 Equation audit -> US4 Julia comparison
                              |                                               |
                              +---------------> US5 authored replay <---------+

Foundational -> US6 Offline diagnostics

US1 + US2 + US3 + US4 + US5 + US6 -> Polish and explicit benchmark records
```

### Parallel Opportunities

- Setup provenance/example/test-support files T002-T004 can proceed in
  parallel after T001 establishes the feature directory conventions.
- Foundational import tests, formulation handoff, and solver loader T005,
  T007, and T008 touch different files and can proceed in parallel.
- Within US1, contract, controlled-solver, and real-HiGHS tests T011-T013 can be
  authored in parallel before implementation.
- Within US2, unit bound, real-HiGHS pair, and optional-Gurobi tests T024-T026
  can be authored in parallel.
- While US2 implementation proceeds, US3's T034 and T036 may start in separate
  files; T035 follows T034 in the shared equation-test module, and T037-T041
  follow US2's shared-file implementation tasks.
- Within US4, fixture and normalization tests T044-T045 can be authored in
  parallel; comparison T046 then joint-certificate T047 extend the same fixture
  test module in sequence.
- Within US5, authored and external replay tests T058-T059 target separate
  files.
- Within US6, package-import, offline-guard, and status-matrix tests T065-T067
  target separate files; fingerprint T068 follows T066 because both extend the
  reference test module.
- Final navigation, migration-index, and fixture-governance documentation
  T075-T077 can proceed in parallel after story completion.

## Parallel Execution Examples

### User Story 1

```text
Parallel test authoring:
  T011 public problem/time/uncertainty contracts
  T012 controlled solver/incumbent/deployability contracts
  T013 real HiGHS restriction integration

Then sequential implementation:
  T014 -> T015 -> T016 -> T017 -> T018 -> T019 -> T020 -> T021 -> T022 -> T023
```

### User Story 2

```text
Parallel test authoring: T024 + T025 + T026
Implementation: T027 -> T028 -> T029 -> T030 -> T031 -> T032 -> T033
```

### User Story 3

```text
Parallel evidence start: T034 + T036
Shared-file continuation: T034 -> T035
Implementation: T037 -> T038 -> T039 -> T040 -> T041 -> T042 -> T043
```

### User Story 4

```text
Parallel evidence start: T044 + T045
Shared-file comparison tests: T044 -> T046 -> T047
Fixture path: T048 -> T049 -> T050 -> T051
Comparison path: T052 -> T053 -> T054 -> T055 -> T056 -> T057
```

### User Story 5

```text
Parallel test authoring: T058 + T059
Implementation and evidence: T060 -> T061 -> T062 -> T063 -> T064
```

### User Story 6

```text
Parallel hardening start: T065 + T066 + T067
Shared-file fingerprint continuation: T066 -> T068
Implementation and CI: T069 -> T070 -> T071 -> T072 -> T073 -> T074
```

## Implementation Strategy

### MVP First: Deployable Restriction

1. Complete Setup and Foundational phases T001-T010.
2. Complete US1 T011-T023.
3. Stop and demonstrate one optimal, independently audited restriction plan
   through the existing Feature 012 envelope.

This MVP chooses bids without activation look-ahead, reports solver-neutral
evidence, enforces the `1e-6` deployability gate, and produces the common plan
contract. It does not yet claim bound parity, Julia comparison, or realized
reference replay.

### Incremental Delivery

1. **MVP / US1**: Deployable restriction with deterministic HiGHS evidence.
2. **US2 then US3 shared-file implementation**: Add optimistic/exact bound
   separation, then complete equation inspectability. US3 equation-oracle and
   source-documentation tests may begin while US2 is in progress.
3. **US4**: Add strict normalized Julia evidence and joint interval-aware
   certification, then run the explicit reference benchmark.
4. **US5**: Bind successful plans to Feature 012 only after acceptance; keep
   external activation optional.
5. **US6**: Lock import, dependency, status, fingerprint, and CI reproducibility
   across the full feature.
6. **Polish**: Update indexes, run compatibility/governance checks, record
   benchmark/optional evidence, and verify reference trees remain untouched.

## Validation Notes

- Routine validation must be deterministic and offline and must not read the
  external activation CSV, `baselines/*`, or `legacy/*`.
- Required Pyomo/HiGHS failures are actionable test failures; optional exact
  Gurobi and external replay may skip only with structured evidence.
- The full 2023-06-18 optimization is selected only by `reference_benchmark`.
- The source JSON's rounded objective/bound does not prove termination,
  optimality, exact gap, unrounded feasibility, or solver tolerances.
- Ordinary Feature 012 schedule fingerprints include producer identity; use
  canonical source-frame decision-content fingerprints for cross-producer
  numerical equality.
- No task authorizes edits under `baselines/robust_storage_bidding` or
  `legacy/*`.
