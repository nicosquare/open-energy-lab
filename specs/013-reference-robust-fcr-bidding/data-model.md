# Data Model: Reference Robust FCR Bidding

All public values are frozen, deeply immutable, finite, versioned, and
serializable to canonical JSON. Tuples preserve interval order; mappings are
copied, key-sorted, and exposed read-only. Validation occurs before the private
solver boundary is imported.

## RobustFCRBatteryParameters

One battery's bidding-visible physical limits.

| Field | Type / unit | Validation |
| --- | --- | --- |
| `maximum_charge_power_kw` | float, kW | finite and greater than zero |
| `maximum_discharge_power_kw` | float, kW | finite and greater than zero |
| `minimum_stored_energy_kwh` | float, kWh | finite, non-negative, less than maximum |
| `maximum_stored_energy_kwh` | float, kWh | finite and greater than minimum |
| `initial_stored_energy_kwh` | float, kWh | within inclusive stored-energy bounds |
| `charge_efficiency` | float, dimensionless | `0 < value <= 1` |
| `discharge_efficiency` | float, dimensionless | `0 < value <= 1` |
| `semantics_version` | string | exact supported version |
| `battery_fingerprint` | SHA-256 | derived from all semantic fields |

The public power limits are magnitudes. The private source-frame lower power
bound is `-maximum_charge_power_kw`; its upper bound is
`maximum_discharge_power_kw`.

## RobustFCRTimeContract

The explicit ordinary-day multi-rate mapping.

| Field | Type | Validation |
| --- | --- | --- |
| `delivery_period` | `CanonicalInterval` | exactly 24 elapsed and local hours |
| `market_timezone` | IANA name | agrees with the canonical period |
| `planning_intervals` | 96 intervals | consecutive, ordered, gapless PT15M partition |
| `energy_intervals` | 24 intervals | consecutive, ordered, gapless PT1H partition |
| `fcr_intervals` | 6 intervals | consecutive, ordered, gapless PT4H partition |
| `planning_to_energy` | 96 integers | zero-based `k // 4`; each energy index occurs four times |
| `planning_to_fcr` | 96 integers | zero-based `k // 16`; each FCR index occurs 16 times |
| `semantics_version` | string | exact supported version |
| `time_contract_fingerprint` | SHA-256 | covers intervals, timezone, and mappings |

The first release rejects 23-hour and 25-hour local delivery days, arbitrary
UTC periods, alternate resolutions, missing or duplicate blocks, and inferred
resampling.

## RecoveryWindowActivationBudget

The exact-window set corresponding to source `gamma`/`Gamma`, but with
unambiguous names.

| Field | Type / unit | Validation |
| --- | --- | --- |
| `recovery_activation_budget_hours` | float, h | positive and no greater than window |
| `recovery_window_hours` | float, h | positive and aligned to the private formulation grid |
| `pointwise_activation_lower` | float | exactly -1 for v1 |
| `pointwise_activation_upper` | float | exactly +1 for v1 |
| `semantics_version` | string | identifies the recovery-window set |
| `recovery_window_fingerprint` | SHA-256 | all semantic values |

No realized activation samples, summary, or fingerprint belongs to this
entity.

## HorizonWideActivationBudget

The full-horizon set used by the non-intraday robust counterpart.

| Field | Type / unit | Validation |
| --- | --- | --- |
| `horizon_hours` | float, h | exactly 24 for public v1 |
| `horizon_activation_budget_hours` | float, h | non-negative and no greater than horizon |
| `derivation_rule` | string | exact supported covering rule |
| `recovery_window_fingerprint` | SHA-256 | points to the source window contract |
| `derivation_inputs` | immutable mapping | records horizon, window, and budget |
| `semantics_version` | string | identifies the horizon-wide set |
| `horizon_budget_fingerprint` | SHA-256 | fields and derivation lineage |

`derive_non_intraday_horizon_budget()` is the only public constructor from a
recovery-window set. For the reference profile it produces 2.75 hours from
24, 0.25, and 2.25 hours. An explicitly serialized value must exactly reconcile
under the versioned derivation rule; solver tolerance is not used here.

## RobustFCRUncertaintyProfile

Pairs one `RecoveryWindowActivationBudget` with its derived
`HorizonWideActivationBudget`. Validation requires matching lineage and time
horizon. Its fingerprint prevents either set from being substituted silently.

## TerminalStoredEnergyRule

