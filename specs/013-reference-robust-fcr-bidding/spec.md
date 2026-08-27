# Feature Specification: Reference Robust FCR Bidding

**Feature Branch**: `013-reference-robust-fcr-bidding`
**Created**: 2026-08-27
**Status**: Draft
**Input**: User description: "Implement a native single-day, non-intraday robust bidder for joint day-ahead arbitrage and symmetric FCR, with deployable restriction schedules, relaxation bounds, Feature 012 evaluation, and bounded comparison against the pinned Julia/Gurobi result."

## Purpose *(mandatory)*

Provide researchers with a native, reproducible way to choose one day's battery
energy and Frequency Containment Reserve (FCR) bids before the realized
activation signal is known. The bidder must reproduce the non-intraday robust
decision method preserved by the pinned `robust-storage-bidding` reference,
while returning the same bidder-neutral schedule and lineage contracts already
evaluated by Feature 012.

This feature separates three forms of evidence that must not be conflated. The
restriction produces a plan that may be offered as robustly deliverable. The
relaxation supplies an upper bound but not a deployable plan. Feature 012 then
replays and settles an accepted restriction plan against realized activation;
that ex-post result is distinct from the bidder's ex-ante objective and robust
feasibility claim.

The feature also establishes a direct, bounded comparison between the native
restriction solve and the pinned Julia/Gurobi Experiment 2 result for
2023-06-18. Exact decision agreement is reported when supported. A different
schedule is accepted as an alternative optimum only when common feasibility
and objective-equivalence checks support that conclusion.

## Clarifications

### Session 2026-08-27

- Q: When may a feasible restriction incumbent that has not been proven optimal emit a deployable plan? → A: Proven optimality is required by default; a feasible incumbent may emit a plan only through explicit caller opt-in and after every deployability check passes.
- Q: Must the complete 2023-06-18 native solve and Julia comparison run in routine CI? → A: No. Routine CI uses equation oracles and bounded small solves; the complete reference solve is an explicit research/release benchmark gate.
- Q: How must feasibility and objective equivalence be assessed for Julia decisions recorded to three decimals? → A: Use joint interval-aware certification over the rounding intervals; do not treat the displayed decisions as exact points.
- Q: What internal threshold determines whether restriction slack and constraint residuals are effectively zero for deployability? → A: Use an absolute `1e-6` threshold in each field's canonical unit, separate from solver tolerances and source precision.
- Q: Which time grids must the Feature 013 public contract support? → A: Only one ordinary 24-hour day with 96 quarter-hour planning intervals, 24 hourly energy blocks, and six four-hour FCR blocks.
- Q: What numerical policy governs native objective ordering and objective equivalence? → A: The solve policy stores finite non-negative absolute and relative comparison tolerances, fingerprinted before solving; public defaults are `1e-6 EUR` and `1e-9`, callers may select other values, and compared native results must carry identical values. Use `max(absolute_tolerance, relative_tolerance * max(abs(a), abs(b), 1 EUR))` for every two-value comparison; source-rounding intervals remain separate.
- Q: How are public solver decisions canonicalized before schedule construction? → A: First negate private discharge-positive energy values into the public charge-positive frame, leave non-negative FCR values unchanged, then apply the fixed `solver-output-kw-1e-9-half-even-v1` rule: quantize each finite kW decision to `1e-9 kW` with decimal round-half-even and normalize signed zero to positive zero. For re-audit, negate canonical energy values back into the private frame, substitute only those 30 decisions into the unmodified raw auxiliary witness, and rerun the independent audit without repair or re-optimization.
- Q: How is a reported relative optimality gap computed? → A: Divide the tolerance-normalized non-negative absolute maximization gap by `max(abs(incumbent), abs(best_upper_bound), 1 EUR)`; report both gaps unavailable when either value is unavailable or when the bound is below the incumbent beyond the objective-comparison tolerance.
- Q: Where does the native solve policy for the normalized 2023-06-18 benchmark come from when the Julia result did not record solver tolerances? → A: It is a separate caller-supplied `RobustFCRSolvePolicy`, never inferred from the source fixture. The researcher-facing benchmark declares and fingerprints the documented `native-reference-benchmark-highs-v1` profile; the source fixture retains only recorded Julia evidence and its unavailable-field declarations.

## Scope Classification *(mandatory)*

