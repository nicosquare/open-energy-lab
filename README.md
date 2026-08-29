# Open Energy Lab

Open Energy Lab is being shaped into a unified Python research library for
energy-system simulation, optimization, learning, planning, control, and
analysis workflows.

The current `legacy/old_tpm` and `legacy/fed_trpo` directories are reference
material. New reusable product code belongs under `src/open_energy_lab`, with
tests under `tests`.

## Foundation Layout

```text
environment.yml
pyproject.toml
examples/
src/open_energy_lab/
tests/unit/
tests/integration/
tests/parity/
tests/fixtures/
docs/architecture/
docs/migration/
```

Current library package areas under `src/open_energy_lab`:

- `weather`: fitted weather artifacts and offline sampling flows.
- `demand`: fitted demand artifacts and weather-conditioned demand sampling.
- `market`: source-independent market artifacts, time contracts, and realized
  activation traces.
- `simulator`: scenario components, family evaluation, planning-dataset
  export, and the sole FCR physical replay and settlement implementation.
- `tpm`: typed-feature TPM artifacts, required SPFlow-backed fit/query flows,
  runtime payloads, and SPN-to-MIO helpers, with backend imports kept lazy.
- `planning`: planning-dataset reload, planning assembly, and required
  Pyomo/HiGHS solve flows, with solver imports kept lazy.
- `control`: deterministic controllers, bidder-neutral schedules, robust FCR
  bidding, and rolling-study orchestration with lazy solver boundaries.
- `experimental` and `visualization`: incubating or deliberately narrower
  areas.

The repository still treats `legacy/*` as reference material rather than
runtime code. SPFlow, Pyomo, and HiGHS are installed in the standard project
environment because TPM/planning workflows require them, but they remain
behind lazy workflow boundaries and are not imported by package roots. Gurobi
is an optional supplemental solver with separate binary and license needs.

## Environment

Create the minimal conda environment and let uv manage Python dependencies:

```bash
conda env create -f environment.yml
conda activate open-energy-lab
uv sync --dev
```

`uv sync --dev` installs the required SPFlow, Pyomo, and HiGHS stack. Ordinary
package imports must not eagerly load those backends or their PyTorch runtime.
Optional Gurobi, TorchRL, CityLearn, W&B, Jupyter, Rust, GPU/SLURM, and live
service capabilities remain outside the routine environment and import path.

## Documentation

- [Foundation architecture](docs/architecture/foundation.md)
- [API maturity policy](docs/migration/api-maturity.md)
- [Dependency policy](docs/migration/dependency-policy.md)
- [Environment assumptions](docs/migration/environment-assumptions.md)
- [TPM planning migration note](docs/migration/tpm-planning.md)
- [Tracked TPM planning examples](examples/tpm_planning/README.md)
- [French aFRR/mFRR architecture and source contract](docs/architecture/rte-balancing-energy.md)
- [French aFRR/mFRR migration and ownership note](docs/migration/afrr-mfrr-services.md)
- [Offline restoration-services working example](examples/restoration_services/README.md)
- [Feature 012 fixed-plan FCR evaluator design](specs/012-fcr-bid-evaluation-parity/plan.md)
- [Feature 012 review and external-data quickstart](specs/012-fcr-bid-evaluation-parity/quickstart.md)
- [FCR bid-evaluation migration and evidence boundary](docs/migration/fcr-bid-evaluation-parity.md)
- [Runnable fixed-plan and bounded-reference examples](examples/fcr_bid_evaluation/README.md)
- [Source-only FCR evaluation notebook](examples/fcr_bid_evaluation/fcr_bid_evaluation_walkthrough.ipynb)
- [Feature 013 robust FCR bidding design](specs/013-reference-robust-fcr-bidding/plan.md)
- [Feature 013 review and benchmark quickstart](specs/013-reference-robust-fcr-bidding/quickstart.md)
- [Reference robust-FCR bidding migration and evidence ledger](docs/migration/reference-robust-fcr-bidding.md)
- [Robust-FCR bidding examples](examples/robust_fcr_bidding/README.md)
- [Feature 015 rolling FCR backtest design](specs/015-fcr-rolling-backtest-parity/plan.md)
- [Feature 015 routine and research quickstart](specs/015-fcr-rolling-backtest-parity/quickstart.md)
- [Rolling FCR parity and validation ledger](docs/migration/fcr-rolling-backtest-parity.md)
- [Rolling FCR study and reference workflows](examples/fcr_rolling_backtest/README.md)
- [Source-only rolling FCR walkthrough notebook](examples/fcr_rolling_backtest/fcr_rolling_backtest_walkthrough.ipynb)
- [Fixture provenance rules](tests/fixtures/README.md)
- [Active Spec Kit plan](specs/015-fcr-rolling-backtest-parity/plan.md)

