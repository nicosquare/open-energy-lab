# Phase 0 Research: FCR Rolling Backtest Parity

## 1. Package ownership and reuse boundary

**Decision**: Put rolling-study contracts and orchestration in
`open_energy_lab.control`, additive rolling optimization contracts beside
Feature 013, activation slicing in `open_energy_lab.market`, and segmented
evaluation in `open_energy_lab.simulator`. Feature 013 remains the only robust
bid optimizer and Feature 012 remains the only physical replay and settlement
implementation.

**Rationale**: Feature 013 already owns bid decisions, residual audits, solver
evidence, deployability, and conversion to Feature 012 plans. Feature 012 owns
the actual battery transition, requested/delivered power, saturation, and FCR
settlement. A deterministic orchestrator may connect those owners but must not
copy their equations. This also keeps the existing package import boundaries
and producer-neutral plan contract intact.

**Alternatives considered**:

- A second rolling simulator was rejected because it would create competing
  physical and settlement truth.
- Generalizing Feature 013's public daily problem to arbitrary horizons was
  rejected because it would weaken the governed exact 24/96/6 contract and
  change existing fingerprints.
- Keeping segmented replay in `control` was rejected because state transitions
  and settlement are simulator-owned behavior.

## 2. Executable, workbook, and paper profile identities

**Decision**: Give every profile a stable executable identity and store its
paper/workbook crosswalk separately. The five Feature 015 profile IDs are:

| Executable profile | Script/result | Behavior | Paper experiment | Workbook column |
| --- | --- | --- | --- | --- |
| `script-11-relaxation-reset-midnight-v1` | `11.jl` / `01` | relaxation, independent reset days | 1 | 11 |
| `script-12-restriction-reset-midnight-v1` | `12.jl` / `02` | restriction, independent reset days | 2 | 12 |
| `script-13-arbitrage-only-midnight-v1` | `13.jl` / `03` | no FCR, midnight carry-over | 4 | 14 |
| `script-14-restriction-rolling-0800-v1` | `14.jl` / `04` | restriction, 08:00 overlap | 5 | 15 |
| `script-15-restriction-rolling-midnight-v1` | `15.jl` / `05` | restriction, midnight carry-over | 3 | 13 |