- **Feature type**: New library capability, reference-method migration, and validation
- **Target surface**: Public single-day robust-bidding inputs and results; Feature 012 fixed-plan output; normalized reference fixture; offline comparison workflow
- **Legacy reference paths**: None. `legacy/*` remains out of scope. The pinned external implementation under `baselines/robust_storage_bidding/` is reference evidence only.
- **New-code location**: Reusable code under `src/open_energy_lab`, with validation under `tests`; exact package and module placement is deferred to planning. No new code belongs under `baselines/*` or `legacy/*`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Produce A Deployable Robust Daily Plan (Priority: P1)

As a storage-market researcher, I need to choose hourly day-ahead power and
four-hour symmetric-FCR capacity for one ordinary delivery day without seeing
the realized activation trace, so that I can submit a physically protected plan
to the common evaluator.

**Why this priority**: A deployable plan is the feature's primary outcome and
the prerequisite for rolling studies and later comparisons with TPM bidders.

**Independent Test**: A reviewer can provide one complete hand-calculable daily
problem, solve the restriction, inspect all 24 energy and six FCR decisions,
and verify that the resulting fixed plan has no modeled feasibility slack above
the declared tolerance.

**Acceptance Scenarios**:

1. **Given** a valid ordinary-day problem on the required 24/96/6 grid with battery limits, initial stored energy, prices, terminal rule, information cutoff, uncertainty budgets, and solve policy, **When** the restriction is solved to an accepted status with no material feasibility slack, **Then** the result contains one robust-labelled Feature 012 fixed plan with 24 hourly energy decisions, six four-hour FCR decisions, complete lineage, and solver evidence.
2. **Given** the same producer-visible inputs, pinned backend versions, and no realized activation data, **When** the restriction is solved repeatedly under the same deterministic policy in one environment, **Then** every fingerprint-bearing objective, bound, gap, schedule, diagnostic, and semantic fingerprint is exactly identical; tolerance-based equivalence is reserved for explicit comparisons and does not make distinct serialized values share a fingerprint.
3. **Given** a problem that is infeasible, has no accepted incumbent, or requires feasibility slack above the deployability tolerance, **When** the solve finishes, **Then** no deployable fixed plan is emitted and the result explains the blocking status and slack evidence.
4. **Given** an attempted bidder input that contains a realized activation trace or evaluation-only activation fingerprint, **When** the problem is validated, **Then** it is rejected before bid selection.

---

### User Story 2 - Distinguish A Feasible Plan From An Optimistic Bound (Priority: P1)

As a researcher reviewing optimization quality, I need the restriction and
relaxation to be identified and interpreted separately so that an optimistic
upper bound is never mistaken for a deliverable market commitment.

**Why this priority**: The scientific claim depends on preserving the direction
and operational meaning of the two approximations.

**Independent Test**: A reviewer can solve a small paired case, reproduce both
objectives, verify the required order, and confirm that only the restriction is
eligible to produce a deployable plan.

**Acceptance Scenarios**:

1. **Given** a problem for which both formulations reach accepted results, **When** their objectives are compared for this maximization problem, **Then** the restriction objective does not exceed the relaxation objective beyond the declared tolerance.
2. **Given** a relaxation result with complete decision values, **When** a caller requests a fixed plan, **Then** the result refuses to represent those decisions as robustly deliverable and explains that they are bound or diagnostic evidence only.
3. **Given** an optional accepted exact result for the same small problem, **When** all three objectives are compared, **Then** the reported order is restriction objective no greater than exact objective and exact objective no greater than relaxation objective within tolerance.
4. **Given** an environment without the optional exact solver, **When** routine validation runs, **Then** the restriction-versus-relaxation evidence remains complete and the unavailable exact comparison is reported without weakening the routine gate.

---

### User Story 3 - Audit The Robustness Equations And Time Mapping (Priority: P1)

As a researcher validating the method, I need uncertainty sets, multi-rate
mapping, efficiency treatment, power headroom, stored-energy bounds, terminal
requirements, and objective components to be inspectable so that I can relate
the native decision problem to the reference equations.

**Why this priority**: A solver returning numbers is not sufficient evidence
that the intended robust formulation was reproduced.

**Independent Test**: A reviewer can calculate a compact oracle by hand and
match the derived horizon budget, repeated block mappings, power envelope,
stored-energy limits, terminal test, and objective decomposition.

**Acceptance Scenarios**:

