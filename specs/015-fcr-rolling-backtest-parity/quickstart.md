# Quickstart: FCR Rolling Backtest Parity

This is the implementation and review path for Feature 015. Run commands from
the repository root. Routine validation is deterministic and offline; it does
not need Julia, Gurobi, the raw baseline, the external activation CSV, network
access, or credentials.

## 1. Prepare the required environment

```bash
uv sync --dev
uv run python -c "import pyomo, highspy; print(pyomo.__version__, highspy.Highs().version())"
```

The required solver versions remain Pyomo `6.10.1` and highspy `1.15.1`.
Imports are lazy even though the dependencies are installed. The existing
`gurobipy==13.0.2` pin remains an optional research extra:

```bash
uv sync --dev --extra gurobi
uv run python -c "import gurobipy; print(gurobipy.gurobi.version())"
```

A valid Gurobi installation may strengthen selected benchmark evidence, but it
cannot replace required HiGHS checks or make Julia a runtime dependency.

## 2. Run the routine Feature 015 gate

```bash
uv run pytest \
  tests/unit/control/test_fcr_rolling_manifest.py \
  tests/unit/control/test_fcr_rolling_orchestration.py \
  tests/unit/control/test_fcr_rolling_results.py \
  tests/unit/control/test_fcr_rolling_reference.py \
  tests/unit/control/test_fcr_rolling_import_boundary.py \
  tests/unit/control/test_fcr_rolling_source_documentation.py \
  tests/integration/control/test_fcr_rolling_highs.py \
  tests/integration/control/test_fcr_rolling_resume.py \
  tests/integration/control/test_fcr_rolling_reference_normalization.py \
  tests/integration/simulator/test_fcr_rolling_feature_012_replay.py \
  -m "not reference_benchmark and not external_reference_data" \
  --strict-markers -ra
```

This gate covers:

- manifest date roles, one-profile identity, exact data descriptors, accepted
  bid assumptions, and activation exclusion from bidder inputs;
- the executable/paper/workbook crosswalk and explicit no-Table-A1 claim;
- ordinary reset days, exact-zero-FCR bidding, midnight carry-over, and the
  08:00 `K_lower=-63` 40-hour fixed-overlap frame;
- three-decimal and full-precision state policies, bootstrap, immutable
  finalization, edge handling, failures, continuity segments, resume, and
  partial/complete aggregates;
- deterministic bounded Pyomo/HiGHS restriction, relaxation, no-FCR, overlap,
  infeasible, time-limit-incumbent, and repeatability cases;
- public activation slicing, guarded causal cutoff state, and prefix/tail/
  full-day reconciliation exclusively through Feature 012;
- normalized source fixture schema, digest manifest, log/JSON reconciliation,
  precision intervals, comparison status, and isolation; and
- stable fingerprints excluding volatile duration, path, host, and log text.

Routine tests assert operation and model-cardinality growth, not wall-clock
duration. They never solve all four reference dates at full size.

## 3. Run an authored offline rolling study

```bash
uv run python examples/fcr_rolling_backtest/run_authored_study.py
```

The example uses small deterministic inputs and no baseline file. It prints:

- manifest/profile/date-role and data fingerprints;
- per-date solve status, objective, upper bound, gap, and plan classification;
- original/provisional/finalized revision history;
- initial, cutoff, realized terminal, and carried stored energy;
- Feature 012 report/settlement fingerprints and metrics;
- eligible, contributing, and omitted aggregate dates; and
- a semantic study fingerprint that remains stable when runtime changes.

Run the source-compatible and native state policies as separate manifests:

```bash
uv run python examples/fcr_rolling_backtest/run_authored_study.py \
  --profile script-15-restriction-rolling-midnight-v1 \
  --state-carry-policy source_three_decimal

uv run python examples/fcr_rolling_backtest/run_authored_study.py \
  --profile script-15-restriction-rolling-midnight-v1 \
  --state-carry-policy native_full_precision
```

Their later decisions and fingerprints are not expected to match. The native
full-precision run makes no source trajectory parity claim.

For the 08:00 example, the first date is initialization-only, successor solves
fix accepted predecessor tails, and the last delivery date remains unfinalized
without a close-out successor:

```bash
uv run python examples/fcr_rolling_backtest/run_authored_study.py \
  --profile script-14-restriction-rolling-0800-v1
```

## 4. Inspect and maintain normalized source evidence

Validate the schemas and committed fixture:

```bash
python -m json.tool \
  specs/015-fcr-rolling-backtest-parity/contracts/fcr-rolling-reference-fixture-v1.schema.json \
  >/dev/null

python -m json.tool \
  specs/015-fcr-rolling-backtest-parity/contracts/fcr-rolling-study-result-v1.schema.json \
  >/dev/null

python -m json.tool \
  tests/fixtures/fcr_rolling_backtest/robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json \
  >/dev/null

sed -n '1,320p' tests/fixtures/fcr_rolling_backtest/README.md
```

