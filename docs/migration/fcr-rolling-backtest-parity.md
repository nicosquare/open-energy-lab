# FCR rolling backtest parity evidence ledger

Feature 015 migrates the pinned reference's five non-intraday executable
profiles into an offline-by-default native rolling study. Feature 013 remains
the optimizer; Feature 012 remains the sole battery replay and settlement
owner. This ledger records which claims are supported as implementation and
validation progress.

## Source behavior map

| Reference source | Behavior used by Feature 015 |
| --- | --- |
| `baselines/robust_storage_bidding/code/01_datastruct.jl:3-48` | Source sign convention, battery and uncertainty defaults, terminal target, model kind, and default time limit. |
| `baselines/robust_storage_bidding/code/02_model.jl:15-32` | Extended hourly indices and fixed predecessor energy overlap. |
| `baselines/robust_storage_bidding/code/02_model.jl:34-75` | Exact no-regulation hourly formulation. |
| `baselines/robust_storage_bidding/code/02_model.jl:86-99,137-143` | Reserve indices, non-intraday zero adjustment, and fixed predecessor reserve overlap. |
| `baselines/robust_storage_bidding/code/02_model.jl:175-188,252-263,289-291` | Robust state propagation, full-frame objective and terminal rule, and lower-index derivation. |
| `baselines/robust_storage_bidding/code/03_backtest_save.jl:5-83` | Activation concatenation, predecessor-tail/current-day replay ordering, and cutoff replay. |
| `baselines/robust_storage_bidding/code/03_backtest_save.jl:86-158` | Ten-second replay behavior and three-decimal persisted state. These equations are evidence for Feature 012 checks, not code to duplicate in Feature 015. |
| `baselines/robust_storage_bidding/code/03_backtest_save.jl:161-204` | Predecessor-result finalization and the limitation of the hard-coded restriction `bilinear_violations` field. |
| `baselines/robust_storage_bidding/code/04_parse_results.jl:4-39,43-100` | Source field meanings, silent missing-file behavior to reject, and workbook aggregation formulas. |
| `baselines/robust_storage_bidding/code/05_dates.txt:1-1453` | Ordered source date list and DST exclusions. |
| `baselines/robust_storage_bidding/code/11.jl:23-95` | Relaxation with independent reset days, result directory 01. |
| `baselines/robust_storage_bidding/code/12.jl:23-95` | Restriction with independent reset days, result directory 02. |
| `baselines/robust_storage_bidding/code/13.jl:23-103` | Sequential no-regulation midnight profile, result directory 03. |
| `baselines/robust_storage_bidding/code/14.jl:23-104` | Sequential 08:00 restriction and accepted-overlap carry, result directory 04. |
| `baselines/robust_storage_bidding/code/15.jl:23-104` | Sequential midnight restriction and stored-energy carry, result directory 05. |

The executable profile crosswalk is deliberately separate from paper labels:
scripts 11/12/13/14/15 correspond to paper Experiments 1/2/4/5/3 and workbook
columns 11/12/14/15/13. Script 13's executable time limit and the workbook's
energy metric also require explicit discrepancy evidence.

## Evidence limits

- No Table A1 parity claim is made. The bounded four-day rerun cannot prove a
  full-history aggregate, and the workbook/paper metric mapping is not fully
  interchangeable with executable output.
- No optimality claim is made from source JSON alone. Several retained logs
  describe time-limited feasible incumbents with upper bounds.
- Displayed three-decimal source values define closed precision intervals;
  they are not exact hidden solver decisions or feasibility proof.
- The restriction JSON's `bilinear_violations=0` field is not an independent
  audit. Native compatibility requires Feature 013's formulation audit.
- Exact 08:00 restart parity may be unavailable because the source did not
  persist the full-precision predecessor decisions it fixed in memory.
- The last bounded 08:00 delivery date remains unfinalized without a following
  successor solve. The first date is initialization evidence.
- Activation-backed replay is unavailable unless a caller explicitly supplies
  the governed Feature 012 CSV. No implementation searches for it.

## Validation record

### Phase 2 — Feature 012/013 compatibility foundation

The protected Feature 012/013, activation, segmented-evaluation, package
surface, and lazy-import selection passed with `307 passed in 138.23s`:

```bash
uv run pytest \
  tests/unit/control/test_robust_fcr_problem.py \
  tests/unit/control/test_robust_fcr_solver.py \
  tests/unit/control/test_robust_fcr_equations.py \
  tests/unit/control/test_robust_fcr_backend_compatibility.py \
  tests/integration/control/test_robust_fcr_highs.py \
  tests/unit/simulator/test_fcr_bid_evaluation.py \
  tests/unit/simulator/test_fcr_settlement.py \
  tests/integration/simulator/test_fcr_bid_evaluation_compatibility.py \
  tests/integration/simulator/test_fcr_bid_evaluation_public_compatibility.py \
  tests/integration/simulator/test_robust_fcr_feature_012_replay.py \
  tests/unit/market/test_activation.py \
  tests/unit/simulator/test_fcr_rolling_evaluation.py \
  tests/unit/control/test_fcr_rolling_import_boundary.py \
  tests/unit/market/test_package_surface.py \
  tests/unit/market/test_import_boundary.py \
  tests/unit/simulator/test_import_boundary.py \
  tests/unit/test_lazy_dependency_boundaries.py \
  tests/unit/test_import_contract.py -q
```

The Feature 013 authored ordinary-day identities remained unchanged:

