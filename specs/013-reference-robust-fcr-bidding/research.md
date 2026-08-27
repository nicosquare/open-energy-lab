# Phase 0 Research: Reference Robust FCR Bidding

## 1. Package ownership and integration boundary

**Decision**: Implement Feature 013 in `open_energy_lab.control` with public
contracts in `robust_fcr_bidding.py`, reference evidence in
`robust_fcr_reference.py`, and private lazy solver/formulation modules. Reuse
Feature 012's schedule and fixed-plan types without changing their API. Replay
is a caller-selected second phase through
`open_energy_lab.simulator.fcr_bid_evaluation`.

**Rationale**: `control` already owns plan production, producer identity, and
the explicit conversion from source decisions to the library's schedules.
`simulator` owns the common physical and settlement environment. Feature 009's
`planning` surface is capacity-design and TPM specific, and its protected
solver behavior intentionally discards incumbents unless optimality is proven.
Feature 013 needs to retain a solver-confirmed feasible incumbent for explicit
opt-in review, so changing the existing adapter would be a regression.

**Alternatives considered**:

- A new `bidding` package was rejected because the existing Feature 012
  ownership already establishes plan production in `control`; a new root would
  split one bidder boundary without providing a second product family.
- `open_energy_lab.planning` was rejected because operational market bidding is
  not the capacity-design problem modeled there and its result/status contract
  is incompatible.
- `simulator` was rejected because optimizer ownership of replay or settlement
  would invalidate bidder-neutral comparison.

## 2. Public time and sign contract

**Decision**: Public v1 accepts exactly one ordinary 24-hour delivery day with
96 quarter-hour planning intervals, 24 hourly energy decisions, and six
four-hour FCR decisions. For one-based source interval `k`, use
`energy_index = ceil(k / 4)` and `fcr_index = ceil(k / 16)`. The private model
may use positive-discharge `x0`; public `RobustFCRDecisions` and the emitted
`EnergyBaselineSchedule` expose charge-positive values `-x0`. FCR capacity
remains non-negative and unchanged.

**Rationale**: The reference uses `K=96`, `delta_t=0.25`, and
`cst_reg_periods=16` in `code/12.jl:27-47`; its constraints and objective map
with `ceil(k*delta_t)` and `ceil(k/cst_reg_periods)` in
`code/02_model.jl:170-174,252-253`. Feature 012 already defines the
charge-positive public boundary. Exact fixed counts reject DST-transition days
and avoid unreviewed resampling.

**Alternatives considered**:

- A configurable public grid was rejected for v1 because it would expand the
  scientific claim beyond the pinned profile.
- Changing the library-wide sign was rejected because it would regress all
  existing battery and evaluator behavior.
- Publishing both sign conventions as peer decision arrays was rejected as
  ambiguous; the source-frame values remain private audit evidence.

## 3. Distinct uncertainty-set contracts

**Decision**: Represent the recovery-window set and horizon-wide set with two
different immutable classes. Derive the horizon activation budget with

```text
n = floor(horizon_hours / recovery_window_hours)
horizon_budget_hours =
    n * recovery_activation_budget_hours
    + min(
        horizon_hours - n * recovery_window_hours,
        recovery_activation_budget_hours,
      )
```

For 24, 0.25, and 2.25 hours this is 2.75 hours. Store the derivation rule,
inputs, result, version, and fingerprint; validate an explicitly supplied
horizon set against the derivation.

**Rationale**: Julia's `gamma` and `Gamma` fields are window quantities
(`code/01_datastruct.jl:8-9`, `code/12.jl:30-33`), while `compute_gammaK`
derives the full-horizon value (`code/02_model.jl:293-305`). Reusing one
ambiguous parameter would reproduce the source naming problem rather than its
mathematics.

**Alternatives considered**:

- One generic activation-budget class was rejected because it permits a
  window budget to be passed where the robust counterpart needs the derived
  horizon budget.
- Supplying only 2.75 hours was rejected because it loses lineage to the
  market-inspired recovery-window assumption.

## 4. Formulation translation

**Decision**: Translate the non-intraday mixed-binary models directly, with
fixed-zero intraday adjustment, common robust constraints, and named equation
families. Both restriction and relaxation remain MILPs. The relaxation omits
the exact bilinear constraint; the restriction adds the `v_res` classification
and two conservative `LambdaHigh` lower-bound families. Preserve the
reference's `lambdaHigh[l]` classification versus `lambdaHigh[k]` tightened
constraint indexing exactly.

Common source behavior includes:

- hard pointwise power headroom at `code/02_model.jl:170-174`;
- `alpha` and `beta` efficiency epigraphs at `code/02_model.jl:191-197`;
- lower and upper robust stored-energy counterparts at
  `code/02_model.jl:183-188`;
