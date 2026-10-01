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

More precisely, script 13 retains the data-structure default of 3,600 seconds,
whereas scripts 14 and 15 explicitly use 900 seconds. The workbook energy
metric derives charging input multiplied by charging efficiency; it is not the
paper's discharge-energy output. These differences are retained as governed
fixture discrepancies rather than reconciled by renaming fields.

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

### Phase 7 — bounded source normalization and comparison semantics

The bounded four-day rerun is normalized into a 99,635-byte fixture with
semantic fingerprint
`d9f12af283ff0377e651d7c7aaf5e81a40f85372a6e1bf62a4f90ab928659d93`
and committed-byte SHA-256
`c075d81cb8a388c82f57c78f3f36aedf9c0da9b0dadbed636b6422e87081be4f`.
Its explicit input manifest has SHA-256
`b84aef1734df9cb366696b9183b47610e540f5ecd47515ac012bf33e67875edc`
and pins all 20 JSON files, 11 logs, ten cited source files, three input-data
descriptors, the committed Julia Project/Manifest, README, workbook, and
Feature 013 fixture. The reviewed post-promotion semantic diff is empty.

Six retained source solves are time-limited feasible incumbents: scripts 14
and 15 on 2023-06-17, 2023-06-18, and 2023-06-19. Their same-solve upper bounds
remain distinct from incumbents. Source JSON's `bilinear_violations=0` is not
used as feasibility evidence. Native source-precision compatibility instead
requires one common witness across the closed three-decimal decision,
objective, state, and accepted-overlap intervals plus Feature 013's modeled
slack and independent residual audit.

Field comparisons preserve nine distinct outcomes:

- `exact_displayed_decision_parity`;
- `source_precision_compatible`;
- `alternative_optimum_compatible`, only with adequate two-sided optimality
  and common-feasibility evidence;
- `source_incumbent_equivalent` for audited objective-equivalent evidence
  against a time-limited source incumbent;
- `improved_feasible_incumbent_compatible_with_source_bound`;
- `bound_incompatible`;
- `mismatch`;
- `unavailable`; and
- `incomplete_or_unfinalized`.

The deterministic summary is `incompatible` when any mandatory field proves a
mismatch or bound incompatibility, `incomplete` when required evidence is
unavailable or unfinalized without a proven conflict, and `compatible` only
when every mandatory field has a compatible outcome. Canonically ordered field
evidence remains authoritative. Two time-limited incumbents are never called
alternative optima merely because their objectives are close.

For script 14, displayed predecessor and successor overlap intervals can be
jointly checked and the fixed-tail objective remains explicit, but exact
full-precision restart parity is unavailable because the predecessor values
fixed in memory were not persisted. The first bounded date remains
initialization-only, the last is unfinalized, and primary paired evidence is
limited to 2023-06-18 and 2023-06-19. This is a no Table A1 parity claim: the
bounded rerun does not prove full-history aggregates or the paper's metric
definitions.

The normalization and pure comparison selection is routine, deterministic,
and offline. Raw results, raw logs, the workbook, complete activation samples,
machine identities, and license text are not redistributed. The generated
candidate exactly reproduced the promoted fixture, and the governed Feature
013 fixture remained byte-identical.

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

> Note (2026-10-01, consolidation steps A5b–A5c): these values were later
> regenerated when in-memory fingerprints were removed and the spec-numbered
> strings were renamed (`docs/dev/consolidation.md`). The time-contract and
> schedule hashes are unchanged. Current pins live in
> `tests/unit/control/test_robust_fcr_problem.py`,
> `tests/unit/control/test_robust_fcr_solver.py` and
> `tests/integration/control/test_robust_fcr_highs.py`.

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

### Phase 5 — realized midnight carry and explicit continuity

Midnight-coupled profiles now replay each accepted full-day plan exclusively
through Feature 012 and construct the next Feature 013 battery from the
realized terminal checkpoint. The modeled robust terminal remains separate
optimization evidence and is never substituted for the realized handoff.

