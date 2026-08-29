# Python API Contract: FCR Rolling Backtest Parity v1

## Package and dependency boundary

The stable study and optimization surface is lazily resolved from
`open_energy_lab.control`; activation slicing is resolved from
`open_energy_lab.market`; segmented replay is resolved from
`open_energy_lab.simulator`. Importing any package or pure-contract module must
not load Pyomo, HiGHS, Gurobi, pandas, Julia, a baseline package, an artifact
path, a network client, or a credential provider. Solver imports occur only
inside an explicitly requested solve.

Production and routine-test modules must not import from `tests`, `baselines`,
or `legacy`. The existing Feature 013 public types, behavior, 24/96/6
validation, and fingerprints remain unchanged.

## Public symbols

```python
from open_energy_lab.control import (
    AGGREGATION_POLICY,
    AcceptedBidPolicy,
    AggregateMetricEvidence,
    CallerSuppliedRollingState,
    ContinuitySegment,
    DeliveryDateClassification,
    DeliveryDateRecordEnvelope,
    FAILURE_POLICY_COUPLED,
    FAILURE_POLICY_INDEPENDENT,
    RESUME_POLICY,
    RobustFCRAcceptedDecisionFixings,
    RobustFCRRollingBiddingProblem,
    RobustFCRRollingSolveResult,
    RollingFCRBatteryBinding,
    RollingFCRDataDescriptor,
    RollingFCRDayInput,
    RollingFCRDayRevision,
    RollingFCRExperimentProfile,
    RollingFCRNumericPolicy,
    RollingFCRReferenceComparison,
    RollingFCRReferenceFieldResult,
    RollingFCRReferenceFixture,
    RollingFCRResumeEvidence,
    RollingFCRStateCarryEvidence,
    RollingFCRStateLink,
    RollingFCRStudyManifest,
    RollingFCRStudyResult,
    RollingFCRValidationError,
    aggregate_rolling_fcr_records,
    assess_rolling_fcr_resume,
    build_robust_fcr_rolling_problem,
    build_rolling_fcr_experiment_profile,
    build_rolling_fcr_study_manifest,
    compare_rolling_fcr_reference,
    derive_rolling_fcr_state_carry,
    extract_accepted_predecessor_fixings,
    load_rolling_fcr_reference_fixture,
    load_rolling_fcr_study_result,
    run_rolling_fcr_study,
    solve_robust_fcr_rolling_bid,
)

from open_energy_lab.market import slice_regulation_activation_trace

from open_energy_lab.simulator import (
    FCRAcceptedPlanSegment,
    FCRSegmentedEvaluationReport,
    build_accepted_plan_market_context,
    evaluate_fixed_fcr_bid_segments,
)
```

All data classes are frozen and deeply immutable. Public builders raise
`RollingFCRValidationError` before any solver or replay starts. Runtime and
solver log metadata are present in `to_dict()` but absent from semantic
fingerprints.

## Profile contract

```python
def build_rolling_fcr_experiment_profile(
    profile_id: Literal[
        "script-11-relaxation-reset-midnight-v1",
        "script-12-restriction-reset-midnight-v1",
        "script-13-arbitrage-only-midnight-v1",
        "script-14-restriction-rolling-0800-v1",
        "script-15-restriction-rolling-midnight-v1",
    ],
) -> RollingFCRExperimentProfile:
    """Return the fixed executable profile and explicit paper/workbook crosswalk."""
```

The returned contract carries behavior from the pinned executable, not an
inferred experiment label. Scripts 13, 14, and 15 crosswalk to paper
Experiments 4, 5, and 3 respectively. A profile is never described as Table A1
parity merely because this builder recognizes the crosswalk.

Profile invariants:

- script 11 is diagnostic relaxation, independent, reset at midnight;
- script 12 is restriction, independent, reset at midnight;
- script 13 is midnight-coupled arbitrage-only with FCR constrained exactly
  to zero;
- script 14 is restriction with the source bootstrap, 08:00 state handoff,
  and fixed accepted predecessor overlap;
