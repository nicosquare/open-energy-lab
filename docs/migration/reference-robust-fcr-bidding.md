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

## Preserved equation ledger

The native formulation uses the following pinned source ranges directly. The
line references are evidence identifiers: production code never opens these
paths at runtime.

| Equation family | Pinned source | Native interpretation and unit |
| --- | --- | --- |
| Variables, domains, fixed intraday adjustment, and binaries | `baselines/robust_storage_bidding/code/02_model.jl:86-135` | `x0`, `xr`, auxiliaries, kWh slacks, and dimensionless case binaries |
| Pointwise charge and discharge headroom | `baselines/robust_storage_bidding/code/02_model.jl:170-174` | `x0 - xr >= x_min` and `x0 + xr <= x_max`, in kW |
| Lower/coupling/upper robust stored energy | `baselines/robust_storage_bidding/code/02_model.jl:183-188` | prefix robust counterparts, in kWh; the horizon budget is in hours |
| Charge/discharge efficiency epigraphs | `baselines/robust_storage_bidding/code/02_model.jl:191-197` | maximum of the charging-efficiency and inverse-discharge-efficiency branches, in kW |
| Diagonal and common mixed-binary upper counterpart | `baselines/robust_storage_bidding/code/02_model.jl:199-219` | triangular `LambdaHigh` bounds, in kW |
| Optional exact relation | `baselines/robust_storage_bidding/code/02_model.jl:220-224` | nonconvex bilinear evidence only |
| Restriction classification and conservative tightening | `baselines/robust_storage_bidding/code/02_model.jl:225-230` | restriction-only lower-bound families, in kW |
| Ex-ante objective and terminal lower bound | `baselines/robust_storage_bidding/code/02_model.jl:252-263` | EUR objective components and terminal kWh requirement |
| Horizon covering budget | `baselines/robust_storage_bidding/code/02_model.jl:293-305` | 24/0.25/2.25 hours derive 2.75 hours |

The source parameter declaration at
`baselines/robust_storage_bidding/code/01_datastruct.jl:3-49` establishes the
positive-discharge battery convention, efficiency fields, window parameters,
prices, slacks, formulations, and solver settings. The complete Experiment 2
profile at `baselines/robust_storage_bidding/code/12.jl:27-95` fixes the
24/96/6 grid and the migrated numerical inputs.

### Sign and multi-rate adapters

The conversion at the public boundary is explicit:

```text
public_charge_positive_kw = -source_positive_discharge_kw
public_fcr_capacity_kw = source_xr_kw
```

The first equation changes only the sign convention. The second retains the
non-negative symmetric capacity magnitude. For one-based source planning index
`k`, hourly energy uses `ceil(k / 4)` and four-hour FCR uses `ceil(k / 16)`;
the native arrays use the equivalent zero-based `k // 4` and `k // 16` maps.

### FCR price unit correction

The `pr` source comment says `EUR/kWh` in
`baselines/robust_storage_bidding/code/01_datastruct.jl:18-20`, but the price
normalization and objective behavior establish `EUR/kW/4h-block`. The native
objective therefore computes `sum(price_per_kw_block * xr_kw)` exactly once
per block; it does not multiply the value by four hours. Day-ahead energy
retains `EUR/kWh` and the quarter-hour integration factor.

### Restriction indexing detail

The migrated restriction intentionally distinguishes interval-local
`lambdaHigh[l]` in the classification decision from prefix-specific
`lambdaHigh[k]` in the triangular tightening. Collapsing those two indices
would change `baselines/robust_storage_bidding/code/02_model.jl:225-230` and
the feasible region. The pure audit reports these classification and
tightening families separately.

### Terminal and slack semantics

The terminal constraint is
`initial_kwh - 0.25 * sum(alpha_kw) >= terminal_minimum_kwh - terminal_end_kwh`
from `baselines/robust_storage_bidding/code/02_model.jl:252-263`. The exact
reference target is not reconstructed from the rounded initial state.
`symin`, `symax`, and `syK[1]` are declared and penalized but inert in the
non-intraday hard robust SOC equations; only terminal-end `syK[2]` relaxes a
constraint. All four groups remain visible audit evidence, and any modeled
slack above `1e-6` blocks a deployable plan.

The displayed objective is exclusively the ex-ante sum of day-ahead value,
FCR capacity value, and the subtracted feasibility-slack penalty. Runtime and
Feature 012 realized activation, settlement, and profit are different evidence
domains and are excluded from this reconciliation.

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

In particular, source variants `lp_relax` and `lp_restrict`, all intraday
recourse equations, force-bilinear heuristics, rolling state carry-over, and
the combined backtest are intentionally excluded from the Feature 013 model.

