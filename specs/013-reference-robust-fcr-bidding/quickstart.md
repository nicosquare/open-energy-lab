# Quickstart: Reference Robust FCR Bidding

This is the implementation and review path for Feature 013. Run commands from
the repository root. Routine validation is deterministic and offline; it does
not need Julia, Gurobi, `baselines/*`, the external activation CSV, network
access, or credentials.

## 1. Prepare the required environment

```bash
uv sync --dev
uv run python -c "import pyomo, highspy; print(pyomo.__version__, highspy.Highs().version())"
```

The required versions are Pyomo `6.10.1` and highspy `1.15.1`. They are already
pinned project dependencies; Feature 013 adds no dependency. Ordinary package
imports remain solver-free even though the backends are installed.

## 2. Run the routine Feature 013 gate

```bash
uv run pytest \
  tests/unit/control/test_robust_fcr_problem.py \
  tests/unit/control/test_robust_fcr_equations.py \
  tests/unit/control/test_robust_fcr_solver.py \
  tests/unit/control/test_robust_fcr_reference.py \
  tests/unit/control/test_robust_fcr_import_boundary.py \
  tests/integration/control/test_robust_fcr_highs.py \
  tests/integration/control/test_robust_fcr_reference_normalization.py \
  tests/integration/simulator/test_robust_fcr_feature_012_replay.py \
  -m "not reference_benchmark and not external_reference_data" \
  --strict-markers -ra
```

This gate covers:

- exact public 24/96/6 validation and ordinary-day rejection;
- 2.75-hour horizon-budget derivation from 0.25/2.25-hour window values;
- hand-calculable headroom, efficiency, stored-energy, terminal, and objective
  equations;
- private reduced-grid restriction/relaxation assembly and real HiGHS solves;
- infeasible, terminal-slack, no-incumbent, and controlled incumbent outcomes;
- the maximization order `z_restriction <= z_relaxation`;
- stable repeated decisions, diagnostics, and fingerprints;
- charge-positive Feature 012 plan extraction and common physical replay; and
- normalized optimization-fixture schema, provenance, precision, tamper, and
  isolation contracts.

The routine suite must not use a wall-clock performance assertion. It pins
semantic index/model cardinalities, verifies quadratic triangular growth on
private bounded profiles, and assembles the public 96-step model without
solving the historical reference case.

## 3. Run an authored offline bid

```bash
uv run python examples/robust_fcr_bidding/run_small_case.py
```

The example prints, in separate sections:

- restriction solve status, objective, best bound, and gap;
- the authored policy's fingerprinted `1e-6 EUR` absolute and `1e-9` relative
  objective-comparison defaults and stable relative-gap denominator;
- day-ahead, FCR-capacity, and slack-penalty objective components;
- maximum slack and residual per named constraint family;
- 24 charge-positive hourly schedule values and six FCR block values;
- raw-versus-`solver-output-kw-1e-9-half-even-v1` decision evidence and the
  unrepaired canonical-witness audit;
- deployable Feature 012 plan and schedule fingerprints; and
- relaxation upper-bound evidence without a deployable plan.

The authored example contains no `RegulationActivationTrace`. A separate
authored Feature 012 example may bind its successful plan to accepted-bid,
market, battery, and activation inputs after bid selection.

## 4. Inspect normalized reference evidence

```bash
python -m json.tool \
  specs/013-reference-robust-fcr-bidding/contracts/robust-fcr-reference-fixture-v1.schema.json \
  >/dev/null

python -m json.tool \
  tests/fixtures/fcr_bidding/robust_storage_bidding_2023-06-18_restriction_v1.json \
  >/dev/null

sed -n '1,280p' tests/fixtures/fcr_bidding/README.md
```

The committed fixture contains only small derived optimization evidence. It
pins the generated result digest, exact terminal target, battery, prices,
uncertainty sets, time mapping, restriction profile, three-decimal objective,
bound, and 30 decisions, unavailable source fields, and joint precision policy.
It cross-references the Feature 012 evaluator fixture but contains no activation
samples or external-data locator.

The generated Julia JSON did not record formal termination, exact gap,
unrounded decisions/auxiliaries, residuals, actual runtime solver versions, or
explicit solver tolerances. These remain unavailable; equal rounded objective
and bound is not treated as proof of optimality.

Maintainers may refresh normalized evidence only from an explicitly selected,
digest-matched local result. The tool writes beneath ignored `artifacts/` and
never overwrites the committed fixture:

```bash
uv run python examples/robust_fcr_bidding/normalize_reference_fixture.py \
  --source-json baselines/robust_storage_bidding/results/02/2023-06-18.json \
  --destination-dir artifacts/reference/robust_fcr_bidding
```

The command never starts Julia or a solver. Review its ordered semantic diff
before deliberately promoting bytes in a separate maintainer action. This is a
fixture-maintenance path, not production or routine validation.

## 5. Run the complete 2023-06-18 optimization benchmark

The complete solve is intentionally excluded from routine CI. It is offline and
does not need the external regulation CSV:

The source fixture does not contain or infer a native solve policy. The test and
researcher command construct the separately named
`native-reference-benchmark-highs-v1` profile with this complete mapping:

| Field | Value |
| --- | --- |
| `solver_name` | `highs` |
| `time_limit_seconds` | explicitly supplied; `3600` in the command below |
| `threads` | `1` |
| `random_seed` | `13` |
| `primal_feasibility_tolerance` | `1e-7` |
| `dual_feasibility_tolerance` | `1e-7` |
| `mip_feasibility_tolerance` | `1e-6` |
| `relative_mip_gap` | `1e-6` |
| `objective_comparison_absolute_tolerance_eur` | `1e-6` |
| `objective_comparison_relative_tolerance` | `1e-9` |
| `allow_feasible_incumbent_plan` | `false` |
| `decision_canonicalization_id` | `solver-output-kw-1e-9-half-even-v1` |

The complete mapping and resulting `solve_policy_fingerprint` are printed and
retained as native evidence. They never replace the fixture's
`not_recorded_source_defaults` declaration. API callers may provide other valid
comparison tolerances through an explicit policy; compared results must use
identical values.

```bash
uv run pytest \
  tests/parity/test_robust_fcr_reference_benchmark.py \
  -m reference_benchmark \
  -q -s
```

Or run the researcher-facing report:

```bash
uv run python examples/robust_fcr_bidding/run_reference_benchmark.py \
  --fixture tests/fixtures/fcr_bidding/robust_storage_bidding_2023-06-18_restriction_v1.json \
  --time-limit-seconds 3600
```

The benchmark reports:

- native objective, upper bound, gap, termination, and independent feasibility;
- the complete separately supplied native solve policy and fingerprint;
- the native objective-comparison allowance used for ordering and the fixed
  native equivalence band used against the rounded source objective interval;
- all 24 energy and six FCR decision deltas;
- canonical decision-content and producer-specific schedule fingerprints;
- one joint latent Julia-vector certificate across all three-decimal decision
  intervals and the objective interval; and
- `exact`, `source_precision_compatible`,
  `alternative_optimum_compatible`, `mismatch`, or `unavailable` for every
  required comparison field.

If the configured limit is reached, retain any valid incumbent, bound, gap,
audit, and incomplete comparison evidence. Do not turn it into optimality or a
routine-test claim. A feasible incumbent emits no plan by default; its policy
cannot be changed after the solve.

## 6. Run the optional exact-bilinear check

A compatible installed and licensed Gurobi environment may run:

```bash
uv run pytest \
  tests/integration/control/test_robust_fcr_optional_gurobi.py \
  -q -s
```

The selected exact adapter must set nonconvex mode explicitly and use the same
small problem and declared inputs as the restriction and relaxation. Accepted
evidence must satisfy:

```text
z_restriction <= z_exact <= z_relaxation
```

Missing binary, incompatible version, or unavailable license produces an
actionable optional-evidence result/skip. It never weakens the required HiGHS
restriction-versus-relaxation gate and never causes exact to fall through to
HiGHS.

## 7. Run the optional physical reference replay

Optimization parity does not use realized activation. To add the ex-post
comparison, the researcher must independently install the exact governed CSV
at the existing ignored Feature 012 path:

```text
artifacts/reference/robust_storage_bidding/regulation_signal.csv
```

Feature 013 never downloads, searches for, or infers this file. Its expected
digest, byte count, schema, and installation policy remain documented in
`specs/012-fcr-bid-evaluation-parity/quickstart.md`.

With the file present, explicitly select:

```bash
uv run pytest \
  tests/integration/simulator/test_robust_fcr_external_reference_replay.py \
  -m external_reference_data \
  -q -s
```

The test supplies the path only to Feature 012 after bid selection. It evaluates
the native and recorded schedules through the same physical and settlement
boundary. If the file is absent, the selected wrapper skips with the exact
installation path; routine optimization and parity remain complete.

## 8. Run compatibility and isolation checks

```bash
uv run pytest \
  tests/unit/control \
  tests/integration/control \
  tests/unit/simulator/test_fcr_bid_evaluation.py \
  tests/unit/simulator/test_fcr_reference_settlement.py \
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

These checks preserve Feature 009 and Feature 012 behavior and verify that
package roots and pure contracts do not load Pyomo, highspy, Gurobi, Julia,
notebooks, pandas, `baselines`, or `legacy`.

## 9. Final static review

```bash
uv run python -m compileall -q \
  src/open_energy_lab/control \
  tests/unit/control \
  tests/integration/control \
  tests/parity

rg "from baselines|import baselines|from legacy|import legacy" \
  src/open_energy_lab/control \
  tests/unit/control \
  tests/integration/control \
  tests/parity

rg "regulation_signal.csv|RegulationActivationTrace" \
  src/open_energy_lab/control

git diff --check
```

The first two searches must return no production/runtime import. The activation
search must return no bidder dependency; documentation-only diagnostic strings
must be reviewed explicitly if any are present.

## Evidence interpretation

- A successful restriction plus zero material slack/residual is evidence for a
  robustly deliverable modeled plan.
- A relaxation value is an optimistic upper-bound formulation result, never a
  market plan.
- A successful Feature 012 replay is one realized ex-post outcome, not proof of
  robust feasibility.
- `source_precision_compatible` means one joint latent schedule inside all
  recorded rounding intervals satisfies the common model and objective band;
  it does not mean the displayed decimals were exact solver values.
- `alternative_optimum_compatible` requires native feasibility, joint source
  feasibility, and common objective-equivalence evidence. Matching rounded
  objective alone is insufficient.
- The ex-ante optimizer objective and ex-post Feature 012 settlement are
  intentionally different quantities.
