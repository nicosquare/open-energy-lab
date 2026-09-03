# Robust FCR Bidding Examples

Feature 013 selects one ordinary delivery day's hourly day-ahead baseline and
six four-hour symmetric-FCR capacity bids before realized activation is known.
It reproduces the pinned reference implementation's non-intraday mixed-binary
restriction and relaxation with native Python and Pyomo. HiGHS remains the
routine backend; the explicitly installed `gurobi` extra provides optional
licensed cross-backend evidence.

This example area is deliberately separated into four evidence paths:

| Path | Purpose | Routine offline? | Deployable plan? |
| --- | --- | --- | --- |
| `robust_fcr_bidding_walkthrough.ipynb` | Visually connect the 24/96/6 inputs, uncertainty budgets, paired formulations, deployability audit, Feature 012 handoff, and bounded Julia fixture | yes, with empty committed outputs | restriction only, after every gate passes |
| `run_small_case.py` | Solve an authored restriction and relaxation, audit the equations, and inspect the Feature 012 plan | yes | restriction only, after every gate passes |
| `run_reference_benchmark.py` | Run the explicit full 2023-06-18 optimization comparison | no; selected research/release gate | only an eligible native restriction incumbent |
| `normalize_reference_fixture.py` | Normalize digest-pinned generated Julia result evidence below ignored `artifacts/` | no; maintainer refresh path | no |

The restriction is a conservative, deployable formulation. The relaxation is
optimistic upper-bound evidence and must never be presented as a market plan.
An optional exact bilinear solve is validation evidence only. All three report
an ex-ante optimization objective; none of them reports Feature 012's realized
settlement or profit.

## Scope boundary

Bid selection accepts battery parameters, 24 hourly energy prices, six
four-hour FCR prices, 96 quarter-hour robust-planning intervals, two distinctly
named uncertainty sets, a terminal-energy rule, an information cutoff, and a
fingerprinted solve policy. It never receives, loads, searches for, or infers a
realized FCR activation trace.

After a restriction plan is accepted by the market, a caller may pass that
unchanged `FixedFCRBidPlan` to Feature 012 together with accepted-volume,
battery, price, and realized-activation evidence. Feature 013 adds no battery
replay or settlement implementation.

The sequence is therefore explicit: solve the restriction, accept its emitted
plan, and only then bind market acceptance and realized activation to an
ordinary `FCRBidEvaluationRequest`. There is no Feature 013 replay wrapper;
both native and recorded plans use Feature 012's existing physical and
settlement evaluator. The bid result serializes `optimization_objective_eur`
and `best_upper_bound_eur` as ex-ante evidence while its Feature 012 realized
settlement and profit entries remain unavailable until that separate replay.

The full Julia/Gurobi comparison uses a small normalized fixture committed
under `tests/fixtures/fcr_bidding/`. Routine code never imports from or reads
`baselines/*` or `legacy/*`. The complete historical solve is excluded from
routine CI, and the external regulation CSV is needed only for a separately
selected Feature 012 physical replay.

Rolling and multi-day backtests, SOC carry-over, intraday recourse, scenario
generation, TPM fitting or bid selection, aFRR/mFRR, degradation cost, live
data acquisition, and full-history paper experiments remain out of scope.

The exact commands and interpretation rules are maintained in the
[Feature 013 quickstart](../../specs/013-reference-robust-fcr-bidding/quickstart.md).

For a guided review, open the
[source-only robust-bidding walkthrough](robust_fcr_bidding_walkthrough.ipynb).
Its default authored case makes a genuine joint arbitrage/FCR choice on a
20 kWh battery. Six unit-labelled figures show the price spread, the shared
baseline/reserve headroom, block-by-block binding constraints, the ex-ante
objective, three unseen-activation replays, and scenario-dependent realized
economics. Only the accepted restriction plan is replayed, and only through
Feature 012. The complete native HiGHS reference benchmark, licensed Gurobi
reference benchmark, external activation replay, and figure export are separately named switches
that default to disabled. Figure export, when selected, is restricted to
`tmp/robust-fcr-bidding-notebook/figures`.

With the governed activation CSV installed explicitly, run only the optional
external replay with:

```bash
uv run pytest \
  tests/integration/simulator/test_robust_fcr_external_reference_replay.py \
  -m external_reference_data -q -s
```

That selected replay has its own 600-second, feasible-incumbent-opt-in policy
so it can answer the ex-post physical question without claiming an optimization
proof. Any accepted incumbent still must pass the unchanged restriction audit;
the separate one-hour reference benchmark keeps feasible-incumbent opt-in
disabled.
