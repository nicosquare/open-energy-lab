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
  tests/integration/simulator/test_fcr_reference_fixture.py
```

This suite proves the plan boundary, hand-calculable physics and accounting,
failed-report behavior, Golden Reference Fixture provenance, precision formulas,
deterministic fingerprints, and Feature 010 compatibility.

## 2. Inspect The Committed Evidence

```bash
sed -n '1,280p' tests/fixtures/fcr_bid_evaluation/README.md
python -m json.tool \
  tests/fixtures/fcr_bid_evaluation/robust_storage_bidding_2023-06-18_aggregate_v1.json
```

The Golden Reference Fixture records the pinned commit, generation command,
original JSON digest, fixed published decisions, prices, battery/time configuration,
expected aggregate fields, mappings, source-precision policy, unsupported fields,
and external-data descriptor. It contains no activation samples.

## 3. Install The External Regulation Data

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

## 4. Run The Complete Reference Evaluation

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

## 5. Evaluate Another Fixed Plan

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

## 6. Feature 010 Regression Gate

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

## 7. Refresh Reference Evidence Deliberately

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