- script 15 is restriction with midnight replay-state carry-over;
- only script 15 supports both source-three-decimal and native-full-precision
  carry policies; script 14 source parity requires three decimals.

`AcceptedBidPolicy.kind` is exactly `assumed_accepted` or
`evidence_backed_accepted`; there is no default. The assumption form carries a
fingerprinted statement that optimizer-selected bids are accepted and never
labels it observed market evidence. The evidence-backed form requires an
individual bid-award descriptor and fingerprint. Both reject system-wide
contracted reserve volume as individual acceptance evidence.

## Manifest construction

```python
def build_rolling_fcr_study_manifest(
    *,
    study_id: str,
    profile: RollingFCRExperimentProfile,
    dates: tuple[DeliveryDateClassification, ...],
    day_ahead_descriptor: RollingFCRDataDescriptor,
    fcr_capacity_descriptor: RollingFCRDataDescriptor,
    activation_descriptor: RollingFCRDataDescriptor,
    battery_binding: RollingFCRBatteryBinding,
    uncertainty_profile: RobustFCRUncertaintyProfile,
    terminal_rule: TerminalStoredEnergyRule,
    solve_policy: RobustFCRSolvePolicy,
    settlement_profile: str,
    acceptance_policy: AcceptedBidPolicy,
    numeric_policy: RollingFCRNumericPolicy,
    failure_policy: str,
    aggregation_policy: str,
    resume_policy: str,
    caller_state_declarations: tuple[CallerSuppliedRollingState, ...] = (),
    reference_lineage: Mapping[str, object] | None = None,
    semantics_version: str = ROLLING_FCR_STUDY_MANIFEST_VERSION,
) -> RollingFCRStudyManifest:
    """Validate and fingerprint one profile over one ordered date sequence."""
```

Construction rejects:

- zero or multiple profiles, duplicate/unsorted dates, or unsupported date
  roles;
- non-ordinary executed delivery days or inputs not mapping to 24/96/6;
- incompatible price, activation, battery, uncertainty, terminal, solver,
  settlement, acceptance, or rounding contracts;
- a source 08:00 profile without its warm-up/close-out semantics or with
  full-precision carry;
- system-wide contracted reserve volume offered as an individual bid award;
- any data/source fingerprint outside its declared role; and
- activation samples, replay output, settlement, comparison output, future
  states, paths, environment variables, or credentials in bidder-visible
  fields.

One manifest is one semantic profile. Comparing two carry policies means
building and running two manifests.

## State carry and accepted overlap

```python
def derive_rolling_fcr_state_carry(
    replay_checkpoint_kwh: float,
    *,
    state_carry_policy: Literal[
        "source_three_decimal",
        "native_full_precision",
    ],
) -> RollingFCRStateCarryEvidence:
    """Return the full-precision checkpoint, carried state, interval, and fingerprint."""


def extract_accepted_predecessor_fixings(
    *,
    plan: FixedFCRBidPlan,
    predecessor_problem_fingerprint: str,
    predecessor_result_fingerprint: str,
) -> RobustFCRAcceptedDecisionFixings:
    """Extract the unchanged 16 hourly and four reserve predecessor tails."""
```

Source-compatible carry uses `Decimal(str(value))`, three places,
`ROUND_HALF_EVEN`, positive-zero normalization, and the closed displayed-value
interval. Native carry preserves the exact value and a degenerate interval.
The two policies have distinct evidence fingerprints. Caller-supplied recovery
states are manifest declarations and continuity links, not an alternative
input accepted by this two-policy helper.

Accepted predecessor extraction never solves or replays. It retains the
accepted plan and predecessor problem/result fingerprints and maps exactly
hours 09–24 plus FCR blocks 3–6 for the 08:00 rolling request. The successor
builder verifies those values rather than permitting them to be re-optimized.

## Additive rolling optimization contract