The fixture contains normalized evidence for scripts/results 01–05 and dates
2023-06-17 through 2023-06-20. It does not contain raw logs, all source JSON,
the workbook, activation samples, machine/license details, or local paths.

Maintainers regenerate only from an explicit input manifest whose entries pin
every selected raw artifact digest:

```bash
uv run python examples/fcr_rolling_backtest/normalize_reference_fixture.py \
  --source-root baselines/robust_storage_bidding \
  --input-manifest examples/fcr_rolling_backtest/reference_inputs_v1.json \
  --destination-dir artifacts/reference/fcr_rolling_backtest
```

The command performs no glob discovery, network access, Julia invocation, or
solver work. It verifies digests before parsing, redacts raw log details,
writes atomically under ignored `artifacts/`, and produces an ordered semantic
diff. It never edits the baseline or overwrites the committed fixture.
Promotion is a separate deliberate review action.

The current Experiment 2 rerun for 2023-06-18 has a different raw digest from
Feature 013's governed original result. The normalizer preserves both
identities and verifies semantic agreement of the displayed objective, bound,
24 energy decisions, and six FCR decisions without changing the Feature 013
fixture.

## 5. Run the bounded native reference benchmark

The complete four-date native solve is intentionally excluded from routine CI:

```bash
uv run pytest \
  tests/parity/test_fcr_rolling_reference_benchmark.py \
  -m reference_benchmark \
  -q -s
```

Or generate the researcher-facing report:

```bash
uv run python examples/fcr_rolling_backtest/run_reference_benchmark.py \
  --fixture tests/fixtures/fcr_rolling_backtest/robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json \
  --profiles all \
  --dates 2023-06-17 2023-06-18 2023-06-19 2023-06-20 \
  --output-dir artifacts/reference/fcr_rolling_backtest/native
```

The benchmark prints and persists separately:

- native incumbent objective, same-solve upper bound, gap, termination, and
  independent feasibility audit;
- all 24 hourly and six FCR decisions per delivery date;
- 40-hour fixed-tail objective components for 08:00 solves;
- state links, lifecycle revisions, and source-rounded/full-precision evidence;
- exact displayed, source-precision, source-incumbent, improved-incumbent,
  bound-incompatible, mismatch, unavailable, and incomplete outcomes; and
- the overall compatible/incompatible/incomplete result derived from field
  statuses.

Time-limited Julia source records remain feasible incumbents with upper bounds,
not proven optima. A close native objective does not become alternative-optimum
evidence unless both solutions have adequate optimality and common independent
feasibility evidence. Exact 08:00 restart parity may remain unavailable because
source JSON did not persist full-precision predecessor fixings.

With a compatible local license, select Gurobi explicitly for additional
cross-backend research evidence:

```bash
uv run python examples/fcr_rolling_backtest/run_reference_benchmark.py \
  --fixture tests/fixtures/fcr_rolling_backtest/robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json \
  --solver gurobi \
  --profiles all \
  --dates 2023-06-17 2023-06-18 2023-06-19 2023-06-20 \
  --output-dir artifacts/reference/fcr_rolling_backtest/native-gurobi
```

Missing Gurobi or a license is actionable optional evidence, never a routine
failure or a reason to skip required HiGHS checks.

With `--profiles all`, the existing Feature 013 adapter may solve scripts 11,
12, and 15. The additive script-13 exact-zero-FCR and script-14 40-hour
formulations currently produce explicit
`optional_gurobi_rolling_adapter_not_implemented` reports. They are not
silently solved by HiGHS, and their unavailable records remain in the report.

## 6. Run optional external activation replay

Feature 015 never downloads, searches for, or infers activation data. To run
bounded ex-post replay, independently place the governed Feature 012 CSV at:

```text
artifacts/reference/robust_storage_bidding/regulation_signal.csv
```

Its provenance, digest, schema, and installation policy remain owned by
Feature 012. Then explicitly select:

```bash
uv run pytest \
  tests/integration/simulator/test_fcr_rolling_external_reference_replay.py \
  -m external_reference_data \
  -q -s
```

The test receives that exact path after all bid-selection inputs are built. It
verifies the digest once, slices only the requested dates/cutoffs, and replays
both source and native accepted plans through Feature 012. If absent, it skips
with the exact expected path. No optimization or normalized-fixture claim is
weakened by the skip.

## 7. Exercise persistence and resume