## French Restoration-Services Research Slice

Feature 011 adds source-independent aFRR and mFRR research contracts under
[`src/open_energy_lab/market`](src/open_energy_lab/market),
[`src/open_energy_lab/control`](src/open_energy_lab/control), and
[`src/open_energy_lab/simulator`](src/open_energy_lab/simulator). Read the
[Feature 011 design](specs/011-afrr-mfrr-services/plan.md) before extending the
slice, and use the
[offline example and notebook guide](examples/restoration_services/README.md)
to reproduce the bounded demonstrations.

This is a deterministic research replay, not a production dispatch service or
bidding optimizer. Public RTE values remain French control-area aggregates;
any battery activation shown by the example is explicitly labelled as a
derived simulation scenario.

## Fixed-Plan FCR Evaluation

Feature 012 evaluates one existing hourly energy schedule and one existing
four-hour FCR capacity schedule through a common physical replay, settlement,
reporting, and validation environment. Manual, heuristic, robust, and future
TPM bidders can therefore be compared without changing the evaluator according
to how a plan was produced.

The optional 2023-06-18 reference workflow maps decisions and aggregate evidence
from the pinned implementation under `baselines/robust_storage_bidding/`. Its
claim is bounded reference-result parity for supported aggregate fields under
documented source-precision intervals. It neither generates bids nor claims
complete ten-second Julia trace parity. Start with the
[Feature 012 quickstart](specs/012-fcr-bid-evaluation-parity/quickstart.md) for
routine offline checks and the explicit external-data workflow, or open the
[source-only evaluation walkthrough](examples/fcr_bid_evaluation/fcr_bid_evaluation_walkthrough.ipynb)
for an offline physical, settlement, diagnostic, producer-neutrality, and
bounded-evidence audit.

## Reference Robust FCR Bidding

Feature 013 selects one day's 24 hourly day-ahead decisions and six four-hour
symmetric FCR capacity bids with the pinned non-intraday mixed-binary robust
restriction. Native Pyomo/HiGHS bidding lives under
[`open_energy_lab.control`](src/open_energy_lab/control); the relaxation is
upper-bound evidence only, and optional exact Gurobi evidence is never a plan.
Realized activation is absent from bid selection.

An eligible restriction emits Feature 012's existing `FixedFCRBidPlan`
unchanged. After market acceptance, callers use Feature 012—not a bidder-owned
replay—for physical delivery and realized settlement. Start with the
[Feature 013 plan](specs/013-reference-robust-fcr-bidding/plan.md),
[example guide](examples/robust_fcr_bidding/README.md), and
[review quickstart](specs/013-reference-robust-fcr-bidding/quickstart.md).
The historical Julia comparison is deliberately bounded by rounded source
precision and unavailable source metadata; it does not claim identical
unrounded decisions, solver proof, or complete Julia trace parity.

## Rolling FCR Backtest Parity

Feature 015 composes Feature 013 bidding and Feature 012 replay into five
explicit non-intraday rolling-study profiles. It covers independent reset
days, exact-zero-FCR arbitrage, realized midnight state carry, and causal 08:00
overlap with accepted predecessor decisions fixed in place. Immutable daily
revision histories retain failed, blocked, provisional, finalized, and
unfinalized dates instead of silently dropping them.

The rolling orchestrator lives in
[`open_energy_lab.control`](src/open_energy_lab/control), activation slicing
stays in [`open_energy_lab.market`](src/open_energy_lab/market), and all
physical replay and settlement remain owned by
[`open_energy_lab.simulator`](src/open_energy_lab/simulator). Bid selection
cannot observe future activation. Routine Pyomo/HiGHS validation is
deterministic and offline; the complete four-date source comparison, optional
Gurobi checks, external activation replay, and full-history study are explicit
research workflows. Start with the [Feature 015 plan](specs/015-fcr-rolling-backtest-parity/plan.md),
[examples](examples/fcr_rolling_backtest/README.md), and
[quickstart](specs/015-fcr-rolling-backtest-parity/quickstart.md).

The bounded Julia/Gurobi fixture distinguishes exact displayed decisions,
source-precision compatibility, source-incumbent equivalence, compatible
improvements under a retained bound, mismatch, and unavailable or unfinalized
evidence. It does not prove Table A1 parity, full-history parity, or optimality
for time-limited source incumbents.

## Local Checks

Run the scaffold validation checks from the repository root:

```bash
uv run pytest tests/unit/test_import_contract.py tests/unit/test_module_scaffold.py
uv run python -c "import open_energy_lab"
```

After the legacy-isolation test is added, include:

```bash
uv run pytest tests/unit/test_no_legacy_imports.py
```

Do not add new reusable code to `legacy/*` unless a future migration,
reference-fix, or submodule-maintenance spec explicitly authorizes it.