The saved `bilinear_violations=0` is not treated as restriction feasibility
evidence: the reference save path computes that check only for relaxation
profiles. Equal rounded objective and bound values are likewise not upgraded to
formal termination, optimality, an exact gap, or unrounded feasibility.

## Evidence limits

Routine validation consists of hand-calculable equation oracles, bounded
Pyomo/HiGHS solves, public 96-step assembly, normalized-fixture checks, and one
Feature 012 replay of an authored accepted plan. The complete 2023-06-18 HiGHS
solve and licensed Gurobi solve of the same reference restriction are explicitly
selected benchmarks; optional external-activation replay cannot weaken the routine gate.

Source-rounded decisions are compared through one joint interval feasibility
and objective certificate. A different native schedule is called an
alternative optimum only when native feasibility, joint source feasibility,
and common objective equivalence all pass. Unsupported source fields remain
`unavailable`, and unexplained differences remain `mismatch`.

## Selected validation records

### Routine offline gate (2026-08-27)

The final exact quickstart selection passed 131 tests in 92.63 seconds on Python
3.14.6 with Pyomo 6.10.1 and highspy/HiGHS 1.15.1. Repeated same-environment
tests proved identical decisions, objective/bound/gap semantic payloads,
diagnostics, audits, certificates, comparisons, and result fingerprints while
excluding elapsed time and temporary paths.

The authored zero-bid restriction/relaxation record is:

- problem fingerprint
  `b804be1a3eb44cb1091a4111f4e7091b71d6ce23f945e877e1be8b1e6f226138`;
- comparison-problem fingerprint
  `6d3d536ba5fc14d344f8f6472decc39505fdd7c92003c1f7cac8819d83cd7189`;
- solve-policy fingerprint
  `860e55d721594ae41c50154132d34148e694ca3278bc7163bac64b79ea7a13f8`;
- objective-comparison-policy fingerprint
  `ed18f9cbc06fca9f16555e534acf235cf542c522202aaff72597839e224606c1`;
- restriction objective/bound/absolute gap/relative gap
  `0.0 EUR / 0.0 EUR / 0.0 EUR / 0.0`, semantic result fingerprint
  `c60d153b1901f36f4906f5f24a6c262a98b0d0a9039c1bd07a08ab3b21d764f6`,
  audit fingerprint
  `d5565b989d68e5510d8a0a48ab8c0825918e11924967be3c3dc02abd46784eb5`,
  and plan fingerprint
  `f8a3f310572c0676e5e70b8b773fa361bbac03b8fadf5cd1758fcc3244a57709`;
- restriction energy/FCR schedule fingerprints
  `649fedacdae1770ad6fdc5828a52ab9578105a48e980bdacfba6b3379374afb4`
  and `366dec5f5172f8e28f40a8873aecccc8e554ce6201a13b030030ae718844c78e`;
- relaxation objective/bound/absolute gap/relative gap
  `0.0 EUR / 0.0 EUR / 0.0 EUR / 0.0`, semantic result fingerprint
  `6e4736d49a5991983b6da4c1e6fc3f9c253347489de612e2c3ad826ef40b0445`,
  audit fingerprint
  `f278e5d9c41232a589b9223dc639493f3048bb8bf53eb1e63e51dfabead6a608`,
  and no plan; and
- common decision-vector fingerprint
  `a00a601eb3cdd1acabf87e3c58c75233b9af3c109675c5d41af0a797bc5a180c`
  plus satisfied bound-comparison fingerprint
  `2f0eee49feae804ea133e28c0ad2523e4ff014f75c4d7ae785135a6534b8d023`.

### Selected full reference benchmark (2026-08-27)

The explicitly selected `reference_benchmark` used the complete caller-owned
`native-reference-benchmark-highs-v1` policy. It selected HiGHS, a 3,600-second
limit, one thread, random seed `13`, primal and dual tolerances of `1e-7`, MIP
feasibility and relative-gap tolerances of `1e-6`, objective-comparison
tolerances of `1e-6 EUR` absolute and `1e-9` relative, no feasible-incumbent
plan opt-in, and `solver-output-kw-1e-9-half-even-v1` canonicalization. The
policy fingerprint was
`d4d8934676fce6755f525ef8844f796669e0ec49158a2107515b2dee29b682ed`.
These settings are native benchmark evidence and are not attributed to Julia.

HiGHS 1.15.1 with Pyomo 6.10.1 reached `maxtimelimit` with a complete,
independently audited incumbent after 3,601.84 seconds. The selected pytest
gate exited successfully with one actionable resource-limit skip after
3,603.13 seconds. The native status was
`feasible`, not `optimal`; objective and same-solve upper bound were
`9.859189984425477 EUR` and `12.053002643603337 EUR`, producing an absolute gap
of `2.19381265917786 EUR` and relative gap `0.18201378727334314`. The result
therefore emitted no plan under the default policy. Stable identities were:

- semantic result
  `752861b52725f493b20134f5ab367cef7fd8d4445f791e685121e2821bf5003e`;
- decision vector
  `8347e2dd0c72664f610185a87ed0f482955cbf8b0c2b7eb7237a8a13c9ad36c0`;
- independent audit
  `cab62ebe16f804f0326e97eddcc56783acbd24925529cc789ec585b7a53ccec7`;
- certification request
  `ec98f78880b51da8a6817e45432c4e7ff803d0076338e148354654b2ac49badd`;
- joint certificate
  `781736f31e4e79666123fd9c1c852c4f0fa4c5f589f9f58d0c5170c3d9f78216`;
  and
- comparison
  `b81c3cc88b6b10e8d6a662a3e5e0d8c50d0c9e6f60e12ca9ce14f46d8b05ec26`.

The comparison produced `1 exact`, `15 source_precision_compatible`,
`0 alternative_optimum_compatible`, `21 mismatch`, and `7 unavailable` fields,
so its overall status is `mismatch`. Native positive-discharge comparison-frame
fingerprints were energy
`76971271b34b4cf8ed331bb9afe39194b5c0e6c56fd3b8920d867d28812b772f`, FCR
`b7c6bc3eec6441eda96a8da3da6fadb204627b7cd7a1d118edfc16c082653c4a`, and
combined
`5a97699bad69aec559a676de60fa7274eb907c2fd32dda0e1ddfc4de749158cd`.
Source counterparts were
`736a4b28e05e7a6d9e625fe060bb1df021081d618ae6509f283dc89d4b9162de`,
`928a73a53d00bbc798f1ea7f599dc1e695c0ca2516071e72bb3929559e011f61`,
and `df898785797d80ae9d19c584400553bb30f997db90a3ee3bf83d2cb4a2df011b`.
Producer-specific schedule and plan fingerprints are unavailable because the
native non-optimal incumbent was not eligible for a plan and the Julia record
contains no Feature 012 producer envelopes.

The normalized source reports rounded objective and bound `11.028 EUR`, a
1,070.788-second Gurobi run, and three-decimal decisions. It does not report
termination, primal/dual status, exact gap or proof, solver tolerances or
versions, unrounded decisions, equation residuals, or restriction bilinear
evidence. The native objective band therefore does not intersect the source
objective interval, and no joint objective-equivalent rounded source schedule
was certified. This resource-limited result is retained as incomplete
comparison evidence; it neither establishes Julia parity nor identifies a
formulation discrepancy by itself, and it does not weaken routine acceptance.

### Selected full Gurobi reference benchmark (2026-08-28)

The optional `gurobi` extra installed `gurobipy` 13.0.2 under Python 3.14.6,
and the caller-configured ignored `GRB_LICENSE_FILE` passed a local licensed
solve probe. The full restriction then used the separate
`native-reference-benchmark-gurobi-v1` profile with the same declared limit,
thread, seed, tolerances, incumbent policy, and canonicalization as the HiGHS
benchmark. Its policy fingerprint was
`420682797823ce0ce61f0c3034937b6f602c3508f33b6ae397df7561806edca2`.
This native policy is not attributed to Julia, and Gurobi 13.0.2 is not the
source environment's recorded Gurobi_jll 11.0.3.

Gurobi reached `maxtimelimit` after 3,602.20 seconds with a complete feasible,
independently audited incumbent. It did not prove optimality: objective and
same-solve upper bound were `11.028269482283491 EUR` and
`11.189539354884609 EUR`, for an absolute gap of `0.16126987260111747 EUR`
and a relative gap of `0.014412556896787514`. Feasible-incumbent plan opt-in
remained disabled, so the result correctly emitted no market plan.

Unlike the HiGHS incumbent, all 24 positive-discharge `x0` decisions, all six
`xr` decisions, and the objective lie inside the Julia artifact's declared
three-decimal source-precision intervals. The independent audit passed with
zero modeled slack and maximum equation residual
`3.1177194159681676e-10`. Stable native identities were:

- semantic result
  `949812bb9348fe20ee6953312733f46aa1f24f665d0fc044a0348bbb0bfa8e90`;
- decision vector
  `4a119bbd2e8792a072746a724149de90b96a3c6265e2abf576009dc60cd530d8`;
- independent audit
  `79d8c1d350529a63a1b69df57e8f2304d0c81168782861b4f9668f3636b95eb1`;
- certification request
  `c42d844acd848ebce8f9e58b56132eae84567154ba2248208cc0bd9d1bc5fa66`;
  and
- direct audited-witness certificate
  `d98ef6bee6c7f3b786f85f7a0ac77c8aa11e866490925e927d4b64375517e02e`.

