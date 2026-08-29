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

## Source-only walkthrough notebook

[`fcr_rolling_backtest_walkthrough.ipynb`](fcr_rolling_backtest_walkthrough.ipynb)
is the visual research walkthrough for Feature 015. It builds all five
profile manifests and, by default, solves the lightweight four-day Script 13
study so midnight carry-over, Feature 012 replay, settlement, and semantic
fingerprints remain quick to inspect. It also visualizes source-compatible
versus full-precision state handoff, the 08:00 fixed overlap, causal cutoffs,
ex-ante versus ex-post economics, lifecycle edges, and the bounded normalized
Julia/Gurobi evidence with explicit units.

Install the optional notebook group and start it from the repository root:

```bash
uv sync --group notebook
uv run jupyter lab \
  examples/fcr_rolling_backtest/fcr_rolling_backtest_walkthrough.ipynb
```

The committed notebook is source-only with empty outputs. All-profile native
solves, the bounded reference benchmark, the external activation path, and
figure export are disabled by default. Enabling the all-profile solve can be
slow because the mixed-binary cases may use their full per-day time limits.

## Authored offline studies

From the repository root, run all five profiles as separate manifests and
results:

```bash
uv run python examples/fcr_rolling_backtest/run_authored_study.py
```

Select one executable profile with `--profile`. Script 15 supports two
different semantic state-carry policies:

```bash
uv run python examples/fcr_rolling_backtest/run_authored_study.py \
  --profile script-15-restriction-rolling-midnight-v1 \
  --state-carry-policy source_three_decimal

uv run python examples/fcr_rolling_backtest/run_authored_study.py \
  --profile script-15-restriction-rolling-midnight-v1 \
  --state-carry-policy native_full_precision
```

Native full precision is rejected for the other four profiles. In particular,
the source-compatible 08:00 profile always uses the three-decimal handoff.
The two script-15 policies have different manifests and fingerprints and make
no promise of identical later decisions.

The command writes a uniform
`fcr-rolling-authored-study-bundle-v1` document when `--output` is supplied.
An exact manifest-compatible prefix can be retained and resumed:

```bash
uv run python examples/fcr_rolling_backtest/run_authored_study.py \
  --profile script-13-arbitrage-only-midnight-v1 \
  --stop-after 2 \
  --output artifacts/fcr_rolling_backtest/authored-partial.json

uv run python examples/fcr_rolling_backtest/run_authored_study.py \
  --profile script-13-arbitrage-only-midnight-v1 \
  --resume-from artifacts/fcr_rolling_backtest/authored-partial.json \
  --output artifacts/fcr_rolling_backtest/authored-complete.json
```

Resume fails closed if any manifest, profile, date, input, solver, carry,
activation, acceptance, settlement, revision, or continuity fingerprint has
changed. Runtime duration and caller output paths remain outside semantic
identity. The authored inputs are useful for deterministic workflow evidence;
they are not Julia comparison evidence.

## Normalized source evidence

The committed normalized fixture is:

```text
tests/fixtures/fcr_rolling_backtest/robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json
```

Only the explicit maintainer normalizer reads caller-listed, digest-pinned raw
source files:

```bash
uv run python examples/fcr_rolling_backtest/normalize_reference_fixture.py \
  --source-root baselines/robust_storage_bidding \
  --input-manifest examples/fcr_rolling_backtest/reference_inputs_v1.json \
  --destination-dir artifacts/reference/fcr_rolling_backtest
```

The command uses no glob discovery, network, Julia, solver, or credential
access. It writes atomically beneath ignored `artifacts/`; promoting a new
fixture is a separate reviewed action. The raw logs, all generated JSON,
workbook, and complete activation CSV are not redistributed.

## Bounded native reference benchmark

The full five-profile/four-date comparison is explicit research work:

```bash
uv run python examples/fcr_rolling_backtest/run_reference_benchmark.py \
  --fixture tests/fixtures/fcr_rolling_backtest/robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json \
  --profiles all \
  --dates 2023-06-17 2023-06-18 2023-06-19 2023-06-20 \
  --solver highs \
  --output-dir artifacts/reference/fcr_rolling_backtest/native
```

The command reads only the explicit normalized fixture. It retains all four
native date records and field comparisons even when a solve is time-limited,
fails, lacks an incumbent, is blocked by missing activation, or remains an
unfinalized 08:00 edge. Per-profile JSON reports and a compact summary are
written atomically. Optimization objective, same-solve bound, independent
feasibility evidence, all 24/6 decisions, lifecycle, and comparison outcomes
remain separate.

Gurobi is selected only when `--solver gurobi` is explicit. The command checks
the optional package, license, and version and reports actionable unavailable
evidence without falling back to HiGHS. Ordinary restriction/relaxation
profiles may use the existing Feature 013 Gurobi adapter. The additive
arbitrage-only and 40-hour 08:00 formulations currently report
`optional_gurobi_rolling_adapter_not_implemented`; they are never silently
solved with another backend. Required validation continues to use HiGHS.

The corresponding explicit pytest gate is:

```bash
uv run pytest tests/parity/test_fcr_rolling_reference_benchmark.py \
  -m reference_benchmark -q -s
```

## Optional activation replay

Feature 015 never searches for, downloads, or infers the external signal. If
the Feature 012-governed file has deliberately been installed at exactly:

```text
artifacts/reference/robust_storage_bidding/regulation_signal.csv
```

run:

```bash
uv run pytest \
  tests/integration/simulator/test_fcr_rolling_external_reference_replay.py \
  -m external_reference_data -q -s
```

The test validates the exact byte digest and four-day coverage before slicing
8,640 ten-second samples per ordinary day. Absence is an actionable skip and
does not weaken offline optimization evidence.

## Optional full-history research request

The 2020-07-01 through 2024-06-30 workflow is never a release gate. Supply one
explicit `fcr-rolling-full-history-request-v1` JSON document and a separately
fingerprinted `fcr-rolling-full-history-data-v1` bundle:

```bash
uv run python examples/fcr_rolling_backtest/run_reference_benchmark.py \
  --study-manifest artifacts/reference/fcr_rolling_backtest/full-history-request.json \
  --resume-output artifacts/reference/fcr_rolling_backtest/full-history-result.json
```

The request has exactly these fields:

- `research_only: true` and `release_gate: false`;
- one `profile_id` and one compatible `state_carry_policy`;
- the immutable 1,453-entry `ordered_dates` list, the eight ordered excluded
  DST dates, and source-list SHA-256
  `6b2412144996135507ea85a73f51b7819897a1f98ae767df4396d18a9605ba51`;
- a mandatory `assumed_accepted` or `evidence_backed_accepted` policy;
- `data_bundle.path` plus its exact byte SHA-256; and
- a `request_fingerprint` computed without the caller-local bundle path.

The data bundle contains the battery and terminal contracts, capacity,
fingerprints for all three data families, exactly ordered 24/6 price rows,
optional explicitly embedded 8,640-value ten-second activation rows, and its
canonical `bundle_fingerprint`. No directory discovery occurs. If a compatible
result already exists at `--resume-output`, the public resume audit governs
reuse. The command writes the canonical result atomically and retains every
failed, blocked, excluded, partial, and unfinalized date. Missing activation
therefore remains visible and blocks coupled handoffs rather than being
substituted.

This bounded or full-history workflow does not claim published Table A1
parity. Source three-decimal schedules are interval evidence; several source
records are time-limited incumbents with upper bounds; source JSON does not
prove independent feasibility; and exact 08:00 restart evidence is unavailable
because hidden full-precision predecessor fixings were not persisted.

See the Feature 015
[quickstart](../../specs/015-fcr-rolling-backtest-parity/quickstart.md) for the
routine validation and isolation gates.