`derive_rolling_fcr_state_carry` applies source-compatible rounding with
`Decimal(str(value))`, `ROUND_HALF_EVEN`, exactly three decimal kWh, positive
zero normalization, and a closed half-unit interval. Native full precision is
an exact identity with a degenerate closed interval. Both forms retain
immutable rounding evidence and distinct fingerprints. State links validate
listed predecessor identity, kWh units, battery bounds, successor initial
state, tolerance, policy, interval, replay, and provenance.

The focused unit selection passed with `49 passed in 2.04s`:

```bash
uv run pytest \
  tests/unit/control/test_fcr_rolling_orchestration.py \
  tests/unit/control/test_fcr_rolling_manifest.py \
  tests/unit/test_import_contract.py -q
```

The complete bounded HiGHS selection passed with `12 passed in 85.82s`. It
includes a repeatable three-day source-rounded arbitrage chain and a native
full-precision restriction chain that becomes activation-blocked, then starts
a separately fingerprinted caller-supplied continuity segment. No state link
bridges that gap.

The combined causal and midnight Feature 012 replay selection passed with
`6 passed in 105.42s`, within the 120-second focused-command limit. Its
three-day policies have distinct manifest, day-input, problem, plan,
state-link, and study identities; every realized successor initial state
reconciles with its eligible predecessor carry. Nested volatile solver runtime
metadata remains reportable but is excluded from envelope and study semantic
fingerprints, so repeated semantic studies compare equal.

### Phase 6 — self-auditing results, aggregates, and resume

Rolling studies now persist a strict immutable evidence graph for day
revisions, envelopes, state links, continuity segments, aggregates, and the
study result. Loading recomputes every nested fingerprint and rejects unknown,
missing, malformed, or contradictory evidence without consulting solvers,
source artifacts, paths, environment state, or the network. Volatile runtime
duration and process-local metadata remain reportable but do not enter semantic
identity; solver versions and other stable backend evidence do.

Aggregation preserves failed, blocked, excluded, provisional, and unfinalized
dates explicitly. It reports exact contributors and omissions and keeps
optimization objectives, best bounds, realized settlement, realized profit,
directional FCR energy, and throughput as separate metrics. Missing quantities
remain unavailable rather than being silently replaced with zero.

Resume validation is fail-closed across the manifest, semantic profile, date
ordering and classification, solver and numeric policies, source lineage,
settlement and acceptance assumptions, input and activation fingerprints,
completed revisions, continuity segments, and carried state. A complete
compatible result can be returned without invoking the solver. A compatible
prefix retains the prior immutable records, recomputes the remaining study,
and produces the same semantic result as an uninterrupted run. Coupled failures
remain visible and block their dependents unless an explicit validated caller
state begins a new continuity segment; independent reset profiles continue.

The focused Phase 6 result, orchestration, import-boundary, and resume
selection passed with `75 passed in 3.67s`. The protected Feature 013 problem,
solver, and bounded HiGHS regressions passed with `80 passed in 94.05s`.

### Phase 8 — common Feature 012 replay and settlement

Independent reset profiles now retain their original optimization revision and
append a finalized revision only when an explicitly supplied activation trace
settles through Feature 012. Missing activation leaves the day visibly
`optimization_only`, with activation, replay, settlement, terminal-state, and
realized-profit evidence unavailable. The study is partial rather than
complete, but later reset days remain independently eligible. Coupled midnight
and 08:00 profiles continue to block successors when an activation-derived
handoff is unavailable.

Every accepted robust restriction, diagnostic relaxation, and arbitrage-only
plan uses the same accepted-plan market context and full-day or segmented
Feature 012 evaluator. Successful replay does not change its classification:
relaxation remains `diagnostic_non_robust`, arbitrage remains
`arbitrage_only` with all six FCR capacities exactly zero, and neither is
reported as a robust deployable plan. Feature 015 imports no battery-transition,
tracking, settlement, or profit equation into control.

