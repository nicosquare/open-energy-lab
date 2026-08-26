# FCR Bid-Evaluation Examples

Feature 012 evaluates fixed bids through one bidder-independent physical and
settlement environment. It does not generate or optimize bids.

The example surface is intentionally split by data and review boundary:

| Consumer | Purpose | Routine offline? | External input |
| --- | --- | --- | --- |
| fixed-plan walkthrough | Build existing hourly energy and four-hour FCR schedules, wrap them in one plan, evaluate them, and inspect success/failure reports | yes | none |
| `run_reference_parity.py` | Map the pinned 2023-06-18 decisions, load a complete activation day, replay it, and report bounded aggregate comparison | no; explicitly selected | caller-supplied regulation CSV via `--activation-path` |
| `normalize_reference_result.py` | Validate a researcher-generated reference JSON and write canonical review output below an ignored directory | no; fixture refresh only | explicit input JSON, expected digest, and output directory |
| expected-failure examples | Demonstrate missing/corrupt external data, invalid static commitments, and the separately labelled diagnostic replay | fixed-plan failures are offline; external-data failures are explicit | none or an explicit invalid path |

## Run The Authored Fixed Plan

From the repository root:

```bash
uv run python examples/fcr_bid_evaluation/run_manual_plan.py
```

The example constructs the existing hourly energy and four-hour FCR schedule
types, wraps those exact objects in a manual `FixedFCRBidPlan`, binds activation,
battery, prices, time, and the explicit reference settlement profile only in the
evaluation request, then prints the complete deterministic report. It also
prints why objective value and bound are unavailable; those optimization
metadata are not replaced with realized profit.

Manual, heuristic, robust, and TPM producers emit these same schedule types and
enter `evaluate_fixed_fcr_bid`; producer identity cannot choose different
physics or accounting.

To inspect a deterministic static reserve-headroom failure with no settlement or
profit:

```bash
uv run python examples/fcr_bid_evaluation/run_manual_plan.py --invalid-headroom
```

The returned `validation_failed` report contains ordered diagnostics and input
lineage. It has no physical trace, settlement, or numeric zero standing in for
unavailable profit.

The full-reference consumer never downloads data and never reads the reference
submodule. Install and verify the caller-managed bytes with:

```bash
mkdir -p artifacts/reference/robust_storage_bidding
curl -fL \
  https://github.com/lauinger/robust-storage-bidding/releases/download/v0.1/regulation_signal.csv \
  -o artifacts/reference/robust_storage_bidding/regulation_signal.csv
sha256sum artifacts/reference/robust_storage_bidding/regulation_signal.csv
```

The required SHA-256 is
`0c2bf5203410f193c555460ec5593b546af42556f29afac821584e403c407d13`.
The loader also enforces 528805941 bytes, exact
`DateTime,Frequency (Hz),xi,xi_EU` header, the selected day, and PT10S cadence.
It raises actionable errors for absent, misplaced, truncated, digest-mismatched,
or structurally invalid data; only the explicitly selected pytest wrapper skips
an absent file.

Then run:

```bash
uv run python examples/fcr_bid_evaluation/run_reference_parity.py \
  --activation-path artifacts/reference/robust_storage_bidding/regulation_signal.csv
```

The command reports the 24/6/96/8,640 mapping counts, input lineage, physical
metrics, settlement components, and each `exact`,
`source_precision_compatible`, or `unavailable` field result. It exits nonzero
if any supported parity field is a `mismatch`. Installation, digest
verification, and evidence limits are documented in the Feature 012 quickstart.

## Refresh Generated Reference Evidence

After an authorized researcher separately runs
`julia --project=. 12.jl 2023-06-18` from the pinned reference `code/`
directory, normalize the generated JSON without starting Julia or a solver:

```bash
uv run python examples/fcr_bid_evaluation/normalize_reference_result.py \
  --input baselines/robust_storage_bidding/results/02/2023-06-18.json \
  --expected-sha256 8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6 \
  --output-dir artifacts/reference/robust_storage_bidding/normalized
```

The helper validates the digest, source configuration, fixed-decision counts,
prices, paired `curr`/`curr_bid` fields, and finite aggregates. It writes
canonical output and an ordered semantic diff only below ignored `artifacts/`
or outside the repository; committed fixture paths require manual review and
promotion.
