# Quickstart: FCR Bid-Evaluation Parity

This is the implementation and review path for Feature 012. Routine checks are
fully offline. The complete 2023-06-18 parity run is separate because Open Energy
Lab does not redistribute the reference regulation CSV.

Run commands from the repository root.

## 1. Routine Offline Validation

No Julia, Gurobi, reference submodule, network, or external CSV is needed:

```bash
uv run pytest \
  tests/unit/control/test_fcr_bid_plan.py \
  tests/unit/market/test_reference_fcr.py \
  tests/unit/simulator/test_fcr_bid_evaluation.py \
  tests/unit/simulator/test_fcr_reference_settlement.py \
  tests/integration/simulator/test_fcr_bid_evaluation_manual.py \
  tests/integration/simulator/test_fcr_bid_evaluation_compatibility.py \
  tests/integration/simulator/test_fcr_reference_fixture.py \
  tests/integration/simulator/test_fcr_reference_normalization.py \
  tests/unit/test_fixture_provenance_docs.py \
  tests/unit/test_migration_policy_docs.py \
  tests/unit/test_ci_workflow.py
```

This suite proves the plan boundary, hand-calculable physics and accounting,
failed-report behavior, Golden Reference Fixture provenance, precision formulas,
deterministic fingerprints, and Feature 010 compatibility.
It also proves zero-network fixture assembly, actionable external-data
boundaries, canonical refresh output, distribution exclusions, and documentation
governance.

### Offline reproducibility record

On 2026-08-26 the exact routine file list above was run twice in fresh pytest
sessions while `socket.socket` was patched to fail on any construction and the
supported external path under `artifacts/` was absent. Both runs completed with
`113 passed` and identical pinned fixture/report fingerprints. No test consulted
an environment-selected path, reference submodule, Julia, Gurobi, or external
activation bytes.

The focused US1/US3 evaluator and audit gate is:

```bash
uv run pytest \
  tests/unit/control/test_fcr_bid_plan.py \
  tests/unit/simulator/test_fcr_bid_evaluation.py \
  tests/unit/simulator/test_fcr_reference_settlement.py \
  tests/integration/simulator/test_fcr_bid_evaluation_manual.py \
  tests/integration/simulator/test_fcr_bid_evaluation_compatibility.py \
  tests/unit/simulator/test_import_boundary.py \
  -q
```

On 2026-08-26 this completed with `57 passed`. It asserts the settled authored
oracle, directional requested/delivered FCR, delivered-only activation payment,
explicit and absent penalties, strict component reconciliation, valid dynamic
SOC saturation, deterministic `validation_failed` reports for static power
headroom, non-economic diagnostic replay, complete report lineage, pinned
fingerprints, and additive lazy exports. The runnable equivalents are:

```bash
uv run python examples/fcr_bid_evaluation/run_manual_plan.py
uv run python examples/fcr_bid_evaluation/run_manual_plan.py --invalid-headroom
```

### Final routine and scaling record

After the SC-014 bounded-pass refactor, the complete routine command required by
Feature 012 was rerun exactly as follows:

```bash
uv run pytest \
  tests/unit/control/test_fcr_bid_plan.py \
  tests/unit/market/test_reference_fcr.py \
  tests/unit/simulator/test_fcr_bid_evaluation.py \
  tests/unit/simulator/test_fcr_reference_settlement.py \
  tests/integration/simulator/ \
  -m "not external_reference_data and not reference_benchmark"

uv run pytest tests/unit/simulator/test_fcr_bid_evaluation_scaling.py -q
```

On 2026-08-26, after the Phase 9 notebook follow-up, these commands completed
with `216 passed, 5 deselected` and `1 passed`, respectively. The additional
routine case is the network-guarded default notebook execution; the additional
deselection is its explicit external-data branch. The scaling test uses an
instrumented 8,640-sample
ordinary day rather than a wall-clock threshold and enforces no more than two
complete primary-collection iterations per validation, replay, aggregation,
settlement, comparison, or fingerprint-materialization stage.

## 2. Run The Source-Only Evaluation Walkthrough

Install the optional notebook environment, then open the walkthrough from the
repository root with the project `.venv/bin/python` kernel:

```bash
uv sync --group notebook
uv run jupyter lab \
  examples/fcr_bid_evaluation/fcr_bid_evaluation_walkthrough.ipynb
```

The committed
`examples/fcr_bid_evaluation/fcr_bid_evaluation_walkthrough.ipynb` is valid
notebook-v4 JSON with stable cell IDs, empty outputs, and no saved execution
counts. Its default configuration sets both `RUN_EXTERNAL_REFERENCE = False`
and `EXPORT_FIGURES = False`. Every default cell therefore runs offline from
the repository root without credentials, network access, the external CSV,
Julia, or a solver.