1. **Given** an exact-window activation budget of 0.25 hours, recovery window of 2.25 hours, and 24-hour horizon, **When** the horizon-wide non-intraday budget is derived, **Then** it is 2.75 hours and retains lineage to the two source parameters and derivation rule.
2. **Given** 96 quarter-hour planning intervals, **When** hourly energy and four-hour FCR decisions are mapped, **Then** each energy decision covers exactly four consecutive planning intervals and each FCR decision covers exactly 16 consecutive planning intervals without gaps or overlaps.
3. **Given** asymmetric charging and discharging efficiencies, **When** robust stored-energy and terminal constraints are audited, **Then** their charge/discharge cases and units can be independently reproduced from the declared problem.
4. **Given** a symmetric reserve commitment, **When** pointwise power headroom is checked, **Then** both maximum upward/discharge and downward/charge requests remain inside the declared power limits under the reference sign convention before conversion to the library convention.
5. **Given** accepted day-ahead and FCR decisions, **When** the ex-ante objective is reported, **Then** energy value, FCR capacity value, feasibility-slack penalty, and total objective reconcile, and no realized activation payment is included.

---

### User Story 4 - Compare Native And Julia Restriction Results (Priority: P1)

As a researcher reproducing the reference experiment, I need the native solve
compared directly with the pinned Julia/Gurobi restriction result on identical
declared inputs so that agreement covers bid selection rather than only replay
of an already supplied schedule.

**Why this priority**: Feature 012 validated the common evaluator for fixed
decisions. Feature 013 must add evidence that the native bidder chooses an
equivalent solution to the reference method.

**Independent Test**: Without starting Julia, reading from `baselines/*`, using
the external activation CSV, or requiring Gurobi, a reviewer can explicitly run
the reference benchmark, solve the normalized 2023-06-18 restriction case, and
inspect comparison statuses for the objective, bound, all 24 energy decisions,
and all six FCR decisions.

**Acceptance Scenarios**:

1. **Given** the normalized 2023-06-18 fixture and a separately supplied, fingerprinted native solve policy, **When** the native restriction is assembled, **Then** its battery values, efficiencies, initial and terminal stored energy, prices, time mappings, uncertainty profile, formulation settings, information cutoff, units, and sign rules match the fixture's declared reference inputs while native solver settings remain explicitly caller-owned and are not attributed to Julia.
2. **Given** native and pinned results for the same problem, **When** they are compared, **Then** objective, bound, 24 energy decisions, six FCR decisions, schedule fingerprints, and feasibility evidence each receive an explicit comparison status and numeric evidence where available.
3. **Given** agreement supported by exact recorded values, **When** comparison runs, **Then** it reports exact parity rather than a weaker status.
4. **Given** disagreement attributable only to declared source rounding, **When** comparison runs, **Then** it reports source-precision compatibility only when a joint decision vector inside all recorded rounding intervals satisfies the common formulation and the corresponding objective interval supports the comparison.
5. **Given** materially different native and recorded decisions, **When** the native schedule is feasible, the joint Julia rounding intervals contain a feasible schedule, and their objectives are equivalent under the common interval-aware policy, **Then** comparison may report alternative-optimum compatibility and must retain the decision differences.
6. **Given** materially different decisions without common feasibility and objective-equivalence evidence, **When** comparison runs, **Then** it reports a mismatch and does not infer solver degeneracy.

---

### User Story 5 - Replay The Selected Plan Through One Environment (Priority: P2)

As a bidder-comparison researcher, I need a successful restriction plan to use
Feature 012's existing replay and settlement boundary so that robust, manual,
heuristic, and future TPM plans are judged by identical physics and accounting.

**Why this priority**: A second optimizer-owned battery model would invalidate
the common-environment comparison.

**Independent Test**: A reviewer can bind one emitted restriction plan to a
complete evaluation context and obtain an ordinary Feature 012 report without
any bidder-specific replay or settlement path.

**Acceptance Scenarios**:

1. **Given** a deployable restriction plan and a complete offline evaluation context, **When** physical validation is requested, **Then** the existing Feature 012 evaluator receives the plan unchanged and returns its normal settled or diagnostic report.
2. **Given** the bidder objective and the resulting realized settlement, **When** both are displayed, **Then** they have distinct names, meanings, units, and fingerprints and are not asserted to be numerically equal.
3. **Given** the optional caller-installed reference activation CSV, **When** the researcher explicitly selects the complete 2023-06-18 replay, **Then** the native and pinned schedules can be evaluated by the same Feature 012 external-reference workflow without the bidder reading activation during plan construction.
4. **Given** the external activation CSV is absent, **When** routine or optimization-parity validation runs, **Then** all required checks still complete offline and no implicit acquisition is attempted.

---

### User Story 6 - Reproduce And Diagnose Solves Offline (Priority: P2)

As a maintainer, I need stable inputs, results, diagnostics, and dependency
boundaries so that routine validation is reviewable on an ordinary CPU machine
without commercial licenses, network access, or the reference runtime.

