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

The fixed-plan walkthrough will use focused imports from
`open_energy_lab.control.fcr_bid_plan` and
`open_energy_lab.simulator.fcr_bid_evaluation`. Manual, heuristic, robust, and
TPM producers all emit the same existing schedule types and enter the same
evaluation function; producer identity cannot choose different physics or
accounting.

The full-reference consumer never downloads data and never reads the reference
submodule. Installation, digest verification, runnable commands, and supported
comparison outcomes are documented in the Feature 012 quickstart. Until the
consumer scripts are implemented, this file is a map of their required
responsibilities and contains no placeholder imports or executable stubs.
