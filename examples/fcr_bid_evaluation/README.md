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
submodule. Installation, digest verification, runnable commands, and supported
comparison outcomes are documented in the Feature 012 quickstart. Until the
reference consumer and normalization helper are implemented in later Feature
012 phases; their rows above define the governed data boundary meanwhile.
