# Reference Robust FCR Bidding Migration

## Scope and pinned evidence

Feature 013 migrates the single-day, non-intraday robust day-ahead/FCR bidder
from the `robust-storage-bidding` reference at commit
`7e44738bb30e5c8204efe40103b9be4c2203685c`. The baseline is read-only evidence;
native reusable code belongs to `src/open_energy_lab/control`, and routine
execution reads neither `baselines/*` nor `legacy/*`.

The relevant source inventory is:

| Source | Evidence used |
| --- | --- |
| `baselines/robust_storage_bidding/code/01_datastruct.jl:3-49` | battery bounds, positive-discharge sign, efficiencies, window parameters, price/slack fields, terminal rule, formulation labels, and solver fields |
| `baselines/robust_storage_bidding/code/02_model.jl:6-305` | variable indexing, non-intraday restriction/relaxation/exact equations, objective, terminal constraint, solver setup, and horizon-budget derivation |
| `baselines/robust_storage_bidding/code/12.jl:27-95` | Experiment 2's 96-step profile, 0.25/2.25-hour window values, efficiencies, energy bounds, terminal target, prices, restriction selection, and result-generation command |
| `baselines/robust_storage_bidding/results/02/2023-06-18.json` | generated three-decimal objective, bound, 24 `x0` decisions, six `xr` decisions, reported slacks, and runtime metadata |

The generated result is not tracked at the pinned baseline revision. Its
authoritative digest is
`8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6`
(6,653 bytes in the reviewed checkout). This digest-pinned generated evidence
is normalized into a small repository-owned fixture; it is never imported or
read by production or routine-test code.

## Behavior preserved

- One ordinary day with 96 quarter-hour robust intervals, 24 hourly `x0`
  decisions, and six four-hour `xr` decisions.
- Source-frame positive-discharge energy, non-negative symmetric FCR capacity,
  and the explicit adapter to Open Energy Lab's public charge-positive power.
- Separate recovery-window inputs (`gamma=0.25 h`, `Gamma=2.25 h`) and the
  covering formula in `code/02_model.jl:293-305`, which derives a 2.75-hour
  horizon-wide budget.
- Hard charge/discharge headroom (`code/02_model.jl:170-174`), robust lower and
  upper stored-energy counterparts (`:183-188`), efficiency epigraphs
  (`:191-197`), diagonal and off-diagonal upper-counterpart bounds
  (`:199-219`), and the restriction-only classification/tightening
  (`:225-230`).
- The ex-ante maximization objective and exact terminal lower bound in
  `code/02_model.jl:252-263`, including the unrounded terminal target
  `53.327556325823224 kWh` from `code/12.jl:77-78`.
- Restriction as deployable lower-objective evidence, relaxation as an
  optimistic upper-objective formulation, and optional exact bilinear evidence
  from `code/02_model.jl:220-224`.

## Preserved equation ledger

The native formulation uses the following pinned source ranges directly. The
line references are evidence identifiers: production code never opens these
paths at runtime.

| Equation family | Pinned source | Native interpretation and unit |
| --- | --- | --- |
| Variables, domains, fixed intraday adjustment, and binaries | `baselines/robust_storage_bidding/code/02_model.jl:86-135` | `x0`, `xr`, auxiliaries, kWh slacks, and dimensionless case binaries |
| Pointwise charge and discharge headroom | `baselines/robust_storage_bidding/code/02_model.jl:170-174` | `x0 - xr >= x_min` and `x0 + xr <= x_max`, in kW |
| Lower/coupling/upper robust stored energy | `baselines/robust_storage_bidding/code/02_model.jl:183-188` | prefix robust counterparts, in kWh; the horizon budget is in hours |
| Charge/discharge efficiency epigraphs | `baselines/robust_storage_bidding/code/02_model.jl:191-197` | maximum of the charging-efficiency and inverse-discharge-efficiency branches, in kW |
| Diagonal and common mixed-binary upper counterpart | `baselines/robust_storage_bidding/code/02_model.jl:199-219` | triangular `LambdaHigh` bounds, in kW |
| Optional exact relation | `baselines/robust_storage_bidding/code/02_model.jl:220-224` | nonconvex bilinear evidence only |
| Restriction classification and conservative tightening | `baselines/robust_storage_bidding/code/02_model.jl:225-230` | restriction-only lower-bound families, in kW |
| Ex-ante objective and terminal lower bound | `baselines/robust_storage_bidding/code/02_model.jl:252-263` | EUR objective components and terminal kWh requirement |
| Horizon covering budget | `baselines/robust_storage_bidding/code/02_model.jl:293-305` | 24/0.25/2.25 hours derive 2.75 hours |