- diagonal upper-counterpart bounds at `code/02_model.jl:199-203`;
- binary disjunction and four common off-diagonal bounds at
  `code/02_model.jl:205-219`;
- exact bilinear relation at `code/02_model.jl:220-224`; and
- restriction-only classification and bounds at
  `code/02_model.jl:225-230`.

The public contract remains fixed at 96 steps. A private normalized model-data
type may assemble reduced, divisible grids for equation and real-solver tests;
it is not exported and cannot bypass public problem validation.

**Rationale**: The relaxation named by the feature is Julia's mixed-binary
`relax`, not its separate `lp_relax`. The formulations share the same physical
inputs and objective and therefore support the maximization bound order
`z_restriction <= z_exact <= z_relaxation`.

**Alternatives considered**:

- The source's `lp_restrict` and `lp_relax` variants were rejected as outside
  scope.
- Replacing the formulation with sampled activation scenarios was rejected
  because it changes both the uncertainty set and deliverability claim.
- Solving the 96-step historical model in routine CI was rejected because its
  triangular indices are `O(K^2)` and the source run records about 1,071
  seconds; routine tests use bounded internal profiles and routinely assemble,
  but do not solve, the public model.

## 5. Objective, terminal rule, and slack semantics

**Decision**: Maximize the common ex-ante objective

```text
day_ahead_value_eur
  = delta_t_hours * sum_k(day_ahead_price_eur_per_kwh[t(k)] * x0_kw[t(k)])
fcr_capacity_value_eur
  = sum_b(fcr_price_eur_per_kw_block[b] * xr_kw[b])
slack_penalty_eur
  = penalty_eur_per_kwh * sum(all modeled energy slacks)
objective_eur
  = day_ahead_value_eur + fcr_capacity_value_eur - slack_penalty_eur
```

Do not include realized activation-energy revenue. Preserve the terminal lower
bound `y0 - delta_t * sum(alpha) >= terminal_min - terminal_slack` from
`code/02_model.jl:254-263`. The reference profile uses the unrounded target
`53.327556325823224 kWh` and the separately rounded initial value
`53.328 kWh` (`code/12.jl:77-78`).

The literal source declares `symin`, `symax`, and two `syK` values and penalizes
all of them (`code/02_model.jl:86-101,252-253`). In the non-intraday branch,
`symin`, `symax`, and `syK[1]` are inert; only `syK[2]` relaxes a constraint.
Implementation must not add the inert slacks to the hard robust SOC constraints.
All declared slacks remain named audit evidence, and any value above `1e-6`
blocks deployment.

**Rationale**: `p0` is EUR/kWh and `pr` is EUR/kW per four-hour block after
conversion in `code/02_model.jl:337-356`; the `pr` comment in
`code/01_datastruct.jl:18-20` is incorrect. For the displayed reference
decisions, the reconstructed components are approximately EUR 0.167437 and EUR
10.860724, totaling EUR 11.028161 before output rounding. Feature 012's
realized total EUR 10.749 is a different ex-post quantity.

**Alternatives considered**:

- Rounding the terminal target to 53.328 was rejected because it changes the
  problem.
- Treating replay profit as the optimization objective was rejected because it
  introduces realized activation and conflates capacity value with settlement.
- Adding source-declared `symin/symax` to hard non-intraday constraints was
  rejected because it widens the feasible region.

## 6. Solver adapter, statuses, and incumbent policy

**Decision**: Add a dedicated private adapter using lazy `import_module`
loading and exact required versions `pyomo==6.10.1` and `highspy==1.15.1`.
Routine HiGHS solves use one thread, seed 13, explicit feasibility/MIP
tolerances, an explicit time limit, `tee=False`, and `load_solutions=False`.
The adapter normalizes independent solve and termination dimensions:

| Solve status | Typical termination | Decision handling |
| --- | --- | --- |
| `optimal` | `optimal` | Complete incumbent required |
| `feasible` | time/interruption/other limit | Retain only a solver-confirmed complete incumbent |
| `no_solution` | limit without incumbent or indeterminate | No decisions |
| `infeasible` | proven infeasible | No decisions |
| `unbounded` | proven unbounded | No decisions |
| `failed` | backend/execution error | No decisions |
| `unavailable` | optional exact backend absent | No decisions |

Default deployment requires `optimal`. A `feasible` incumbent can produce a
plan only when `allow_feasible_incumbent_plan=True` was fingerprinted before
the solve and all remaining audits pass. Model values are never read merely
because variables exist; the result must prove a solution is present before it
is loaded. For maximization, `best_bound` is normalized as an upper bound; the
fixed plan receives that same-solve bound, not the separate relaxation
objective.

**Rationale**: This preserves the user's explicit policy and avoids stale
values. The Feature 009 adapter is a useful version/options precedent but
returns on non-optimal termination without loading an incumbent, so it cannot
be reused directly.

