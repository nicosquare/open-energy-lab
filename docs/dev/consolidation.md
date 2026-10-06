# Library Consolidation

Working tracker for turning Open Energy Lab into a readable library after
specs 001–016. This work runs outside Spec Kit, as small reviewed PRs. Each PR
checks its item off here and links itself.

## Why

Each spec was built as a self-contained slice with its own validation helpers,
error classes, fingerprint and evidence records, parity checks, and a lazy
`__init__` that lists every export three times. None of this was shared across
packages. The domain logic is sound: one battery kernel, compact controllers,
weather and demand, and a substantial TPM compile/attach pipeline. Most of the
bulk comes from this scaffolding.

## Decisions (2026-09-28)

| # | Topic | Decision |
|---|---|---|
| D1 | Julia reference parity | Keep it runnable as thesis evidence, but move it out of the core library into `validation/`. Library users don't see it. |
| D2 | Provenance | Fingerprint and version only what gets persisted (artifacts, study results), using one shared helper. In-memory objects are plain dataclasses. |
| D3 | Compatibility | Break freely (v0.1, no outside users). Rename APIs, change formats, regenerate fixtures, and re-run `artifacts/` and `tmp/` outputs as needed. |
| D4 | Workflow | Consolidate outside Spec Kit in small PRs, then rewrite `AGENTS.md` around the new architecture. Spec Kit stays for new research features. |
| D5 | TPM | Extract it as a standalone distribution in a uv workspace (`packages/tpm/`) with no `open_energy_lab` imports. OEL `planning` and `~/dev/tpm_for_sp` both depend on it. Move it to its own repo once the API settles. The name is still to be decided. |

## Baseline (main @ `3a5307e`)

| Package | Lines | Files | `__all__` exports |
|---|---|---|---|
| control | 20,983 | 16 | 109 |
| tpm | 19,116 | 21 | 140 |
| simulator | 13,289 | 23 | 111 |
| market | 12,981 | 10 | 86 |
| planning | 5,119 | 9 | 33 |
| weather | 2,491 | 7 | 8 |
| demand | 2,050 | 7 | 7 |
| visualization | 1,521 | 5 | 3 |
| core | 328 | 2 | 4 |
| **total src** | **77,900** | | |

Tests: 279 `test_*.py` files, 66,963 lines. About 15% of that is meta or
contract tests (import boundaries, export lists, doc wording).

| Smell (grep over `src/open_energy_lab`) | Count |
|---|---|
| `def _finite(` copies | 17 |
| `def _non_empty*` copies | 21 |
| `_sha256` / `_fingerprint` / `_sha` copies | 26 |
| canonical-JSON serializers | 10 |
| `_freeze` / `_deep_freeze` / `_thaw` copies | 22 |
| `fingerprint` mentions | 1,969 |
| `object.__setattr__` | 817 |
| `Feature 0NN` / `feature-0NN` strings | 93 |
| `legacy` mentions | 151 |
| `parity` mentions | 112 |
| exception classes | 78 |

Import cycles, each hidden by lazy imports:

- ~~control ↔ simulator: plan and schedule types live in `control`.~~ Removed in A2.
- ~~simulator ↔ market: `market/reference_fcr.py` golden fixture.~~ Removed in A3a.
- tpm ↔ planning: `tpm/fit.py` and `tpm/query.py` load planning datasets.

Baseline test run (`uv run pytest tests/unit tests/integration`, 24m53s):
**2209 passed, 6 failed, 2 skipped**. Parity suite not run. All 6 failures are
in TPM and were already failing at `3a5307e`:

- `tests/unit/tpm/test_package_surface.py`, 2 tests. The root exports 16 names
  the test doesn't expect (e.g. `CategoricalMixtureConfig`).