| Field | Type / unit | Validation |
| --- | --- | --- |
| `minimum_terminal_stored_energy_kwh` | float, kWh | within battery energy bounds |
| `allow_penalized_shortfall` | bool | true for the migrated profile |
| `shortfall_penalty_eur_per_kwh` | float | finite and strictly positive |
| `rule_id` | string | non-empty |
| `rule_fingerprint` | SHA-256 | all fields |

The reference fixture stores the exact target
`53.327556325823224 kWh`; it must not be reconstructed from the rounded initial
state.

## RobustFCRPriceInputs

| Field | Type / unit | Validation |
| --- | --- | --- |
| `day_ahead_energy_prices_eur_per_kwh` | tuple[24] | finite; negatives and ties allowed |
| `fcr_capacity_prices_eur_per_kw_block` | tuple[6] | finite; negatives and ties allowed |
| `energy_interval_refs` | tuple[24] | one reference per time-contract interval |
| `fcr_interval_refs` | tuple[6] | one reference per time-contract interval |
| `price_input_fingerprint` | SHA-256 | values, units, intervals, and source refs |

No price is treated as activation or realized settlement. The FCR price is per
accepted kW for its four-hour block; it is not multiplied by four in the
objective.

## RobustFCRSolvePolicy

The immutable, pre-solve reproducibility and plan-eligibility policy.

| Field | Type | Validation / default |
| --- | --- | --- |
| `solver_name` | string | `highs` required routine; explicit `gurobi` optional |
| `time_limit_seconds` | float | finite and positive |
| `threads` | int | positive; default 1 |
| `random_seed` | int | default 13 |
| `primal_feasibility_tolerance` | float | positive and explicit |
| `dual_feasibility_tolerance` | float | positive and explicit |
| `mip_feasibility_tolerance` | float | positive and explicit |
| `relative_mip_gap` | float | non-negative and explicit |
| `objective_comparison_absolute_tolerance_eur` | float, EUR | finite and non-negative; default `1e-6` |
| `objective_comparison_relative_tolerance` | float | finite and non-negative; default `1e-9` |
| `allow_feasible_incumbent_plan` | bool | default false |
| `decision_canonicalization_id` | string | exactly `solver-output-kw-1e-9-half-even-v1` |
| `solve_policy_fingerprint` | SHA-256 | all semantic policy values |

The deployability threshold is not configurable here; public v1 fixes it at
absolute `1e-6` per canonical unit. Runtime duration is report metadata and not
part of this fingerprint. For two objective values `a` and `b`, the comparison
allowance is
`max(objective_comparison_absolute_tolerance_eur,
objective_comparison_relative_tolerance * max(abs(a), abs(b), 1 EUR))`.
Restriction, relaxation, and optional exact results can be ordered only when
their problem fingerprints therefore carry the same comparison policy. The
two comparison fields are configurable public inputs; values other than the
defaults remain valid when finite and non-negative. The fixed decision
canonicalization ID is the only non-configurable normalization choice in public
v1.

## RobustFCRBiddingProblem

The single aggregate producer-visible input.

| Field | Type | Rules |
| --- | --- | --- |
| `problem_id` | string | non-empty, stable caller identity |
| `semantics_version` | string | exact public v1 version |
| `battery` | `RobustFCRBatteryParameters` | required |
| `time_contract` | `RobustFCRTimeContract` | exact 24/96/6 |
| `prices` | `RobustFCRPriceInputs` | exact alignment |
| `uncertainty` | `RobustFCRUncertaintyProfile` | matching 24-hour horizon |
| `terminal_rule` | `TerminalStoredEnergyRule` | valid for battery |
| `solve_policy` | `RobustFCRSolvePolicy` | declared before solve |
| `information_cutoff_utc` | aware UTC datetime | no later than delivery start |
| `producer_input_fingerprints` | immutable mapping | lowercase SHA-256 values; decision-visible inputs only |
| `provenance` | immutable mapping | versioned origins and normalization lineage |
| `problem_fingerprint` | SHA-256 | every decision-relevant field above |

The constructor has no activation, expected result, comparison, parity,
realized settlement, credential, file-search, or external-CSV field. Unknown
serialized fields are rejected. When adapting lineage to Feature 012, safe keys
such as `robust_problem`, `uncertainty_profile`, `market_prices`, and
`solve_policy` are used because Feature 012 correctly rejects evaluation-only
terms in producer-input names.

## RobustFCRFormulationProfile