```python
def build_robust_fcr_rolling_problem(
    *,
    problem_id: str,
    profile: RollingFCRExperimentProfile,
    current_time_contract: RobustFCRTimeContract,
    battery: RobustFCRBatteryParameters,
    current_prices: RobustFCRPriceInputs,
    uncertainty: RobustFCRUncertaintyProfile,
    terminal_rule: TerminalStoredEnergyRule,
    solve_policy: RobustFCRSolvePolicy,
    information_cutoff_utc: datetime,
    producer_input_fingerprints: Mapping[str, str],
    provenance: Mapping[str, object],
    predecessor_prices: RobustFCRPriceInputs | None = None,
    accepted_fixings: RobustFCRAcceptedDecisionFixings | None = None,
    predecessor_cutoff_utc: datetime | None = None,
    semantics_version: str = ROBUST_FCR_ROLLING_PROBLEM_VERSION,
) -> RobustFCRRollingBiddingProblem:
    """Build an exact-zero-FCR or 40-hour fixed-overlap request."""


def solve_robust_fcr_rolling_bid(
    problem: RobustFCRRollingBiddingProblem,
) -> RobustFCRRollingSolveResult:
    """Solve through Feature 013's shared private formulation/audit adapter."""
```

For `script-14-restriction-rolling-0800-v1`, construction requires:

- source planning indices `-63..96`, hourly indices `-15..24`, and FCR indices
  `-3..6`;
- exactly 16 fixed predecessor energy decisions corresponding to hours 09–24
  and four fixed reserve decisions corresponding to blocks 3–6;
- the predecessor price tail and state observed at previous-day 08:00;
- exact identity with the accepted predecessor plan; and
- no activation sample or future evaluation object.

For this profile, `battery.initial_stored_energy_kwh` is the source-rounded
realized checkpoint at previous-day 08:00—the start of the extended horizon.
The not-yet-observed current-day midnight state is represented by the robust
propagation through fixed predecessor decisions; it is not invented as an
ordinary daily-problem input. `current_time_contract` still identifies the
24-hour delivery day whose new decisions are extracted.

The complete 40-hour objective is reported with its fixed predecessor-tail
constant as a separate component. The returned current-day schedule remains
24 hourly and six four-hour decisions. It never changes the accepted
predecessor plan.

For `script-13-arbitrage-only-midnight-v1`, the model has 24 hourly decisions
and constrains every FCR decision exactly to zero. Zero FCR prices are not a
valid substitute.

The function shares Feature 013's lazy backend loading, status normalization,
decision mapping, independent residual audit, and semantic solver evidence.
Refactoring those private helpers must leave existing Feature 013 golden
fingerprints unchanged.

### Plan-classification invariants

| Formulation/result | Plan behavior |
| --- | --- |
| Audited eligible restriction | May emit robust-labelled `FixedFCRBidPlan` under Feature 013 policy |
| Audited feasible restriction incumbent | May emit only when the solve policy opted in before solving |
| Relaxation | May emit a diagnostic non-robust replay plan; never deployable |
| Arbitrage-only | May emit an arbitrage-only plan with all six FCR values exactly zero |
| No complete/audited incumbent | No plan |

## Accepted market context and segmented replay

```python
def build_accepted_plan_market_context(
    *,
    plan: FixedFCRBidPlan,
    period: CanonicalInterval,
    day_ahead_prices_eur_per_kwh: tuple[float, ...],
    fcr_capacity_prices_eur_per_kw_block: tuple[float, ...],
    acceptance_policy: AcceptedBidPolicy,
    source_fingerprints: Mapping[str, str],
) -> EvaluationMarketContext:
    """Build explicit individual-plan acceptance and converted price evidence."""


def slice_regulation_activation_trace(
    trace: RegulationActivationTrace,
    *,
    period: CanonicalInterval,
) -> RegulationActivationTrace:
    """Return an exact half-open, coverage-preserving trace subset."""


def evaluate_fixed_fcr_bid_segments(
    *,
    evaluation_id: str,
    plan: FixedFCRBidPlan,
    periods: tuple[CanonicalInterval, ...],
    market_contexts: tuple[EvaluationMarketContext, ...],
    activation_trace: RegulationActivationTrace,
    battery_binding: RollingFCRBatteryBinding,
    initial_stored_energy_kwh: float,
    settlement_profile: str,
    numeric_tolerance: float,
) -> FCRSegmentedEvaluationReport:
    """Slice and evaluate unchanged accepted-plan segments through Feature 012."""
```