**Why this priority**: Reproducibility and dependency isolation are required for
the bidder to become shared research infrastructure.

**Independent Test**: A clean offline checkout can run equation oracles, paired
bounded formulations, required open-source small solves, normalized-fixture
contract checks, import-boundary checks, and Feature 012 compatibility tests
twice with stable semantic results. The complete reference solve remains an
explicit research/release benchmark.

**Acceptance Scenarios**:

1. **Given** an ordinary offline CPU environment with the required project dependencies, **When** routine validation runs, **Then** no network, credentials, Julia process, Gurobi license, external activation data, `baselines/*` runtime read, or legacy import is required.
2. **Given** a solve that is optimal, feasible with an accepted incumbent, infeasible, unbounded, interrupted, timed out, or failed, **When** its result is reported, **Then** status, available objective and bound, gap, slack evidence, solver identity, versions, termination reason, and ordered diagnostics remain internally consistent.
3. **Given** identical semantic inputs expressed in deterministic order, **When** their problem and result fingerprints are generated repeatedly, **Then** the fingerprints are identical and exclude volatile runtime duration from semantic identity.
4. **Given** an unavailable or incompatible required routine solver, **When** a solve is requested, **Then** it fails actionably rather than silently substituting an unvalidated backend.

### Edge Cases

- The problem does not use the exact public v1 grid of one ordinary 24-hour delivery day, 96 quarter-hour planning intervals, 24 hourly energy-price intervals, and six four-hour FCR-price intervals, or those intervals are incomplete, duplicated, out of order, overlapping, or misaligned; it is rejected rather than resampled or generalized.
- A daylight-saving transition produces 23 or 25 local hours; the initial reference profile rejects it rather than stretching or truncating the 24-hour contract.
- Battery power, stored-energy, efficiency, initial-state, or terminal parameters are non-finite, have invalid units, violate their bounds, or imply an invalid centered target.
- Activation budgets are negative, exceed their horizon or recovery window, use incompatible units, or do not reproduce the declared derived horizon budget.
- Prices are negative, zero, or tied across intervals; valid negative prices remain supported and tied optima are not assumed to have unique schedules.
- A reserve decision is negative, an energy or reserve decision is missing, or schedule extraction would create gaps or overlaps.
- The solver returns a feasible incumbent at a limit without proving optimality; the result distinguishes objective, best bound, and gap, emits no deployable plan by default, and permits one only when the caller explicitly opted in before the solve and all deployability checks pass.
- A nominally successful restriction solution has any feasibility slack or independently checked constraint residual above absolute `1e-6` in its canonical unit; no robust-labelled deployable plan is emitted.
- A relaxation solution happens to replay successfully for one activation trace; this does not promote it to a robustly deliverable plan.
- The rounded Julia fixture lies near a constraint boundary or produces adjacent rounded objectives; comparison performs one joint feasibility and objective certification over all recorded decision intervals and retains unavailable evidence rather than treating displayed values as exact or widening the internal solver tolerance.
- Native and reference objectives match but decisions differ; alternative-optimum compatibility is unavailable unless both common feasibility and common objective-equivalence evidence pass.
- Runtime duration, host paths, temporary solver names, or log ordering differ across runs; these volatile details do not change semantic fingerprints.
- The optional exact backend or external activation CSV is unavailable; optional evidence is skipped actionably while routine validation remains complete.
- The explicit full-reference benchmark reaches its configured resource limit; it reports its incumbent, bound, gap, and incomplete comparison evidence without converting the benchmark into a routine-CI failure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST expose a reusable single-day robust-bidding capability that consumes validated producer-visible inputs and returns immutable solve evidence plus, when eligible, an existing Feature 012 fixed plan.
- **FR-002**: The public problem contract MUST identify its schema and semantics version and contain battery power and stored-energy bounds, efficiencies, initial stored energy, terminal rule, prices, time contract, information cutoff, uncertainty profile, solve policy, units, sign convention, provenance, and complete input fingerprints.
- **FR-003**: The Feature 013 public v1 contract MUST accept only one ordinary 24-hour horizon containing exactly 96 consecutive quarter-hour planning intervals, 24 consecutive hourly energy-price intervals, and six consecutive four-hour FCR-price intervals; every other horizon, resolution, or block duration MUST be rejected without resampling or inference.
- **FR-004**: Bid selection inputs MUST exclude realized activation samples, realized activation fingerprints, expected replay results, realized settlement, and any other information unavailable at the declared decision cutoff.
- **FR-005**: The feature MUST define the horizon-wide activation-budget set and recovery-window activation-budget set as distinct immutable concepts with their own parameters, units, validation, semantic versions, and fingerprints.
- **FR-006**: The horizon-wide budget derivation MUST be explicit and testable; the reference values of a 24-hour horizon, 0.25-hour exact-window budget, and 2.25-hour recovery window MUST derive a 2.75-hour non-intraday horizon budget.
- **FR-007**: The feature MUST represent and validate the fixed mapping from 24 hourly energy blocks and six four-hour FCR blocks to all 96 quarter-hour planning intervals without accepting configurable block durations, inferring missing intervals, or changing resolution.
- **FR-008**: The feature MUST preserve the reference robust equations for pointwise power headroom, efficiency-dependent stored-energy protection, terminal stored energy, uncertainty-budget dualization, formulation-specific case handling, and feasibility slack, with exact source citations.
- **FR-009**: The feature MUST provide separate restriction and relaxation formulation profiles and MUST identify the restriction as the lower objective and the relaxation as the upper objective for the maximization problem.
- **FR-010**: The restriction and relaxation MUST use the same validated physical inputs, prices, uncertainty profile, time mapping, terminal rule, objective definition, and solve tolerances when their bounds are compared.
- **FR-011**: Only a restriction result with an accepted solve status, a complete decision vector, no validation errors, and every deployability slack and independently checked constraint residual no greater than absolute `1e-6` in its canonical unit MAY emit a robust-labelled fixed plan. Proven optimality MUST be the default accepted status; a feasible incumbent without proven optimality MAY emit a plan only when the caller explicitly selected that policy before solving.
- **FR-012**: A relaxation result MUST NOT emit or masquerade as a robustly deliverable fixed plan, even when it contains complete decisions or happens to replay successfully against a particular activation trace.
- **FR-013**: Every eligible restriction plan MUST use the existing hourly `EnergyBaselineSchedule`, four-hour `FCRCapacitySchedule`, and `FixedFCRBidPlan` contracts rather than defining bidder-specific substitute schedules.
- **FR-014**: Public schedules MUST use the library's charge-positive battery-power convention; any private positive-discharge reference variables MUST be converted explicitly, without changing magnitudes or the non-negative meaning of symmetric FCR capacity.
- **FR-015**: A solve result MUST report formulation identity, solve and termination status, objective value, best bound, absolute and relative optimality gaps, accepted-incumbent status, component objective values, slack and residual evidence, solver identity and versions, configured tolerances and limits, schedule availability, ordered diagnostics, and semantic fingerprints, marking unavailable fields explicitly. For maximization, the absolute gap MUST be the tolerance-normalized non-negative `best_upper_bound - incumbent`; the relative gap MUST divide it by `max(abs(incumbent), abs(best_upper_bound), 1 EUR)`. Missing inputs or a bound below the incumbent beyond the declared objective-comparison tolerance MUST produce unavailable gaps and a structured inconsistency diagnostic rather than a fabricated value.
- **FR-016**: Semantic problem and result fingerprints MUST be deterministic, include every decision-relevant input, numerical-policy value, canonicalization version, and formulation version, and exclude volatile values such as wall-clock runtime and local filesystem location. Public decisions MUST use `solver-output-kw-1e-9-half-even-v1`: decimal round-half-even to `1e-9 kW` followed by signed-zero normalization; canonical audit MUST substitute only those decisions into the unchanged raw auxiliary witness and MUST NOT repair or re-optimize it. Other fingerprint-bearing numeric evidence, including objective, bound, and gap, MUST NOT be tolerance-rounded; repeated routine solves in one pinned backend environment MUST reproduce those serialized values exactly, and any distinct value MUST change the fingerprint even when a comparison would consider it numerically equivalent.
- **FR-017**: The ex-ante optimization objective MUST separately reconcile accepted day-ahead energy value, FCR capacity value, feasibility-slack penalty, and total objective and MUST NOT include realized activation-energy revenue or Feature 012 realized penalties.
- **FR-018**: Bidder objective values, solver bounds, and Feature 012 realized settlement values MUST retain distinct field names, meanings, lineage, and fingerprints.
- **FR-019**: Post-solve physical replay and settlement MUST use Feature 012's existing evaluation boundary and MUST NOT introduce a second bidder-owned battery transition, activation replay, or settlement implementation.
- **FR-020**: The feature MUST preserve Feature 012 plan validation, evaluation, settlement, comparison, report, and fingerprint behavior for existing manual, heuristic, robust-labelled fixed, and TPM-labelled fixed plans.
- **FR-021**: The feature MUST include deterministic equation-level oracles covering uncertainty-budget derivation, time-block mapping, pointwise power headroom, charging and discharging efficiency cases, stored-energy limits, terminal requirements, slack interpretation, and objective assembly.
- **FR-022**: Routine validation MUST include bounded paired restriction and relaxation cases, infeasible and non-deployable-slack cases, accepted-incumbent handling, repeatability, sign conversion, fixed-plan extraction, and normalized reference-fixture contract checks; it MUST NOT run the complete 2023-06-18 optimization by default.
- **FR-023**: For every paired accepted maximization solve, the feature MUST verify that the restriction objective does not exceed the relaxation objective beyond `max(objective_comparison_absolute_tolerance_eur, objective_comparison_relative_tolerance * max(abs(restriction_objective), abs(relaxation_objective), 1 EUR))`; public v1 defaults MUST be absolute `1e-6 EUR` and relative `1e-9`, stored and fingerprinted in the common solve policy.
- **FR-024**: An optional accepted exact result for the same small problem MUST be compared using the order restriction objective no greater than exact objective and exact objective no greater than relaxation objective; missing optional exact evidence MUST be reported explicitly.
- **FR-025**: The feature MUST include a small normalized, provenance-rich fixture derived from the pinned 2023-06-18 Experiment 2 result and sufficient, together with a separately supplied and fingerprinted native `RobustFCRSolvePolicy`, to reconstruct the single-day restriction problem and compare its recorded objective, bound, 24 energy decisions, and six FCR decisions without a runtime read from `baselines/*`. The fixture MUST NOT invent native or Julia tolerances that the source did not record.
- **FR-026**: The normalized reference fixture MUST record the pinned reference revision, source path and digest, generation or normalization command, formulation profile, source rounding, units, signs, time mapping, input values, expected values, field availability, and redistribution status.
- **FR-027**: Reference comparison MUST report field-level statuses that distinguish exact parity, source-precision compatibility, alternative-optimum compatibility, mismatch, and unavailable evidence.
- **FR-028**: A source-precision-compatible result MUST use intervals derived from documented input and output rounding and MUST certify the recorded Julia decisions jointly rather than as independent pointwise residual allowances; it MUST NOT relax the internal solver-feasibility tolerance or infer unsupported temporal detail.
- **FR-029**: Alternative-optimum compatibility MUST require the native schedule to satisfy the common formulation, one joint decision vector within all Julia rounding intervals to satisfy that formulation, and the native and interval-valued Julia objectives under one common objective definition to be equivalent within the declared source-precision bound and the native solve policy's objective-comparison tolerance; decision differences MUST remain visible. For an interval comparison, the relative scale MUST use `max(abs(native_objective), abs(source_interval_lower), abs(source_interval_upper), 1 EUR)` so the native equivalence band is fixed before certification.
- **FR-030**: A decision difference that lacks common feasibility evidence, common objective-equivalence evidence, or adequate source precision MUST be reported as a mismatch rather than attributed to solver choice.
- **FR-031**: The complete 2023-06-18 optimization comparison MUST be an explicitly selected research/release benchmark that runs offline without the external regulation CSV because realized activation is not an optimization input; it MUST NOT be part of routine CI.
- **FR-032**: A complete 2023-06-18 physical replay MAY use the existing explicit Feature 012 external-reference path only when the researcher selects it and supplies the validated activation CSV; absence of that file MUST NOT fail routine validation.
- **FR-033**: Routine production and validation paths MUST NOT import from `baselines/*` or `legacy/*`, start Julia, require a commercial solver or license service, access the network, inspect credentials, download data, or load the external activation CSV.
- **FR-034**: The repository's required open-source mathematical-programming workflow MUST solve the restriction and relaxation in routine validation while preserving lazy dependency imports and actionable missing-or-incompatible dependency failures.
- **FR-035**: A compatible licensed exact backend MAY provide optional small-case bilinear and cross-backend evidence, but its absence MUST NOT change the public restriction, relaxation, fixed-plan, or routine-validation contracts.
- **FR-036**: The migrated behavior and equations MUST cite the exact pinned sources listed under Reference Implementation Requirements; the publication MAY provide mathematical context but MUST NOT replace code-level provenance.
- **FR-037**: Rolling or multi-day backtests, previous-day state carry-over, intraday recourse, market-scenario generation, TPM fitting or bid selection, aFRR/mFRR bidding, degradation costs, live market-data acquisition, and full-history paper experiments MUST remain out of scope.

