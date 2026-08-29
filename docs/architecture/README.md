# Architecture Documentation

Architecture notes describe the target `open_energy_lab` package layout, public
library boundaries, module roadmap, and foundation decisions that guide future
migration work.

Reusable product code belongs under `src/open_energy_lab`; `legacy/*` remains
reference material unless a later spec explicitly authorizes otherwise.

- [ENTSO-E Transparency Platform R3 integration](./entsoe-transparency-platform.md)
- [RTE Balancing Energy 5.2 integration](./rte-balancing-energy.md)

## Feature 011 restoration-services map

- Source: additive restoration contracts in
  [`market`](../../src/open_energy_lab/market),
  [`control`](../../src/open_energy_lab/control), and
  [`simulator`](../../src/open_energy_lab/simulator), with live RTE acquisition
  isolated in `market/rte.py`.
- Design: [Feature 011 implementation plan](../../specs/011-afrr-mfrr-services/plan.md)
  and [source/replay contracts](../../specs/011-afrr-mfrr-services/contracts/).
- Example: [offline aFRR/mFRR replay and notebook](../../examples/restoration_services/README.md).

The architecture supports bounded, deterministic research scenarios. It does
not claim that public area aggregates are asset commands, and it provides no
production dispatch or reserve-bidding optimization.

## Feature 012 fixed-plan FCR evaluation map

- Contracts: bidder lineage and schedule references in
  [`control`](../../src/open_energy_lab/control), explicit reference inputs in
  [`market`](../../src/open_energy_lab/market), and common physical replay,
  settlement, reporting, and comparison in
  [`simulator`](../../src/open_energy_lab/simulator).
- Design: [Feature 012 implementation plan](../../specs/012-fcr-bid-evaluation-parity/plan.md),
  [migration boundary](../migration/fcr-bid-evaluation-parity.md), and
  [review quickstart](../../specs/012-fcr-bid-evaluation-parity/quickstart.md).
- Examples: [fixed-plan and explicit external-reference consumers](../../examples/fcr_bid_evaluation/README.md)
  and the [source-only evaluation walkthrough](../../examples/fcr_bid_evaluation/fcr_bid_evaluation_walkthrough.ipynb).

This is a bidder-independent evaluator, not a bid optimizer. Reference-result
parity is limited to the aggregate evidence exported by the pinned reference
implementation and its field-specific source-precision bounds; no complete
ten-second Julia trace parity is claimed.

## Feature 013 reference robust-FCR bidding map

- Contracts and native bidder: immutable problem/result/reference contracts,
  Pyomo formulation handoff, lazy HiGHS/Gurobi adapters, equation audit, and
  bidder-neutral plan extraction in
  [`control`](../../src/open_energy_lab/control).
- Downstream owner: Feature 012's existing
  [`simulator`](../../src/open_energy_lab/simulator) evaluator alone owns
  post-acceptance activation replay and realized settlement.
- Design: [Feature 013 implementation plan](../../specs/013-reference-robust-fcr-bidding/plan.md),
  [migration/equation ledger](../migration/reference-robust-fcr-bidding.md),
  and [review quickstart](../../specs/013-reference-robust-fcr-bidding/quickstart.md).
- Examples: [authored solve, explicit historical benchmark, and fixture-normalization paths](../../examples/robust_fcr_bidding/README.md),
  plus the [source-only robust-bidding walkthrough](../../examples/robust_fcr_bidding/robust_fcr_bidding_walkthrough.ipynb).

The deployable restriction and upper-bound relaxation preserve the pinned
single-day, non-intraday 24/96/6 formulation. Bid selection cannot access
realized activation. The normalized Julia result supports rounded-decision and
objective comparison with explicit precision/certification categories, not
unrounded solver-proof or full-trace equality.

## Feature 015 rolling FCR backtest map

- Study contracts and orchestration: immutable manifests, daily revision
  envelopes, continuity/state links, resume, aggregation, rolling solve
  requests, and bounded reference comparison in
  [`control`](../../src/open_energy_lab/control).
- Optimization owner: Feature 013's private formulation, solver-status,
  extraction, and independent-audit machinery; its stable single-day 24/96/6
  public contract remains unchanged.
- Realized-data owner: half-open activation slicing in
  [`market`](../../src/open_energy_lab/market).
- Physical owner: segmented composition of Feature 012's sole replay and
  settlement implementation in
  [`simulator`](../../src/open_energy_lab/simulator).
- Design: [Feature 015 implementation plan](../../specs/015-fcr-rolling-backtest-parity/plan.md),
  [rolling evidence ledger](../migration/fcr-rolling-backtest-parity.md), and
  [routine/research quickstart](../../specs/015-fcr-rolling-backtest-parity/quickstart.md).
- Examples: [authored studies, fixture normalization, bounded benchmark,
  external replay, and resumable full-history paths](../../examples/fcr_rolling_backtest/README.md),
  plus the [source-only visual walkthrough](../../examples/fcr_rolling_backtest/fcr_rolling_backtest_walkthrough.ipynb).

Each manifest represents exactly one executable profile: scripts 11–15 cover
independent reset, diagnostic relaxation, exact-zero-FCR arbitrage, 08:00
fixed overlap, and realized midnight carry. Bid selection receives only data
available at its declared cutoff. Original and finalized records remain
separate, edge and failed dates stay visible, and source-rounded versus native
full-precision carry policies have different identities.

Routine execution is offline Pyomo/HiGHS. The complete bounded reference
benchmark, optional Gurobi, external activation CSV, and 1,453-date workflow
are explicitly selected research evidence. The four-day fixture can support
source-precision and time-limit-incumbent compatibility; it cannot by itself
support Table A1, full-history, or proven-optimum parity.
