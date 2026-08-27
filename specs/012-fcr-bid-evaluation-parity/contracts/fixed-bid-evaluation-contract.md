# Fixed FCR Bid-Evaluation Contract

## Ownership

Control owns the identity and provenance of a fixed bid plan. Market adapters own
validation of market/reference inputs and construction of existing activation
traces. The simulator owns accepted-commitment preflight, battery physics,
delivery attribution, settlement selection, daily reporting, comparison, and
result fingerprints.

The bid producer never owns physical clipping or settlement, and the evaluator
never chooses or revises schedule values.

## Public Interface Shape

```python
build_fixed_fcr_bid_plan(
    *,
    plan_id: str,
    producer: BidPlanProducer,
    information_cutoff_utc: datetime,
    energy_schedule: EnergyBaselineSchedule,
    fcr_schedule: FCRCapacitySchedule,
    producer_input_fingerprints: Mapping[str, str],
    solve_status: str,
    objective: OptimizationMetric,
    objective_bound: OptimizationMetric,
    diagnostics: Sequence[PlanDiagnostic] = (),
    semantics_version: str = "oel.fixed-fcr-bid-plan.v1",
) -> FixedFCRBidPlan

evaluate_fixed_fcr_bid(
    request: FCRBidEvaluationRequest,
) -> DailyFCRBidEvaluationReport

diagnose_fixed_fcr_bid(
    request: FCRBidEvaluationRequest,
) -> InvalidFCRBidDiagnosticReplay
```

Focused module imports are required initially. Any package-root exports must use
the repository's lazy export map and preserve import-light behavior.

## Schedule Reference Rule

`FixedFCRBidPlan` receives the existing schedule objects and retains those
references. It does not accept raw interval arrays. Its serialized view contains
only:

```json
{
  "energy_schedule_ref": {
    "schedule_id": "...",
    "semantics_version": "...",
    "schedule_fingerprint": "..."
  },
  "fcr_schedule_ref": {
    "schedule_id": "...",
    "semantics_version": "...",
    "schedule_fingerprint": "..."
  }
}
```

Resolving a serialized plan requires caller-supplied schedules whose three
reference fields match. Interval values are never reconstructed from the plan.

## Information-Cutoff Rule

- Producer input lineage may contain only information available at or before
  `information_cutoff_utc`.
- Realized activation identity and reference expected outputs are forbidden in
  producer input lineage.
- The evaluator binds activation, realized market context, settlement profile,
  and expected fixture after receiving the frozen plan.
- Changing producer kind without changing any evaluation-relevant value cannot
  change the physical trace or settlement; it changes only identity/report
  lineage.

## Evaluation Request Gate

The request contains one plan, one battery, one existing activation trace, one
existing multi-rate contract, one market/accounting context, one explicit
settlement profile, optional penalty/terminal rules, tolerance, and optional
expected fixture.

Validation proceeds in stable order:

1. exact types, semantics versions, finite values, and fingerprint forms;
2. plan schedule object/reference integrity;
3. information-cutoff and activation-separation rules;
4. absolute period, timezone, and 24/6/96/8,640 coverage;
5. market price and accepted-bid reference alignment;
6. non-negative FCR capacity and battery parameter compatibility;
7. charge/discharge power headroom and accepted-commitment eligibility;
8. activation resolution/content and battery fingerprint recheck;
9. settlement-profile and optional comparison compatibility.

No gate fills, interpolates, clips, coerces, downloads, or consults a fallback.

Accepted-commitment eligibility is a static gate over schedule integrity,
battery compatibility, and bidirectional reserve power headroom. It does not
inspect the realized activation trajectory. Activation resolution, values, and
coverage are validated separately at evaluation time.

## One Physical Replay Rule

The evaluator and Feature 010 wrapper call the same internal physical replay
kernel. The kernel consumes validated schedules, activation, battery, time grid,
and tolerance and produces the existing sample/checkpoint/saturation meanings.

The Feature 010 adapter continues to:

- accept the existing `StackedServiceReplayRequest`;
- enforce its existing `MarketDataArtifact` volume and price references;
- call its existing default settlement;
- return the existing `StackedServiceReplayResult`; and
- produce unchanged trace and result fingerprints.

The reference adapter supplies explicit reference price and accepted-bid evidence
without claiming that those values are A44/A81 observations. The adapters may not
fork battery equations or delivery attribution.

A plan that passes static accepted-commitment eligibility can still reach a
stored-energy bound under the realized activation trace. That dynamic saturation
remains a settled evaluation: activation-energy revenue uses delivered energy,
and only an explicit penalty rule charges non-delivery. A saturated run is
outside the initial reference-parity domain and returns unavailable comparison
evidence rather than a reference-compatibility claim.

## Result Discriminant

### Settled

A successful report contains the complete trace/reference, daily metrics,
selected settlement, lineage, ordered diagnostics, optional comparison, and all
applicable fingerprints.

### Validation Failed

A failed report contains plan identity, evaluation-input identity, ordered
validation diagnostics, and a result fingerprint. It contains no physical trace,
settlement, objective reinterpretation, component profit, or total profit.

The value `0.0` is never used as a substitute for unavailable failed-evaluation
economics.

### Diagnostic Replay

Diagnostic replay is a separate explicit function. Its result is labelled
`invalid_commitment_diagnostic`, includes the validation errors that made the plan
invalid, and is rejected by normal settlement/comparison APIs. It may expose
samples, tracking, and saturation only for investigation.

## Determinism

Identical semantic inputs produce identical:

- validation order and diagnostic order;
- replay sample and aggregate order;
- settlement component order;
- field-comparison order;
- canonical serialized bytes; and
- plan, input, trace, settlement, comparison, and result fingerprints.

No evaluator path reads wall-clock time, environment variables, credentials,
network state, a solver, `baselines/`, or `legacy/`.

## Compatibility Gates

- Existing Feature 010 schedules, request constructors, error cases, result
  payloads, fixture bytes, default settlement, traces, and fingerprints remain
  unchanged.
- Zero FCR preserves baseline-only replay and creates no activation revenue or
  penalty.
- Zero baseline yields zero day-ahead revenue while FCR capacity, delivered
  activation, tracking, and throughput remain visible.
- FCR requests reject Feature 011 aFRR/mFRR schedules and activation types.
- Package-root imports remain lazy; no Julia, solver, pandas, or baseline import
  is introduced into ordinary control/market/simulator imports.
