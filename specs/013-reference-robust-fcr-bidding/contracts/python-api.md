# Python API Contract: Robust FCR Bidding v1

## Package boundary

The stable user surface is resolved lazily from `open_energy_lab.control`.
Importing that package, `robust_fcr_bidding`, or `robust_fcr_reference` must not
load Pyomo, HiGHS, Gurobi, Julia, pandas, a baseline package, an artifact path,
network client, or credential provider. Pyomo and solver imports occur only
when a solve or joint certification is explicitly invoked.

The implementation adds no endpoint, CLI protocol, or persisted solve-result
format. Examples are thin callers of this Python API.

## Public symbols

The following symbols are public v1 contracts:

```python
from open_energy_lab.control import (
    ConstraintFamilyResidual,
    FeasibilityAudit,
    HorizonWideActivationBudget,
    JointReferenceCertificate,
    ObjectiveBreakdown,
    RecoveryWindowActivationBudget,
    RobustFCRBatteryParameters,
    RobustFCRBiddingProblem,
    RobustFCRBoundComparison,
    RobustFCRDecisions,
    RobustFCRFormulationProfile,
    RobustFCRPriceInputs,
    RobustFCRReferenceComparison,
    RobustFCRReferenceFixture,
    RobustFCRSolvePolicy,
    RobustFCRSolveResult,
    RobustFCRTimeContract,
    RobustFCRUncertaintyProfile,
    RobustFCRValidationError,
    RobustFCRSolverDependencyUnavailableError,
    RobustFCRSolverUnavailableError,
    TerminalStoredEnergyRule,
    build_robust_fcr_reference_problem,
    build_robust_fcr_bidding_problem,
    build_robust_fcr_time_contract,
    compare_robust_fcr_bounds,
    compare_robust_fcr_reference,
    derive_non_intraday_horizon_budget,
    load_robust_fcr_reference_fixture,
    solve_robust_fcr_bid,
)
```

All data classes are frozen and use tuple/read-only mapping fields. Their
`to_dict()` methods return detached JSON-compatible values, ISO-8601 UTC
timestamps ending in `Z`, declared units, semantic versions, and fingerprints.

## Construction contract

```python
def build_robust_fcr_time_contract(
    *,
    delivery_date: date,
    market_timezone: str,
    semantics_version: str = ROBUST_FCR_TIME_CONTRACT_VERSION,
) -> RobustFCRTimeContract:
    """Build an exact ordinary-day 24/96/6 partition or raise validation."""


def derive_non_intraday_horizon_budget(
    recovery_window: RecoveryWindowActivationBudget,
    *,
    horizon_hours: float = 24.0,
    semantics_version: str = HORIZON_WIDE_ACTIVATION_BUDGET_VERSION,
) -> HorizonWideActivationBudget:
    """Apply the versioned covering formula and retain derivation lineage."""


def build_robust_fcr_bidding_problem(
    *,
    problem_id: str,
    battery: RobustFCRBatteryParameters,
    time_contract: RobustFCRTimeContract,
    prices: RobustFCRPriceInputs,
    uncertainty: RobustFCRUncertaintyProfile,
    terminal_rule: TerminalStoredEnergyRule,
    solve_policy: RobustFCRSolvePolicy,
    information_cutoff_utc: datetime,
    producer_input_fingerprints: Mapping[str, str],
    provenance: Mapping[str, object],
    semantics_version: str = ROBUST_FCR_BIDDING_PROBLEM_VERSION,
) -> RobustFCRBiddingProblem:
    """Validate and fingerprint the complete producer-visible problem."""
```

Construction rejects:

- any non-ordinary or non-24/96/6 time contract;
- missing, overlapping, unsorted, resampled, or differently sized price data;
- invalid battery, terminal, uncertainty, cutoff, unit, or fingerprint values;
- a horizon budget inconsistent with its recovery-window derivation; and
- any serialized or lineage key indicating activation samples, expected replay,
  comparison/parity output, realized settlement, credentials, or external data.

Negative energy and FCR prices are valid. Negative FCR decisions are not.

## Solve contract

```python
def solve_robust_fcr_bid(
    problem: RobustFCRBiddingProblem,
    *,
    formulation: Literal["restriction", "relaxation", "exact"] = "restriction",
) -> RobustFCRSolveResult:
    """Solve one formulation and return complete solver-neutral evidence."""
```

Behavior:

1. Validate/fingerprint before importing the backend.
2. Use the problem's immutable solve policy; callers cannot toggle incumbent
   acceptance after termination.