### Reference Implementation Requirements

- **Source paths**:
  - `baselines/robust_storage_bidding/code/01_datastruct.jl`
  - `baselines/robust_storage_bidding/code/02_model.jl`
  - `baselines/robust_storage_bidding/code/12.jl`
  - `baselines/robust_storage_bidding/results/02/2023-06-18.json`
- **Behavior to preserve**: Reference parameter meanings and units; positive-discharge source convention; 24/96/6 multi-rate indexing; non-intraday restriction and relaxation objective direction; robust power and stored-energy constraints; charging/discharging efficiency cases; horizon-budget derivation; terminal lower-bound rule; feasibility-slack penalties; Experiment 2 restriction inputs, objective, bound, and recorded schedules.
- **Behavior to improve or drop**: Runtime coupling to Julia, JuMP, Gurobi, global CSV tables, relative source paths, implicit source indexing, commercial-license-only routine execution, activation loading during the combined backtest script, and ambiguity between optimization objective and realized settlement are not preserved.
- **Parity evidence**: Hand-derived equation oracles; deterministic paired restriction/relaxation problems; a normalized fixture with source digests; field-level objective, bound, and 30-decision comparison; common feasibility and objective re-evaluation for alternative optima; optional licensed exact and external physical-replay checks.

### Key Entities

