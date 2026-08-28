# FCR rolling backtest parity

This example package is the research-facing entry point for Feature 015. It
will run deterministic, native Python studies for the five pinned
non-intraday robust-storage-bidding executable profiles while preserving the
following ownership boundaries:

- Feature 013 selects bids and owns optimization feasibility evidence.
- Feature 012 performs every battery replay, settlement, and realized-profit
  calculation.
- Feature 015 orders dates, carries state, records immutable revisions, and
  compares normalized source evidence.

Routine examples and tests are offline and authored. They do not import or
read `baselines/robust_storage_bidding`, invoke Julia, require Gurobi, inspect
credentials, access the network, or discover an external activation file.
HiGHS remains the required routine solver through Feature 013's lazy backend.

The bounded Julia/Gurobi rerun is maintainer input to an explicit,
digest-pinned normalizer only. Raw source JSON, logs, the workbook, and the
complete activation CSV remain outside the committed fixture tree. The
normalized fixture records evidence strength: source-rounded schedules and
time-limited incumbents are not presented as proven optimal parity.

The authored study, normalizer, reference benchmark, optional Gurobi check,
optional external-activation replay, resume workflow, and full-history
research commands will be added in their dependency-ordered implementation
phases. Until then, use the Feature 015
[quickstart](../../specs/015-fcr-rolling-backtest-parity/quickstart.md) as the
authoritative workflow contract.