```bash
uv run python examples/fcr_rolling_backtest/run_authored_study.py \
  --stop-after 2 \
  --output artifacts/fcr_rolling_backtest/authored-partial.json

uv run python examples/fcr_rolling_backtest/run_authored_study.py \
  --resume-from artifacts/fcr_rolling_backtest/authored-partial.json \
  --output artifacts/fcr_rolling_backtest/authored-complete.json
```

Resume validates the manifest, profile, ordered dates, every data and source
descriptor, solve/numeric/rounding/settlement/acceptance policy, reused date
fingerprints, continuity segment, and carried state. Changing any one must fail
closed. Changing only elapsed runtime may retain semantic compatibility.

A caller-supplied state after an interruption starts a new declared continuity
segment; reports and comparisons must not imply that it repaired the earlier
gap.

## 8. Run the optional full-history workflow

The 2020-07-01 through 2024-06-30 study is research-only and not an acceptance
requirement. After constructing a fully fingerprinted local request and data
bundle, run it resumably:

```bash
uv run python examples/fcr_rolling_backtest/run_reference_benchmark.py \
  --study-manifest artifacts/reference/fcr_rolling_backtest/full-history-request.json \
  --resume-output artifacts/reference/fcr_rolling_backtest/full-history-result.json
```

The `fcr-rolling-full-history-request-v1` document declares `research_only`,
`release_gate: false`, exactly one profile and carry policy, the immutable
1,453-date source ordering and eight explicit DST exclusions, the authoritative
date-list SHA-256, an explicit assumed-accepted or evidence-backed individual
bid policy, and the path plus byte digest of an
`fcr-rolling-full-history-data-v1` bundle. Its request fingerprint excludes the
caller-local path while retaining the bundle digest.

The separate bundle supplies canonical manifest inputs, exactly ordered 24/6
price rows for every requested date, and only explicitly available activation
traces. Neither request nor command performs directory discovery. Missing
activation, failed solves, dependent blocking, partial checkpoints, and
unfinalized dates remain visible. A compatible `--resume-output` is reused only
after strict semantic validation. This workflow does not claim Table A1 parity
until profile mapping, completeness, metric meaning, source precision, and
aggregate comparison all pass.

## 9. Run compatibility and isolation checks

```bash
uv run pytest \
  tests/unit/control \
  tests/integration/control \
  tests/unit/simulator/test_fcr_bid_evaluation.py \
  tests/integration/simulator/test_fcr_bid_evaluation_compatibility.py \
  tests/integration/simulator/test_fcr_bid_evaluation_public_compatibility.py \
  -m "not reference_benchmark and not external_reference_data" \
  --ignore=tests/integration/control/test_robust_fcr_optional_gurobi.py \
  --strict-markers -ra

uv run pytest \
  tests/unit/test_ci_workflow.py \
  tests/unit/test_fixture_provenance_docs.py \
  tests/unit/test_migration_policy_docs.py \
  tests/unit/test_lazy_dependency_boundaries.py \
  tests/unit/test_import_contract.py \
  tests/unit/test_no_legacy_imports.py \
  -q
```

These checks preserve Feature 012 and Feature 013 behavior and verify lazy
Pyomo/HiGHS/Gurobi boundaries. If the existing required-backend matrix needs a
Feature 015 selection, keep bounded rolling solver tests in that job and leave
the complete reference benchmark excluded.

## 10. Final static review

```bash
uv run python -m compileall -q \
  src/open_energy_lab/control \
  src/open_energy_lab/market \
  src/open_energy_lab/simulator \
  tests/unit/control \
  tests/integration/control \
  tests/integration/simulator \
  tests/parity

rg "from baselines|import baselines|from legacy|import legacy" \
  src/open_energy_lab \
  tests/unit/control \
  tests/integration/control \
  tests/integration/simulator \
  tests/parity

rg "RegulationActivationTrace|regulation_signal.csv" \
  src/open_energy_lab/control

git diff --check
```

The import search must return no production/runtime dependency. The activation
search must return no bidder input or hidden file lookup; type-check-only or
diagnostic references, if any, require explicit review.

## Evidence interpretation

- Successful audited restriction evidence supports modeled robust
  deliverability under its exact policy; realized replay is a separate ex-post
  result.
- Relaxation is an upper-bound formulation. Its replay is diagnostic and never
  a robust-plan claim.
- A source-compatible time-limit incumbent is not proven optimal.
- Source-precision compatibility is a joint interval/formulation statement,
  not exact source bytes or exact hidden decisions.
- An unfinalized edge, missing activation, blocked successor, or partial
  aggregate remains visible and prevents a complete-study claim.
- The bounded rerun can support executable-profile comparison, but not the
  paper's full-history Table A1 parity by itself.