- **Robust FCR Bidding Problem**: One immutable, versioned ordinary-day decision problem on the fixed public v1 24/96/6 grid, linking the battery, initial and terminal stored energy, 24 hourly energy prices, six four-hour FCR prices, 96 quarter-hour planning intervals, information cutoff, uncertainty profile, objective policy, solve policy, units, provenance, and fingerprints. It never contains realized activation.
- **Horizon-Wide Activation Budget**: The non-intraday robust set limiting pointwise activation magnitude and total absolute activation duration over the full horizon; it records its budget, horizon, units, derivation lineage, and semantic identity.
- **Recovery-Window Activation Budget**: The exact-window set limiting absolute activation within each recovery window; it records the window budget, recovery duration, units, and the rule used to derive a covering horizon-wide budget.
- **Robust Formulation Profile**: The named restriction, relaxation, or optional exact interpretation of one common problem, including equation version, objective direction, deployability meaning, and formulation-specific tolerances.
- **Robust FCR Solve Result**: Immutable solver-neutral evidence containing status, objective, bound, gap, objective components, slack and residual evidence, decisions when available, deployability, diagnostics, versions, and fingerprints.
- **Deployable Robust Bid Plan**: An existing Feature 012 fixed plan produced only from an eligible restriction result, containing the existing energy and FCR schedules plus robust producer identity, decision cutoff, input fingerprints, objective, bound, solve status, and diagnostics.
- **Reference Restriction Fixture**: A small normalized artifact containing the input and output evidence needed to compare the 2023-06-18 native solve with the pinned Experiment 2 restriction result without using the reference repository at runtime.
- **Reference Optimization Comparison**: Field-level evidence comparing common inputs, objective, bound, all decisions, schedules, and feasibility with exact, source-precision-compatible, alternative-optimum-compatible, mismatch, or unavailable status. Source-rounded Julia decisions are represented by one joint interval-certification problem, not by independently tolerated point values.