The source parameter declaration at
`baselines/robust_storage_bidding/code/01_datastruct.jl:3-49` establishes the
positive-discharge battery convention, efficiency fields, window parameters,
prices, slacks, formulations, and solver settings. The complete Experiment 2
profile at `baselines/robust_storage_bidding/code/12.jl:27-95` fixes the
24/96/6 grid and the migrated numerical inputs.

### Sign and multi-rate adapters

The conversion at the public boundary is explicit:

```text
public_charge_positive_kw = -source_positive_discharge_kw
public_fcr_capacity_kw = source_xr_kw
```

The first equation changes only the sign convention. The second retains the
non-negative symmetric capacity magnitude. For one-based source planning index
`k`, hourly energy uses `ceil(k / 4)` and four-hour FCR uses `ceil(k / 16)`;
the native arrays use the equivalent zero-based `k // 4` and `k // 16` maps.

### FCR price unit correction

The `pr` source comment says `EUR/kWh` in
`baselines/robust_storage_bidding/code/01_datastruct.jl:18-20`, but the price
normalization and objective behavior establish `EUR/kW/4h-block`. The native
objective therefore computes `sum(price_per_kw_block * xr_kw)` exactly once
per block; it does not multiply the value by four hours. Day-ahead energy
retains `EUR/kWh` and the quarter-hour integration factor.

### Restriction indexing detail

The migrated restriction intentionally distinguishes interval-local
`lambdaHigh[l]` in the classification decision from prefix-specific
`lambdaHigh[k]` in the triangular tightening. Collapsing those two indices
would change `baselines/robust_storage_bidding/code/02_model.jl:225-230` and
the feasible region. The pure audit reports these classification and
tightening families separately.

### Terminal and slack semantics

The terminal constraint is
`initial_kwh - 0.25 * sum(alpha_kw) >= terminal_minimum_kwh - terminal_end_kwh`
from `baselines/robust_storage_bidding/code/02_model.jl:252-263`. The exact
reference target is not reconstructed from the rounded initial state.
`symin`, `symax`, and `syK[1]` are declared and penalized but inert in the
non-intraday hard robust SOC equations; only terminal-end `syK[2]` relaxes a
constraint. All four groups remain visible audit evidence, and any modeled
slack above `1e-6` blocks a deployable plan.

The displayed objective is exclusively the ex-ante sum of day-ahead value,
FCR capacity value, and the subtracted feasibility-slack penalty. Runtime and
Feature 012 realized activation, settlement, and profit are different evidence
domains and are excluded from this reconciliation.

## Behavior improved

- Public immutable, versioned inputs make units, mappings, cutoff, provenance,
  numerical policies, and fingerprints explicit.
- Recovery-window and horizon-wide uncertainty sets have distinct contracts;
  the source's ambiguous `gamma` naming does not cross that boundary.
- Pyomo and HiGHS replace Julia/JuMP/Gurobi for routine solves while remaining
  lazy imports; exact Gurobi evidence is optional and isolated.
- A pure-Python audit independently checks every named constraint family,
  auxiliary witness, binary, slack, objective component, and canonicalized
  schedule before plan eligibility.
- Solver tolerances, the fixed `1e-6` deployability threshold, objective
  comparison tolerances, `1e-9 kW` decision canonicalization, and source
  rounding intervals remain separate policies.