`build_accepted_plan_market_context` adds a dedicated accepted-plan context; it
does not label assumed acceptance as a reference result or market-wide volume.
Day-ahead values are explicitly converted from EUR/kWh to EUR/MWh by
multiplying by 1,000. FCR block values are mapped to Feature 012's declared
capacity-settlement unit without interpreting contracted system volume as bid
acceptance.

Segmentation invariants:

1. Periods are ordered, contiguous, nonempty, and exactly partition the plan
   period selected for evaluation.
2. Each sliced plan keeps the original producer, solve, schedule lineage, and
   pre-delivery information cutoff.
3. Each sliced activation trace exactly matches its period and resolution.
4. A fresh Feature 012 battery is created per segment using the previous
   Feature 012 terminal checkpoint as the next initial state, after declared
   handoff rounding where required.
5. Every segment invokes the public Feature 012 evaluator; this API contains no
   battery transition, tracking, saturation, settlement, or profit equation.
6. The composite report checks state, additive metric, and settlement
   reconciliation and fingerprints every contributing Feature 012 report.

For causal 08:00 state derivation, callers supply only the prefix period and
prefix activation slice. Traces identical through the cutoff must yield the
same state link and successor bid even if all future samples differ.

## Study orchestration

```python
def run_rolling_fcr_study(
    manifest: RollingFCRStudyManifest,
    day_inputs: tuple[RollingFCRDayInput, ...],
    *,
    activation_traces: Mapping[date, RegulationActivationTrace] | None = None,
    resume_from: RollingFCRStudyResult | None = None,
) -> RollingFCRStudyResult:
    """Run the deterministic profile state machine in manifest date order."""
```

The orchestrator:

1. Validates all bidder-visible inputs and fingerprints before loading a
   solver or inspecting an activation mapping.
2. Reuses compatible resume envelopes after an exact semantic audit.
3. Emits one envelope for every requested date, including exclusions,
   failures, blocked dates, warm-up, and close-out.
4. Uses `solve_robust_fcr_bid` for ordinary restriction/relaxation days and the
   additive rolling solver only for no-FCR/08:00 needs.
5. Evaluates only accepted unchanged plans through the segmented/public
   Feature 012 path.
6. Passes no activation object or post-cutoff result to bid construction.
7. Applies the selected state-carry policy and records full-precision and
   carried state separately.
8. Continues independent profiles after failure; blocks coupled successors
   until a valid manifest-declared caller state starts a new continuity
   segment.
9. Finalizes 08:00 predecessor evidence only after its successor solve/replay
   and marks the terminal edge unfinalized when no successor exists.
10. Builds aggregate evidence without zero filling or dropping dates.

Every solved revision reports both absolute and relative gap plus volatile
runtime metadata. Every applicable input/problem/plan/activation/replay/
settlement/result fingerprint is either a SHA-256 value or explicit
`unavailable` evidence with ordered reasons. Every study result includes
status counts that reconcile exactly to its ordered envelopes.

Missing activation permits `optimization_only` evidence for independent
profiles. It blocks any coupled successor whose required state must be derived
from activation unless a valid caller state is declared.

## Resume, aggregation, and persistence

```python
def assess_rolling_fcr_resume(
    manifest: RollingFCRStudyManifest,
    prior_result: RollingFCRStudyResult,
) -> RollingFCRResumeEvidence:
    """Return ordered exact compatibility evidence; never partly approve a mismatch."""


def aggregate_rolling_fcr_records(
    manifest: RollingFCRStudyManifest,
    records: tuple[DeliveryDateRecordEnvelope, ...],
) -> tuple[AggregateMetricEvidence, ...]:
    """Aggregate declared contributors and retain every omission reason."""


def load_rolling_fcr_study_result(path: Path) -> RollingFCRStudyResult:
    """Validate schema, all nested fingerprints, and semantic identity."""
```