### Dependency and Environment Requirements

- **Core dependencies**: Use the repository's existing required Pyomo and HiGHS optimization environment; no new unconditional core dependency is authorized by this specification, and dependency imports remain lazy at public package boundaries.
- **Optional dependencies**: A compatible licensed Gurobi environment may supply exact bilinear or cross-backend evidence. Julia and JuMP are fixture-generation or research-reference tools only and are never production or routine-test dependencies.
- **External services**: None for routine use. No network, credential, download, or license service is required for the open-source restriction and relaxation workflow.
- **External data**: The external regulation CSV is evaluation-only and optional. It is not needed for optimization or required reference-optimization parity.
- **Hardware assumptions**: Ordinary CPU-only research workstation or CI runner; no GPU, SLURM cluster, or specialized accelerator is required.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A researcher can submit one valid public v1 problem and receive either a fully evidenced solve result or an actionable non-solution report covering exactly 96 quarter-hour planning intervals, 24 hourly energy decisions, and six four-hour FCR decisions, with no missing or inferred blocks; 100% of problems using another grid are rejected before model assembly.
- **SC-002**: Every eligible restriction solve with all deployability slacks and independently checked residuals at or below absolute `1e-6` in their canonical units emits exactly one Feature 012 fixed plan whose 30 decisions, information cutoff, objective, bound, producer identity, diagnostics, and input lineage are inspectable; every ineligible restriction or relaxation emits zero deployable plans.
- **SC-003**: For 100% of paired accepted routine cases, the restriction objective is no greater than the relaxation objective within the declared numerical tolerance; wherever an accepted exact result is available, all three objectives satisfy the required bound order.
- **SC-004**: The reference profile derives 2.75 hours from the declared 24-hour horizon, 0.25-hour exact-window budget, and 2.25-hour recovery window in every supported serialization and calculation path.
- **SC-005**: When the explicit full-reference benchmark is selected, the normalized 2023-06-18 comparison assigns a status to the objective, bound, all 24 energy decisions, all six FCR decisions, and both schedule fingerprints, with zero unexplained fields and zero decision mismatches hidden as assumed solver degeneracy.
- **SC-006**: Any alternative-optimum-compatible comparison includes passing native feasibility, joint Julia rounding-interval feasibility, and common interval-valued objective-equivalence evidence; otherwise it is classified as a mismatch or unavailable.
- **SC-007**: At least one complete deployable restriction plan passes Feature 012 evaluation using the existing replay and settlement path, while its ex-ante objective and ex-post realized settlement remain separately identifiable and reconcilable in their own domains.
- **SC-008**: Two repeated routine solves and comparisons from identical semantic inputs in the same pinned backend environment produce exactly identical serialized objective, bound, gap, schedules, diagnostics, comparison statuses, and semantic fingerprints. Numerical tolerance is used to classify explicit comparisons, not to collapse distinct serialized values into one semantic identity.
- **SC-009**: All routine equation, bounded solve, extraction, normalized-fixture contract, Feature 012 compatibility, import-boundary, and offline-isolation checks complete without selecting the full-reference benchmark and without network access, credentials, Julia, a commercial license, `baselines/*` runtime access, or the external activation CSV.
- **SC-010**: A researcher can determine from one result, without consulting solver logs, whether a plan is deployable, whether optimality was proven, the best available bound and gap, whether any slack was used, which comparison evidence is available, and why any requested plan or parity claim was rejected.