- `tests/integration/tpm/test_backend_adapter_workflow.py`,
  `test_generic_rows_workflow.py`, `test_real_spflow_backend.py`. These fail in
  the v1 serialized `spn_mip` payload path used for direct chance-model solves
  ("requires a valid current-SPFlow model payload", "does not expose a
  serialized SPN MIO payload"). This path is retired in B3.
- `tests/integration/tpm/test_mio_solver.py::test_solve_spn_chance_model_from_artifact_solves_with_gurobi`.
  It loads a `schema_version 'v1'` fixture, which is now rejected as
  `LegacyTPMArtifactVersionError`.

## Progress

Regenerate with `uv run python tools/consolidation_metrics.py`.

| After | src lines | market | simulator | control | core | `_finite` | `_non_empty*` | sha/fingerprint | freeze/thaw |
|---|---|---|---|---|---|---|---|---|---|
| baseline `3a5307e` | 77,900 | 12,981 | 13,289 | 20,983 | 328 | 17 | 21 | 26 | 22 |
| A1 core + market | 77,838 | 12,517 | 13,289 | 20,983 | 730 | 14 | 14 | 21 | 15 |
| A1 simulator | 77,492 | 12,510 | 12,914 | 20,983 | 766 | 8 | 8 | 12 | 8 |
| A1 control | 77,250 | 12,504 | 12,914 | 20,728 | 785 | 1 | 2 | 4 | 6 |
| A1 weather/demand/planning | 77,214 | 12,504 | 12,802 | 20,728 | 785 | 1 | 2 | 4 | 6 |
| A2 plan/schedule contracts | 77,313 | 12,504 | 13,782 | 19,847 | 785 | 1 | 2 | 4 | 6 |
| A3a validation code (+6,873 in `oel_validation/`) | 70,425 | 11,316 | 13,222 | 14,707 | 785 | 1 | 2 | 4 | 6 |
| A4a package surfaces | 69,053 | 11,044 | 12,778 | 14,227 | 785 | 1 | 2 | 4 | 6 |
| A4b names | 69,038 | 11,044 | 12,778 | 14,212 | 785 | 1 | 2 | 4 | 6 |

A1 simulator full suite: **2230 passed, 4 failed (the v1 `spn_mip` TPM tests still in the baseline; the two surface tests were fixed by #18), 2 skipped**.

A1 control full suite **plus `tests/parity`**: **2235 passed, same 4 v1 `spn_mip` TPM failures, 3 skipped** (1h35m).

A1 weather/demand/planning full suite: **2232 passed, same 4 v1 `spn_mip` TPM failures, 2 skipped** (parity not rerun; no parity-covered code changed).

A2 full suite **plus `tests/parity`**: **2234 passed, 3 skipped, 6 failed**. Four are the v1 `spn_mip` TPM tests. One was an integration ownership assertion missed in the first pass, fixed in `85df9b2`. One was the flaky ENTSO-E refresh test below, which loads no module changed by A2.

A3a full suite **plus `tests/parity`**: **2237 passed, 3 skipped, 6 failed**. Four are the v1 `spn_mip` TPM tests. Two were the robust-FCR and rolling walkthrough notebooks, which still imported moved names from the control root; fixed in the notebook commit (13 notebook tests pass).

A3b: full suite **plus `tests/parity`**: **2238 passed, 4 skipped, same 4 v1 `spn_mip` TPM failures**. The extra skip was intermittent: two later runs covering every test file skipped only the two opt-in Gurobi checks and the robust benchmark below.

A4a full suite **plus `tests/parity`**: **2210 passed, 3 skipped, same 4 v1 `spn_mip` TPM failures**. Collected tests: 2246 on `main` − 50 (the 24 superseded meta-tests, parametrized) + 21 (new surface tests) = 2217.

A4b full suite **plus `tests/parity`**: **2208 passed, 3 skipped, 6 failed**. Four are the v1 `spn_mip` TPM tests. Two were a test that simulates the old dependency-error wording, fixed in the follow-up commit; that test file then passed in full. Skips: the two opt-in Gurobi checks and the robust benchmark (resource limit).

### Known issues found along the way

- `tests/integration/market/test_entsoe_fixture_workflow.py::test_unchanged_refresh_writes_nothing_and_preserves_current_identity`
  failed twice within about an hour on 2026-09-29 (refresh reported
  `published` instead of `unchanged`), then passed 9 times in a row on both
  the A2 branch and `main`. It looks time-dependent. It could be a real bug
  (an unchanged refresh occasionally publishing a new artifact), so
  investigate it separately; it is out of scope for the consolidation PRs.
  Tracked in [#23](https://github.com/nicosquare/open-energy-lab/issues/23).

A1 core + market full suite: **2226 passed (2209 + 17 new core tests), same 6 baseline TPM failures, 2 skipped**.

## Track A — energy library

- [x] **A1 core foundation.** Add `core/validation.py`, `core/serialization.py`
  (canonical JSON, fingerprint, atomic write-once), `core/time.py`, and
  `core/errors.py`. Move `market` onto them first, then the other packages.
  Behavior-preserving.
  - [x] core + market ([#17](https://github.com/nicosquare/open-energy-lab/pull/17)). Every market
    copy was proven equivalent to its core replacement before deletion
    (87/87 cases at `1319b4e`). Kept local because behavior differs:
    `market.artifact._positive_int` / `_non_negative_int` (accept `2.0`),
    `market.reference_fcr._freeze` (sorts keys) and `_integer(minimum=)`,
    `market.activation._utc` (also parses strings), `market.time._require_utc`
    (offset in message). Standardized: error message wording only; no test
    pinned it.
  - [x] simulator ([#20](https://github.com/nicosquare/open-energy-lab/pull/20)). Proven equivalent
    first (42/42 cases at `28d7d8c`). core gained `positive`, `non_negative`,
    and `freeze(sort_keys=)`; `market.reference_fcr._freeze` moved onto it.
    Also: `BatteryComponent.to_dict()` replaces three identical
    `_battery_payload` copies (two more remain in control), and the eight
    helpers duplicated in `stochastic_weather` / `stochastic_demand` now live
    in `simulator/_family_summary.py`. `validated_summary_fields` takes
    `supported=` explicitly because the two modules allow different fields.
    Kept local: the product-specific enum parsers in `restoration_*`
    (`_input_kind`, `_direction`, ...) and `_blackout_grid_availability`
    (differs per module). One difference: the old `_thaw` in three FCR
    modules left Enum members as-is, while `core.thaw` returns their values.
    Canonical bytes are identical and those modules hold no Enums.
  - [x] control ([#21](https://github.com/nicosquare/open-energy-lab/pull/21)). Proven equivalent first
    (40/40 cases at `0e3ff69`). core gained `integer(minimum=)` and
    `normalize_zero` on `positive` / `non_negative`. The last two
    `_battery_payload` copies now use `BatteryComponent.to_dict()`. Two known
    differences are asserted in the proof rather than skipped:
    `fcr_bid_plan._thaw` (Enum values; bytes identical) and
    `stacked_service._canonical_json`, which never thawed: same bytes for
    everything it accepted, and it now also accepts read-only mappings and
    non-string keys. Kept local: `robust_fcr_bidding._positive` (a test pins
    its message); the robust-FCR canonical form `_deep_freeze` / `_thaw` /
    `_canonical_json` / `_fingerprint` (a provenance-format decision for A5);
    `restoration_service._plain` (converts only product/direction enums in
    the persisted `parameters`); the `_finite_tuple` variants; the
    tuple-returning `_sequence` in the reference modules; `_utc_from_text`;
    `fcr_rolling_reference._enum`. Line savings are small here because
    control's bulk is evidence and provenance code (A3/A5).
  - [x] weather, demand, planning ([#22](https://github.com/nicosquare/open-energy-lab/pull/22)). Narrowed scope, agreed on
    2026-09-29: their `_positive_int` / `_string_sequence` /
    `_validate_timestamp` copies coerce (`int(value)`, `str(item)`) and
    differ from each other and from core's strict checks, so replacing them
    would change behavior. They are deferred to A5. Done instead:
    `simulator/_weather_schema.py` moved to `weather/schema.py` (weather no
    longer imports a private simulator module), and exact duplicates removed:
    `_candidate_ordering` (planning), `_numeric_vector` / `_covariance_matrix`
    (weather), `_numeric_sequence` and the UTC parser (demand). Not merged
    despite identical code: `_validate_training_record_summary`, which calls
    each module's own differing helpers.
- [x] **A2 shared schedule types** ([#24](https://github.com/nicosquare/open-energy-lab/pull/24)).
  Decided 2026-09-29: the simulator owns the contracts it evaluates, not
  `core/`. `core` would otherwise depend on `market.time`, and `market` already
  depends on `core`. Layering is now market ← simulator ← control.
  `control/fcr_bid_plan.py` moved to `simulator/fcr_bid_plan.py` (the
  reference mapping stays in control until A3). The restoration contracts
  (capacity and energy schedules, capability) moved to
  `simulator/restoration_contracts.py`; the aFRR/mFRR baseline heuristics stay
  in control. `test_simulator_modules_never_load_control` enforces the
  direction. Test changes: ownership assertions for the moved names only.
- [x] **A3 validation package** (D1). Shape agreed on 2026-09-29: a top-level
  `oel_validation/` package, not in the wheel, importable from the repo root.
  TPM evidence stays with Track B.
  - [x] A3a code ([#25](https://github.com/nicosquare/open-energy-lab/pull/25)):
    `market/reference_fcr.py`, `control/robust_fcr_reference.py`,
    `control/fcr_rolling_reference.py`, the evaluator parity functions, and the
    reference schedule mapping now live in `oel_validation/`. 16 exports left
    the control and simulator roots. `evaluate_fixed_fcr_bid` keeps a generic
    optional `comparison_fixture` hook (protocols `EvaluationComparisonFixture`
    and `EvaluationComparison`), so request and report bytes are unchanged.
    `tests/unit/test_validation_boundary.py` guards the boundary. Breaks
    simulator ↔ market.
  - [x] A3b scripts ([#26](https://github.com/nicosquare/open-energy-lab/pull/26)). Scope
    narrowed on 2026-09-29: the six reference tools (`run_reference_*`,
    `normalize_reference_*`) moved from `examples/` to `oel_validation/scripts/`.
    Run them with `uv run python -m oel_validation.scripts.<name>`; the
    commands documented before failed on `main`. The three reference fixtures
    stay in `tests/fixtures` (test inputs for 20+ tests). The generation
    command recorded inside `fcr_bidding/..._restriction_v1.json` is kept as
    the historical record, because moving the fixtures would force a
    provenance and fingerprint regeneration chain.
  - [ ] Follow-up: `control/_robust_fcr_formulation.py` still holds the
    reference-certificate helpers (`assemble_robust_fcr_reference_certificate`,
    `audit_closed_reference_witness`, `RobustFCRReferenceIntervalAudit`). They
    share formulation internals with the real solve path.
- [x] **A4 package surface**, split into three PRs on 2026-09-30:
  - [x] A4a surfaces: plain-import roots with curated exports (market 86 → 29,
    simulator 106 → 42, control 98 → 37; planning, weather, demand and
    visualization unchanged). Everything else stays importable from its
    submodule. `control/fcr_bid_plan.py` is removed and simulator exports the
    contracts it owns. `tests/unit/test_package_surfaces.py` replaces 24
    per-package meta-tests after an assertion-by-assertion audit (see the
    A4a commit message); only lazy-loading checks were dropped on purpose.
    The audit caught a regression: eager imports loaded `socket` through
    `multiprocessing`, fixed by importing it where it is used.
  - [x] A4b names: `build_feature_010_market_context` → `build_market_data_context`,
    `settle_reference_fcr_bid` → `settle_fixed_fcr_bid`,
    `ReferenceSettlementBreakdown` → `FixedFCRBidSettlement`, and
    `FEATURE_010_DEFAULT_SETTLEMENT_PROFILE` → `STACKED_SERVICE_SETTLEMENT_PROFILE`
    (the value is unchanged). The two private solver aliases for "Feature 013
    callers" are removed. About 40 messages, docstrings and comments now
    describe the behavior. Kept for A5 (33 lines in control and simulator):
    persisted strings such as producer_version, semantics, conversion_id,
    context_kind, creation_cause, efficiency_lineage,
    feasible_incumbent_rule, `feature_012_*` payload keys, and one recorded
    plan diagnostic. tpm is untouched.
  - [x] A4c tests: pytest now runs all of `tests/`, with a default `-m` that
    deselects the `slow`, `notebook` and opt-in groups (`licensed_gurobi`,
    `live_*`, `reference_benchmark`, `external_reference_data`). A plain
    `pytest` is the routine offline suite: 2155 passed + 4 xfailed in about
    2 minutes. CI went from 4 jobs with file lists and about 15 `--ignore`
    entries to `tests` (3.11–3.14), `slow` (every push/PR, agreed on
    2026-09-30) and `notebooks`; licensed, live and reference checks are
    local opt-in. Closes a CI coverage gap (market, core, visualization and
    several root-level tests never ran) and stops live ENTSO-E/RTE calls in
    routine local runs. The 4 v1 `spn_mip` TPM tests are
    `xfail(strict=True)` until B3. Still open: `AGENTS.md` "Useful Checks"
    lists the old commands (rewritten in A7).
    The first CI run found two issues local 3.14 runs could not: the
    boundary tests forbade all of `urllib`, but `pathlib` imports
    `urllib.parse` on Python <= 3.12 (now only `urllib.request` and
    `urllib.response` are forbidden); and float `sum()` differs on Python
    3.11, so pinned fingerprints failed there. OEL now requires
    **Python >= 3.12** (agreed 2026-10-01; caveat: `tpm_for_sp` pins
    < 3.12). CI on GitHub: tests 3.12–3.14 about 3 min each, slow about
    6 min, notebooks about 3 min, all green.
- [x] **A5 provenance trim** (D2). Keep fingerprints on persisted artifacts
  and results only. Add one versioned JSON artifact base shared by weather,
  demand, market, and the planning dataset. Settle one loading behavior for
  the coercing helpers left in weather, demand, and planning, and decide the
  fate of the robust-FCR canonical form kept in control.
  Plan (agreed 2026-10-01): three PRs. Existing saved rolling results may
  break (D3); restoration fingerprints are trimmed in A6.
  - [x] A5a artifact base: new `core/artifact.py` (JSON decode without
    NaN, path-or-mapping reader, staged fingerprint sealing and
    verification, immutable filenames, write-once publication, sidecar
    checks). The four market artifacts use it (market −365 lines net; core +258).
    Weather, demand, the planning dataset and the study manifest now load
    strictly with core checks (no `int()`/`float()`/`str()` coercion; NaN,
    bools as numbers and naive timestamps are refused), each with its own
    `ValidationError` subclass, and write atomically. Planning `created_at`
    is filled once at construction instead of inside `to_dict()`.
    Persisted bytes are unchanged: the SHA-256-locked market fixtures pass
    and key order is kept. Small behavior changes: sidecar locators with
    `:` are refused; activation traces are written once, with a race check;
    study shard locators must be safe relative paths. Follow-up: planning
    validation still lives in `from_dict`, not the constructor.
    Checks: `pytest` 2174 passed + 4 xfailed, `-m slow` 34 passed,
    `-m notebook` 7 passed.
  - [x] A5b in-memory fingerprints (agreed 2026-10-01: remove self-only
    hashes, turn real checks into object comparisons, keep hashes whose
    values the rolling study saves). Removed from FCR settlement, market
    context, evaluation request and reports, rolling-evaluation segments,
    every robust bidding input (battery, time contract, budgets,
    uncertainty, terminal rule, prices, solve policy), formulation
    profile, decisions, witness audit, bound comparison, model input and
    the rolling data descriptor (src −482 lines net). Checks that compared
    hashes now compare objects: horizon budget vs recovery window,
    bound-comparison problems (`RobustFCRSolveResult` holds its problem),
    predecessor prices and fixings. Saved hash values change, the saved
    format does not; rolling results saved before this branch no longer
    resume (accepted). Evidence: a `to_dict()` snapshot of the control,
    simulator and parity tests is identical to `main` apart from the
    removed keys and hash values (tooling kept in history,
    commit `daa4287`). Deferred: stacked-service replay hashes (A6; the
    stated reason, feeding restoration settlement, was wrong, see A6
    simulator); producer lineage
    (`producer_input_fingerprints`, `configuration_fingerprint`), which is
    caller-supplied provenance with a look-ahead guard; and the rolling
    backtest's acceptance policy, battery binding, numeric policy and day
    input hashes, which are woven into saved evidence (A5c).
  - [x] A5c-1 (agreed 2026-10-01 to split A5c in two): robust FCR hashes
    use core canonical JSON (bytes unchanged: every robust golden pin
    passes untouched). The 33 persisted `feature-0NN` strings now describe
    what they are (e.g. `feature-013-v1` -> `robust-fcr-bidder-v1`,
    `feature_010_market_artifact` -> `market_artifact`); a `to_dict()`
    snapshot matches `main` once the same renames are applied, apart from
    hash values. Only the remaining `feature-016` mention is a tpm
    docstring (Track B). Checks: `pytest` 2174 passed + 4 xfailed,
    `-m slow` 34, `-m notebook` 7.
  - [x] A5c-2 (scope agreed 2026-10-01 from a field-by-field map): the
    saved `RollingFCRStudyResult` (now v2) keeps one seal, the resume
    identity (manifest, profile, requested day inputs, supplied
    activations) and the `plan_fingerprint`/`activation_fingerprint`
    links. Nested seals, links to unsaved objects, `fingerprint_evidence`,
    aggregate `source_fingerprints`, `stable_runtime_evidence` and
    per-record identity copies are gone. A two-day test study goes from
    28.7 KB / 124 hashes to 15.5 KB / 14. Resume compares content.
    Manifest, profile and day-input hashes are computed properties. src
    −558 lines net. Evidence (commit `ba4d380`): every saved result lost
    exactly those paths, gained none, and changed no other value besides
    `semantics_version`. Kept on purpose: producer lineage maps (fixings,
    cutoff checkpoint, numeric policy, caller state, carry evidence,
    battery binding), as decided in A5b. The stale pins in
    `docs/migration/fcr-rolling-backtest-parity.md` carry a dated note.
    Checks: `pytest` 2174 passed + 4 xfailed, `-m slow` 34, `-m notebook` 7.
- [x] **A6 merge variants**, one PR per package:
  - [x] market. Mapped 2026-10-01; decided not to merge the two artifact
    formats or the FCR/restoration sign conventions: the data is genuinely
    different (fixed three-series ENTSO-E artifact vs open-ended RTE
    series with value states; unitless upward-positive FCR activation vs
    battery-signed kW restoration requests) and the real-data fixtures pin
    their bytes. Two PRs instead:
    - [x] market-1: one load/publish sequence for both artifacts
      (`market/_artifact_io.py`); the restoration sign convention lives on
      `RestorationDirection` (`signed`, `magnitude_of`, `of_signed`,
      `of_two_sided`); restoration grid, price, proxy-mapping and rule
      self-hashes are gone, with hashes that feed saved values computed
      from `to_dict()`, so every saved value and the real-replay expected
      results are unchanged. Net +26 src lines: a structure change, not a
      size one. The baseline configuration hashes stay (they hash build
      inputs the configs do not keep).
    - [x] market-2: after reading both clients, only about 30-50 lines
      were really shared (agreed 2026-10-01 to keep it small).
      `market/_http.py` holds the header lookup, the transient-status test
      and one bounded open/read helper; each client keeps its own retry
      loop, Retry-After rule and error reporting. RTE now also refuses
      HTTPS-to-HTTP redirects and oversized Content-Length before reading
      (new tests pin both). Net +25 src lines: one implementation of the
      transport safety checks rather than fewer lines.
  - [x] simulator (mapped and scoped 2026-10-01). Two tracker items were
    already true: stacked FCR has one replay kernel shared by the stacked
    replay, bid evaluation and rolling evaluation, and
    `battery.apply_power_request` is the only step. Merging stacked with
    aFRR/mFRR, or unifying their saturation rules, would change pinned
    results for little gain. Done: one price-alignment loop for both FCR
    settlements (each keeps its own arithmetic and `sum()`/`+=`, so bits
    are identical), the dead `_directional_energy` deleted, and the stacked
    replay result hashes its own `to_dict()` (values unchanged). Correction
    to A5b: the stacked replay hashes never fed the restoration settlement
    (that reads the aFRR/mFRR results' own hash). Correction to A5b/A5c:
    the opt-in `external_reference_data` tests do run on this machine; one
    still read a hash removed in A5b and is fixed; all 6 pass.
  - [x] control (mapped and scoped 2026-10-02). aFRR and mFRR now share one
    baseline path with a product parameter (public names, the two config
    classes and mode enums stay; payloads unchanged, so the restoration
    expected results match byte-for-byte; -121 lines). The three rolling
    loops share one study-result assembly (-25 lines); a cutoff-strategy
    object was not built, because the per-mode lifecycle rules are what
    differs. The rolling problem was not folded into the base problem: its
    fields, fingerprint, solver path and witness audit are genuinely
    different, and sharing the formulation core (~80 lines) would change
    constraint order and could change HiGHS solve paths and golden hashes.
- [ ] **A7 docs and rules.** Write concept docs, archive `docs/migration/` and
  `specs/` as history, and rewrite `AGENTS.md`.

## Track B — standalone TPM library

Can run in parallel with Track A once the TPM part of A3 lands.

Mapped 2026-10-02; order changed so the move comes after the cleanup:

- [x] **B1 decouple inside OEL.** `tpm` imports nothing from
  `open_energy_lab` outside itself (enforced by
  `tests/unit/tpm/test_standalone_imports.py`). `fit_tpm_artifact` and
  `fit_tpm_artifact_from_study_manifest` moved to `planning/tpm_fit.py` and
  now build a generic request for `fit_tpm_artifact_from_rows` (two optional
  request fields added); fitted artifacts are identical apart from the
  pickle hash, which varies run to run. The empirical (`fixture_replay`)
  query reads the dataset JSON itself. `build_spn_chance_model` stays in
  `tpm`: it does not import OEL. src -118 lines. tpm tests that use planning
  fixtures move out in B3.
- [x] **B2 retire dead paths** (scope agreed 2026-10-02). Removed the v1
  serialized `spn_mip` path (`build_spn_mip_payload`, `supports_spn_mip`,
  the two `*_from_artifact` helpers), its `planning/problem.py` branch, the
  `supports_spn_mip_serialization` capability flag, the tpm `FEATURE_NAME`,
  the 4 strict-xfail tests and one synthetic planning test. src -229 lines.
  Kept because they are live: `planning-v1` MIO mode (planning payloads),
  MIO compiler v1 (every schema-v2 artifact, incl. the production SPFlow
  fixture), `fixture_replay` (6 fixtures, 8 test files), and the exact
  categorical lookup in `build_spn_chance_model`; revisit in B4/B5.
- [x] **B3 workspace package** (agreed 2026-10-02: installed as `sp-tpm`,
  imported as `tpm`; Python >= 3.11 for sp-tpm, OEL stays >= 3.12).
  - [x] B3a move: uv workspace with `packages/sp-tpm/` (git mv keeps
    history). Core dependencies numpy, scipy, torch, `spflow==1.1.0`;
    Pyomo, HiGHS and Gurobi are extras (tpm_for_sp excludes Pyomo/HiGHS).
    All `open_energy_lab.tpm` references now use `tpm`; no shim.
  - [x] B3b standalone tests: `tests/{unit,integration}/tpm` now run with
    only sp-tpm installed. The 5 notebook and fitting test files that need
    OEL moved to the planning test folders, and the 3 `test_mio.py` tests
    built on planning's piecewise terms moved to
    `tests/unit/planning/test_spn_chance_model_planning_terms.py`. TPM
    fixture paths live in `tests/integration/tpm/fixture_paths.py`, so
    planning imports them, not the reverse. `test_standalone_imports.py`
    also forbids OEL imports in the tpm tests. New CI job `sp-tpm`:
    Python 3.11, sp-tpm[highs] only, `src/` off the path (583 passed,
    1 Gurobi skip). Tests stay in the repo-level `tests/` tree; moving them
    under `packages/sp-tpm/` can wait for B6.
- [x] **B4 internal consolidation** (scope agreed 2026-10-03, three PRs). The
  three circuit evaluators keep their own node maths (probability floors and
  log-sum-exp vs max vs piecewise differ), so only the traversal is shared.
  Merging `product_mixture` into `native` moves to B5/B6: tpm_for_sp's
  knapsack training is built on it.
  - [x] B4a shared helpers. New `tpm/_io.py` (canonical JSON bytes,
    streaming atomic write) replaces the inline copy in `mio.py`, the
    artifact writer and the two hand-rolled checkpoint writers (refinement,
    categorical). One strict interpolation helper
    (`piecewise.interpolate_within_breakpoints`) replaces the copies in
    `mio.py` and `conditional_mio.py`. The Pyomo model attributes
    `_open_energy_lab_*` set by tpm became `_tpm_*`; the OEL candidate model
    lost two attributes nothing read, and OEL's own backend version tags
    keep their name. Temp-dir prefixes renamed `tpm-*`. src -20 lines.
    Evidence: each changed helper's output recorded per test on main and on
    the branch (1,700 calls, 173 tpm and planning tests); everything stable
    across two main runs matched, and the only other difference was which
    thread wins a deliberate publication race.
  - [x] B4b split `mio.py` (3491 lines) into the `tpm/mio/` package:
    `compiler` (992), `evaluate` (389), `condition` (330), `encode` (780),
    `chance_model` (1030, the serialized-SPN chance model) and `_common`
    (44). All 87 top-level definitions moved verbatim (checked by comparing
    source segments). `tpm/mio/__init__.py` re-exports every name imported
    from `tpm.mio` today, including the two private helpers tpm_for_sp
    uses; tests reaching other private helpers import from the submodules.
    The submodules join the lazy-import boundary test. Stale
    `src/open_energy_lab/tpm` paths in `docs/migration` fixed. src +137
    lines (imports, docstrings, `__init__`). `git blame -C -C` follows the
    moved code.
  - [x] B4c one memoized DAG traversal. New `tpm/_graph.py`
    (`memoized_acyclic`) holds the memo cache, cycle detection and
    missing-node check that 8 recursive walks wrote out by hand: the three
    evaluators (compiled MIO, serialized categorical SPN, conditional
    circuit), the conditioning rewrite, the graph compactor, circuit
    validation, attachment bounds and the attachment initializer. Each node
    function keeps its body and still recurses through `visit`, so visiting
    order, laziness, Pyomo initialization order and error order are
    unchanged. src +9 lines: the gain is one tested place for the
    bookkeeping, not size; the mapping's -80 estimate assumed a post-order
    rewrite, which would have changed error order. Evidence: every
    traversal's return value (floats exactly; conditioned graphs as root and
    nodes, since their provenance block varies run to run) and every raised
    message recorded per test on main and on the branch, 1,741 calls in 151
    tpm and planning tests, 13 of them errors: all identical apart from the
    deliberate publication race.
- [ ] **B5 public API and style.** Lay out `schema/`, `learn/`, `compile/`,
  `embed/` (pyomo, gurobi), and `evaluate/`. Make public the private names
  `tpm_for_sp` relies on (`_stabilize_leaf_parameters`,
  `_materialize_native_categorical_leaves`, `_spflow_operation_children`).
  Type, format, and document the research-kernel modules. SPFlow 1.1.0 and
  torch stay core dependencies (2026-10-03); only Pyomo, HiGHS and Gurobi are
  extras. SPNs are built with SPFlow only, so the non-SPFlow paths go first
  (scope agreed 2026-10-03).
  - [x] B5a remove planning's `empirical_dataset` risk mode. Planning always
    solves the SPN-MIO: `PlanningProblemDefinition` loses
    `risk_evaluation_mode` and `fixture_baseline`, the assembly loses
    `candidate_designs` and `deterministic_fixture_baseline`, and
    `PlanningDecisionCandidate`, the row-counting candidate builder, the
    candidate Pyomo model and the deterministic handoff shortcut are gone. A
    non-current-SPFlow artifact now raises a clear `ValueError` instead of
    silently falling back; a missing Pyomo fails at the solve boundary with
    the existing dependency error. `planning_problem_case.json` and the
    HiGHS/Gurobi/optional-solve tests now use the current-SPFlow production
    fixture (HiGHS optimal at epsilon 0.9, infeasible at 0.5; Gurobi matches
    HiGHS within 1e-9). src -711 lines. Evidence: planning assembly and solve
    outputs recorded per test on main (twice, no noise) and on the branch,
    removed keys stripped: all 5 tests that ran the SPN-MIO path on main are
    identical.
  - [x] B5b SPFlow-only tpm. Removed the `fixture_replay` query mode,
    the injected-backend fit branch with its "table" sidecar
    (`fit_spflow_model`, `evaluate_spflow_query`), and the adapter registry
    and capability detection. `optional_spflow.py` is now `spflow_backend.py`;
    `require_spflow_backend` is a lazy import plus version check (a missing
    SPFlow raises the plain `ImportError`). `execution_mode` stays in
    persisted artifacts but must be "production" (a `fixture_replay`
    artifact is rejected as removed); it left the fit config, the query
    request and planning. Planning's backend hook is `solve_spn_model`. New
    sidecars drop `backend_capabilities`/`backend_adapter_name`. Deleted the
    `fixture_replay` fixtures (`tpm_artifact_v2*`, `tpm_query_case.json`),
    `test_execution_modes.py` and the adapter tests; tests that fitted with a
    fake backend now fit real SPFlow. src -786, tests -916. Evidence:
    fit/load/query/compile/condition/evaluate outputs recorded per test on
    main (twice) and on the branch: 171 tests, 415 calls; all surviving
    production-path tests identical, and the 22 differing calls are the
    intended moves (14 fake-backend fits now real SPFlow, 5 loads moved to
    the production fixture, 3 downstream of those, 2 reworded errors).
    tpm_for_sp (B6) must switch `optional_spflow` imports to
    `spflow_backend` and drop three `execution_mode="production"` arguments.
  - [ ] B5c public API: make tpm_for_sp's private names public, prune unused
    exports, decide `product_mixture`/`categorical_native` with tpm_for_sp.
- [ ] **B6 switch `tpm_for_sp`.** Make it depend on the workspace package
  instead of the whole `references/oel` submodule, then drop the re-export.

## Rules for every PR

- Unit, integration, and parity suites stay green against the baseline, or the
  PR states why a test changed.
- Update the metrics above when an item lands.
- Don't add new per-module copies of helpers that exist in `core/` (or in the
  TPM package's internal helpers).
- `tests/parity/test_robust_fcr_reference_benchmark.py` skips on this machine
  ("reached its selected resource limit with a non-optimal audited
  incumbent"). HiGHS on the session's 10 cores does not prove optimality within
  its 3,600 s limit (the Julia reference solved it with Gurobi in 1,070 s).
  Confirmed on `main` @ `5cfcb09`, so it predates the consolidation. The full
  robust reference comparison is therefore not produced by the routine parity
  run here. Decide how to produce it if it is cited as thesis evidence (e.g.
  Gurobi, or a longer limit). Note: the machine's high load average comes from
  another user's processes stuck in uninterruptible I/O; actual CPU use is
  about 2%, so it is not load.