**Rationale**: Current script behavior after `12.jl` is a permutation of the
paper numbering. Git history retains the descriptive former filenames;
`result_overview.xlsx` labels columns 11–19, while its semantic order follows
the paper rather than current scripts. The paper describes Experiment 3 as
midnight carry-over, Experiment 4 as no-FCR, and Experiment 5 as 08:00 rolling.
See [`11.jl` through `15.jl`](../../baselines/robust_storage_bidding/code/),
[`result_overview.xlsx`](../../baselines/robust_storage_bidding/results/result_overview.xlsx),
and the [paper experiment descriptions and Table A1](https://arxiv.org/pdf/2510.10856).

The bounded four-day rerun is therefore direct executable-profile evidence,
not Table A1 reproduction. Script 13 also retains the source default 3,600
second limit while the paper/workbook Experiment 4 profile reports 900 seconds.
Workbook throughput is not paper output: the parser computes charging input
times charging efficiency, whereas the paper's row is discharge-energy output.

**Alternatives considered**:

- Calling scripts 13–15 paper Experiments 3–5 was rejected as factually wrong.
- Renaming profiles only by paper number was rejected because implementation
  behavior is sourced from the executable scripts.
- Claiming Table A1 parity from four days was rejected because the table is a
  full-history aggregate and contains a distinct energy metric.

## 3. Date ordering, roles, and continuity

**Decision**: A manifest stores one ordered date sequence and classifies every
date independently as `included`, `warm-up`, `close-out`, or `excluded`, plus
a comparison-eligibility flag and reason. Coupled profiles use the previous
*listed* date to reproduce source behavior. Any caller-supplied resume state
after a gap starts a new continuity segment and cannot repair or imply parity
across the missing chain.

**Rationale**: `code/05_dates.txt` contains 1,453 ordered dates and excludes
eight European DST days. The source drivers use the previous listed line, not
calendar adjacency, so a source-compatible profile carries across those gaps.
Keeping role, execution, lifecycle, and comparison eligibility separate avoids
silently dropping warm-up, close-out, failed, or unfinalized days.

**Alternatives considered**:

- Requiring calendar-adjacent dates was rejected for the source profile because
  it would alter executable behavior; a future stricter profile can be added.
- Omitting warm-up and close-out records was rejected because it hides the
  predecessor and successor evidence required by rolling finalization.

## 4. Ordinary, arbitrage-only, and 08:00 optimization frames

**Decision**: Ordinary restriction, relaxation, and midnight carry-over days
call Feature 013's existing daily solver. Add a rolling-only formulation
request for exact-zero-FCR and 08:00 overlap while sharing private normalized
equations, audit, extraction, and solver adapters with Feature 013.

For the 08:00 source case:

```text
K_lower = round((8 - 24) / 0.25 + 1) = -63
quarter-hour indices = -63 ... 96        (160 values / 40 hours)
hourly x0 indices = -15 ... 24           (40 values)
four-hour xr indices = -3 ... 6          (10 values)
fixed predecessor x0 = prior hours 09 ... 24
fixed predecessor xr = prior blocks 3 ... 6
```

The 40-hour objective includes the fixed predecessor tail. Comparisons either
use the same full objective or subtract an identically reconstructed fixed
constant from both sides. The no-FCR source branch has a 24-hour hourly model,
no `xr` variable, and later injects six zero values for output compatibility;
native code must fix every FCR capacity decision exactly to zero at model
level.

**Rationale**: These are the executable equations in
`code/02_model.jl:15-32,34-75,86-99,137-143,175-188,252-263,289-291`.
They cannot be represented as a normal Feature 013 problem, and zeroing prices
does not constrain FCR capacity to zero.

**Alternatives considered**:

- Solving two independent 24-hour problems for the 08:00 profile was rejected
  because it loses robust propagation through the fixed predecessor tail.
- Reconstructing the 40-hour model in the orchestrator was rejected because
  it would duplicate Feature 013 equations.
- Using zero FCR prices for the arbitrage-only profile was rejected because
  zero-price reserve may still be selected under degeneracy.

## 5. Accepted plans and immutable 08:00 finalization

**Decision**: Preserve the predecessor's original full-day
`FixedFCRBidPlan`. The successor solve fixes the already accepted 08:00–24:00
tail; it does not revise that plan. Store original, provisional, and finalized
*evaluation* evidence as append-only revisions in one date envelope.

The 08:00 workflow is:

1. Bootstrap the first date with the source's effective midnight solve and
   mark it initialization-only where applicable.
2. Evaluate the accepted plan from 00:00 to 08:00 through Feature 012.
3. Record the cutoff checkpoint and apply the declared three-decimal source
   handoff policy.
4. Build the successor 40-hour request with predecessor decisions fixed.
5. Evaluate the unchanged predecessor tail from rounded cutoff state through
   Feature 012 and finalize that date.
6. Keep the last delivery date unfinalized until a successor close-out solve
   exists; never include it silently in complete parity aggregates.

**Rationale**: `code/03_backtest_save.jl:9-58,164-193` replays segments and
then mutates only part of the predecessor JSON. That produces mixed-provenance
evidence and loses the original. Immutable revisions preserve both states and
make the close-out dependency explicit.

**Alternatives considered**:

- A composite plan was rejected because no market decision changes.
- Mutating one date result in place was rejected because it obscures what was
  known before and after the successor.
- Treating the final bounded date as finalized was rejected because no later
  solve closes it.

## 6. Feature 012 cutoff replay and causal isolation

**Decision**: Add a simulator-owned segmented-evaluation API that slices an
accepted fixed plan and activation trace to an exact half-open period and calls
the public Feature 012 evaluator for each segment. It creates a fresh battery
component from an immutable binding, returns the final public replay
checkpoint, and deterministically reconciles segment metrics/fingerprints.
No optimizer object receives a `RegulationActivationTrace`.

**Rationale**: Feature 012 already evaluates any exactly aligned plan/time/
activation period. It lacks a public activation subset operation and a
composite segmented report, but does not need new physics. A guarded causal
test can provide two activation traces identical through 08:00 and different
afterward; the next bid and cutoff state must remain identical. Another guard
will raise if orchestration attempts post-cutoff trace access.

Feature 013 prices use EUR/kWh while Feature 012 energy settlement expects
EUR/MWh. The adapter multiplies explicitly by 1,000 and records the conversion.
Both use charge-positive public power.

**Alternatives considered**:

- Reimplementing the battery transition for a cutoff was rejected as duplicate
  physics.
- Passing a full-day trace and promising not to inspect the tail was rejected
  because causality should be structurally enforced by the sliced object.
- Approximating the 08:00 state from schedule energy was rejected because it
  ignores tracking, saturation, and efficiency behavior.

## 7. State handoff and rounding policies

**Decision**: Store both the full-precision replay checkpoint and the carried
value, with policy and fingerprints. Use Decimal round-half-even to three
decimal kWh from `Decimal(str(value))`, normalize signed zero, and validate the
closed rounding interval. The source-compatible 08:00 profile permits only
`source_three_decimal`; midnight carry-over supports that policy and
`native_full_precision` as separate manifest identities.

**Rationale**: `bt_simulation` rounds `soc_bid` and `soc_terminal` to three
decimals before the next `CaseData.y0`, while overlapping decisions remain live
unrounded solver values. Full precision is scientifically useful for native
studies but cannot claim later source trajectory parity. The coupled
successor's initial state is the realized Feature 012 handoff, not the robust
model's terminal proxy. A state link records modeled terminal and realized
handoff reconciliation separately.

**Alternatives considered**:

- Globally rounding solver decisions was rejected because the source does not
  do so in memory.
- Treating modeled terminal energy as realized carry-over was rejected because
  the source explicitly replays activation.
- One unlabeled numeric policy was rejected because rounded and full-precision
  chains have different semantics and fingerprints.

## 8. Acceptance, market evidence, and activation availability

**Decision**: Every manifest declares exactly one bid-acceptance policy. The
source-compatible policy fingerprints the assumption that optimizer-selected
bids are accepted. A future evidence-backed policy may identify individual bid
acceptance, but system-wide contracted reserve volume is always rejected as
individual acceptance proof. Activation descriptors belong in the manifest;
actual traces are supplied separately for evaluation only.

When activation is absent, independent profiles may still produce explicit
optimization-only records. Coupled profiles that require an activation-derived
handoff become `blocked_by_predecessor` unless a valid manifest-declared caller
state starts a new continuity segment.

**Rationale**: The available price and activation inputs are sufficient for
the stated study; no additional RTE or ENTSO-E document type establishes
individual acceptance. Keeping the assumption explicit prevents the simulator
from silently interpreting system volume as a participant award.

**Alternatives considered**:

- Assuming acceptance without an identity/fingerprint was rejected because it
  changes settlement applicability.
- Making activation a bidder input was rejected as future-information leakage.
- Failing all independent optimization when activation is absent was rejected
  because ex-ante evidence remains valid and distinguishable.

## 9. Solver, incumbent, and plan-classification policy

**Decision**: Preserve Feature 013's solver-neutral evidence and independent
residual audit. HiGHS remains required for routine cases; Gurobi remains
optional. Restriction plans are deployable only under Feature 013's existing
optimal or explicitly opted-in feasible-incumbent policy and tolerance audit.
Relaxation decisions may be converted to a diagnostic non-robust plan solely
for replay; they can never be labeled robustly deployable. The arbitrage-only
profile is exact because FCR is constrained to zero.

The historical source-continuation profile may feed a solver-confirmed,
independently feasible time-limit incumbent forward only under an explicit
fingerprinted policy. A native strict profile may stop instead; the two cannot
share a manifest or parity claim.

**Rationale**: Several source 08:00 and midnight rolling solves reached their
900-second limit with feasible incumbents and upper bounds, and the driver fed
them forward without status gating. Source JSON omits termination status; logs
provide it. `bilinear_violations=0` in restriction JSON is hardcoded and is not
feasibility proof. Some source residuals also exceed `1e-6`, so source
compatibility and native deployability must remain separate fields.

**Alternatives considered**:

- Treating all retained source results as optimal was rejected because logs
  contradict it.
- Automatically accepting every time-limit incumbent was rejected because it
  bypasses Feature 013's deployability policy.
- Calling relaxation schedules robust was rejected because the formulation is
  an upper bound, not a deliverability certificate.

## 10. Date records, failures, resume, and aggregates

**Decision**: Return one immutable envelope for every requested date in input
order. Revisions and terminal lifecycle statuses are explicit. Independent
profiles continue after a failure. Coupled profiles mark later dependent dates
blocked until a valid caller state starts a new continuity segment.

Resume requires exact agreement of:

- manifest and executable-profile fingerprints;
- ordered dates and all data/source descriptors;
- solver, numeric, rounding, settlement, and acceptance policies;
- every reused date-envelope and revision semantic fingerprint; and
- the last valid carried state, predecessor link, and continuity segment.

Aggregates identify eligible, contributing, and omitted dates with reasons;
they may be `complete` or `partial`, never zero-fill missing values, and keep
optimization objective, upper bound, settlement, profit, and throughput as
separate metrics. Runtime metadata remains reportable but is excluded from
semantic fingerprints and resume compatibility.

**Rationale**: The source parser silently skips absent files. That behavior
cannot support trustworthy completeness or restart evidence. Semantic identity
must also exclude machine-dependent runtime while retaining all inputs and
scientific results.

**Alternatives considered**:

- Resuming by date alone was rejected because it can mix solver/data policies.
- Dropping failed dates was rejected because it inflates aggregates.
- Treating a caller state as continuity with the blocked chain was rejected
  because no evidence connects the two segments.

## 11. Source precision and comparison outcomes

**Decision**: Compare fields independently, then derive an overall
`compatible`, `incompatible`, or `incomplete` class. Required field outcomes
are:

- `exact_displayed_decision_parity`
- `source_precision_compatible`
- `alternative_optimum_compatible`
- `source_incumbent_equivalent`
- `improved_feasible_incumbent_compatible_with_source_bound`
- `bound_incompatible`
- `mismatch`
- `unavailable`
- `incomplete_or_unfinalized`

For three-decimal source values, build closed intervals of half a displayed
unit and jointly certify one latent full-precision vector against the complete
formulation, objective interval, rounded state handoffs, and cross-day fixed
overlap. Endpoint inclusion follows Julia's recorded rounding policy. Exact
display equality is not feasibility proof.

For a maximization time-limit result:

- objective-equivalent audited decisions may be source-incumbent equivalent;
- a better audited incumbent no greater than the source upper bound may be an
  improved compatible incumbent;
- an objective above the allowed source bound is bound-incompatible; and
- `alternative_optimum_compatible` requires sufficient optimality and common
  feasibility evidence for both sides.

**Rationale**: The source JSON rounds decisions, objectives, bounds, state, and
results to three decimals and omits auxiliaries. In the 08:00 chain, successor
fixings came from unrounded in-memory predecessor decisions, which the artifacts
cannot reconstruct exactly. A joint latent certificate prevents individually
compatible scalars that have no single feasible realization from passing.

**Alternatives considered**:

- Scalar tolerance checks were rejected because they ignore coupled
  feasibility.
- Calling close objectives alternative optima was rejected for time-limited
  incumbents.
- Rebuilding exact fixings from displayed values was rejected because the
  source used different hidden values.

## 12. Normalized fixture and provenance

**Decision**: Create one strict Feature 015 fixture for five profiles by four
dates. A maintainer normalizer accepts an explicit source root and explicit raw
input manifest; it uses no glob discovery. It verifies every SHA-256 before
parsing, segments consolidated logs by exact run markers, reconciles JSON and
log fields, redacts license/machine material, and writes atomically only below
ignored `artifacts/`. Promotion to `tests/fixtures/fcr_rolling_backtest/` is a
separate reviewed action.

The fixture records:

- pinned revision `7e44738bb30e5c8204efe40103b9be4c2203685c`;
- exact source, 20 JSON, 11 log, input-descriptor, committed Manifest, Project,
  and workbook digests used;
- script/result/paper/workbook crosswalk and discrepancies;
- Julia 1.10.1 and runtime Gurobi 11.0.3 evidence, separately from README
  claims and committed package versions;
- log-derived termination/incumbent/bound evidence;
- rounded decisions, states, objective components, lifecycle, and unavailable
  fields; and
- precision, redistribution, and Feature 013 cross-reference metadata.

The new `results/02/2023-06-18.json` digest is retained as separate rerun
evidence. It is semantically compared with, but never replaces, Feature 013's
governed original fixture.

**Rationale**: Raw generated results/logs are untracked, mutable, and may
contain machine/license information. The normalized fixture must be small,
reviewable, offline, and sufficient to exercise comparison semantics without
silently upgrading evidentiary strength.

**Alternatives considered**:

- Committing raw logs and all JSON was rejected for redistribution, privacy,
  size, and reviewability reasons.
- Reading `baselines/*` directly in parity tests was rejected because routine
  validation must be isolated from mutable source artifacts.
- Expanding Feature 013's fixture was rejected because its governed single-day
  evidence and fingerprint must remain unchanged.

## 13. Validation and performance strategy

**Decision**: Validate at four levels:

1. Pure hand-calculable oracles for ordering, role selection, lower-index
   derivation, fixed overlaps, cutoff state, rounding, revision transitions,
   failure propagation, resume, and aggregate reconciliation.
2. Deterministic bounded Pyomo/HiGHS cases for every profile family,
   infeasibility, time-limit incumbent policy, repeated fingerprints, and
   restriction/relaxation ordering.
3. Authored multi-day replay exclusively through Feature 012, including causal
   twin traces, segment/full-day reconciliation, and daily/aggregate totals.
4. Direct normalized-source comparison; the complete four-date native solve is
   an explicit `reference_benchmark`, and optional activation replay is marked
   `external_reference_data`.

Routine performance tests assert deterministic operation counts, index/model
cardinalities, and linear date-orchestration growth rather than wall-clock
time. The complete four-day solve and full 2020–2024 resumable study are
research workflows, never acceptance gates.

**Rationale**: The 96- and 160-step robust formulations contain quadratic
triangular families and historical solves may run to 900 or 3,600 seconds.
Wall-clock thresholds would be nondeterministic and unsuitable for routine CI,
while bounded real solves still validate backend integration.

**Alternatives considered**:

- Running all bounded reference dates in routine CI was rejected because it
  exceeds the existing backend budget.
- Mock-only solver tests were rejected because they cannot validate Pyomo/
  HiGHS assembly and extraction.
- Wall-clock assertions were rejected because shared CI load is not scientific
  evidence.

## 14. Evidence limits

The feature will state these limits wherever results are presented:

- The four-day rerun validates bounded executable behavior, not published
  full-history Table A1 aggregates or published runtime.
- Raw source JSON/logs are generated, untracked rerun evidence; their digests
  are pinned by the normalizer but they are not upstream committed artifacts.
- Exact rolling restart is unavailable from JSON because unrounded predecessor
  decisions were not persisted.
- The final 08:00 delivery date is unfinalized without a later successor.
- Source JSON does not independently prove feasibility or optimality, and its
  restriction `bilinear_violations=0` field is not an audit.
- Source chains continued with time-limit incumbents; a stricter native policy
  may deliberately choose a different trajectory.
- Full-precision native carry-over is a useful OEL profile but not later-day
  source trajectory parity.
- Activation replay is unavailable unless the caller explicitly supplies the
  digest-matched external trace.

No unresolved research item remains.

## Source citation map for implementation

Implementation tests and migration documentation will cite these exact
behavior owners rather than a generic baseline directory:

| Source | Behavior used by Feature 015 |
| --- | --- |
| `baselines/robust_storage_bidding/code/01_datastruct.jl:3-48` | source sign convention, battery/uncertainty/time defaults, terminal target field, model kind, and 3,600-second default |
| `baselines/robust_storage_bidding/code/02_model.jl:15-32` | extended hourly indices and fixed predecessor energy overlap |
| `baselines/robust_storage_bidding/code/02_model.jl:34-75` | exact no-regulation hourly formulation |
| `baselines/robust_storage_bidding/code/02_model.jl:86-99,137-143` | reserve indices, non-intraday zero adjustment, and fixed predecessor reserve overlap |
| `baselines/robust_storage_bidding/code/02_model.jl:175-188,252-263,289-291` | propagated robust state bounds, full-frame objective/terminal rule, and lower-index derivation |
| `baselines/robust_storage_bidding/code/03_backtest_save.jl:5-83` | activation concatenation, predecessor-tail/current-day replay ordering, and cutoff replay |
| `baselines/robust_storage_bidding/code/03_backtest_save.jl:86-158` | ten-second physical replay, clipping, efficiency, market metrics, and three-decimal persisted states |
| `baselines/robust_storage_bidding/code/03_backtest_save.jl:161-204` | predecessor JSON finalization and the restriction `bilinear_violations` evidence limit |
| `baselines/robust_storage_bidding/code/04_parse_results.jl:4-39,43-100` | normalized field meanings, silent missing-file behavior to reject, and workbook aggregate formulas |
| `baselines/robust_storage_bidding/code/05_dates.txt:1-1453` | authoritative ordered full-history list and DST exclusions |
| `baselines/robust_storage_bidding/code/11.jl:23-95` | relaxation/reset parameters, independent invocation, result directory, and replay/save call |
| `baselines/robust_storage_bidding/code/12.jl:23-95` | restriction/reset parameters, independent invocation, result directory, and replay/save call |
| `baselines/robust_storage_bidding/code/13.jl:23-103` | sequential no-regulation profile, default time limit, state carry, and result directory |
| `baselines/robust_storage_bidding/code/14.jl:23-104` | sequential 08:00 restriction, 900-second limit, state/decision carry, and result directory |
| `baselines/robust_storage_bidding/code/15.jl:23-104` | sequential midnight restriction, 900-second limit, state carry, and result directory |

The normalizer's explicit input manifest supplies exact SHA-256 identities for
every generated bounded JSON and retained log used. The workbook is cited only
for the reconciled profile crosswalk and documented metric discrepancy; it is
not a runtime input or direct Table A1 oracle.