## Assumptions

- The public v1 decision horizon is exactly one ordinary 24-hour delivery day with 96 quarter-hour planning intervals, 24 hourly energy decisions, six four-hour symmetric-FCR decisions, and no intraday adjustment decisions. Other grids and daylight-saving transition days are deferred to later rolling-study work.
- The exact-window parameters are retained even though the non-intraday formulation uses their derived horizon-wide covering budget; this preserves the distinction required for later causal intraday work.
- The restriction is the only deployable formulation in this feature. The relaxation is scientific bound evidence, and the exact bilinear formulation is optional validation evidence.
- The pinned 2023-06-18 result is a restriction result solved by the reference Gurobi workflow and records rounded objectives and schedules; exact native schedule equality may therefore be unavailable even when the native formulation is equivalent.
- The normalized reference fixture does not own a native solve policy and does not infer Julia tolerances. The benchmark caller supplies a complete `RobustFCRSolvePolicy`; the documented researcher-facing command uses `native-reference-benchmark-highs-v1` and reports its fingerprint separately from source provenance.
- The complete 2023-06-18 native optimization and Julia-result comparison is an explicit research/release benchmark because the pinned reference solve took about 1,071 seconds; routine CI validates the equations, bounded formulations, fixture contract, and comparison machinery without executing that full solve.
- A solver may select a different solution from a tied or numerically degenerate optimum. Such a result is not accepted merely because objectives look similar; the common feasibility and objective-equivalence requirements apply.
- The three-decimal Julia decisions represent documented rounding intervals. Compatibility is established only through a joint interval-aware feasibility and objective check; independent per-field tolerance checks are insufficient.
- Deployability uses an absolute `1e-6` threshold for each slack and independently checked constraint residual in its canonical unit. Solver feasibility tolerances, objective-comparison tolerances (absolute `1e-6 EUR`, relative `1e-9`), the `solver-output-kw-1e-9-half-even-v1` decision rule, and source-rounding precision are separately named and fingerprinted; none widens another.
- A feasible incumbent returned at a configured limit is always reportable but is non-deployable by default. It may become deployable only when the caller explicitly opted into incumbent acceptance before solving and every robust-feasibility condition passes; it must never be labelled proven optimal.
- Feature 012 remains the authority for physical replay, activation binding, settlement, daily metrics, diagnostics, and realized-result fingerprints.
- The existing required Pyomo and HiGHS dependencies are sufficient for routine restriction and relaxation validation, provided imports remain lazy. No new core dependency is expected.
- The pinned `baselines/robust_storage_bidding/` revision remains reference-only. Small normalized evidence may be committed under the library's test-fixture policy with complete provenance and redistribution status.
- Full historical backtesting and intraday recourse begin only after this single-day bidder and its reference comparison are validated.