- problem: `60096175d66da13ee99eac05b0680a040e7d8dd15f8ebd6f9aca3f8f0a4c1a62`
- comparison problem: `8b5b362db4bed3af10a3026ff678b3cc338e3ee96da134d0f432817e4968da52`
- time contract: `9d584023b06e5a6f5ea4e475cd9aa49d1a4d63b0edef9aafb7c4181e78d63c56`
- controlled semantic result: `15f1f5077033ecd7b7c2261bed82706ad26b56ead7c4f6889ab87e2f74ea2cae`
- controlled decision vector: `a00a601eb3cdd1acabf87e3c58c75233b9af3c109675c5d41af0a797bc5a180c`
- controlled energy schedule: `1e83cf52c59b1b85d6796bc063ef1d9f90b94d22fe076d58b30ca190debb73b2`
- controlled FCR schedule: `1d1f4651e2bf2a691d227cdf3c7c315d558e798d7f24e510dc470d4a9f9a110a`
- controlled fixed plan: `e81de0cad18c716aa8476883e90477e5a7dd056678bfe8391b9446be031d06e7`

The real presolve-zero HiGHS case also retained result fingerprint
`92b532198aae634948e96369dbd48101f9c7bb7cc8fbb0bd7c798ab010ff4deb`
and plan fingerprint
`5da0ba402a0f973117539b42d1f798c9adc24ac52ed841b15069409a3bd35992`.
No optional source runtime, network, credentials, Julia, Gurobi, or external
activation CSV was used by this checkpoint.

### Phase 3 — five executable profile families

The pure manifest/crosswalk/oracle contracts, additive Pyomo formulations,
bounded HiGHS cases, initial ordered orchestration, public control surface, and
lazy-import checks passed with `58 passed in 57.60s`:

```bash
uv run pytest \
  tests/unit/control/test_fcr_rolling_manifest.py \
  tests/unit/control/test_fcr_rolling_source_documentation.py \
  tests/unit/control/test_fcr_rolling_orchestration.py \
  tests/integration/control/test_fcr_rolling_highs.py \
  tests/unit/control/test_fcr_rolling_import_boundary.py \
  tests/unit/test_import_contract.py -q
```

All five executable profile identities constructed and produced bounded,
ordered optimization evidence:

| Executable profile | Formulation/state family | Plan classification | Profile fingerprint |
| --- | --- | --- | --- |
| `script-11-relaxation-reset-midnight-v1` | relaxation/reset | diagnostic non-robust | `b30877d59634c14c6e337711cbdbcb05df47abb6db57c6c1a006a5704265d49d` |
| `script-12-restriction-reset-midnight-v1` | restriction/reset | robust candidate | `4b3dc124fa0467f0d31055858b1bc38bab3ee4774ce7347d93bbfdb443f5ef2a` |
| `script-13-arbitrage-only-midnight-v1` | exact-zero-FCR/midnight carry | arbitrage only | `bf082f8d94c5df63165456c9ea5e7c7d4fe80e68c6bddd35d46322b3ecbad221` |
| `script-14-restriction-rolling-0800-v1` | restriction/40-hour fixed overlap | robust candidate | `18c142dc223d75c256c781b39d017008b9e7e8f06cc086a4fd448f8d860c08ce` |
| `script-15-restriction-rolling-midnight-v1` | restriction/midnight carry | robust candidate | `783effe5276659ceb2aa5e73d1c1ee83d6d6c6a927f5c0db56c09414eb92827a` |

The 08:00 oracle asserts `K_lower=-63`, 160 quarter-hour indices, 40
hourly indices, ten four-hour FCR indices, and exact 16/4 accepted predecessor
fixings. The arbitrage-only model carries six explicit model-fixed zero FCR
decisions. Both additive formulations report an independent equation-family
residual audit, objective/bound/gap evidence, and only current-day 24/6 public
charge-positive decisions. Complete causal 08:00 finalization and realized
midnight state links remain deliberately deferred to their subsequent task
groups; this checkpoint makes no such completion claim.

### Phase 4 — causal 08:00 overlap and immutable finalization

The 08:00 workflow now extracts the accepted predecessor plan's unchanged
full-precision hours 09–24 and blocks 3–6, evaluates only the exact half-open
00:00–08:00 prefix through Feature 012, and carries both the full-precision
checkpoint and its deterministic three-decimal handoff. The successor's
40-hour problem is constructed and solved before any post-cutoff tail replay;
the tail is evaluation-only evidence used afterward to append a finalized
revision without replacing the original plan.

The authored causal replay selection passed with `5 passed in 91.77s`:

```bash
uv run pytest \
  tests/integration/simulator/test_fcr_rolling_feature_012_replay.py -q
```

The twin traces have identical 00:00–08:00 samples and different later
samples. They produced exactly identical cutoff state-link, accepted-fixing,
successor-input, rolling-problem, 24/6 decision, and plan fingerprints. Their
later finalized activation fingerprints differed, proving that post-cutoff
information remains evaluation evidence rather than bid input. The guarded
call-order assertion also proves the successor solve precedes tail access.

The bounded four-date chain retained exactly one envelope per date with these
latest lifecycle states: `initialization_only`, `finalized`, `finalized`, and
`unfinalized`. The first three envelopes retain `original -> provisional ->
finalized` histories; the close-out retains `original -> provisional`, is
explicitly absent from finalized-parity eligibility, and remains present in
the result. All three state links reconcile.

After the lifecycle changes, the prior Feature 015 profile/import selection
passed with `60 passed in 50.82s`, and the protected Feature 013 problem,
solver, HiGHS, and fingerprint regressions passed with `80 passed in 85.67s`.
No external activation CSV, baseline runtime read, Julia, Gurobi, network, or
credential access was used.