**Alternatives considered**:

- Accepting all feasible incumbents was rejected because it weakens the
  default plan claim.
- Silently substituting another solver was rejected because it breaks
  reproducibility and required-backend evidence.
- Treating the relaxation objective as the restriction solver bound was
  rejected because they are different solves with different meanings.

## 7. Independent audit and deterministic identity

**Decision**: Extract the complete internal witness—market decisions,
auxiliaries, binaries, and modeled slacks—and evaluate it with pure Python code
that does not inspect Pyomo constraints. Report the maximum positive violation,
unit, and witness location for every equation family, binary integrality, and
every slack. Deployment requires every canonical-unit residual and slack to be
at most absolute `1e-6`.

Keep five numerical policies separate:

1. configured solver tolerances for search and termination;
2. the fixed `1e-6` deployability threshold for independent evidence;
3. native objective comparison with configurable, fingerprinted absolute and
   relative allowances whose public defaults are `1e-6 EUR` and `1e-9`;
4. public-decision canonicalization to `1e-9 kW` with decimal round-half-even;
   and
5. fixture source-rounding intervals for Julia comparison.

Retain raw extracted values for audit. Negate private discharge-positive `x0`
into public charge-positive energy and retain non-negative `xr`, then quantize
those public decisions under `solver-output-kw-1e-9-half-even-v1`: start from
each float's locale-independent shortest round-trip decimal representation,
quantize to `1e-9 kW` with decimal round-half-even, and normalize signed zero.
Re-audit by mapping canonical energy back to discharge-positive `x0` and
substituting only those 30 values into the raw witness while retaining all raw
auxiliaries, binaries, and slacks. Do not repair, project, or re-optimize the
canonical witness; a new violation blocks deployment. Stable
SHA-256 identities use finite, sorted, compact canonical JSON. Problem,
formulation, solve request, raw witness, canonical decisions, schedule content,
solve result, joint certificate, and comparison each have separate
fingerprints. Runtime, host paths, log text/order, and temporary names are
non-semantic metadata.

Decision canonicalization is the only tolerance-like normalization applied to
semantic numeric payloads. Within one pinned backend environment, repeated
routine objectives, bounds, gaps, residuals, and slacks must serialize exactly
the same. Comparison tolerances can classify two distinct values as equivalent,
but their distinct payloads and fingerprints remain distinct.

For native objective values `a` and `b`, compare with
`tau = max(configured_absolute_eur, configured_relative *
max(abs(a), abs(b), 1 EUR))`; the public defaults reduce to `max(1e-6 EUR,
1e-9 * max(abs(a), abs(b), 1 EUR))`. Paired results must carry identical
configured values. For a Julia objective interval, compute the relative scale
once from the native objective and both interval endpoints before constructing
the native equivalence band. This native allowance does not widen source
rounding intervals. Maximization gaps
use `best_upper_bound - incumbent`; gaps within `[-tau, 0)` normalize to zero,
while a more negative value yields unavailable gap fields and a structured
bound-inconsistency diagnostic. Relative gap divides an available absolute gap
by `max(abs(incumbent), abs(best_upper_bound), 1 EUR)`.

**Rationale**: Solver status alone is not deliverability evidence, and using
the Pyomo constraint expressions as the only audit would repeat the same
translation. Feature 012 schedule fingerprints contain IDs and lineage, so
cross-producer comparison also needs decision-content fingerprints in one
canonical positive-discharge comparison frame.

**Alternatives considered**:

- Trusting solver feasibility was rejected because formulation/extraction
  errors would go undetected.
- Comparing ordinary plan fingerprints across producers was rejected because
  valid lineage differences change those fingerprints.
- Including wall-clock duration in semantic identity was rejected because it
  makes repeated results unstable without adding mathematical evidence.

## 8. Reference fixture and evidence limits

**Decision**: Create a new strict
`oel.robust-fcr-reference-restriction.v1` fixture under
`tests/fixtures/fcr_bidding/`. It is self-contained for optimization
reconstruction and cross-references, but does not modify, Feature 012's
aggregate replay fixture. The fixture pins reference revision
`7e44738bb30e5c8204efe40103b9be4c2203685c`, generated-result SHA-256
`8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6`,
source paths, normalization command, exact problem inputs, formulation
profile, recorded values, source rounding, field availability, redistribution,
and semantic fingerprint.

The source fixture deliberately contains no native `RobustFCRSolvePolicy`.
Native reconstruction requires one as a separate caller-supplied input and
records its fingerprint without attributing its settings to Julia. The
researcher-facing benchmark uses the fully documented
`native-reference-benchmark-highs-v1` mapping; API callers may supply another
valid policy. This preserves the source's unavailable tolerance evidence while
keeping every native run reproducible.

