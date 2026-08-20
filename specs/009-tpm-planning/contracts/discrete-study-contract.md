# Discrete Planning Study Contract

The planning study surface accepts explicit battery and solar option catalogs,
an adequacy event, a named existing controller, and an islanded, supplied, or
two-state Markov grid-availability policy. The configuration order is the
Cartesian product in battery-major, solar-minor order.

Each absolute sample ID identifies one shared weather, demand, and grid trace
that is reused across every equipment configuration. Batches and process
workers may change execution layout, but not semantic rows or their ordering.

Schema-v2 datasets use atomic JSON manifests and deterministic JSONL or Parquet
shards. The manifest records request and semantic hashes, equipment metadata,
active event semantics, selected compact-fit columns, and shard integrity
digests. Each row retains the controller name and horizon-indexed PV generation,
site load, requested and realized battery power, post-step battery state of
charge, grid availability, and unmet load. Positive battery power means charge;
negative power means discharge. Parquet is the default; JSONL has the same
semantic digest.

Compact TPM fitting materializes only selected columns after an explicit dense
tensor memory preflight. Equipment option IDs are categorical decisions. The
model sidecar stores the learned SPN, feature schema, and row count without
duplicating the large training table.

Planning encodes each categorical decision as a one-hot vector and applies the
installed cost of the selected option directly in the MIO objective. It does
not enumerate empirical candidates. After HiGHS returns an optimum, the chosen
option IDs are queried against native SPFlow. A probability discrepancy above
`1e-6`, or native risk above epsilon plus `1e-9`, produces
`validation_failed`.

Hourly studies may set `local_start_step` within the local day. Weather and
demand requests use the same offset, while the simulator starts every episode
from the equipment option's explicit initial SOC; the offset never implies a
controller or battery-state burn-in.

For recommendation studies, training, validation, and final-test manifests are
independent. Candidate selection considers only genuinely compilable SPFlow
models and uses validation Brier score with smaller node count as the tie-break.
Final recommendation additionally requires the documented held-out calibration
limits, both labels, selected native probability inside its confidence
interval, native/MIO error at most `1e-6`, and the selected design's one-sided
95% held-out risk bound no greater than epsilon. Otherwise solve output is
exploratory.