3. Use HiGHS for routine restriction and relaxation. `exact` requires explicit
   compatible Gurobi selection and nonconvex mode; it never falls through to
   HiGHS.
4. Solve without implicit solution loading. Load values only if backend results
   contain a solver-confirmed incumbent.
5. Reject incomplete or non-finite incumbent values.
6. Independently recompute objective, variable bounds, binary integrality,
   slacks, and all named equation-family residuals in pure Python.
7. Negate private discharge-positive energy into the public charge-positive
   frame, retain non-negative FCR, and normalize those public decisions under
   `solver-output-kw-1e-9-half-even-v1`: create a decimal from each finite
   float's shortest round-trip representation, round-half-even to `1e-9 kW`,
   and normalize signed zero. Negate canonical energy back into private `x0`,
   substitute only those 30 decisions into the unchanged raw auxiliary
   witness, and re-audit without repair or re-optimization before schedule
   construction.
8. Populate `deployable_plan` only for an eligible restriction.

Missing/incompatible required Pyomo or HiGHS raises an actionable
`RobustFCRSolverDependencyUnavailableError`; an unavailable required HiGHS
execution raises `RobustFCRSolverUnavailableError`. An explicitly requested
optional exact backend may instead return structured `unavailable` evidence so
the restriction/relaxation result remains usable.

### Status invariants

| `solve_status` | Objective/decisions | Plan eligibility |
| --- | --- | --- |
| `optimal` | complete | restriction eligible after audit |
| `feasible` | complete incumbent | restriction eligible only with pre-solve opt-in and audit |
| `no_solution` | absent | never |
| `infeasible` | absent | never |
| `unbounded` | absent | never |
| `failed` | absent | never |
| `unavailable` | absent | never |

The result's normalized best bound is an upper bound for this maximization
problem. If a proven-optimal backend omits it, the objective may be used as the
bound with an explicit evidence code. A separate relaxation objective is never
substituted for that same-solve bound.

### Fixed-plan invariants

An emitted plan:

- is exactly Feature 012's `FixedFCRBidPlan`;
- has `BidPlanProducer.producer_kind == "robust"`;
- has 24 `EnergyBaselineSchedule` intervals with
  `power_kw = -internal_x0_kw` and `schedule_source="fixed"`;
- has six non-negative four-hour `FCRCapacitySchedule` intervals;
- uses `solve_status="optimal"`, or `"feasible"` only under the explicit
  incumbent policy;
- reports the ex-ante objective and same-solve best bound as
  `OptimizationMetric` values in EUR;
- uses safe input-lineage keys (`robust_problem`, `uncertainty_profile`,
  `market_prices`, and `solve_policy`); and
- references the separate solve-evidence fingerprint in a stable diagnostic.

No relaxation or exact result emits a plan, regardless of its physical replay.

## Bound comparison contract

```python
def compare_robust_fcr_bounds(
    restriction: RobustFCRSolveResult,
    relaxation: RobustFCRSolveResult,
    *,
    exact: RobustFCRSolveResult | None = None,
) -> RobustFCRBoundComparison:
    """Check compatible problem/profile identities and maximization bounds."""
```

The function requires the same problem and equation version. For accepted
values it verifies:

```text
restriction objective <= relaxation objective
restriction objective <= exact objective <= relaxation objective  # if exact
```

It requires identical absolute and relative objective-comparison values in the
solve policies. For objective values `a` and `b`, it accepts `a <= b` only when

```text
a <= b + max(
    objective_comparison_absolute_tolerance_eur,
    objective_comparison_relative_tolerance * max(abs(a), abs(b), 1 EUR),
)
```

Public v1 defaults are `1e-6 EUR` absolute and `1e-9` relative. The comparison
reports each inequality, allowance, and delta and marks missing exact evidence
`unavailable`. It does not relabel a relaxation result as a solver best bound
or a plan.

## Reference fixture contract

```python
def load_robust_fcr_reference_fixture(
    path: str | Path,
) -> RobustFCRReferenceFixture:
    """Load exactly the caller-selected local normalized optimization fixture."""
```

The loader validates
`robust-fcr-reference-fixture-v1.schema.json`, exact supported versions,
counts, units, signs, mappings, derivation, source digest, fixture fingerprint,
field availability, and redistribution declarations. It never searches for a
fixture, follows a download URL, reads `baselines/*`, reads the external
activation CSV, or invokes Julia/Gurobi.

Native reconstruction keeps source evidence and caller-owned execution policy
separate:

```python
def build_robust_fcr_reference_problem(
    fixture: RobustFCRReferenceFixture,
    *,
    solve_policy: RobustFCRSolvePolicy,
) -> RobustFCRBiddingProblem:
    """Reconstruct source inputs with one explicit native solve policy."""
```

The function never derives solver tolerances, incumbent policy, comparison
tolerances, or canonicalization from the Julia `solve_profile`. The returned
problem records both the fixture fingerprint and the separately supplied solve
policy fingerprint. The source's `not_recorded_source_defaults` declaration
remains unavailable evidence rather than being replaced by native values.

## Reference comparison contract

```python
def compare_robust_fcr_reference(
    fixture: RobustFCRReferenceFixture,
    native_result: RobustFCRSolveResult,
) -> RobustFCRReferenceComparison:
    """Compare native restriction evidence with the rounded Julia record."""
```

The comparison assigns a result to:

- optimization objective and source solver bound;
- each of 24 source-frame energy decisions;
- each of six FCR decisions;
- canonical energy, FCR, and combined decision-content fingerprints;
- native and source-specific Feature 012 schedule fingerprints; and
- native audit, joint reference feasibility, and objective equivalence.

Status values are `exact`, `source_precision_compatible`,
`alternative_optimum_compatible`, `mismatch`, and `unavailable`.

The comparison internally solves one certification restriction with all 30
source decisions simultaneously constrained to their closed three-decimal
rounding intervals. It also constrains the common objective to the intersection
of the recorded objective interval and the native equivalence band, and limits
all deployability slacks to `1e-6`. No pointwise displayed decision is treated
as an exact source value, and source solver proof/bound evidence is not inferred
from a primal feasibility certificate.

For the interval-valued objective, the native allowance is computed once as
`max(objective_comparison_absolute_tolerance_eur,
objective_comparison_relative_tolerance *
max(abs(native_objective), abs(source_lower), abs(source_upper), 1 EUR))`.
This fixed allowance constructs the native equivalence band; it never widens
the source interval or the `1e-6` feasibility threshold.

An ordinary Feature 012 plan or schedule fingerprint may differ solely because
it contains IDs and producer lineage. The comparison therefore reports those
fingerprints but uses canonical source-frame decision-content fingerprints to
decide numerical schedule equality.

## Feature 012 replay handoff

Feature 013 intentionally adds no replay wrapper. The supported flow is:

```python
solve_result = solve_robust_fcr_bid(problem, formulation="restriction")
plan = solve_result.deployable_plan
if plan is None:
    raise RuntimeError(solve_result.deployability_reasons)

# After bid acceptance and after realized activation becomes available:
evaluation_request = FCRBidEvaluationRequest(
    bid_plan=plan,
    # existing Feature 012 battery, market, accepted-bid, and activation inputs
)
evaluation_report = evaluate_fixed_fcr_bid(evaluation_request)
```

The bidder must not import or instantiate `RegulationActivationTrace`. The
caller binds accepted capacity evidence, realized activation, and settlement
context after plan selection. The optimization objective and evaluation
settlement retain distinct names and fingerprints and are never asserted equal.

## Fingerprint contract

Canonical serialization is UTF-8 JSON with sorted keys, compact separators,
preserved tuple order, finite numbers only, normalized UTC timestamps, and
normalized negative zero, followed by lowercase SHA-256. Solver decisions are
first canonicalized with `solver-output-kw-1e-9-half-even-v1`; other numeric
fields are not silently quantized by the JSON serializer.

Semantic result identity includes problem, formulation, solve request, solver
and backend versions, normalized status/termination, available objective and
bound, gaps, raw/canonical decision fingerprints, slacks, residuals, ordered
diagnostics, and canonical schedule-content identity. It excludes elapsed time,
host and filesystem paths, temporary names, raw log text/order, and the
`FixedFCRBidPlan` fingerprint to avoid circularity.

Within one pinned backend environment, repeated routine solves must reproduce
every fingerprint-bearing numeric value exactly. Objective-comparison
tolerances classify explicit inequalities and parity results only; they do not
round objective, bound, gap, residual, or slack values for serialization or
cause distinct payloads to share a fingerprint.

## Compatibility guarantees

- No Feature 012 public type or semantics version changes.
- No `open_energy_lab.planning` public type or solver behavior changes.
- Existing manual, heuristic, robust-labelled fixed, and TPM-labelled fixed
  plans continue to evaluate identically.
- Package-root imports stay clear of all solver and research stacks.
- Production and routine tests do not import from `tests`, `baselines`, or
  `legacy`.