| Field | Type | Meaning |
| --- | --- | --- |
| `kind` | enum | `restriction`, `relaxation`, or optional `exact` |
| `equation_version` | string | pins translated equation families |
| `objective_sense` | string | always `maximize` |
| `deployability_role` | enum | `candidate_plan`, `upper_bound_only`, or `exact_evidence_only` |
| `source_refs` | tuple | exact Julia path/line declarations |
| `formulation_fingerprint` | SHA-256 | all semantic fields |

Only `restriction` has `candidate_plan`. The mixed-binary relaxation is never
promoted by replay success. Exact is isolated behind an explicitly selected
compatible Gurobi backend with nonconvex mode enabled.

## RobustFCRDecisions

The solver-neutral public decision vector.

| Field | Type / sign | Validation |
| --- | --- | --- |
| `energy_baseline_charge_positive_kw` | tuple[24] | finite |
| `fcr_capacity_kw` | tuple[6] | finite and non-negative |
| `canonicalization_id` | string | matches solve policy |
| `energy_decision_content_fingerprint` | SHA-256 | time/value content, no producer ID |
| `fcr_decision_content_fingerprint` | SHA-256 | time/value content, no producer ID |
| `decision_vector_fingerprint` | SHA-256 | both arrays, signs, units, mappings |

Raw discharge-positive solver values and auxiliaries belong to the private
solve witness and are fingerprinted separately. Before canonicalization,
private energy `x0` is negated into the public charge-positive frame; FCR `xr`
remains non-negative. Under `solver-output-kw-1e-9-half-even-v1`, each resulting
finite public kW decision is converted from its locale-independent shortest
round-trip decimal representation, quantized to `Decimal("0.000000001")` with
`ROUND_HALF_EVEN`, converted back to a finite float, and normalized from either
signed zero to `0.0`.

The canonical witness negates the 24 canonical charge-positive energy values
back into private discharge-positive `x0`, retains canonical `xr`, and
substitutes only those 30 values into the raw witness. All raw auxiliaries,
binaries, and modeled slacks remain unchanged, after which the independent
audit and objective reconciliation run again. Canonicalization never repairs,
projects, or re-optimizes a witness. A canonical residual or slack above
`1e-6` blocks plan extraction even when the raw witness passed.

## ObjectiveBreakdown

| Field | Unit | Reconciliation |
| --- | --- | --- |
| `day_ahead_energy_value_eur` | EUR | `delta_t * sum(p0 * x0)` |
| `fcr_capacity_value_eur` | EUR | `sum(pr * xr)` |
| `feasibility_slack_penalty_eur` | EUR | non-negative penalty amount |
| `total_objective_eur` | EUR | energy + capacity - penalty |
| `reconciliation_residual_eur` | EUR | absolute independent difference |

It contains no realized activation revenue, penalties, or Feature 012 profit.

## ConstraintFamilyResidual and FeasibilityAudit

`ConstraintFamilyResidual` records a stable family ID, relation, canonical
unit (`kW`, `kWh`, `EUR`, or dimensionless), checked count, maximum positive
violation, witness indices, and source equation refs.

`FeasibilityAudit` contains:

- all ordered constraint-family residuals;
- all named modeled slack values, including source-declared inert slacks;
- binary-integrality and variable-bound evidence;
- objective reconciliation evidence;
- raw-witness and canonical-witness fingerprints;
- `deployability_threshold = 1e-6`; and
- `passes_deployability_audit`.

The audit is computed by pure Python from extracted values. It does not query
Pyomo constraint residuals or use source-rounding bounds.

## SolverEvidence

| Field | Type | Notes |
| --- | --- | --- |
| `solve_status` | enum | `optimal`, `feasible`, `no_solution`, `infeasible`, `unbounded`, `failed`, `unavailable` |
| `termination_status` | enum/string | normalized cause, separate from solution status |
| `has_incumbent` | bool | true only for a solver-confirmed complete solution |
| `objective_value_eur` | optional float | incumbent value |
| `best_upper_bound_eur` | optional float | normalized maximization bound |
| `absolute_gap_eur` | optional float | tolerance-normalized non-negative `bound - incumbent` |
| `relative_gap` | optional float | `absolute_gap_eur / max(abs(incumbent), abs(bound), 1 EUR)` |
| `solver_name`, `solver_version` | strings | actual backend evidence |
| `pyomo_version`, `highspy_version` | optional strings | actual stack evidence |
| `configured_options` | immutable mapping | tolerances, seed, threads, limit |
| `model_cardinality` | immutable mapping | variables, binaries, constraints, index counts |
| `runtime_seconds` | optional float | non-semantic metadata |

