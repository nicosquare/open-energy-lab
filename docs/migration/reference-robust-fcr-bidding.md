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