Daily evidence retains separate plan, activation, Feature 012 replay, and
settlement fingerprints plus realized terminal state. Twelve coverage-labelled
aggregate families now remain distinct: optimization objective, best upper
bound, total realized settlement, realized profit, five settlement components
(day-ahead, FCR capacity, activation energy, combined FCR, and penalty), both
directional delivered-FCR energies, and throughput. Each aggregate is an
ordered `math.fsum` over its declared revisions with exact contributor,
omission, and revision-fingerprint lineage; absent values are never zero-filled.

The authored multi-day replay suite passed with `9 passed in 106.64s`. It
checks exact daily-to-study reconciliation, immutable original-to-finalized
history, physical terminal-state evidence, settlement/report fingerprints,
independent reset semantics, diagnostic non-robust retention, exact-zero-FCR
arbitrage replay, and explicit missing-activation behavior:

```bash
uv run pytest -q \
  tests/integration/simulator/test_fcr_rolling_feature_012_replay.py
```

The protected Feature 012 public compatibility, product-separation, and
settlement selection passed with `52 passed in 1.34s`:

```bash
uv run pytest -q \
  tests/integration/simulator/test_fcr_bid_evaluation_public_compatibility.py \
  tests/integration/simulator/test_fcr_bid_evaluation_compatibility.py \
  tests/unit/simulator/test_fcr_settlement.py \
  tests/integration/simulator/test_restoration_product_separation.py \
  tests/integration/simulator/test_fcr_bid_evaluation_manual.py
```

The explicitly selected external-data test also passed with `1 passed in
283.46s`. Before opening any evaluation-only samples, it built all four source
plans and native restriction problems for 2023-06-17 through 2023-06-20. It
then accepted only the exact path
`artifacts/reference/robust_storage_bidding/regulation_signal.csv`, verified
the 528,805,941-byte file and SHA-256
`0c2bf5203410f193c555460ec5593b546af42556f29afac821584e403c407d13`
once, scanned it once, and delegated four date imports to the existing Feature
012 activation contract. Each date had exactly 8,640 PT10S samples, and all
eight source/native requests settled through Feature 012 with exact
24/6/96/8,640 energy/FCR/checkpoint/activation counts and non-null trace,
settlement, and result fingerprints. Native solves used an explicit
60-second-per-date HiGHS policy and required an independently audited accepted
plan; this replay is performance evidence, not a new optimality or schedule-
parity claim. The test remains excluded from routine CI and skips actionably at
the exact expected path when the caller has not installed the governed CSV.

### Phase 9 — deterministic routine and optional research gates

The exact first compatibility-and-isolation command in the Feature 015
quickstart was run twice with the network unavailable, all research markers
excluded, and the optional Gurobi module ignored. Both runs collected the same
124 tests and passed without skips or failures:

- pass 1: `124 passed in 200.69s`;
- pass 2: `124 passed in 193.48s`.

After each pass, the authored script-13 study was run with the same declared
10-second HiGHS time-limit policy. Both complete four-date runs produced
semantic fingerprint
`4145f5727200e6c6eeb82befd895aea6923de4e0b0fc4acb0f2a561db0719c2b`.
Elapsed solver duration remained reportable but did not affect semantic
identity. A run with the CLI's different 30-second default was deliberately
not compared as repeatability evidence because solver policy is part of the
manifest identity.

The non-routine paths were collected explicitly without executing their
research workload:

| Evidence path | Selection | Collected | Routine status |
| --- | --- | ---: | --- |
| Complete five-profile/four-date native comparison | `tests/parity/test_fcr_rolling_reference_benchmark.py -m reference_benchmark` | 3 | Explicit benchmark only |
| Governed external activation replay | `tests/integration/simulator/test_fcr_rolling_external_reference_replay.py -m external_reference_data` | 1 | Requires the exact caller-installed CSV |
| Optional licensed Gurobi checks | `tests/integration/control/test_robust_fcr_optional_gurobi.py` | 3 | Explicit optional module; never a HiGHS fallback |

Collection proves that each opt-in route is discoverable; it does not add
runtime evidence. The complete benchmark, licensed Gurobi solves, and external
CSV replay therefore remain unavailable in this routine Phase 9 checkpoint.
Their absence does not weaken the required offline Pyomo/HiGHS gate, and no
Julia process, baseline runtime artifact, credential, or network access was
used.