The walkthrough evaluates the authored fixed plan, plots its schedule and
physical trace, audits settlement and directional energy, explains the static
`validation_failed` case, and proves that manual, heuristic, robust, and
TPM-labelled plans have identical physical and settlement fingerprints when
their evaluation inputs match. It then inspects Golden Reference Fixture
provenance, the 24/6 mapping, supported/unavailable fields, and field-specific
source-precision bounds. The five deterministic figures remain in memory.
Figure files are written only when explicitly enabled and only below:

```text
tmp/fcr-bid-evaluation-notebook/figures
```

When the explicit external-reference branch is enabled, the notebook adds a
sixth figure with separate EUR, kWh, and kW panels. Each panel places the Julia
expected value beside the Open Energy Lab actual value, shows available expected
and actual precision intervals, and colors the comparison by exact,
source-precision-compatible, or mismatch status.

Run the source and default execution contracts with:

```bash
uv run pytest \
  tests/unit/simulator/test_fcr_bid_evaluation_notebook.py \
  tests/integration/simulator/test_fcr_bid_evaluation_notebook_execution.py \
  -m "not external_reference_data" \
  -q
```

After installing the governed CSV as described below, select the complete
notebook branch through the explicit external-data test:

```bash
uv run pytest \
  tests/integration/simulator/test_fcr_bid_evaluation_notebook_execution.py \
  -m external_reference_data \
  -q
```

That test injects the explicit CSV path and enables only the guarded reference
section. When the file is absent it skips with the installation path; it never
downloads, searches for, or infers the source. Even when selected, the notebook
claims only supported bounded aggregate parity—not bid optimization, TPM bid
selection, or complete Julia trace parity.

On 2026-08-26 the source/default notebook command completed with
`6 passed, 1 deselected` and reproduced display fingerprint
`14ac81308ab6efbaa34140c296f6c651dc43262ce2cc5ba8d57985d3fb18eb96`.
The explicitly selected external command produced one actionable skip because
the governed CSV was absent at the documented local path. Routine correctness
remained fully exercised offline.

## 3. Inspect The Committed Evidence

```bash
sed -n '1,280p' tests/fixtures/fcr_bid_evaluation/README.md
python -m json.tool \
  tests/fixtures/fcr_bid_evaluation/robust_storage_bidding_2023-06-18_aggregate_v1.json
```

The Golden Reference Fixture records the pinned commit, generation command,
original JSON digest, fixed published decisions, prices, battery/time configuration,
expected aggregate fields, mappings, source-precision policy, unsupported fields,
and external-data descriptor. It contains no activation samples.

## 4. Install The External Regulation Data

Use the download named by the pinned reference README and place it in the ignored
OEL artifact directory:

```bash
mkdir -p artifacts/reference/robust_storage_bidding
curl -fL \
  https://github.com/lauinger/robust-storage-bidding/releases/download/v0.1/regulation_signal.csv \
  -o artifacts/reference/robust_storage_bidding/regulation_signal.csv
sha256sum artifacts/reference/robust_storage_bidding/regulation_signal.csv
```

The expected digest is:

```text
0c2bf5203410f193c555460ec5593b546af42556f29afac821584e403c407d13
```

The expected byte count is `528805941`, and the header is:

```text
DateTime,Frequency (Hz),xi,xi_EU
```

Do not commit the file. `artifacts/` is ignored and is the supported local
placement. The OEL loader performs no download and does not fall back to an
untracked copy inside `baselines/`.

The older `lauinger/MV` URL still present in the pinned
`data/regulation_signal_info.txt` is superseded by the pinned README instruction.
Regardless of locator, bytes are accepted only if the exact digest, size, schema,
date coverage, and cadence pass.

Absent, misplaced, truncated, digest-mismatched, wrong-header, wrong-column,
non-finite, duplicated, gapped, overlapping, or wrong-date inputs fail with an
actionable domain error. The library never downloads or searches for a
same-named file. Only the explicitly selected pytest wrapper converts an absent
file into a skip with this installation path.

## 5. Run The Complete Reference Evaluation

After placing the CSV:

```bash
uv run python examples/fcr_bid_evaluation/run_reference_parity.py \
  --activation-path artifacts/reference/robust_storage_bidding/regulation_signal.csv
```

Or run the explicit integration test:

```bash
uv run pytest \
  tests/integration/simulator/test_fcr_reference_aggregate_parity.py \
  -m external_reference_data \
  -q
```

The loader verifies the entire file and selects exactly 8,640 `xi_EU` values for
2023-06-18. The resulting case must contain 24 energy decisions, six FCR
decisions, 96 checkpoints, and 8,640 PT10S samples.

The expected comparison is bounded by the evidence in the generated JSON:

- fixed decision mapping and supported daily aggregates are compared;
- exact displayed three-decimal matches are recorded;
- fields affected by rounded decisions may report
  `source_precision_compatible` under analytic field-specific intervals;
- unsupported detailed reference fields report `unavailable`; and
- no complete ten-second Julia trace parity is claimed.

Julia and Gurobi are not used by this command or test.

### Initial acceptance result

The 2026-08-26 explicit full-data run completed successfully with overall status
`source_precision_compatible` and no mismatches. The source-precision fields
were day-ahead profit, minimum/maximum/terminal stored energy, and discharge
energy; supported remaining aggregates were exact at the recorded display
precision. Stable content fingerprints were:

```text
physical trace: f292f4990d99f6ca4aa7bb12c304b70751396e3c2005544577c58ceb153573f6
settlement:     8e5382463fd8e9bd110214fa4cd87be7539ae0fab70eb4ead0bb2b55cbbf72ca
comparison:     1e16c8f03f3c8c649ab1a435d8a14849f51b168b91fc7915df236c492a8b274e
```

The settlement fingerprint above supersedes the pre-audit value after the
versioned profile began serializing directional FCR energy and combined-FCR
reconciliation. The physical trace and comparison fingerprint were unchanged.

Activation-artifact, evaluation-input, and final-report fingerprints also bind
the explicit file locator and therefore are checked for repeatability at a
given installation path rather than treated as path-independent golden values.

### Final post-polish full-data regression

After the bounded-pass and documentation changes, the explicit consumer above
was rerun using the regular digest-verified file at the documented ignored
artifact path. It again settled all 8,640 samples with overall
`source_precision_compatible`, zero supported mismatches, and the same exact
trace and comparison fingerprints recorded at T039. The settlement fingerprint
remained the intentional post-audit value shown above; its difference from
T039's `d8241f80dafc8c6b3444f479b74c6c16fd8f79fae4e9d73f60e6fc3177da0c7e`
is solely the versioned addition of directional FCR energy and combined-FCR
reconciliation, not physical or economic drift.

The explicitly selected integration command completed with `3 passed` in
57.93 seconds. At the documented artifact locator the path-bound final report
fingerprint was
`6aa9c1e75101354523432adecbf6b8dfb7fa946211151ebcfc7e767575777bb3`;
the path-independent trace, settlement, and comparison values stayed exactly
as recorded above.

## 6. Evaluate Another Fixed Plan

Every bidder supplies the existing schedule types, then wraps them once:

```python
from open_energy_lab.control.fcr_bid_plan import build_fixed_fcr_bid_plan
from open_energy_lab.simulator.fcr_bid_evaluation import (
    FCRBidEvaluationRequest,
    evaluate_fixed_fcr_bid,
)

plan = build_fixed_fcr_bid_plan(
    plan_id="candidate-001",
    producer=producer,
    information_cutoff_utc=cutoff,
    energy_schedule=energy_schedule,
    fcr_schedule=fcr_schedule,
    producer_input_fingerprints=input_fingerprints,
    solve_status="not_applicable",
    objective=objective_unavailable,
    objective_bound=bound_unavailable,
)

report = evaluate_fixed_fcr_bid(
    FCRBidEvaluationRequest(
        evaluation_id="candidate-001-reference-day",
        plan=plan,
        market_context=market_context,
        activation_trace=activation_trace,
        battery=battery,
        time_contract=time_contract,
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
        penalty_rule=None,
        terminal_soc_target=None,
        comparison_fixture=None,
        numeric_tolerance=1e-6,
        semantics_version="oel.fcr-bid-evaluation.v1",
    )
)
```

Manual, heuristic, robust, and TPM producers use this same path. Activation is
bound in the evaluation request, not exposed to the bidder before its information
cutoff.

A statically invalid schedule, battery, or reserve-power-headroom commitment
returns `validation_failed` with diagnostics and no profit. Use the separate
diagnostic operation only for physical investigation; its output cannot be
compared as valid bidder performance. Dynamic stored-energy saturation after
valid preflight remains settled, prices only delivered activation, applies only
an explicit non-delivery penalty, and is outside the initial reference-parity
domain.

## 7. Feature 010 Regression Gate

Run the unchanged FCR behavior and import boundaries:

```bash
uv run pytest \
  tests/unit/control/test_stacked_service.py \
  tests/unit/simulator/test_stacked_service.py \
  tests/unit/simulator/test_fcr_settlement.py \
  tests/integration/simulator/test_stacked_service_manual.py \
  tests/integration/simulator/test_stacked_service_compatibility.py \
  tests/integration/simulator/test_stacked_service_real_replay.py \
  -m "not reference_benchmark and not external_reference_data"

uv run pytest \
  tests/unit/control/test_import_boundary.py \
  tests/unit/simulator/test_import_boundary.py \
  tests/unit/test_import_contract.py \
  tests/unit/test_lazy_dependency_boundaries.py \
  tests/unit/test_no_legacy_imports.py

rg "from (baselines|legacy)|import (baselines|legacy)" \
  src/open_energy_lab/control \
  src/open_energy_lab/market \
  src/open_energy_lab/simulator
```

Existing Feature 010 fixture bytes, default settlement values, traces, and
fingerprints must remain unchanged.

The final additive compatibility gate also includes exact public constructors,
serialization, module ownership, Feature 011 product separation, zero-service
profiles, and import isolation:

```bash
uv run pytest \
  tests/integration/simulator/test_fcr_bid_evaluation_public_compatibility.py \
  tests/integration/simulator/test_fcr_bid_evaluation_product_separation.py \
  tests/integration/simulator/test_fcr_bid_evaluation_compatibility.py \
  tests/unit/test_no_legacy_imports.py \
  tests/unit/test_lazy_dependency_boundaries.py \
  tests/unit/test_import_contract.py \
  tests/unit/simulator/test_import_boundary.py \
  tests/unit/market/test_rte_environment.py \
  -q
```

On 2026-08-26 this gate passed `121` tests. Before the Phase 9 notebook
follow-up, the broad unchanged market,
control, simulator, fixture-generation, and integration suite passed `845`
tests with five explicitly excluded live/reference-data/benchmark selections:

```bash
uv run pytest \
  tests/unit/market tests/unit/control tests/unit/simulator \
  tests/integration/market tests/integration/control tests/integration/simulator \
  -m "not live_entsoe and not reference_benchmark and not external_reference_data" \
  -q
```

The narrower unchanged Feature 010 command immediately above passed `54` tests
with the benchmark deselected, and the import/lazy/no-reference-import command
passed `128` tests. The extra broad-suite test relative to the earlier record is
the new Feature 012 scaling gate; no existing Feature 010 result or fingerprint
changed.

### Explicit Feature 010 benchmark result

The unchanged benchmark was selected separately and passed on Linux
6.8.0-124-generic x86_64, Python 3.14.6, Intel Xeon Gold 5218R at 2.10 GHz,
with 503 GiB host memory and repository revision `62f20c6` before the
compatibility-only changes:

```text
1.551052453, 1.313645234, 1.756199315, 1.581977689, 1.332762067 seconds
```

All five measured artifact-load/replay/settlement/fingerprint runs were below
the Feature 010 ten-second limit. This check required no network or credential;
there was no environment-only limitation to record.

## 8. Distribution Inspection

Build both distributions and inspect their complete manifests:

```bash
uv build
unzip -l dist/open_energy_lab-0.1.0-py3-none-any.whl
tar -tvf dist/open_energy_lab-0.1.0.tar.gz
```

On 2026-08-26 the final build produced a 369,822-byte wheel containing 86 files
and a 1,519,529-byte sdist containing 690 files. Neither manifest contained
`regulation_signal.csv`, an `artifacts/` path, or a `baselines/` path. The wheel
contained no reference data. The sdist contained only the two intended small,
reviewable Feature 012 JSON fixtures:

```text
tests/fixtures/fcr_bid_evaluation/manual_fcr_bid_evaluation_v1.json
tests/fixtures/fcr_bid_evaluation/robust_storage_bidding_2023-06-18_aggregate_v1.json
```

The generated `dist/` directory remains ignored and is not fixture evidence.

## 9. Refresh Reference Evidence Deliberately

Reference execution is not part of normal validation. If an authorized
researcher intentionally refreshes it, run the baseline in its own project and
normalize the result into ignored output first:

```bash
cd baselines/robust_storage_bidding/code
julia --project=. 12.jl 2023-06-18
cd ../../..

uv run python examples/fcr_bid_evaluation/normalize_reference_result.py \
  --input baselines/robust_storage_bidding/results/02/2023-06-18.json \
  --expected-sha256 8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6 \
  --output-dir artifacts/reference/robust_storage_bidding/normalized
```

The normalizer validates but never starts Julia or mutates the baseline. Promotion
from ignored output to `tests/fixtures/` is an explicit reviewed change. A future
full-precision decision export requires a new fixture/precision schema version;
it cannot silently upgrade the initial rounded-evidence claim.

The output file is
`artifacts/reference/robust_storage_bidding/normalized/normalized_reference_result.json`.
It is canonical JSON containing the validated source digest/configuration,
decisions, prices, mapped aggregate evidence, and a deterministic ordered
semantic diff against the committed fixture. The helper refuses output under a
committed repository path outside ignored `artifacts/`.