The comparison therefore has `3 exact`, `34 source_precision_compatible`,
`0 alternative_optimum_compatible`, `0 mismatch`, and `7 unavailable` fields,
with overall status `source_precision_compatible`. The unavailable fields are
the source bound proof and producer-specific plan/schedule identities. This is
strong reproduction of the saved Julia result at its available precision, but
not exact Julia parity: the native solve is not proven optimal, the Gurobi
versions differ, and the Julia record omits unrounded decisions, tolerances,
termination, and proof metadata.

### Optional Gurobi formulation evidence (2026-08-28)

The explicitly selected optional Gurobi gate completed with three passing
tests in 28.57 seconds. It exercised the linear restriction, linear relaxation,
and nonconvex exact route under the configured license; verified that the
restriction alone may emit a plan; and satisfied
`restriction <= exact <= relaxation` on the deterministic bounded case.
Gurobi remains absent from routine validation, imports lazily only after
explicit selection, and never silently falls through to HiGHS.

### External Feature 012 replay (2026-08-27)

The explicitly selected `external_reference_data` gate found the governed CSV
at its ignored path, validated all 528,805,941 bytes and SHA-256, and passed on
the final rerun in 624.80 seconds. Bid selection completed before the CSV was
opened. The distinct
`native-reference-external-replay-highs-v1` policy used a 600-second limit and
explicit feasible-incumbent opt-in; its policy fingerprint was
`f99c91a2afff96667c11797c47ea95e04a37756c0cddbcbef19bf7617c5a863c`.
The accepted restriction incumbent was independently audited, had status
`feasible`, objective `9.859189984425477 EUR`, and same-solve upper bound
`12.256713420445767 EUR`. These values are not an optimality claim.

Both plans used activation artifact fingerprint
`8f36b8ac32987e6d8a7c055e150560873cd9252aa8e842d6c2cc0bf3f523dae7`
and the same 24/6/96/8,640 Feature 012 mappings. Recorded fingerprints were:

- plan `6bbbf946b8d12762971e5b369d4f63fa57b0a17d8977ca84de4655927bf36f11`;
- physical trace `f292f4990d99f6ca4aa7bb12c304b70751396e3c2005544577c58ceb153573f6`;
- settlement `8e5382463fd8e9bd110214fa4cd87be7539ae0fab70eb4ead0bb2b55cbbf72ca`;
- result `6aa9c1e75101354523432adecbf6b8dfb7fa946211151ebcfc7e767575777bb3`;
  and realized profit `10.748929939607164 EUR`.

Native fingerprints were:

- plan `3ef3d2ac8f8e5028d9ef7199e7afcb614f32a0a775a1bd2ca72821d6b6842a79`;
- physical trace `0612d26460bcfb10d69cc20b391dc44b3ed5786083374ff45fa06b13f00b769f`;
- settlement `9b6100295e3ece76b5e317050d7375cdf95b19842d7098950672a17f2a52b937`;
- result `1465d37034271f00c0823cdc74f6ece139382719af378d39d7da12512695fe56`;
  and realized profit `9.61415456889596 EUR`.

Different trace, settlement, and profit values are expected because this gate
replays different accepted schedules. It demonstrates one common evaluator and
activation input; it does not establish schedule equality or Julia optimization
parity.

### Source-only walkthrough follow-up (updated 2026-08-31)

The guided notebook at
`examples/robust_fcr_bidding/robust_fcr_bidding_walkthrough.ipynb` uses an
authored 24/96/6 problem in which a 20 kWh battery jointly selects day-ahead
arbitrage and symmetric FCR. It earns 2.8 EUR of ex-ante arbitrage value and
1.454545 EUR of ex-ante FCR value, with no reserve in the first two blocks and
3.636364 kW in the final four. Default execution remains offline: HiGHS solves
the restriction and relaxation, the independent audit governs restriction
deployability, and only the emitted fixed plan enters Feature 012 after three
evaluation-only activation traces have been authored. The notebook does not
introduce another replay, battery transition, settlement, or profit model.

Six unit-labelled figures now focus on the decision: input prices, shared
baseline/reserve power headroom, block-by-block constraint attribution,
ex-ante objective components, nominal/upward/downward physical replay, and
scenario-dependent realized economics. The normalized Julia/Gurobi source
precision is reported as a table; a residual plot with explicit kW units and
the closed +/-0.0005 kW envelope appears only when the identical historical
native benchmark is enabled.
The complete historical HiGHS solve, licensed Gurobi reference benchmark,
external activation replay, and figure export are disabled by default. The committed
notebook retains stable cell IDs, empty outputs, and no execution counts.

The execution contract blocks network calls and credential reads, checks all
three settled Feature 012 scenarios, verifies six in-memory figures, pins the
display fingerprint
`a49277c072f2e45803614a3c9766625b4baf63c6e165986aba0c4fa52fc05395`,
and requires no exported files or changes to the committed notebook.