### Phase 10 — final contracts, compatibility, isolation, and optional evidence

After synchronizing the public API, strict JSON wire schema, command guide,
and lazy export snapshots, the exact routine Feature 015 command completed
with `126 passed in 196.21s`. It excluded `reference_benchmark` and
`external_reference_data`, used required one-thread Pyomo/HiGHS only, and
retained the stable authored-study evidence recorded in Phase 9.

The protected Feature 013 quickstart gate completed with
`137 passed in 100.78s`. It rechecked ordinary-day 24/96/6 validation,
uncertainty-budget equations, restriction/relaxation ordering, deterministic
decisions and fingerprints, normalized reference isolation, lazy backend
behavior, and the Feature 012 handoff. The exact Feature 012 offline gate then
completed with `121 passed in 5.85s`, covering the bidder-neutral plan,
physical evaluator, settlement, Golden Reference Fixture, source precision,
normalization, CI, and documentation governance.

The final CI/documentation/import selection completed with
`115 passed in 5.08s`. It covered workflow selection, fixture provenance,
migration policy, lazy dependencies, exact package exports, and no-legacy/
no-baseline import contracts.

`compileall` succeeded for control, market, simulator, and all selected
Feature 015 test trees. Static review found:

- no `baselines` or `legacy` import in production or routine/parity tests;
- no raw baseline/result/external-CSV locator attached to `Path`, `open`,
  `read_*`, `glob`, or `rglob` in the rolling runtime boundary;
- no network, environment, credential, license-file, or subprocess probe in
  rolling production modules; and
- three `RegulationActivationTrace` references only inside the post-solve
  `_activation_for_date` replay guard. They validate evaluation-only input and
  are absent from rolling problem and solve entry points.

Optional evidence was selected explicitly. The Gurobi module reported
`1 passed, 2 skipped in 0.55s`: the no-fallback contract passed, while the
linear and exact-bilinear solver checks skipped because the optional Gurobi
binary was unavailable to Pyomo. Required HiGHS evidence remained green. The
governed four-day `external_reference_data` replay was locally available and
completed with `1 passed in 279.82s`; it reverified the Feature 012-owned CSV
path/digest and evaluated all source/native plans solely through Feature 012.

Both committed Feature 015 JSON schemas passed `python -m json.tool`. All
seven quickstart review links resolved to local files, the focused source and
migration documentation contracts completed with `22 passed in 0.10s`, and
`git diff --check` was clean. The final Phase 10 diff was limited to the
Feature 015 quickstart, this validation ledger, and task completion evidence;
neither `baselines/robust_storage_bidding` nor `legacy/*` was modified.

### Phase 11 — source-only visual walkthrough follow-up

The Feature 015 example now includes
`examples/fcr_rolling_backtest/fcr_rolling_backtest_walkthrough.ipynb`. The
offline default builds all five profile manifests, executes the lightweight
four-day Script 13 study with required HiGHS, and delegates every realized
state, settlement, and profit value to Feature 012. It also performs a real
two-day checkpoint/resume demonstration and inspects all twenty records in the
committed normalized Julia/Gurobi fixture. Research-scale all-profile solving,
the native reference benchmark, explicit external-activation verification,
and figure export remain disabled by default.

Markdown equations document the uncertainty-budget derivation, midnight
state handoff, three-decimal precision envelope, 08:00 accepted fixings,
causal half-open cutoff, and ex-ante/ex-post economic boundary. Seven figures
use explicit kW, kWh, EUR, time, or categorical axes; no normalized deviation
is plotted as though it had an energy unit. The committed notebook retains
stable cell IDs, empty outputs, and no execution counts.

Notebook source and guarded offline execution contracts completed with
`7 passed`. The focused Feature 015 source-documentation, lazy-import,
no-legacy/no-baseline, fixture-provenance, and migration-policy regression
selection completed with `128 passed`. The execution contract blocks network
and credential access, verifies the pinned display fingerprint, preserves the
committed notebook bytes, and confirms that default execution exports no
files.