- Feature 012 alone owns accepted-bid binding, realized activation, physical
  replay, and settlement. Ex-ante objective and ex-post profit are never
  equated.

## Behavior deliberately dropped

Runtime coupling to Julia, JuMP, global CSV tables, Gurobi-only routine use,
relative source paths, implicit indexing, activation loading during the
combined backtest, intraday variants, LP variants, and ambiguous objective
versus settlement labels are not migrated. No code writes under the reference
tree.

In particular, source variants `lp_relax` and `lp_restrict`, all intraday
recourse equations, force-bilinear heuristics, rolling state carry-over, and
the combined backtest are intentionally excluded from the Feature 013 model.

The saved `bilinear_violations=0` is not treated as restriction feasibility
evidence: the reference save path computes that check only for relaxation
profiles. Equal rounded objective and bound values are likewise not upgraded to
formal termination, optimality, an exact gap, or unrounded feasibility.

## Evidence limits

Routine validation consists of hand-calculable equation oracles, bounded
Pyomo/HiGHS solves, public 96-step assembly, normalized-fixture checks, and one
Feature 012 replay of an authored accepted plan. The complete 2023-06-18 solve
is an explicitly selected `reference_benchmark`; optional Gurobi exact evidence
and optional external-activation replay cannot weaken the routine gate.

Source-rounded decisions are compared through one joint interval feasibility
and objective certificate. A different native schedule is called an
alternative optimum only when native feasibility, joint source feasibility,
and common objective equivalence all pass. Unsupported source fields remain
`unavailable`, and unexplained differences remain `mismatch`.

## Selected validation records

### External Feature 012 replay (2026-08-27)

The explicitly selected `external_reference_data` gate found the governed CSV
at its ignored path, validated all 528,805,941 bytes and SHA-256, and passed in
634.85 seconds. Bid selection completed before the CSV was opened. The distinct
`native-reference-external-replay-highs-v1` policy used a 600-second limit and
explicit feasible-incumbent opt-in; its policy fingerprint was
`f99c91a2afff96667c11797c47ea95e04a37756c0cddbcbef19bf7617c5a863c`.
The accepted restriction incumbent was independently audited, had status
`feasible`, objective `9.859189984425477 EUR`, and same-solve upper bound
`12.256713420445767 EUR`. These values are not an optimality claim.

Both plans used activation artifact fingerprint
`8f36b8ac32987e6d8a7c055e150560873cd9252aa8e842d6c2cc0bf3f523dae7`
and the same 24/6/96/8,640 Feature 012 mappings. Recorded fingerprints were:

- plan `6bbbf946b8d12762971e5b369d4f63fa57b0a17d8977ca84de4655927bf36f11`;
- physical trace `f292f4990d99f6ca4aa7bb12c304b70751396e3c2005544577c58ceb153573f6`;
- settlement `8e5382463fd8e9bd110214fa4cd87be7539ae0fab70eb4ead0bb2b55cbbf72ca`;
- result `6aa9c1e75101354523432adecbf6b8dfb7fa946211151ebcfc7e767575777bb3`;
  and realized profit `10.748929939607164 EUR`.

Native fingerprints were:

- plan `3ef3d2ac8f8e5028d9ef7199e7afcb614f32a0a775a1bd2ca72821d6b6842a79`;
- physical trace `0612d26460bcfb10d69cc20b391dc44b3ed5786083374ff45fa06b13f00b769f`;
- settlement `9b6100295e3ece76b5e317050d7375cdf95b19842d7098950672a17f2a52b937`;
- result `1465d37034271f00c0823cdc74f6ece139382719af378d39d7da12512695fe56`;
  and realized profit `9.61415456889596 EUR`.

Different trace, settlement, and profit values are expected because this gate
replays different accepted schedules. It demonstrates one common evaluator and
activation input; it does not establish schedule equality or Julia optimization
parity.