Resume rejects changes to the manifest, profile, ordered dates, any input/
source/activation descriptor, solve/numeric/rounding/acceptance/settlement
policy, reused envelope/revision, or terminal state link. Runtime-only
differences do not change semantic compatibility. A caller-supplied state
begins a new continuity segment and cannot certify the prior gap.

Aggregates report `eligible_dates`, `contributing_dates`, and
`omitted_dates_with_reasons` for every metric. `partial` values remain useful
but cannot support a complete-study parity claim. The persisted schema is
[fcr-rolling-study-result-v1.schema.json](./fcr-rolling-study-result-v1.schema.json).
Its top-level wire keys are `semantics_version`, `records`,
`aggregate_metrics`, the requested-input and supplied-activation fingerprint
maps, `stable_runtime_evidence`, `runtime_metadata`, and the remaining strict
study identity/lifecycle fields emitted by `RollingFCRStudyResult.to_dict()`.
It does not use the earlier design-only `schema_version`, `date_records`, or
`aggregates` names.

## Reference fixture and comparison

```python
def load_rolling_fcr_reference_fixture(
    path: Path,
) -> RollingFCRReferenceFixture:
    """Load the strict normalized fixture without resolving source artifacts."""


def compare_rolling_fcr_reference(
    *,
    manifest: RollingFCRStudyManifest,
    result: RollingFCRStudyResult,
    fixture: RollingFCRReferenceFixture,
) -> RollingFCRReferenceComparison:
    """Compare normalized source and native evidence under explicit policies."""
```

The loader accepts only the schema in
[fcr-rolling-reference-fixture-v1.schema.json](./fcr-rolling-reference-fixture-v1.schema.json),
recomputes its fingerprint, and rejects unknown semantic keys, malformed
digests, profile/date mismatches, and absent discrepancy declarations. It
never searches for raw JSON, logs, workbook, Julia, or activation data.

Comparison field outcomes are exactly:

```text
exact_displayed_decision_parity
source_precision_compatible
alternative_optimum_compatible
source_incumbent_equivalent
improved_feasible_incumbent_compatible_with_source_bound
bound_incompatible
mismatch
unavailable
incomplete_or_unfinalized
```

Field outcomes are authoritative. Overall compatibility is:

- `compatible` only when every mandatory field is compatible and required
  lifecycle evidence is complete;
- `incompatible` when at least one mandatory field has proven bound
  incompatibility or mismatch; and
- `incomplete` otherwise, including unavailable or unfinalized evidence.

The summary also retains the canonically ordered distinct evidence bases that
produced it; the compatibility class never replaces field outcomes.

`alternative_optimum_compatible` requires sufficient optimality and common
independent feasibility evidence for both vectors. Two time-limited incumbents
are never alternative optima merely because objectives are close. A better
audited incumbent may be compatible with a source time-limit result only when
it lies within the source upper bound under the declared tolerance.

Three-decimal source decisions are certified jointly as latent closed
intervals against formulation, objective, carry-over, and predecessor-overlap
constraints. For 08:00 chains, absent persisted unrounded fixings make exact
restart parity unavailable unless the joint cross-day certificate establishes
a common latent vector.

## Error and diagnostics contract

Validation errors are raised only before a date begins and identify the exact
field. Once study execution starts, per-date solver/replay failures become
ordered diagnostics and explicit `failed`/`blocked_by_predecessor` envelopes;
they are not discarded as exceptions unless process integrity is compromised.

Diagnostics use stable phase/code/severity/field/evidence references and sort
by declared phase, date order, code, and field. Human messages are not semantic
keys. Missing optional Gurobi, external activation, or full-history evidence is
reported as actionable `unavailable`, never as successful parity.