The generated result is not tracked by the pinned submodule commit; it is
governed as digest-pinned derived evidence. It records objective and bound
11.028, 30 decisions rounded to three decimals, and duration 1070.788 seconds,
but not termination/primal/dual status, exact gap, unrounded variables,
constraint residuals, or actual runtime solver versions. Equal rounded
objective and bound is not upgraded to proof of optimality. The saved
`bilinear_violations=0` is also not restriction evidence because
`code/03_backtest_save.jl:197-204` runs that check only for relaxation profiles.

**Rationale**: Feature 012's loader enforces its exact aggregate section set and
its fixture lacks uncertainty and exact terminal inputs. Extending it would
change a stable evaluator contract while still mixing ex-ante and ex-post
evidence.

**Alternatives considered**:

- Reading `baselines/*` at runtime was rejected by the reproducibility and
  isolation requirements.
- Copying activation metadata into the optimizer fixture was rejected because
  activation is not a bidding input.
- Inferring source optimality or exact feasibility from rounded outputs was
  rejected as unsupported.

## 9. Joint source-precision and alternative-optimum comparison

**Decision**: Treat every three-decimal recorded decision as a closed
`displayed +/- 0.0005 kW` interval, intersect reserve intervals with
non-negativity, and treat the displayed objective/bound as separate closed
`+/- 0.0005 EUR` intervals. Build one auxiliary restriction MILP in which all
30 latent decisions are simultaneously bounded by their intervals, all common
equations and the exact fixture inputs apply, deployability slacks are at most
`1e-6`, and the objective lies inside its recorded interval. Feasibility is the
joint source certificate; 30 independent residual allowances are forbidden.

Comparison precedence is:

1. `exact` only where exact source evidence genuinely exists;
2. `source_precision_compatible` when native decisions lie in the recorded
   boxes and the joint certificate passes;
3. `alternative_optimum_compatible` when decisions differ, native feasibility
   passes, the joint source certificate passes with an objective interval that
   intersects the native equivalence band, and the native status is accepted;
4. `mismatch` when required common evidence fails; and
5. `unavailable` when the source never recorded the required field.

The source solver bound is metadata, not an expression of the latent decision
vector. Compare a native best bound with its rounding interval separately and
leave source proof status unavailable. The source code sets only solver choice,
nonconvex mode, console logging, and a 3600-second limit
(`code/02_model.jl:268-282`); its generated JSON does not preserve solver
tolerance values. The fixture must mark those source values unavailable rather
than claim runtime-tolerance identity. Restriction and relaxation native solves
do use one identical declared policy.

**Rationale**: A single latent schedule must explain all rounded values and the
objective at once. This supports a bounded scientific claim while preserving
visible decision differences and source limitations.

**Alternatives considered**:

- Treating displayed decisions as exact was rejected because their aggregate
  objective already shows sub-mill precision was discarded.
- A blanket 0.001 tolerance was rejected because it mixes decision rounding,
  objective rounding, solver feasibility, and physical units.
- Labeling equal objectives with different decisions as solver degeneracy was
  rejected without common feasibility and interval-objective evidence.

## 10. Validation and dependency gates

**Decision**: Use six separated evidence tiers:

1. routine pure unit oracles for input rejection, time mapping, budget
   derivation, efficiency cases, power/SOC/terminal equations, objective,
   statuses, and fingerprints;
2. routine private small-grid Pyomo/HiGHS cases for optimal restriction and
   relaxation, infeasibility, terminal slack, incumbent policies,
   repeatability, and bound order;
3. routine public 96-step assembly/cardinality and normalized-fixture contract
   checks without solving the historical case;
4. routine fixed-plan extraction and one authored Feature 012 replay;
5. explicit `reference_benchmark` full 2023-06-18 solve and comparison; and
6. optional Gurobi exact small case plus separately optional
   `external_reference_data` Feature 012 replay.

Routine isolation guards block network, credential reads, subprocesses,
`baselines/*`, `legacy/*`, artifacts, external CSV, and Gurobi. Avoid flaky
wall-clock assertions: pin semantic index/cardinality counts and quadratic
growth, and keep the existing CI process limit. The full historical reference
has 4,656 triangular and 4,560 strict off-diagonal pairs; a literal K=96
translation is approximately 10,301 variables/33,643 constraints for the
restriction and 10,206/24,333 for the relaxation.

**Rationale**: The feature remains fully useful and testable offline with the
required open-source backend, while expensive or externally constrained
evidence is explicit and cannot silently weaken routine validation.

**Alternatives considered**:

- Making the complete reference solve routine was rejected due its recorded
  resource demand and the spec's clarification.
- Using `external_reference_data` for optimization parity was rejected because
  realized activation is not an optimizer input.
- Skipping missing HiGHS was rejected because it is a required dependency;
  only the licensed exact backend may skip actionably.