Unavailable numeric evidence is `None` with a structured diagnostic; it is not
fabricated from other formulations. Let `raw_gap = best_upper_bound_eur -
objective_value_eur` and let `tau` be their objective-comparison allowance. A
non-negative raw gap is retained; a raw gap in `[-tau, 0)` is normalized to
zero with explicit normalization evidence. If either input is unavailable, or
if `raw_gap < -tau`, both gap fields are `None`; the latter case records a
`solver_bound_inconsistent` diagnostic instead of hiding the inconsistency.

## RobustFCRSolveResult

| Field | Type | Relationship |
| --- | --- | --- |
| `problem_fingerprint` | SHA-256 | exact solved problem |
| `formulation` | `RobustFCRFormulationProfile` | exact model kind |
| `solver` | `SolverEvidence` | normalized solve outcome |
| `raw_objective` | optional `ObjectiveBreakdown` | independently recomputed witness objective |
| `decisions` | optional `RobustFCRDecisions` | only for a complete accepted witness |
| `feasibility_audit` | optional `FeasibilityAudit` | required whenever an incumbent exists |
| `deployability_status` | enum | `eligible`, `blocked`, or `not_applicable` |
| `deployability_reasons` | ordered tuple | explicit policy/audit reasons |
| `deployable_plan` | optional `FixedFCRBidPlan` | exactly one only when eligible |
| `diagnostics` | ordered tuple | stable codes and evidence refs |
| `semantic_result_fingerprint` | SHA-256 | excludes runtime and plan fingerprint |
| `runtime_metadata` | immutable mapping | non-semantic duration/log summary |

The plan fingerprint is excluded from the solve-result fingerprint and the
solve-evidence fingerprint is referenced from a stable plan diagnostic. This
prevents a circular identity.

### Result state transitions

```text
validated problem
  -> assembled formulation
  -> solver outcome
     -> no incumbent -> terminal non-plan result
     -> complete incumbent
        -> independent raw audit
        -> canonicalize decisions
        -> independent canonical audit
        -> policy gate
           -> eligible restriction -> one FixedFCRBidPlan
           -> relaxation/exact or failed gate -> no plan
```

Eligibility requires all of:

1. restriction formulation;
2. complete finite incumbent;
3. `optimal`, or `feasible` with preselected opt-in;
4. every slack and residual no greater than `1e-6`;
5. successful objective reconciliation and sign conversion; and
6. complete deterministic Feature 012 schedule construction.

## RobustFCRReferenceFixture

The immutable parsed form of the JSON schema in `contracts/`. It contains
source provenance/digest, exact problem inputs, reference formulation,
three-decimal recorded decisions/objective/bound, source-rounding policy,
explicit unavailable fields, cross-reference to Feature 012 evaluation
evidence, redistribution status, and fixture fingerprint. It contains no
activation samples, runtime path, or native solve policy. A caller must supply
a complete `RobustFCRSolvePolicy` separately when reconstructing a native
problem. Its fingerprint is retained as native evidence and is never presented
as a recorded Julia setting.

## JointReferenceCertificate

Evidence from one auxiliary restriction feasibility problem:

- all 30 simultaneous decision intervals;
- intersection objective interval;
- maximum permitted deployability slack (`1e-6`);
- normalized solver outcome and residual audit;
- certificate fingerprint; and
- an unavailable reason when certification cannot be completed.

The certificate is not a deployable plan and never reads the external
activation trace.

## RobustFCRReferenceComparison

Contains ordered field results for the objective, source bound, 24 energy
decisions, six FCR decisions, decision-content fingerprints, producer-specific
schedule fingerprints, and feasibility evidence. Each field status is one of:

- `exact`;
- `source_precision_compatible`;
- `alternative_optimum_compatible`;
- `mismatch`; or
- `unavailable`.

It also records native feasibility, the joint reference certificate, objective
interval intersection, retained decision deltas, overall status, and a
comparison fingerprint. Status precedence follows the order above, except any
required mismatch makes the overall result `mismatch`; unavailable source
proof fields remain unavailable and do not become exact through inference.

## Feature 012 relationship

`RobustFCRSolveResult.deployable_plan` is the only optimizer-to-evaluator
object. After market acceptance, a caller supplies accepted-bid evidence,
settlement prices, battery component, and realized activation to the existing
`FCRBidEvaluationRequest`. The bidder never constructs
`RegulationActivationTrace`, never fabricates acceptance, and never owns a
battery replay or settlement transition.
